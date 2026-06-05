#!/usr/bin/env python3
"""
合并风险指标到基金数据，重新计算靠谱分（v5: 收益60%+回撤30%+夏普10%），导入 Supabase

用法：
  python scripts/merge_risk_and_import.py
    [--funds scripts/funds_output.ndjson]
    [--risk scripts/risk_indicators.ndjson]

环境变量（通过 GitHub Secrets 注入）：
  SUPABASE_MGMT_TOKEN  — Supabase Personal Access Token（必需）
  SUPABASE_PROJECT_REF — Supabase 项目引用 ID
"""
import json
import subprocess
import time
import os
import sys
import argparse

# ===== 配置 =====
SUPABASE_PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF', 'tqhtegazxykkqfcpejky')
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN', '')
MGMT_API = f'https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query'
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

if not MGMT_TOKEN:
    print('ERROR: 未设置 SUPABASE_MGMT_TOKEN')
    sys.exit(1)


def run_mgmt_sql(sql):
    """通过 Supabase Management API 执行 SQL"""
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
    if isinstance(resp, dict) and resp.get('message'):
        raise Exception(resp['message'][:200])
    return resp


def _esc(s):
    if s is None:
        return "''"
    return "'" + str(s).replace("'", "''") + "'"


def _esc_null(v):
    if v is None:
        return 'NULL'
    try:
        f = float(v)
        if f == 0:
            return 'NULL'
        return str(f)
    except:
        return 'NULL'


def load_ndjson(filepath):
    """加载 NDJSON 文件"""
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data


def merge_risk_indicators(funds, risk_data):
    """将风险指标合并到基金数据中"""
    risk_map = {}
    for r in risk_data:
        code = r.get('c', '')
        if code:
            risk_map[code] = r

    merged = 0
    for fund in funds:
        code = fund.get('c', '')
        if code in risk_map:
            r = risk_map[code]
            fund['dd1y'] = r.get('dd1y')
            fund['dd2y'] = r.get('dd2y')
            fund['dd3y'] = r.get('dd3y')
            fund['dd5y'] = r.get('dd5y')
            fund['sr1y'] = r.get('sr1y')
            fund['sr2y'] = r.get('sr2y')
            fund['sr3y'] = r.get('sr3y')
            fund['sr5y'] = r.get('sr5y')
            merged += 1

    print(f'  合并风险指标: {merged}/{len(funds)} 只基金')
    return funds


def calc_scores_v5(funds):
    """
    v5 靠谱指数计算（全市场统一排名百分位×100）
    权重：收益排位×60% + 回撤排位×30% + 夏普排位×10%
    
    所有基金均参与评分（不再要求收益率>0）
    """
    periods = [
        {'k': 'k0w', 'r': 'r0w', 'dd': None, 'sr': None},
        {'k': 'k1m', 'r': 'r1m', 'dd': None, 'sr': None},
        {'k': 'k3m', 'r': 'r3m', 'dd': None, 'sr': None},
        {'k': 'k6m', 'r': 'r6m', 'dd': None, 'sr': None},
        {'k': 'k1',  'r': 'r1y', 'dd': 'dd1y', 'sr': 'sr1y'},
        {'k': 'k2',  'r': 'r2y', 'dd': 'dd2y', 'sr': 'sr2y'},
        {'k': 'k3',  'r': 'r3y', 'dd': 'dd3y', 'sr': 'sr3y'},
        {'k': 'k5',  'r': 'r5y', 'dd': 'dd5y', 'sr': 'sr5y'},
    ]
    W_RET = 0.60
    W_DD = 0.30
    W_SR = 0.10

    for period in periods:
        pk, rk, dk, sk = period['k'], period['r'], period['dd'], period['sr']
        # 所有基金参与排名
        valid = [(i, funds[i]) for i in range(len(funds))]
        if not valid:
            continue

        valid_n = len(valid)
        # 收益排位（降序）
        ret_ranked = sorted(valid, key=lambda x: x[1].get(rk, 0) or 0, reverse=True)
        ret_pct = {}
        for rank, (idx, fund) in enumerate(ret_ranked):
            ret_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0

        # 回撤排位（仅长周期有）
        dd_pct = {}
        if dk:
            dd_ranked = sorted(valid, key=lambda x: x[1].get(dk, -999) or -999, reverse=True)
            for rank, (idx, fund) in enumerate(dd_ranked):
                val = fund.get(dk)
                dd_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else (50.0 if val is not None else None)

        # 夏普排位（仅长周期有）
        sr_pct = {}
        if sk:
            sr_ranked = sorted(valid, key=lambda x: x[1].get(sk, -999) or -999, reverse=True)
            for rank, (idx, fund) in enumerate(sr_ranked):
                val = fund.get(sk)
                sr_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else (50.0 if val is not None else None)

        for idx, fund in valid:
            rp = ret_pct.get(idx)
            dp = dd_pct.get(idx) if dk else None
            sp = sr_pct.get(idx) if sk else None

            if dp is not None and sp is not None:
                score = round(W_RET * rp + W_DD * dp + W_SR * sp, 4)
            else:
                score = round(rp, 4)

            if score is not None:
                fund[pk] = score

    return funds


def import_to_supabase(funds):
    """通过 Management API 批量导入"""
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
                _esc_null(r.get('k0w')),
                _esc_null(r.get('k1m')),
                _esc_null(r.get('k3m')),
                _esc_null(r.get('k6m')),
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

        cols = 'c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y'
        sql = f"INSERT INTO fund_scores ({cols}) VALUES\n" + ',\n'.join(values)

        try:
            run_mgmt_sql(sql)
            imported += len(batch)
            print(f'  [{i}-{i+len(batch)}] +{len(batch)}条 (累计{imported})')
        except Exception as e:
            print(f'  [{i}-{i+len(batch)}] 错误: {str(e)[:100]}')

        time.sleep(0.15)

    return imported


def main():
    parser = argparse.ArgumentParser(description='合并风险指标 + 重新计算靠谱分 + 导入 Supabase')
    parser.add_argument('--funds', default=os.path.join(SCRIPT_DIR, 'funds_output.ndjson'))
    parser.add_argument('--risk', default=os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson'))
    args = parser.parse_args()

    print('=' * 60)
    print('合并风险指标 + 靠谱分 v5 重新计算 + Supabase 导入')
    print('=' * 60)

    # 1. 加载数据
    print('\n[1] 加载数据...')
    if not os.path.exists(args.funds):
        print(f'ERROR: 基金数据文件不存在: {args.funds}')
        sys.exit(1)
    funds = load_ndjson(args.funds)
    print(f'  基金数据: {len(funds)}条')

    risk_data = []
    if os.path.exists(args.risk):
        risk_data = load_ndjson(args.risk)
        print(f'  风险指标: {len(risk_data)}条')
    else:
        print(f'  风险指标文件不存在: {args.risk}，将仅使用收益排位')

    # 2. 合并风险指标
    if risk_data:
        print('\n[2] 合并风险指标...')
        funds = merge_risk_indicators(funds, risk_data)

    # 3. 重新计算靠谱分
    print('\n[3] 重新计算靠谱指数 v5（全基金参与）...')
    calc_scores_v5(funds)
    scored_funds = [r for r in funds if r.get('k3', 0) > 0]
    print(f'  有靠谱分的基金: {len(scored_funds)}只')

    # 4. 清空旧数据并导入
    print('\n[4] 清空 fund_scores 旧数据...')
    try:
        run_mgmt_sql('TRUNCATE TABLE fund_scores')
        print('  已清空')
    except Exception as e:
        print(f'  清空失败: {e}')

    print(f'\n[5] 导入 {len(funds)} 条到 Supabase...')
    imported = import_to_supabase(funds)

    # 6. 写入 meta
    print('\n[6] 写入 fund_scores_meta...')
    nav_date = funds[0].get('date', '') if funds else ''
    try:
        run_mgmt_sql('TRUNCATE TABLE fund_scores_meta')
        run_mgmt_sql(
            f"INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) "
            f"VALUES (NOW()::text, {len(funds)}, {len(scored_funds)}, '{nav_date}')"
        )
        print(f'  meta: total={len(funds)}, scored={len(scored_funds)}, date={nav_date}')
    except Exception as e:
        print(f'  meta写入失败: {e}')

    # 7. 验证
    print('\n[7] 验证...')
    result = run_mgmt_sql("SELECT count(*) as cnt FROM fund_scores")
    print(f'  fund_scores: {result[0]["cnt"]} 条')

    stats = run_mgmt_sql(
        "SELECT t0, count(*) as cnt, count(k3) as scored "
        "FROM fund_scores GROUP BY t0 ORDER BY cnt DESC"
    )
    print('\n  分类统计:')
    for s in stats:
        print(f'    {s["t0"]}: {s["cnt"]}只, 有靠谱分{s["scored"]}只')

    print('\nDone!')


if __name__ == '__main__':
    main()
