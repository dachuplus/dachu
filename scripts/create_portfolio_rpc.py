#!/usr/bin/env python3
"""重建 get_user_portfolios_by_email RPC（SECURITY DEFINER，仅管理员可查他人组合）。
仅返回服务端自建组合（user_portfolios），AI 组合存于客户端 localStorage，服务端不可见 => is_ai=false。
"""
import os
import re
import sys
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, '.env.local')

# 读取 .env.local 中的 SUPABASE_PAT / ref
pat = None
ref = 'tqhtegazxykkqfcpejky'
with open(ENV_PATH, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('SUPABASE_PAT='):
            pat = line.split('=', 1)[1].strip()
        elif line.startswith('VITE_SUPABASE_URL='):
            m = re.search(r'https://([^.]+)\.supabase\.co', line)
            if m:
                ref = m.group(1)

if not pat:
    print('ERROR: SUPABASE_PAT not found in .env.local')
    sys.exit(1)

URL = f'https://api.supabase.com/v1/projects/{ref}/database/query'
HEADERS = {
    'Authorization': f'Bearer {pat}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
}

def run_sql(sql):
    r = requests.post(URL, headers=HEADERS, json={'query': sql}, timeout=60)
    try:
        body = r.json()
    except Exception:
        body = r.text
    return r.status_code, body

# 1) 检查现有函数签名
check = "SELECT proname, pg_get_function_result(oid) AS ret FROM pg_proc WHERE proname='get_user_portfolios_by_email';"
sc, sb = run_sql(check)
print('CHECK existing:', sc, sb)

# 2) 若存在且签名不符，先 DROP（按参数类型 (text)）
drop = "DROP FUNCTION IF EXISTS public.get_user_portfolios_by_email(text);"
sc2, sb2 = run_sql(drop)
print('DROP:', sc2, sb2)

# 3) 重建（SECURITY DEFINER，仅管理员可查，JOIN app_users 按 email 匹配）
create = """
CREATE OR REPLACE FUNCTION public.get_user_portfolios_by_email(p_email text)
RETURNS TABLE(name text, portfolio_data jsonb, is_ai boolean, updated_at timestamptz)
LANGUAGE sql
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT up.name, up.portfolio_data, false AS is_ai, up.updated_at
  FROM public.user_portfolios up
  JOIN public.app_users au ON au.id = up.user_id
  WHERE au.user_email = p_email
    AND auth.email() = '57502460@qq.com'
  ORDER BY up.updated_at DESC;
$$;
"""
sc3, sb3 = run_sql(create)
print('CREATE:', sc3, sb3)

grant = "GRANT EXECUTE ON FUNCTION public.get_user_portfolios_by_email(text) TO anon, authenticated;"
sc4, sb4 = run_sql(grant)
print('GRANT:', sc4, sb4)

# 4) 验证
verify = "SELECT proname, pg_get_function_result(oid) AS ret FROM pg_proc WHERE proname='get_user_portfolios_by_email';"
sc5, sb5 = run_sql(verify)
print('VERIFY:', sc5, sb5)
