#!/usr/bin/env python3
"""
fetch_fund_allocation.py — 抓取基金资产配置 / 规模变动 / 持有人结构数据

三级流水线（与项目最高风控规则一致）：
  接口拉取 → fund_scores_staging（写入 12 列）→ fund_scores_test（验证镜像）
  → fund_scores（生产，--to-prod 手动确认后合并）

数据源：
  1. zcpz（资产配置明细）— 页面内嵌 chartData 变量
     → stock_pct(股票占比%), bond_pct(债券占比%), cash_pct(现金占比%)
  2. gmbd（份额/净资产规模变动）— FundArchivesDatas API
     → sub_purchase(期间申购亿份), sub_redemption(期间赎回亿份),
       net_sub_share(净申购亿份), total_share_end(期末总份额亿份),
       net_asset_end(期末净资产亿元), nav_change_rate(净资产变动率)
  3. cyrjg（持有人结构）— FundArchivesDatas API
     → inst_hold_pct(机构持有%), indiv_hold_pct(个人持有%), internal_hold_pct(内部持有%)

用法：
  # 每日增量（写入 staging + 镜像 test，不碰生产）：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_fund_allocation.py
  # 全量回填 + 直接合并进生产（一次性，沙箱/手动）：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_fund_allocation.py --force --to-prod
  # 仅测试单只基金（000001），不写库：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_fund_allocation.py --dry-run
"""

import os
import sys
import json
import re
import time
import argparse
import subprocess
from datetime import datetime, date

# ── 环境加载 ────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)


def _load_env():
    p = os.path.join(_PROJECT_ROOT, '.env.local')
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass


_load_env()

PAT = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN')
if not PAT:
    sys.exit('ERROR: 需设置 SUPABASE_PAT 或 SUPABASE_MGMT_TOKEN')

MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

# ── 12 个新列 ──────────────────────────────────────────────────────
ALLOC_COLS = [
    'stock_pct', 'bond_pct', 'cash_pct',
    'sub_purchase', 'sub_redemption', 'net_sub_share',
    'total_share_end', 'net_asset_end', 'nav_change_rate',
    'inst_hold_pct', 'indiv_hold_pct', 'internal_hold_pct',
]

# 三个目标表都确保有这 12 列（staging 通过 CREATE LIKE 继承，但显式 ALTER 双保险）
NEW_COLUMNS = ""
for _t in ('fund_scores', 'fund_scores_staging', 'fund_scores_test'):
    for _c in ALLOC_COLS:
        NEW_COLUMNS += f"ALTER TABLE {_t} ADD COLUMN IF NOT EXISTS {_c} float8;\n"


# ── SQL 执行工具 ───────────────────────────────────────────────────
def pg(sql, timeout=300):
    from _db import run_sql as _db_run_sql
    return _db_run_sql(sql, timeout=timeout)


# ── 数据抓取函数 ────────────────────────────────────────────────────
def _http_get(url, headers=None, timeout=15):
    """通用 HTTP GET"""
    h = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
    if headers:
        h.update(headers)
    cmd = ['curl', '-s', '--max-time', str(timeout), url]
    for k, v in h.items():
        cmd += ['-H', f'{k}: {v}']
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 5)
    return r.stdout


def _strip_suffix(code):
    """去掉 .OF 后缀，东财 fundf10 页面用裸代码（zcpz 必须）"""
    return code.replace('.OF', '').replace('.of', '')


def fetch_zcpz(code):
    """抓取资产配置明细（zcpz）—— 从页面 HTML 提取 chartData 变量

    返回 dict: {report_date, stock_pct, bond_pct, cash_pct}，取最新报告期一行。
    注意：fund_scores.c 带 .OF 后缀，而 fundf10 页面用裸代码（zcpz_000001.html）。
    """
    bare = _strip_suffix(code)
    url = f'https://fundf10.eastmoney.com/zcpz_{bare}.html'
    html = _http_get(url)

    m = re.search(r'var chartData\s*=\s*(\{.+?\});?\s*(?:var|</script)', html, re.DOTALL)
    if not m:
        return None

    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return None

    dates = data.get('Dates', [])
    gp = data.get('GP', [])
    zq = data.get('ZQ', [])
    xj = data.get('XJ', [])

    if not dates or len(dates) == 0:
        return None

    idx = len(dates) - 1  # 最新报告期
    return {
        'report_date': dates[idx],
        'stock_pct': float(gp[idx]) if idx < len(gp) else None,
        'bond_pct': float(zq[idx]) if idx < len(zq) else None,
        'cash_pct': float(xj[idx]) if idx < len(xj) else None,
    }


def _extract_api_content(raw, var_name='apidata'):
    """从东财 API 响应中提取 content 字段的 HTML 字符串。"""
    patterns = [
        rf'var {var_name}_apidata=\{{\s*content:\s*"(.+?)"\s*\}}',
        rf'var {var_name}=\{{\s*content:\s*"(.+?)"\s*\}}',
    ]
    for pat in patterns:
        m = re.search(pat, raw, re.DOTALL)
        if m:
            return m.group(1)
    return None


def parse_html_table(html_content):
    """解析东财返回的 HTML table，提取 tbody 行为 list[list[str]]"""
    rows = []
    tbody_m = re.search(r'<tbody>(.+?)</tbody>', html_content, re.DOTALL)
    if not tbody_m:
        return rows
    for tr_m in re.finditer(r'<tr[^>]*>(.+?)</tr>', tbody_m.group(1), re.DOTALL):
        tr_text = tr_m.group(1)
        cells = [re.sub(r'<[^>]+>', '', td_m.group(1)).strip()
                 for td_m in re.finditer(r'<td[^>]*>(.+?)</td>', tr_text, re.DOTALL)]
        if cells:
            rows.append(cells)
    return rows


def fetch_gmbd(code):
    """抓取规模变动详情（gmbd）—— FundArchivesDatas API（容忍 .OF 后缀）

    返回 dict 或 None（取最新报告期一行）
    """
    url = f'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=gmbd&code={code}&per=1&page=1'
    raw = _http_get(url, headers={'Referer': f'https://fundf10.eastmoney.com/gmbd_{code}.html'})

    content = _extract_api_content(raw, 'gmbd')
    if not content:
        content = _extract_api_content(raw, 'apidata')
    if not content:
        return None

    rows = parse_html_table(content)
    if not rows:
        return None

    row = rows[0]

    def _pct(s):
        s = s.replace('%', '').strip()
        try:
            return float(s)
        except ValueError:
            return None

    def _num(s):
        try:
            return float(s.strip())
        except ValueError:
            return None

    sub_p = _num(row[1]) if len(row) > 1 else None
    sub_r = _num(row[2]) if len(row) > 2 else None
    return {
        'report_date': row[0] if len(row) > 0 else None,
        'sub_purchase': sub_p,
        'sub_redemption': sub_r,
        'net_sub_share': round(sub_p - sub_r, 4) if sub_p is not None and sub_r is not None else None,
        'total_share_end': _num(row[3]) if len(row) > 3 else None,
        'net_asset_end': _num(row[4]) if len(row) > 4 else None,
        'nav_change_rate': _pct(row[5]) if len(row) > 5 else None,
    }


def fetch_cyrjg(code):
    """抓取持有人结构（cyrjg）—— FundArchivesDatas API（容忍 .OF 后缀）

    返回 dict 或 None（取最新公告期一行）
    """
    url = f'https://fundf10.eastmoney.com/FundArchivesDatas.aspx?type=cyrjg&code={code}&per=1&page=1'
    raw = _http_get(url, headers={'Referer': f'https://fundf10.eastmoney.com/cyrjg_{code}.html'})

    content = _extract_api_content(raw, 'cyrjg')
    if not content:
        content = _extract_api_content(raw, 'apidata')
    if not content:
        return None

    rows = parse_html_table(content)
    if not rows:
        return None

    row = rows[0]

    def _pct(s):
        s = s.replace('%', '').strip()
        try:
            return float(s)
        except ValueError:
            return None

    return {
        'report_date': row[0] if len(row) > 0 else None,
        'inst_hold_pct': _pct(row[1]) if len(row) > 1 else None,
        'indiv_hold_pct': _pct(row[2]) if len(row) > 2 else None,
        'internal_hold_pct': _pct(row[3]) if len(row) > 3 else None,
    }


# ── 主流程 ──────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description='抓取基金配置/规模/持有人数据（三级流水线）')
    parser.add_argument('--dry-run', action='store_true', help='仅测试单只基金 (000001)，不写库')
    parser.add_argument('--force', action='store_true', help='全量抓取（忽略已存在的数据）')
    parser.add_argument('--to-prod', action='store_true', help='抓取后把 fund_scores_test 合并进 fund_scores 生产表')
    parser.add_argument('--limit', type=int, default=0, help='限制抓取数量（0=全部）')
    parser.add_argument('--batch-size', type=int, default=50, help='每批请求数量')
    parser.add_argument('--delay', type=float, default=0.3, help='每批间隔秒数')
    # ── 方案B：分片并行（各片写专属临时表，避免并行 DROP/CREATE _alloc_tmp 冲突）──
    parser.add_argument('--shard', type=int, default=None,
                        help='分片索引（0-based），配合 --shards 把待抓取列表拆成 N 片并行')
    parser.add_argument('--shards', type=int, default=1, help='总分片数（>=1）')
    args = parser.parse_args()

    if args.shard is not None:
        if args.shards < 1:
            sys.exit('ERROR: --shards 必须 >= 1')
        if not (0 <= args.shard < args.shards):
            sys.exit(f'ERROR: --shard 必须在 [0, {args.shards}) 范围内')
    # 分片专属临时表名（避免 8 个并行 job 抢同一张 _alloc_tmp 导致冲突）
    tmp_table = f'_alloc_tmp_{args.shard}' if args.shard is not None else '_alloc_tmp'

    print('=' * 64, flush=True)
    print(' 基金配置/规模/持有人数据 ETL（staging → test → prod）', flush=True)
    print('=' * 64, flush=True)

    # 1. 确保三张表都有 12 个新列
    #    分片模式下 8 个 job 并发跑本步，ALTER IF NOT EXISTS 可能因竞态报
    #    "column already exists"，此时列其实已存在，故分片模式降级为告警不退出；
    #    非分片模式仍严格退出（列缺失会导致后续 UPDATE 失败）。
    print('\n[1] 确保 12 列存在于 fund_scores / staging / test...', flush=True)
    try:
        pg(NEW_COLUMNS, timeout=120)
        print('  ✓ ALTER TABLE 完成（12 列 × 3 表）', flush=True)
    except Exception as e:
        if args.shard is not None:
            print(f'  [WARN] ALTER TABLE 竞态（分片模式忽略）: {e}', flush=True)
        else:
            print(f'  ✗ ALTER TABLE 失败: {e}', flush=True)
            sys.exit(1)

    if args.dry_run:
        code = '000001'
        print(f'\n[DRY-RUN] 测试基金 {code}', flush=True)
        zcpz = fetch_zcpz(code)
        print(f'  zcpz (资产配置): {zcpz}', flush=True)
        gmbd = fetch_gmbd(code)
        print(f'  gmbd (规模变动): {gmbd}', flush=True)
        cyrjg = fetch_cyrjg(code)
        print(f'  cyrjg (持有人结构): {cyrjg}', flush=True)
        print('\n✅ DRY-RUN 完成，未写入任何数据', flush=True)
        return

    # 2. 获取全部基金代码列表
    print('\n[2] 获取基金代码列表...', flush=True)
    funds = pg("SELECT c FROM fund_scores ORDER BY c")
    codes = [r['c'] for r in funds]
    total = len(codes)
    print(f'  共 {total} 只基金', flush=True)

    # 增量：跳过生产表已有 stock_pct 的基金（除非 --force）
    skip_set = set()
    if not args.force:
        done = pg("SELECT c FROM fund_scores WHERE stock_pct IS NOT NULL")
        skip_set = {r['c'] for r in done}
        print(f'  增量模式：已跳过 {len(skip_set)} 只（生产已有数据），待抓取 {total - len(skip_set)} 只', flush=True)

    todo = [c for c in codes if c not in skip_set]
    # 分片：把待抓取列表按索引切分给各并行 job（不相交，避免并行冲突）
    if args.shard is not None:
        todo = [c for i, c in enumerate(todo) if i % args.shards == args.shard]
        print(f'  分片模式: shard={args.shard}/{args.shards}, 本片待抓取 {len(todo)} 只', flush=True)
    if args.limit > 0:
        todo = todo[:args.limit]
        print(f'  限制前 {args.limit} 只（--limit）', flush=True)
    print(f'  实际待抓取: {len(todo)} 只', flush=True)

    # 3. 逐批抓取
    batch_size = args.batch_size
    results = {}  # code -> merged dict
    stats = {'ok': 0, 'zcpz_ok': 0, 'gmbd_ok': 0, 'cyrjg_ok': 0, 'fail': 0, 'empty': 0}

    print(f'\n[3] 开始抓取（batch={batch_size}, delay={args.delay}s）...', flush=True)
    for start_idx in range(0, len(todo), batch_size):
        batch = todo[start_idx:start_idx + batch_size]
        batch_num = start_idx // batch_size + 1
        total_batches = (len(todo) + batch_size - 1) // batch_size

        for code in batch:
            row_data = {}
            try:
                z = fetch_zcpz(code)
                if z and z.get('stock_pct') is not None:
                    row_data['stock_pct'] = z['stock_pct']
                    row_data['bond_pct'] = z['bond_pct']
                    row_data['cash_pct'] = z['cash_pct']
                    stats['zcpz_ok'] += 1
            except Exception:
                pass
            try:
                g = fetch_gmbd(code)
                if g and g.get('sub_purchase') is not None:
                    row_data['sub_purchase'] = g['sub_purchase']
                    row_data['sub_redemption'] = g['sub_redemption']
                    row_data['net_sub_share'] = g['net_sub_share']
                    row_data['total_share_end'] = g['total_share_end']
                    row_data['net_asset_end'] = g['net_asset_end']
                    row_data['nav_change_rate'] = g['nav_change_rate']
                    stats['gmbd_ok'] += 1
            except Exception:
                pass
            try:
                c = fetch_cyrjg(code)
                if c and c.get('inst_hold_pct') is not None:
                    row_data['inst_hold_pct'] = c['inst_hold_pct']
                    row_data['indiv_hold_pct'] = c['indiv_hold_pct']
                    row_data['internal_hold_pct'] = c['internal_hold_pct']
                    stats['cyrjg_ok'] += 1
            except Exception:
                pass

            if row_data:
                results[code] = row_data
                stats['ok'] += 1
            else:
                stats['empty'] += 1

        done = min(start_idx + batch_size, len(todo))
        print(f'  [{batch_num}/{total_batches}] 已处理 {done}/{len(todo)} '
              f'(成功:{stats["ok"]} 空值:{stats["empty"]} zcpz:{stats["zcpz_ok"]} gmbd:{stats["gmbd_ok"]} cyrjg:{stats["cyrjg_ok"]})', flush=True)
        if start_idx + batch_size < len(todo):
            time.sleep(args.delay)

    if not results:
        print('\n⚠ 无有效数据，结束', flush=True)
        return

    # 4. 写入临时表（分片专属表名，避免并行冲突）
    print(f'\n[4] 写入临时表 {tmp_table}（{len(results)} 条）...', flush=True)
    pg(f'DROP TABLE IF EXISTS {tmp_table}')
    pg(f'CREATE TABLE {tmp_table} (c text PRIMARY KEY, {", ".join(ALLOC_COLS)})')

    insert_batch = 500
    cols_sql = ', '.join(ALLOC_COLS)
    inserted = 0
    for s in range(0, len(results), insert_batch):
        chunk = list(results.items())[s:s + insert_batch]
        vals = []
        for code, data in chunk:
            safe = code.replace("'", "''")
            parts = [f"'{safe}'"]
            for col in ALLOC_COLS:
                v = data.get(col)
                parts.append('NULL' if v is None else str(v))
            vals.append(f'({", ".join(parts)})')
        sql = f'INSERT INTO {tmp_table} (c, {cols_sql}) VALUES {", ".join(vals)}'
        try:
            pg(sql, timeout=120)
            inserted += len(chunk)
        except Exception as e:
            print(f'  [WARN] 批量插入失败: {e}', flush=True)
    print(f'  ✓ {tmp_table} 写入 {inserted} 条', flush=True)

    # 5. 合并到 staging（一级）：COALESCE 保护已有值
    #    --to-prod 模式（方案B-B 独立流水线）下跳过 staging 写入：
    #    该流水线直写生产 fund_scores，不再污染方案B-A 流水线拥有的 staging 快照，
    #    避免两条流水线对 fund_scores_staging 的并发写竞争。生产 alloc 列由
    #    promote_staging.py 的 COALESCE 备份回填保护，无需依赖 staging。
    if args.to_prod:
        print('\n[5] --to-prod 模式：跳过 fund_scores_staging 写入（方案B-A 的 staging 快照由 COALESCE 备份保护）', flush=True)
    else:
        print('\n[5] 合并到 fund_scores_staging（一级，COALESCE 保护）...', flush=True)
        set_clause = ', '.join([f'{c} = COALESCE(t.{c}, fs.{c})' for c in ALLOC_COLS])
        pg(f'UPDATE fund_scores_staging fs SET {set_clause} FROM {tmp_table} t WHERE fs.c = t.c', timeout=300)
        print('  ✓ staging 已更新', flush=True)

    # 6. 镜像到 fund_scores_test（二级：验证用）
    print('\n[6] 镜像到 fund_scores_test（二级，验证）...', flush=True)
    set_clause_t = ', '.join([f'{c} = COALESCE(t.{c}, ft.{c})' for c in ALLOC_COLS])
    pg(f'UPDATE fund_scores_test ft SET {set_clause_t} FROM {tmp_table} t WHERE ft.c = t.c', timeout=300)
    print('  ✓ test 已更新', flush=True)

    # 7. 校验摘要（test 表）
    print('\n[7] 校验摘要（fund_scores_test）', flush=True)
    check = pg(f"""
        SELECT count(*) AS total,
               count(stock_pct) AS has_zcpz,
               count(sub_purchase) AS has_gmbd,
               count(inst_hold_pct) AS has_cyrjg
        FROM fund_scores_test
    """)[0]
    print(f'  fund_scores_test 总数: {check["total"]}')
    print(f'  有资产配置(zcpz): {check["has_zcpz"]} ({check["has_zcpz"]/max(check["total"],1)*100:.1f}%)')
    print(f'  有规模变动(gmbd): {check["has_gmbd"]} ({check["has_gmbd"]/max(check["total"],1)*100:.1f}%)')
    print(f'  有持有人结构(cyrjg): {check["has_cyrjg"]} ({check["has_cyrjg"]/max(check["total"],1)*100:.1f}%)')

    # 8. 可选：合并进生产
    if args.to_prod:
        print(f'\n[8] 合并 {tmp_table} → fund_scores（生产，COALESCE 保护）...', flush=True)
        set_clause_p = ', '.join([f'{c} = COALESCE(t.{c}, f.{c})' for c in ALLOC_COLS])
        pg(f'UPDATE fund_scores f SET {set_clause_p} FROM {tmp_table} t WHERE f.c = t.c', timeout=600)
        prod_check = pg(f"""
            SELECT count(*) AS total,
                   count(stock_pct) AS has_zcpz,
                   count(sub_purchase) AS has_gmbd,
                   count(inst_hold_pct) AS has_cyrjg
            FROM fund_scores
        """)[0]
        print(f'  ✓ 生产表已合并。fund_scores: 总数 {prod_check["total"]} | '
              f'zcpz {prod_check["has_zcpz"]} | gmbd {prod_check["has_gmbd"]} | cyrjg {prod_check["has_cyrjg"]}')
    else:
        print('\n[8] 未指定 --to-prod：数据已写入 staging + test，生产表未改动。')
        print('    确认无误后运行: python3 scripts/fetch_fund_allocation.py --to-prod', flush=True)

    # 清理
    pg(f'DROP TABLE IF EXISTS {tmp_table}')
    print('\n✅ ETL 完成！', flush=True)


if __name__ == '__main__':
    main()
