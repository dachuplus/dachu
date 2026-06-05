#!/usr/bin/env python3
"""
从 Supabase Management API 拉取全量基金，重新计算靠谱分，批量 UPDATE 写回。
"""
import sys
import json
import time
import requests

MGMT_TOKEN = 'TOKEN_REMOVED'
SUPABASE_PROJECT_REF = 'tqhtegazxykkqfcpejky'
MGMT_API = f'https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query'

HEADERS = {
    'Authorization': f'Bearer {MGMT_TOKEN}',
    'Content-Type': 'application/json',
}


def pg_query(sql):
    """通过 Management API 执行 SQL"""
    resp = requests.post(MGMT_API, headers=HEADERS, json={'query': sql})
    if resp.status_code != 200 and resp.status_code != 201:
        print(f'  SQL ERROR [{resp.status_code}]: {resp.text[:200]}')
        return None
    try:
        return resp.json()
    except:
        return None


def calc_scores_v5(funds):
    """
    v5 靠谱指数计算（全市场统一排名百分位×100）
    权重：收益排位×60% + 回撤排位×30% + 夏普排位×10%
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
        valid = [(i, funds[i]) for i in range(len(funds))]
        if not valid:
            continue

        valid_n = len(valid)

        # 收益排位（降序）
        ret_ranked = sorted(valid, key=lambda x: float(x[1].get(rk) or 0), reverse=True)
        ret_pct = {}
        for rank, (idx, _) in enumerate(ret_ranked):
            ret_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0

        # 回撤排位（仅长周期有）
        dd_pct = {}
        if dk:
            dd_ranked = sorted(valid, key=lambda x: float(x[1].get(dk) or -999), reverse=True)
            for rank, (idx, fund) in enumerate(dd_ranked):
                val = fund.get(dk)
                dd_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else (50.0 if val is not None else None)

        # 夏普排位（仅长周期有）
        sr_pct = {}
        if sk:
            sr_ranked = sorted(valid, key=lambda x: float(x[1].get(sk) or -999), reverse=True)
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


def fetch_all_funds():
    """分页拉取全量基金"""
    print('[1] 从 Supabase 拉取全量基金数据...')
    all_funds = []
    offset = 0
    limit = 1000

    fields = 'c,n,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y'

    while True:
        sql = f'SELECT {fields} FROM fund_scores ORDER BY c LIMIT {limit} OFFSET {offset}'
        batch = pg_query(sql)
        if batch is None or len(batch) == 0:
            break
        all_funds.extend(batch)
        offset += limit
        print(f'  已拉取 {len(all_funds)} 条...', end='\r')

    print(f'\n  共拉取 {len(all_funds)} 条基金记录')
    return all_funds


def update_scores(funds, batch_size=200):
    """批量 UPDATE 靠谱分"""
    print(f'\n[3] 批量 UPDATE {len(funds)} 条记录...')
    total = len(funds)
    success = 0
    fail = 0

    for i in range(0, total, batch_size):
        batch = funds[i:i+batch_size]
        # 构建 CASE WHEN 的批量更新 SQL
        codes = [f"'{f['c']}'" for f in batch]
        code_list = ', '.join(codes)

        # 使用 UPDATE ... FROM (VALUES ...) 批量更新
        values_parts = []
        for f in batch:
            c = f['c'].replace("'", "''")
            k0w = f.get('k0w', 0)
            k1m = f.get('k1m', 0)
            k3m = f.get('k3m', 0)
            k6m = f.get('k6m', 0)
            k1 = f.get('k1', 0)
            k2 = f.get('k2', 0)
            k3 = f.get('k3', 0)
            k5 = f.get('k5', 0)
            values_parts.append(f"('{c}',{k0w},{k1m},{k3m},{k6m},{k1},{k2},{k3},{k5})")

        values_str = ', '.join(values_parts)
        sql = f"""
        UPDATE fund_scores SET
          k0w = v.k0w,
          k1m = v.k1m,
          k3m = v.k3m,
          k6m = v.k6m,
          k1 = v.k1,
          k2 = v.k2,
          k3 = v.k3,
          k5 = v.k5
        FROM (VALUES {values_str}) AS v(c, k0w, k1m, k3m, k6m, k1, k2, k3, k5)
        WHERE fund_scores.c = v.c
        """

        result = pg_query(sql)
        if result is not None:
            success += len(batch)
        else:
            fail += len(batch)

        batch_num = i // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f'  批次 {batch_num}/{total_batches}: 成功 {success}, 失败 {fail}')
        time.sleep(0.2)

    print(f'\n完成！总计成功 {success}, 失败 {fail}')


def main():
    # 1. 拉取全量数据
    funds = fetch_all_funds()
    if not funds:
        print('未获取到基金数据，退出')
        sys.exit(1)

    # 2. 重新计算靠谱分
    print(f'\n[2] 重新计算靠谱指数 v5（{len(funds)}只基金，全周期）...')
    calc_scores_v5(funds)

    # 统计
    for pk in ['k0w', 'k1m', 'k3m', 'k6m', 'k1', 'k2', 'k3', 'k5']:
        cnt = sum(1 for f in funds if f.get(pk, 0) > 0)
        print(f'  {pk}: {cnt}只有分')

    # 3. 批量写回
    update_scores(funds)


if __name__ == '__main__':
    main()
