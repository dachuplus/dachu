#!/usr/bin/env python3
"""诊断 fund_scores_staging 当前数据是否通过 promote 校验。"""
import os, json, subprocess, sys

TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or os.environ.get('SUPABASE_PAT')
API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

def pg(sql, timeout=120):
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), '-X', 'POST', API,
         '-H', f'Authorization: Bearer {TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', json.dumps({'query': sql})],
        capture_output=True, text=True, timeout=timeout + 10)
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:200]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        resp = json.loads(t)
    except json.JSONDecodeError:
        raise RuntimeError(f'非JSON: {t[:200]}')
    if isinstance(resp, dict) and resp.get('message'):
        raise RuntimeError(resp['message'][:300])
    return resp

def get_t0(table):
    rows = pg(f"SELECT t0, count(*) AS cnt FROM {table} WHERE t0 IS NOT NULL GROUP BY t0")
    return {r['t0']: r['cnt'] for r in rows}

print('=== 诊断 staging 表现状 ===', flush=True)
try:
    st = pg("SELECT to_regclass('fund_scores_staging') AS t")
    print('staging regclass:', st)
except Exception as e:
    print('ERROR accessing db:', e); sys.exit(1)

sc = get_t0('fund_scores_staging')
stotal = sum(sc.values())
pc_raw = get_t0('fund_scores')
CANON = {'股票型基金': '股票型', '混合型基金': '混合型', '债券型基金': '债券型'}
pc = {}
for t0, c in pc_raw.items():
    if not t0:
        continue
    key = CANON.get(t0, t0)
    if key not in ('指数型', '混合型', '债券型', '股票型', 'FOF', '货币型', 'QDII'):
        continue
    pc[key] = pc.get(key, 0) + c
ptotal = sum(pc.values())

print(f'\n[staging 总数] {stotal}')
print(f'[prod 总数]    {ptotal}')
print(f'[staging分布] {sc}')
print(f'[prod分布]    {pc}')

print('\n--- 逐条校验 ---')
ok = True
def check(cond, msg):
    global ok
    print(('  ✓ ' if cond else '  ✗ FAIL ') + msg)
    ok &= cond

check(stotal >= 19000, f'1. staging>=19000: {stotal}')
for t0, c in pc.items():
    if t0 == '货币型':
        continue
    s = sc.get(t0, 0)
    check(s >= c * 0.95, f'2. [{t0}] staging {s} >= 95% prod {c} ({c*0.95:.0f})')
hb = sc.get('货币型', 0)
check(hb >= 900, f'3. 货币型>=900: {hb}')

kall = pg("SELECT count(*) AS tot, count(k_all) AS s FROM fund_scores_staging")[0]
r = (kall['s']/kall['tot']) if kall['tot'] else 0
check(r >= 0.90, f'4. k_all非空率>90%: {r*100:.1f}% ({kall["s"]}/{kall["tot"]})')

hb2 = pg("SELECT count(*) AS tot, count(k_all) AS s FROM fund_scores_staging WHERE t0='货币型'")[0]
r2 = (hb2['s']/hb2['tot']) if hb2['tot'] else 0
check(hb2['tot']>0 and r2>=0.90, f'5. 货币型k_all非空>90%: {r2*100:.1f}% ({hb2["s"]}/{hb2["tot"]})')

hb3 = pg("SELECT count(*) AS tot, count(r1y) AS s FROM fund_scores_staging WHERE t0='货币型'")[0]
check(hb3['s'] >= hb3['tot']*0.90, f'6. 货币型r1y非空>90%: {hb3["s"]}/{hb3["tot"]}')

g = pg("SELECT score_grade, count(*) AS c FROM fund_scores_staging GROUP BY score_grade")
gm = {x['score_grade']: x['c'] for x in g}
print(f'   [grade分布] {gm}')
check((gm.get('green',0)+gm.get('blue',0)+gm.get('orange',0))>0, f'7. green/blue/orange 均存在')

print('\n=== 结论 ===')
print('PASS ✅ 可切换' if ok else 'FAIL ❌ 拒绝切换')
