#!/usr/bin/env python3
"""放宽 user_permissions 写策略：主管理员 或 已被授予管理员(is_admin=true)的用户均可管理。
读策略保持 SELECT USING true（任意登录用户可读取，避免子查询 RLS 递归）。
"""
import os, requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(ROOT, '.env.local')
pat = None
with open(ENV_PATH) as f:
    for line in f:
        line = line.strip()
        if line.startswith('SUPABASE_PAT='):
            pat = line.split('=', 1)[1].strip()
REF = 'tqhtegazxykkqfcpejky'
URL = f'https://api.supabase.com/v1/projects/{REF}/database/query'
H = {'Authorization': f'Bearer {pat}', 'Content-Type': 'application/json', 'Accept': 'application/json'}

def run(sql):
    r = requests.post(URL, headers=H, json={'query': sql}, timeout=60)
    try:
        return r.status_code, r.json()
    except Exception:
        return r.status_code, r.text

drop = 'DROP POLICY IF EXISTS "user_permissions admin write" ON user_permissions;'
sc, sb = run(drop)
print('DROP:', sc, sb)

create = """
CREATE POLICY "user_permissions admin write" ON user_permissions
  FOR ALL TO public
  USING (
    auth.email() = '57502460@qq.com'
    OR EXISTS (SELECT 1 FROM user_permissions up WHERE up.user_email = auth.email() AND up.is_admin = true)
  )
  WITH CHECK (
    auth.email() = '57502460@qq.com'
    OR EXISTS (SELECT 1 FROM user_permissions up WHERE up.user_email = auth.email() AND up.is_admin = true)
  );
"""
sc2, sb2 = run(create)
print('CREATE:', sc2, sb2)

verify = "SELECT policyname, cmd, qual, with_check FROM pg_policies WHERE tablename='user_permissions';"
sc3, sb3 = run(verify)
print('VERIFY:', sc3, sb3)
