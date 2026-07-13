#!/usr/bin/env python3
"""
sync_etfs_to_fund_scores.py — 将标签关联的 ETF/LOF 场内基金补充进 fund_scores 主表

背景：
  fund_scores 主表由 nightly 的 promote_staging 从 fund_scores_staging 重建，
  而 staging 仅含天天基金 FundGuideapi 的 .OF 场外基金，不含场内 ETF/LOF。
  因此标签弹窗中大量 ETF/LOF 关联基金在 fund_scores 查不到 → 基金经理/收益为空。

  【用户已明确的数据模型】所有标签统一从 fund_scores 取「基金 + 基金经理」：
  本脚本把 ETF/LOF 也作为一等公民写入 fund_scores，使标签弹窗不再有空经理。

本脚本应在 promote_staging 之后运行（nightly 步骤 5h 调用），逻辑：
  1. 找出 fund_tag_funds 中「不在 fund_scores」的基金代码（约 918 只 ETF/LOF）；
  2. 用东财 fundf10 jbgk 解析基金经理/分类/管理人/规模/费率（复用 parse_jbgk）；
     —— 若东财解析失败，回退 fund_tag_funds.fund_manager（历史回填值，存在时）；
  3. 用 fund_tag_funds 的 syl_1n→r1y、syl_d→daily_change、tag_name→tags；
  4. UPSERT 进 fund_scores（ON CONFLICT (c) DO UPDATE），幂等、可每日重跑。

这样 ETF 在每日夜跑 TRUNCATE 重建后仍由本步骤重新追加，持久化得以保证，
且所有标签都统一从 fund_scores 取基金 + 基金经理。

用法：
  python3 sync_etfs_to_fund_scores.py            # 全量同步缺失 ETF/LOF
  python3 sync_etfs_to_fund_scores.py --limit 5  # 仅前 5 只（调试）
  python3 sync_etfs_to_fund_scores.py --skip-fetch  # 不抓东财，仅用 fund_tag_funds 回填值
"""
import os
import sys
import time
import json
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

# 复用兄弟脚本的 jbgk 解析器（仅标准库 + requests，导入安全）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from fetch_fund_basic_info import parse_jbgk  # noqa: E402

MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or os.environ.get('SUPABASE_PAT')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN（或 SUPABASE_PAT）')
PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF') or 'tqhtegazxykkqfcpejky'
MGMT_URL = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


def is_on_exchange(code):
    """判断场内基金（ETF/LOF）。场内代码：沪市 5xxxxx、深市 15xxxx/16xxxx。
    场外（开放式）基金统一以 .OF 后缀入库，与 nightly 的 FundGuideapi 约定一致，
    避免与每日重建的 .OF 行重复。"""
    if not code or len(code) != 6 or not code.isdigit():
        return False
    return code.startswith('5') or code.startswith('15') or code.startswith('16')


def canonical_key(code):
    """fund_scores 主键：场内用裸码，场外加 .OF 后缀。"""
    return code if is_on_exchange(code) else code + '.OF'


# 写入 fund_scores 的列（不含评分列 k_all/score_grade 等，ETF 不评分）
UPSERT_COLS = [
    'c', 'n', 't0', 't1', 't1_tt', 'daily_change', 'r1y',
    'fund_manager', 'company', 'fund_scale', 'share_scale',
    'manage_fee', 'custody_fee', 'sale_fee', 'found_date', 'tags',
]


def mgmt_query(sql, timeout=120):
    resp = requests.post(
        MGMT_URL,
        headers={'Authorization': f'Bearer {MGMT_TOKEN}', 'Content-Type': 'application/json'},
        json={'query': sql},
        timeout=timeout,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f'MGMT {resp.status_code}: {resp.text[:300]}')
    text = resp.text.strip()
    if not text:
        return []
    try:
        return resp.json()
    except json.JSONDecodeError:
        return []


def fetch_jbgk_html(code, timeout=12):
    """抓取 fundf10 基本概况页 HTML（ETF/LOF 同样有基金经理）"""
    url = f'https://fundf10.eastmoney.com/jbgk_{code}.html'
    try:
        r = requests.get(
            url,
            headers={'User-Agent': UA, 'Referer': 'https://fundf10.eastmoney.com/'},
            timeout=timeout,
        )
        if r.status_code == 200 and '基金经理' in r.text:
            return r.text
    except Exception:
        pass
    return None


def get_missing_etfs(limit=None):
    """返回 fund_tag_funds 中不在 fund_scores 的基金（聚合每只一行）"""
    sql = """
    SELECT tf.fund_code,
           (array_agg(tf.fund_name ORDER BY tf.sort_order ASC))[1] AS fund_name,
           (array_agg(tf.fund_type ORDER BY tf.sort_order ASC))[1] AS fund_type,
           MAX(tf.syl_1n) AS syl_1n,
           MAX(tf.syl_d) AS syl_d,
           MAX(tf.fund_manager) AS fallback_manager,
           array_agg(DISTINCT tf.tag_name) AS tag_names
    FROM fund_tag_funds tf
    WHERE NOT EXISTS (
        SELECT 1 FROM fund_scores fs
        WHERE fs.c = tf.fund_code OR fs.c = tf.fund_code || '.OF'
    )
    GROUP BY tf.fund_code
    ORDER BY tf.fund_code
    """
    if limit:
        sql = sql.rstrip().rstrip(';') + f" LIMIT {int(limit)}"
    return mgmt_query(sql)


def build_row(rec, skip_fetch=False):
    code = rec['fund_code']
    c_key = canonical_key(code)
    html = None if skip_fetch else fetch_jbgk_html(code)
    info = parse_jbgk(html) if html else {}

    manager = info.get('fund_manager') or rec.get('fallback_manager') or None
    t0 = info.get('t0') or '指数型'
    t1 = info.get('t1') or t0

    return {
        'c': c_key,
        'n': rec.get('fund_name') or code,
        't0': t0,
        't1': t1,
        't1_tt': rec.get('fund_type') or None,
        'daily_change': rec.get('syl_d'),
        'r1y': rec.get('syl_1n'),
        'fund_manager': manager,
        'company': info.get('company'),
        'fund_scale': info.get('fund_scale'),
        'share_scale': info.get('share_scale'),
        'manage_fee': info.get('manage_fee'),
        'custody_fee': info.get('custody_fee'),
        'sale_fee': info.get('sale_fee'),
        'found_date': info.get('found_date'),
        'tags': rec.get('tag_names') or [],
    }


def esc(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'TRUE' if v else 'FALSE'
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, list):
        if not v:
            return 'NULL'
        items = ', '.join("'" + str(x).replace("'", "''") + "'" for x in v)
        return f"ARRAY[{items}]::text[]"
    return "'" + str(v).replace("'", "''") + "'"


def upsert(rows, batch_size=50):
    total = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        values = []
        for r in batch:
            vals = [esc(r.get(col)) for col in UPSERT_COLS]
            values.append('(' + ', '.join(vals) + ')')
        set_clauses = ', '.join(f"{c}=EXCLUDED.{c}" for c in UPSERT_COLS)
        sql = (
            f"INSERT INTO fund_scores ({', '.join(UPSERT_COLS)}) VALUES "
            + ', '.join(values)
            + f" ON CONFLICT (c) DO UPDATE SET {set_clauses};"
        )
        mgmt_query(sql, timeout=600)
        total += len(batch)
        print(f'  upsert {total}/{len(rows)}', flush=True)
    return total


def main():
    parser = argparse.ArgumentParser(description='将标签关联 ETF/LOF 补充进 fund_scores')
    parser.add_argument('--limit', type=int, default=0, help='仅同步前 N 只（调试）')
    parser.add_argument('--skip-fetch', action='store_true', help='不抓东财，仅用 fund_tag_funds 回填值')
    parser.add_argument('--workers', type=int, default=4, help='东财抓取并发数')
    parser.add_argument('--delay', type=float, default=0.2, help='请求间隔（秒）')
    args = parser.parse_args()

    print('=' * 60, flush=True)
    print(' 将标签关联 ETF/LOF 补充进 fund_scores 主表', flush=True)
    print('=' * 60, flush=True)

    missing = get_missing_etfs(limit=args.limit if args.limit else None)
    print(f'\n[1] 待补充 ETF/LOF 数量: {len(missing)}', flush=True)
    if not missing:
        print('  无需补充，fund_scores 已覆盖全部标签关联基金。', flush=True)
        return

    # 并发抓取东财 jbgk（仅解析经理/分类，幂等）
    print(f'\n[2] 抓取东财 fundf10 概况（并发 {args.workers}，间隔 {args.delay}s）...', flush=True)
    rows = [None] * len(missing)

    def worker(idx, rec):
        return idx, build_row(rec, skip_fetch=args.skip_fetch)

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(worker, i, rec): i for i, rec in enumerate(missing)}
        done = 0
        for fut in as_completed(futures):
            idx, row = fut.result()
            rows[idx] = row
            done += 1
            if done % 50 == 0:
                print(f'  ... 已解析 {done}/{len(missing)}', flush=True)
            time.sleep(args.delay)

    rows = [r for r in rows if r]
    with_mgr = sum(1 for r in rows if r.get('fund_manager'))
    print(f'  解析完成: {len(rows)} 只，其中含基金经理 {with_mgr} 只', flush=True)

    print(f'\n[3] UPSERT 进 fund_scores（幂等）...', flush=True)
    n = upsert(rows)
    print(f'\n完成：向 fund_scores 写入/更新 {n} 只 ETF/LOF。', flush=True)
    print('   这些基金现在与其他场外基金一样，标签弹窗可统一从 fund_scores 取经理与收益。', flush=True)


if __name__ == '__main__':
    main()
