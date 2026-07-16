import requests, json, os
env = {}
with open('.env.local') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k,v = line.split('=',1)
            env[k.strip()] = v.strip()
PAT = env.get('SUPABASE_PAT','')
ANON = env.get('VITE_SUPABASE_ANON_KEY','')
REF = 'tqhtegazxykkqfcpejky'
H = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}
url = f'https://api.supabase.com/v1/projects/{REF}/database/query'
def q(sql):
    r = requests.post(url, headers=H, json={'query': sql}, timeout=15)
    return r.json()

print("="*72)
print("A) fund_scores_meta 行数 + 列")
r = q("SELECT COUNT(*) AS cnt FROM fund_scores_meta;")
print("  count:", r)
r = q("SELECT column_name FROM information_schema.columns WHERE table_name='fund_scores_meta' ORDER BY ordinal_position;")
cols = [c['column_name'] for c in r if isinstance(c,dict)]
print("  columns:", cols)

print("="*72)
print("B) fund_scores 是否有 date / nav_date 列")
r = q("SELECT column_name FROM information_schema.columns WHERE table_name='fund_scores' AND column_name IN ('date','nav_date','update_date');")
print("  date-like cols:", [c['column_name'] for c in r if isinstance(c,dict)])

print("="*72)
print("C) 匿名 REST 取 fund_scores_meta 实际返回")
r = requests.get(f'https://{REF}.supabase.co/rest/v1/fund_scores_meta?select=nav_date,tsq,update_time&order=tsq.desc&limit=3',
                 headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=10)
print(f"  status={r.status_code}")
print(f"  body={r.text[:600]}")

print("="*72)
print("D) 匿名 REST 取 fund_scores date 列")
r = requests.get(f'https://{REF}.supabase.co/rest/v1/fund_scores?select=c,date&limit=1',
                 headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=10)
print(f"  status={r.status_code}")
print(f"  body={r.text[:300]}")
