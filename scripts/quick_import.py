#!/usr/bin/env python3
"""快速导入 fund_scores（直接用 requests）"""
import json, time, os, sys

# 用 urllib 替代 requests 避免 SSL 问题
import urllib.request
import urllib.error

MGMT_TOKEN = 'TOKEN_REMOVED'
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def pg_query(sql):
    data = json.dumps({'query': sql}).encode('utf-8')
    req = urllib.request.Request(MGMT_API, data=data, method='POST')
    req.add_header('Authorization', f'Bearer {MGMT_TOKEN}')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode('utf-8')
            if not body.strip():
                return []
            result = json.loads(body)
            if isinstance(result, dict) and result.get('message'):
                raise Exception(result['message'][:200])
            return result
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        raise Exception(f'HTTP {e.code}: {body[:200]}')

def esc(s):
    if s is None: return "''"
    return "'" + str(s).replace("'", "''") + "'"

def esc_null(v):
    if v is None: return 'NULL'
    try:
        f = float(v)
        return 'NULL' if f == 0 else str(f)
    except:
        return 'NULL'

def load_ndjson(filepath):
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line: data.append(json.loads(line))
    return data

print('Loading funds...', flush=True)
funds = load_ndjson(os.path.join(SCRIPT_DIR, 'funds_output.ndjson'))
print(f'Funds: {len(funds)}', flush=True)

print('Loading risk...', flush=True)
risk_path = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')
if os.path.exists(risk_path):
    risk_data = load_ndjson(risk_path)
    print(f'Risk: {len(risk_data)}', flush=True)
    risk_map = {r.get('c',''): r for r in risk_data if r.get('c')}
    merged = 0
    for fund in funds:
        code = fund.get('c', '')
        if code in risk_map:
            r = risk_map[code]
            for k in ['dd1y','dd2y','dd3y','dd5y','sr1y','sr2y','sr3y','sr5y']:
                fund[k] = r.get(k)
            merged += 1
    print(f'Merged: {merged}', flush=True)

# Recalc scores
print('Recalculating scores v5...', flush=True)
W_RET, W_DD, W_SR = 0.60, 0.30, 0.10
periods = [
    ('k0w','r0w',None,None), ('k1m','r1m',None,None), ('k3m','r3m',None,None), ('k6m','r6m',None,None),
    ('k1','r1y','dd1y','sr1y'), ('k2','r2y','dd2y','sr2y'), ('k3','r3y','dd3y','sr3y'), ('k5','r5y','dd5y','sr5y'),
]
for pk, rk, dk, sk in periods:
    valid = [(i, funds[i]) for i in range(len(funds))]
    vn = len(valid)
    ret_ranked = sorted(valid, key=lambda x: x[1].get(rk, 0) or 0, reverse=True)
    ret_pct = {idx: (1 - rank / (vn - 1)) * 100 if vn > 1 else 50.0 for rank, (idx, _) in enumerate(ret_ranked)}
    dd_pct, sr_pct = {}, {}
    if dk:
        dd_ranked = sorted(valid, key=lambda x: x[1].get(dk, -999) or -999, reverse=True)
        dd_pct = {idx: (1 - rank / (vn - 1)) * 100 if vn > 1 else (50.0 if fund.get(dk) is not None else None)
                  for rank, (idx, fund) in enumerate(dd_ranked)}
    if sk:
        sr_ranked = sorted(valid, key=lambda x: x[1].get(sk, -999) or -999, reverse=True)
        sr_pct = {idx: (1 - rank / (vn - 1)) * 100 if vn > 1 else (50.0 if fund.get(sk) is not None else None)
                  for rank, (idx, fund) in enumerate(sr_ranked)}
    for idx, fund in valid:
        rp = ret_pct.get(idx)
        dp = dd_pct.get(idx) if dk else None
        sp = sr_pct.get(idx) if sk else None
        fund[pk] = round(W_RET * rp + W_DD * dp + W_SR * sp, 4) if (dp is not None and sp is not None) else round(rp, 4)

scored = sum(1 for r in funds if r.get('k3', 0) > 0)
print(f'Scored: {scored}', flush=True)

# Truncate
print('Truncating...', flush=True)
pg_query('TRUNCATE TABLE fund_scores')
print('Truncated', flush=True)

# Import
print(f'Importing {len(funds)} funds...', flush=True)
BATCH = 100
imported = 0
cols = 'c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y'

for i in range(0, len(funds), BATCH):
    batch = funds[i:i+BATCH]
    values = []
    for r in batch:
        vals = [
            esc(r.get('c','')), esc(r.get('n','')), esc(r.get('t0','')), esc(r.get('t1','')), esc(r.get('t2','')),
            esc(r.get('t6','')), r.get('a',0) or 0, esc_null(r.get('hp')),
            esc_null(r.get('ytd')), esc_null(r.get('r0w')), esc_null(r.get('r1m')), esc_null(r.get('r3m')),
            esc_null(r.get('r6m')), esc_null(r.get('r1y')), esc_null(r.get('r2y')), esc_null(r.get('r3y')),
            esc_null(r.get('r5y')), esc_null(r.get('nav')), esc(r.get('date','')),
            esc_null(r.get('k0w')), esc_null(r.get('k1m')), esc_null(r.get('k3m')), esc_null(r.get('k6m')),
            esc_null(r.get('k1')), esc_null(r.get('k2')), esc_null(r.get('k3')), esc_null(r.get('k5')),
            esc_null(r.get('k7')), esc_null(r.get('k10')),
            esc_null(r.get('dd1y')), esc_null(r.get('dd2y')), esc_null(r.get('dd3y')), esc_null(r.get('dd5y')),
            esc_null(r.get('sr1y')), esc_null(r.get('sr2y')), esc_null(r.get('sr3y')), esc_null(r.get('sr5y')),
        ]
        values.append('(' + ','.join(str(v) for v in vals) + ')')
    
    sql = f'INSERT INTO fund_scores ({cols}) VALUES\n' + ',\n'.join(values)
    try:
        pg_query(sql)
        imported += len(batch)
        if (i // BATCH) % 20 == 0:
            print(f'  [{i}-{i+len(batch)}] {imported}/{len(funds)}', flush=True)
    except Exception as e:
        print(f'  [{i}-{i+len(batch)}] ERROR: {str(e)[:150]}', flush=True)
    time.sleep(0.1)

print(f'Import done: {imported}', flush=True)

# Meta
nav_date = funds[0].get('date', '') if funds else ''
pg_query('TRUNCATE TABLE fund_scores_meta')
pg_query(f"INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) VALUES (NOW()::text, {len(funds)}, {scored}, '{nav_date}')")
print(f'Meta: total={len(funds)}, scored={scored}, date={nav_date}', flush=True)

# Verify
result = pg_query("SELECT count(*) as cnt FROM fund_scores")
print(f'Verification: {result[0]["cnt"]} rows', flush=True)
print('Done!', flush=True)
