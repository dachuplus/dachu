#!/usr/bin/env python3
"""
计算 k_all (v7加权综合分) 和 score_grade，并批量写入 Supabase。

k_all = 各周期靠谱分的加权平均值
权重: k0w(5%) + k1m(5%) + k3m(10%) + k6m(15%) + k1(20%) + k2(20%) + k3(15%) + k5(10%)
只有有数据(>0)的周期参与加权，权重按比例重新归一化。

score_grade 基于 k_all 百分位：
  - >=80: green (前20%)
  - >=50: blue (20%-50%)
  -  >0:  orange (后50%)
  -  null/0: gray (无数据)
"""
import sys
import json
import time
import os
import requests

MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN')

SUPABASE_PROJECT_REF = 'tqhtegazxykkqfcpejky'
MGMT_API = f'https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query'

HEADERS = {
    'Authorization': f'Bearer {MGMT_TOKEN}',
    'Content-Type': 'application/json',
}

# v7 周期权重
PERIOD_WEIGHTS = {
    'k0w': 5, 'k1m': 5, 'k3m': 10, 'k6m': 15,
    'k1': 20, 'k2': 20, 'k3': 15, 'k5': 10,
    'k7': 0, 'k10': 0,  # 当前无数据
}


def pg_query(sql):
    """通过 Management API 执行 SQL"""
    resp = requests.post(MGMT_API, headers=HEADERS, json={'query': sql})
    if resp.status_code != 200 and resp.status_code != 201:
        print(f'  SQL ERROR [{resp.status_code}]: {resp.text[:200]}')
        return None
    try:
        return resp.json()
    except Exception:
        return None


def fetch_all():
    """分页拉取全量基金的 k 字段"""
    print('[1] 从 Supabase 拉取 k 字段...')
    all_data = []
    offset = 0
    limit = 1000

    k_fields = ['k0w', 'k1m', 'k3m', 'k6m', 'k1', 'k2', 'k3', 'k5', 'k7', 'k10']
    fields = 'c,' + ','.join(k_fields)

    while True:
        sql = f'SELECT {fields} FROM fund_scores ORDER BY c LIMIT {limit} OFFSET {offset}'
        batch = pg_query(sql)
        if batch is None or len(batch) == 0:
            break
        all_data.extend(batch)
        offset += limit
        print(f'  已拉取 {len(all_data)} 条...', end='\r')

    print(f'\n  共拉取 {len(all_data)} 条记录')
    return all_data


def compute_k_all(funds):
    """计算 k_all 和 score_grade"""
    print('\n[2] 计算 k_all (v7 加权) ...')

    k_fields = ['k0w', 'k1m', 'k3m', 'k6m', 'k1', 'k2', 'k3', 'k5', 'k7', 'k10']

    total = len(funds)
    scored = 0

    for f in funds:
        total_w = 0
        weighted_sum = 0
        for kf in k_fields:
            w = PERIOD_WEIGHTS.get(kf, 0)
            val = float(f.get(kf) or 0)
            if val > 0 and w > 0:
                weighted_sum += val * w
                total_w += w

        if total_w > 0:
            f['k_all'] = round(weighted_sum / total_w, 4)
            scored += 1
        else:
            f['k_all'] = None

    # 计算百分位
    print(f'  有 k_all 分的基金: {scored}/{total}')
    print('  计算百分位 rank...')

    scored_funds = [f for f in funds if f['k_all'] is not None]
    scored_funds.sort(key=lambda x: x['k_all'], reverse=True)
    n = len(scored_funds)

    for rank, f in enumerate(scored_funds):
        pct = (1 - rank / (n - 1)) * 100 if n > 1 else 50
        if pct >= 80:
            f['score_grade'] = 'green'
        elif pct >= 50:
            f['score_grade'] = 'blue'
        else:
            f['score_grade'] = 'orange'

    # 无 k_all 的设为 gray
    for f in funds:
        if 'score_grade' not in f:
            f['score_grade'] = 'gray'

    # 统计
    grades = {}
    for f in funds:
        g = f['score_grade']
        grades[g] = grades.get(g, 0) + 1
    for g, c in sorted(grades.items()):
        print(f'  {g}: {c}只')

    return funds


def update_all(funds, batch_size=500):
    """批量 UPDATE k_all 和 score_grade"""
    print(f'\n[3] 批量 UPDATE {len(funds)} 条记录...')
    total = len(funds)
    success = 0
    fail = 0

    for i in range(0, total, batch_size):
        batch = funds[i:i + batch_size]

        # 使用 VALUES 批量更新
        values_parts = []
        for f in batch:
            c = f['c'].replace("'", "''")
            k_all = f.get('k_all')
            k_all_str = str(k_all) if k_all is not None else 'NULL'
            grade = f.get('score_grade', 'gray')
            values_parts.append(f"('{c}',{k_all_str},'{grade}')")

        values_str = ', '.join(values_parts)
        sql = f"""
        UPDATE fund_scores SET
          k_all = v.k_all,
          score_grade = v.score_grade
        FROM (VALUES {values_str}) AS v(c, k_all, score_grade)
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


def update_meta(funds):
    """更新 fund_scores_meta"""
    print('\n[4] 更新 fund_scores_meta...')
    scored_count = sum(1 for f in funds if f.get('k_all') is not None)

    # 获取 nav_date
    result = pg_query("SELECT nav_date, tsq FROM fund_scores_meta WHERE id = 8")
    nav_date = ''
    tsq = ''
    if result and len(result) > 0:
        nav_date = result[0].get('nav_date', '') or ''
        tsq = result[0].get('tsq', '') or ''

    # UPDATE
    pg_query(f"""
    UPDATE fund_scores_meta
    SET scored_count = {scored_count},
        total_count = {len(funds)},
        nav_date = '{nav_date}',
        tsq = NOW()::text
    WHERE id = 8
    """)

    print(f'  total={len(funds)}, scored={scored_count}, date={nav_date}')


def main():
    # 1. 拉取全量 k 字段
    funds = fetch_all()
    if not funds:
        print('未获取到基金数据，退出')
        sys.exit(1)

    # 2. 计算 k_all 和 score_grade
    compute_k_all(funds)

    # 3. 批量写回
    update_all(funds)

    # 4. 更新 meta
    update_meta(funds)


if __name__ == '__main__':
    main()
