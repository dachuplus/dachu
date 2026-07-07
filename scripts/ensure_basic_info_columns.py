#!/usr/bin/env python3
"""
ensure_basic_info_columns.py — 为 fund_scores 表新增基本信息字段（幂等）

新增列：
  - share_scale   numeric  份额规模（亿份）
  - custody_fee   numeric  托管费率（%/年）
  - sale_fee      numeric  销售服务费率（%/年）
  - found_date    text     成立日期（YYYY-MM-DD）

使用 Supabase Management API 执行 DDL（requests 库，避免 urllib 403）。
先查 information_schema 确认列不存在，再 ALTER TABLE ADD COLUMN IF NOT EXISTS。
"""
import os
import sys
import json
import requests

# 从环境变量读取（CI 注入），本地回退到 .env.local
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or os.environ.get('SUPABASE_PAT')
PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF') or 'tqhtegazxykkqfcpejky'

MGMT_API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'

NEW_COLUMNS = [
    ('share_scale', 'numeric', '份额规模（亿份）'),
    ('custody_fee', 'numeric', '托管费率（%/年）'),
    ('sale_fee', 'numeric', '销售服务费率（%/年）'),
    ('found_date', 'text', '成立日期（YYYY-MM-DD）'),
]


def pg_query(sql, timeout=60):
    if not MGMT_TOKEN:
        print('[ERROR] SUPABASE_MGMT_TOKEN / SUPABASE_PAT 未设置')
        sys.exit(1)
    payload = json.dumps({'query': sql})
    r = requests.post(
        MGMT_API,
        headers={
            'Authorization': f'Bearer {MGMT_TOKEN}',
            'Content-Type': 'application/json',
        },
        data=payload,
        timeout=timeout,
    )
    if r.status_code not in (200, 201, 204):
        raise RuntimeError(f'DDL failed HTTP {r.status_code}: {r.text[:300]}')
    try:
        return r.json()
    except Exception:
        return None


def column_exists(col):
    sql = (
        "SELECT column_name FROM information_schema.columns "
        f"WHERE table_name = 'fund_scores' AND column_name = '{col}'"
    )
    res = pg_query(sql)
    if isinstance(res, list):
        return len(res) > 0
    return False


def main():
    print(f'检查 fund_scores 表结构（project: {PROJECT_REF}）', flush=True)
    for col, dtype, comment in NEW_COLUMNS:
        if column_exists(col):
            print(f'  ✓ {col} 已存在，跳过', flush=True)
            continue
        sql = f'ALTER TABLE fund_scores ADD COLUMN IF NOT EXISTS {col} {dtype};'
        try:
            pg_query(sql)
            print(f'  + 新增 {col} ({dtype}) — {comment}', flush=True)
        except Exception as e:
            print(f'  ✗ 新增 {col} 失败: {e}', flush=True)
            sys.exit(1)
    print('✅ 列检查/新增完成', flush=True)


if __name__ == '__main__':
    main()
