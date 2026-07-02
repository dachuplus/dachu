#!/usr/bin/env python3
"""
将 fund_combined 的分类同步到 fund_scores（以天天基金分类为准）

用法：
  python3 sync_classification_to_fund_scores.py

该脚本在 CI 步骤 3b 执行，确保 fund_scores.t0/t1 与 fund_combined 保持一致。
"""

import os
import requests
import sys

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or ''

# 也支持 VITE_ 前缀 + ANON_KEY 的组合
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3')

if not MGMT_TOKEN:
    # Fallback: try PAT from env
    MGMT_TOKEN = os.environ.get('SUPABASE_PAT', '')

if not MGMT_TOKEN:
    print('ERROR: 缺少 SUPABASE_MGMT_TOKEN')
    sys.exit(1)


def mgmt_query(sql):
    """执行 SQL 通过 Supabase Management API"""
    url = f'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'
    headers = {'Authorization': f'Bearer {MGMT_TOKEN}', 'Content-Type': 'application/json'}
    resp = requests.post(url, headers=headers, json={'query': sql}, timeout=120)
    if resp.status_code != 200:
        print(f'  SQL ERROR: {resp.text[:200]}')
        return None
    try:
        return resp.json()
    except:
        return []


def main():
    print('=' * 60)
    print('🔄 同步分类: fund_combined → fund_scores')
    print('=' * 60)

    # Step 1: 更新不一致的分类
    print('\n步骤1: 更新已存在行中不一致的分类...')
    sql_update = """
    UPDATE fund_scores fs SET
      t0 = fc.t0,
      t1 = fc.t1
    FROM fund_combined fc
    WHERE REPLACE(fs.c, '.OF', '') = fc.c
      AND fs.t0 IS DISTINCT FROM fc.t0
    """
    result = mgmt_query(sql_update)
    print(f'  完成 (affected rows printed above if any)')

    # Step 2: 插入 fund_combined 中有但 fund_scores 中没有的基金
    print('\n步骤2: 插入缺失的基金...')
    sql_insert = """
    INSERT INTO fund_scores (c, n, t0, t1, company, fund_scale, manage_fee)
    SELECT fc.c || '.OF', fc.name, fc.t0, fc.t1, fc.company, fc.fund_scale, fc.manage_fee
    FROM fund_combined fc
    WHERE NOT EXISTS (
        SELECT 1 FROM fund_scores fs
        WHERE REPLACE(fs.c, '.OF', '') = fc.c
    )
    RETURNING c
    """
    inserted = mgmt_query(sql_insert)
    if inserted:
        print(f'  新增 {len(inserted)} 只基金')
    else:
        print('  无需新增')

    # Step 3: 验证最终分类分布
    print('\n步骤3: 验证最终分类分布...')
    sql_dist = """
    SELECT t0, count(*) as cnt
    FROM fund_scores
    GROUP BY t0
    ORDER BY cnt DESC
    """
    dist = mgmt_query(sql_dist)
    if dist:
        for row in dist:
            print(f'  {row["t0"]}: {row["cnt"]}')

    sql_total = "SELECT count(*) as cnt FROM fund_scores"
    total = mgmt_query(sql_total)
    if total:
        print(f'\n  fund_scores 总计: {total[0]["cnt"]}')

    print('\n✅ 分类同步完成')


if __name__ == '__main__':
    main()
