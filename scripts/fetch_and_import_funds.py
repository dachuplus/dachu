#!/usr/bin/env python3
"""
fund_scores 全量抓取 + Supabase 导入脚本
1. 从天天基金 FundGuideapi 拉取全量基金（5大分类）
2. 全市场统一排名计算靠谱指数（v5: 收益60%+回撤30%+夏普10%）
   - 无风险指标时，仅用收益排位计算（归一化到100分）
3. 通过 Supabase REST API 批量导入

注意：风险指标（回撤+夏普）需单独运行 fetch_risk_indicators.py 后重新计算
"""
import json
import subprocess
import time
import math
import sys
import os
import argparse

# ===== 配置（从环境变量读取，GitHub Actions 通过 Secrets 注入）=====
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN', '')
SUPABASE_PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF', 'tqhtegazxykkqfcpejky')
MGMT_API = f'https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query'

# 脚本目录
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 验证必要的环境变量
if not ANON_KEY and not MGMT_TOKEN:
    print('ERROR: 缺少凭证！请设置环境变量 SUPABASE_ANON_KEY 和 SUPABASE_MGMT_TOKEN')
    sys.exit(1)
if not MGMT_TOKEN:
    print('WARNING: 未设置 SUPABASE_MGMT_TOKEN，跳过数据库写入操作')
if not ANON_KEY:
    print('WARNING: 未设置 SUPABASE_ANON_KEY')

FT_MAP = {
    'gp': '股票型基金',
    'zq': '债券型基金',
    'hh': '混合型基金',
    'fof': 'FOF',
    'qdii': 'QDII基金',
}
FT_LIST = list(FT_MAP.keys())


def _float(v):
    try:
        return float(v) if v and v.strip() and v.strip() != '' else 0
    except:
        return 0


def _null_float(v):
    """Convert to float, return None if invalid"""
    try:
        val = float(v)
        return val if val != 0 else None
    except:
        return None


def fetch_funds(ft):
    """从天天基金拉取指定分类的全部基金（用 curl 避免被限速）"""
    all_funds = []
    for pi in range(1, 5):
        url = (
            'https://fund.eastmoney.com/data/FundGuideapi.aspx?dt=0&ft=' + ft +
            '&sd=&ed=&sc=3nzf&st=desc&pi=' + str(pi) + '&pn=5000&zf=diy&sh=list'
        )
        print(f'  拉取 {FT_MAP[ft]}({ft}) 第{pi}页...', end='', flush=True)
        try:
            result = subprocess.run(
                ['curl', '-s', '-H', 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
                 '-H', 'Referer: https://fund.eastmoney.com/', url],
                capture_output=True, text=True, timeout=15
            )
            text = result.stdout
            if not text or '{' not in text:
                print(' 无响应，跳过')
                break
            s = text.find('{')
            e = text.rfind('}') + 1
            if s < 0 or e <= s:
                print(' 解析失败')
                break
            data = json.loads(text[s:e])
            items = data.get('datas', [])
            total_count = int(data.get('datacount', 0))
            for item in items:
                f = item.split(',')
                if len(f) < 13:
                    continue
                all_funds.append({
                    'c': f[0].strip() + '.OF',
                    'n': (f[1] or '').strip(),
                    't0': FT_MAP[ft],
                    't1': (f[3] or '').strip() or FT_MAP[ft],
                    't2': (f[3] or '').strip(),
                    't6': '',
                    'a': 0,
                    'hp': 0,
                    'ytd': _float(f[4]),
                    'r0w': _float(f[5]),
                    'r1m': _float(f[6]),
                    'r3m': _float(f[7]),
                    'r6m': _float(f[8]),
                    'r1y': _float(f[9]),
                    'r2y': _float(f[10]),
                    'r3y': _float(f[11]),
                    'r5y': _float(f[12]),
                    'nav': _float(f[16]) if len(f) > 16 else 0,
                    'date': f[15].strip() if len(f) > 15 else '',
                })
            print(f' +{len(items)}条 (总计{total_count}, 累计{len(all_funds)})')
            if len(all_funds) >= total_count or len(items) < 5000:
                break
        except Exception as e:
            print(f' 异常: {e}')
            break
        time.sleep(0.5)
    return all_funds


def calc_scores_v5(funds):
    """
    v5 靠谱指数计算（全市场统一排名百分位×100）
    权重：收益排位×60% + 回撤排位×30% + 夏普排位×10%
    
    无风险指标时，仅用收益排位（100分制）
    有风险指标时，三指标加权
    
    k1→近1年(r1y), k2→近2年(r2y), k3→近3年(r3y), k5→近5年(r5y)
    k7/k10→暂无数据
    """
    periods = [
        {'k': 'k1', 'r': 'r1y', 'dd': 'dd1y', 'sr': 'sr1y'},
        {'k': 'k2', 'r': 'r2y', 'dd': 'dd2y', 'sr': 'sr2y'},
        {'k': 'k3', 'r': 'r3y', 'dd': 'dd3y', 'sr': 'sr3y'},
        {'k': 'k5', 'r': 'r5y', 'dd': 'dd5y', 'sr': 'sr5y'},
    ]
    W_RET = 0.60
    W_DD = 0.30
    W_SR = 0.10

    total_scored = 0

    for period in periods:
        pk, rk, dk, sk = period['k'], period['r'], period['dd'], period['sr']
        valid = [(i, funds[i]) for i in range(len(funds)) if (funds[i].get(rk, 0) or 0) > 0]
        if not valid:
            continue

        valid_n = len(valid)
        # 收益排位（降序，越高越好）
        ret_ranked = sorted(valid, key=lambda x: x[1].get(rk, 0) or 0, reverse=True)
        ret_pct = {}
        for rank, (idx, fund) in enumerate(ret_ranked):
            ret_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0

        # 回撤排位（dd降序，越大越好）
        dd_ranked = sorted(valid, key=lambda x: x[1].get(dk, -999) or -999, reverse=True)
        dd_pct = {}
        for rank, (idx, fund) in enumerate(dd_ranked):
            val = fund.get(dk)
            dd_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0 if val is not None else None

        # 夏普排位（降序，越高越好）
        sr_ranked = sorted(valid, key=lambda x: x[1].get(sk, -999) or -999, reverse=True)
        sr_pct = {}
        for rank, (idx, fund) in enumerate(sr_ranked):
            val = fund.get(sk)
            sr_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0 if val is not None else None

        for idx, fund in valid:
            rp = ret_pct.get(idx)
            dp = dd_pct.get(idx)
            sp = sr_pct.get(idx)

            if dp is not None and sp is not None:
                # 三指标加权
                score = round(W_RET * rp + W_DD * dp + W_SR * sp, 4)
            else:
                # 仅收益排位（无风险指标），归一化到收益部分
                score = round(rp, 4)

            if score is not None:
                fund[pk] = score
                if fund.get(pk, 0) > 0:
                    total_scored += 1

    return total_scored


def run_mgmt_sql(sql):
    """通过 Management API 执行 SQL（用 curl）"""
    payload = json.dumps({'query': sql})
    result = subprocess.run(
        ['curl', '-s', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise Exception(f'curl failed: {result.stderr[:100]}')
    resp = json.loads(result.stdout)
    # Check for error in response
    if isinstance(resp, dict) and resp.get('message'):
        raise Exception(resp['message'][:200])
    return resp


def import_to_supabase(funds):
    """通过 Management API 批量导入 fund_scores"""
    BATCH = 100
    imported = 0

    for i in range(0, len(funds), BATCH):
        batch = funds[i:i + BATCH]
        values = []
        for r in batch:
            vals = [
                _esc(r.get('c', '')),
                _esc(r.get('n', '')),
                _esc(r.get('t0', '')),
                _esc(r.get('t1', '')),
                _esc(r.get('t2', '')),
                _esc(r.get('t6', '')),
                r.get('a', 0) or 0,
                _esc_null(r.get('hp')),
                _esc_null(r.get('ytd')),
                _esc_null(r.get('r0w')),
                _esc_null(r.get('r1m')),
                _esc_null(r.get('r3m')),
                _esc_null(r.get('r6m')),
                _esc_null(r.get('r1y')),
                _esc_null(r.get('r2y')),
                _esc_null(r.get('r3y')),
                _esc_null(r.get('r5y')),
                _esc_null(r.get('nav')),
                _esc(r.get('date', '')),
                _esc_null(r.get('k1')),
                _esc_null(r.get('k2')),
                _esc_null(r.get('k3')),
                _esc_null(r.get('k5')),
                _esc_null(r.get('k7')),
                _esc_null(r.get('k10')),
                _esc_null(r.get('dd1y')),
                _esc_null(r.get('dd2y')),
                _esc_null(r.get('dd3y')),
                _esc_null(r.get('dd5y')),
                _esc_null(r.get('sr1y')),
                _esc_null(r.get('sr2y')),
                _esc_null(r.get('sr3y')),
                _esc_null(r.get('sr5y')),
            ]
            values.append(f"({','.join(str(v) for v in vals)})")

        cols = 'c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y'
        sql = f"INSERT INTO fund_scores ({cols}) VALUES\n" + ',\n'.join(values)

        try:
            run_mgmt_sql(sql)
            imported += len(batch)
            print(f'  [{i}-{i+len(batch)}] +{len(batch)}条 (累计{imported})')
        except Exception as e:
            print(f'  [{i}-{i+len(batch)}] 错误: {str(e)[:100]}')

        time.sleep(0.2)

    return imported


def _esc(s):
    """Escape string for SQL"""
    if s is None:
        return "''"
    return "'" + str(s).replace("'", "''") + "'"


def _esc_null(v):
    """Escape nullable numeric for SQL"""
    if v is None:
        return 'NULL'
    try:
        f = float(v)
        if f == 0:
            return 'NULL'
        return str(f)
    except:
        return 'NULL'


def main():
    print('=' * 60)
    print('fund_scores 全量抓取 + Supabase 导入')
    print('=' * 60)

    # 1. 拉取天天基金全量
    print('\n[1] 拉取天天基金全量数据...')
    all_funds = []
    for ft in FT_LIST:
        funds = fetch_funds(ft)
        all_funds.extend(funds)
        time.sleep(0.5)

    # 去重
    deduped = {}
    for fund in all_funds:
        deduped[fund['c']] = fund
    all_funds = list(deduped.values())
    print(f'\n  去重后: {len(all_funds)}只')

    # 2. 初始化风险指标字段
    for fund in all_funds:
        fund['k1'] = 0
        fund['k2'] = 0
        fund['k3'] = 0
        fund['k5'] = 0
        fund['k7'] = 0
        fund['k10'] = 0
        fund['dd1y'] = None
        fund['dd2y'] = None
        fund['dd3y'] = None
        fund['dd5y'] = None
        fund['sr1y'] = None
        fund['sr2y'] = None
        fund['sr3y'] = None
        fund['sr5y'] = None

    # 3. 计算靠谱指数（v5，仅收益排位）
    print('\n[2] 计算靠谱指数 v5（仅收益排位，无风险指标）...')
    scored = calc_scores_v5(all_funds)
    scored_funds = [r for r in all_funds if r.get('k3', 0) > 0]
    print(f'  有靠谱分的基金: {len(scored_funds)}只')

    # 保存 NDJSON（供后续风险指标步骤使用）
    output_file = os.path.join(SCRIPT_DIR, 'funds_output.ndjson')
    with open(output_file, 'w', encoding='utf-8') as f:
        for fund in all_funds:
            f.write(json.dumps(fund, ensure_ascii=False) + '\n')
    print(f'\n  已保存 NDJSON: {output_file} ({len(all_funds)}条)')

    # 如果是仅输出模式，到此结束
    if args.output_only:
        print('\n[--output-only] 跳过数据库写入')
        print(f'  NDJSON 文件: {output_file}')
        return

    # 4. 清空旧数据并导入
    print('\n[3] 清空 fund_scores 旧数据...')
    try:
        run_mgmt_sql('TRUNCATE TABLE fund_scores')
        print('  已清空')
    except Exception as e:
        print(f'  清空失败: {e}')

    print(f'\n[4] 导入 {len(all_funds)} 条到 Supabase...')
    imported = import_to_supabase(all_funds)

    # 5. 写入 meta
    print('\n[5] 写入 fund_scores_meta...')
    nav_date = all_funds[0].get('date', '') if all_funds else ''
    try:
        run_mgmt_sql('TRUNCATE TABLE fund_scores_meta')
        run_mgmt_sql(f"INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) VALUES (NOW()::text, {len(all_funds)}, {len(scored_funds)}, '{nav_date}')")
        print(f'  meta: total={len(all_funds)}, scored={len(scored_funds)}, date={nav_date}')
    except Exception as e:
        print(f'  meta写入失败: {e}')

    # 6. 验证
    print('\n[6] 验证...')
    result = run_mgmt_sql("SELECT count(*) as cnt FROM fund_scores")
    print(f'  fund_scores: {result[0]["cnt"]} 条')

    # 各分类统计
    stats = run_mgmt_sql("SELECT t0, count(*) as cnt, count(k3) as scored FROM fund_scores GROUP BY t0 ORDER BY cnt DESC")
    print('\n  分类统计:')
    for s in stats:
        print(f'    {s["t0"]}: {s["cnt"]}只, 有靠谱分{s["scored"]}只')

    # Top 10 靠谱分
    top10 = run_mgmt_sql("SELECT c, n, t0, k1, k3 FROM fund_scores WHERE k3 > 0 ORDER BY k3 DESC LIMIT 10")
    print('\n  Top 10 靠谱分:')
    for t in top10:
        print(f'    {t["c"]} {t["n"]}: k1={t["k1"]}, k3={t["k3"]}')

    print('\nDone!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='基金数据全量抓取 + Supabase 导入')
    parser.add_argument('--output-only', action='store_true', help='仅输出 NDJSON，不写入 Supabase')
    args = parser.parse_args()
    main()
