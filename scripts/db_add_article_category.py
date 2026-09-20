#!/usr/bin/env python3
"""
给 public.articles 增加 category 列（博客/影视/美食/游戏 四类）。
通过 Supabase Management API 的 database/query 端点执行 DDL。
SUPABASE_PAT 与项目 ref 从环境变量读取（不打印任何密钥）。

用法（在 repo 根目录）：
  bash -c 'set -a; . ./.env.local; set +a; python3 scripts/db_add_article_category.py'
"""
import os
import sys
import json
import urllib.request

SUPABASE_PAT = os.environ.get('SUPABASE_PAT')
PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF') or 'tqhtegazxykkqfcpejky'

if not SUPABASE_PAT:
    print('❌ 未找到 SUPABASE_PAT（请先 source .env.local）', file=sys.stderr)
    sys.exit(1)

SQL = (
    "ALTER TABLE public.articles "
    "ADD COLUMN IF NOT EXISTS category text NOT NULL DEFAULT 'blog' "
    "CHECK (category IN ('blog','film','food','game'));"
)

url = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'
req = urllib.request.Request(
    url,
    data=json.dumps({'query': SQL}).encode('utf-8'),
    headers={
        'Authorization': f'Bearer {SUPABASE_PAT}',
        'Content-Type': 'application/json',
    },
    method='POST',
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = resp.read().decode('utf-8')
        print('✅ SQL 执行成功（HTTP %d）' % resp.status)
        # 仅打印返回摘要，不打印任何密钥
        try:
            j = json.loads(body)
            print('   response:', json.dumps(j, ensure_ascii=False)[:300])
        except Exception:
            print('   response:', body[:300])
except urllib.error.HTTPError as e:
    err = e.read().decode('utf-8', 'replace')
    print('❌ HTTP 错误 %d: %s' % (e.code, err[:500]), file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print('❌ 请求失败: %s' % e, file=sys.stderr)
    sys.exit(1)
