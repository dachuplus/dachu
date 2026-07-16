#!/usr/bin/env python3
import os, re, sys, requests

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

# 1) 当前 RLS 策略
sc, sb = run("SELECT policyname, cmd, roles, qual, with_check FROM pg_policies WHERE tablename='user_permissions';")
print('RLS policies:', sc)
print(sb)

# 2) 确认表已启用 RLS
sc2, sb2 = run("SELECT relname, relrowsecurity FROM pg_class WHERE relname='user_permissions';")
print('RLS enabled:', sc2, sb2)
