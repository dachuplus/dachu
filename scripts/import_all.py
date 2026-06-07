#!/usr/bin/env python3
"""合并风险指标 + 重新计算靠谱分 v5 + 导入 Supabase（使用 curl + subprocess）"""
import json, time, subprocess, os, sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN（Supabase Personal Access Token）')
PROJECT_REF = 'tqhtegazxykkqfcpejky'
MGMT_API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'

def pg_query(sql):
    """通过 Supabase Management API 执行 SQL（curl + subprocess）"""
    payload = json.dumps({'query': sql})
    result = subprocess.run(
        ['curl', '-s', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        raise Exception(f'curl failed: {result.stderr[:100]}')
    text = result.stdout.strip()
    if not text:
        return []
    resp = json.loads(text)
    if isinstance(resp, dict) and resp.get('message'):
        raise Exception(resp['message'][:200])
    return resp

def esc(s):
    if s is None:
        return "''"
    return "'" + str(s).replace("'", "''") + "'"

def esc_null(v):
    if v is None:
        return 'NULL'
    try:
        f = float(v)
        if f == 0:
            return 'NULL'
        return str(f)
    except:
        return 'NULL'

def load_ndjson(filepath):
    data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                data.append(json.loads(line))
    return data

print('=' * 60)
print('合并风险指标 + 靠谱分 v5 + 导入 Supabase', flush=True)
print('=' * 60, flush=True)

# 1. 加载基金数据
print('\n[1] 加载基金数据...', flush=True)
funds = load_ndjson(os.path.join(SCRIPT_DIR, 'funds_output.ndjson'))
print(f'  基金数据: {len(funds)}条', flush=True)

# 2. 加载风险指标
risk_path = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')
risk_data = []
if os.path.exists(risk_path):
    risk_data = load_ndjson(risk_path)
    print(f'  风险指标: {len(risk_data)}条', flush=True)
else:
    print('  风险指标文件不存在', flush=True)

# 3. 合并风险指标
if risk_data:
    print('\n[2] 合并风险指标...', flush=True)
    risk_map = {}
    for r in risk_data:
        code = r.get('c', '')
        if code:
            risk_map[code] = r
    merged = 0
    for fund in funds:
        code = fund.get('c', '')
        if code in risk_map:
            r = risk_map[code]
            fund['dd1y'] = r.get('dd1y')
            fund['dd2y'] = r.get('dd2y')
            fund['dd3y'] = r.get('dd3y')
            fund['dd5y'] = r.get('dd5y')
            fund['sr1y'] = r.get('sr1y')
            fund['sr2y'] = r.get('sr2y')
            fund['sr3y'] = r.get('sr3y')
            fund['sr5y'] = r.get('sr5y')
            merged += 1
    print(f'  合并风险指标: {merged}/{len(funds)}只', flush=True)

# 4. 重新计算靠谱分 v5
print('\n[3] 重新计算靠谱指数 v5...', flush=True)
W_RET, W_DD, W_SR = 0.60, 0.30, 0.10
periods = [
    {'k': 'k0w', 'r': 'r0w', 'dd': None, 'sr': None},
    {'k': 'k1m', 'r': 'r1m', 'dd': None, 'sr': None},
    {'k': 'k3m', 'r': 'r3m', 'dd': None, 'sr': None},
    {'k': 'k6m', 'r': 'r6m', 'dd': None, 'sr': None},
    {'k': 'k1',  'r': 'r1y', 'dd': 'dd1y', 'sr': 'sr1y'},
    {'k': 'k2',  'r': 'r2y', 'dd': 'dd2y', 'sr': 'sr2y'},
    {'k': 'k3',  'r': 'r3y', 'dd': 'dd3y', 'sr': 'sr3y'},
    {'k': 'k5',  'r': 'r5y', 'dd': 'dd5y', 'sr': 'sr5y'},
]

for period in periods:
    pk = period['k']
    rk = period['r']
    dk = period['dd']
    sk = period['sr']
    valid = [(i, funds[i]) for i in range(len(funds))]
    valid_n = len(valid)
    
    ret_ranked = sorted(valid, key=lambda x: x[1].get(rk, 0) or 0, reverse=True)
    ret_pct = {}
    for rank, (idx, _) in enumerate(ret_ranked):
        ret_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else 50.0
    
    dd_pct = {}
    if dk:
        dd_ranked = sorted(valid, key=lambda x: x[1].get(dk, -999) or -999, reverse=True)
        for rank, (idx, fund) in enumerate(dd_ranked):
            val = fund.get(dk)
            dd_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else (50.0 if val is not None else None)
    
    sr_pct = {}
    if sk:
        sr_ranked = sorted(valid, key=lambda x: x[1].get(sk, -999) or -999, reverse=True)
        for rank, (idx, fund) in enumerate(sr_ranked):
            val = fund.get(sk)
            sr_pct[idx] = (1 - rank / (valid_n - 1)) * 100 if valid_n > 1 else (50.0 if val is not None else None)
    
    for idx, fund in valid:
        rp = ret_pct.get(idx)
        dp = dd_pct.get(idx) if dk else None
        sp = sr_pct.get(idx) if sk else None
        if dp is not None and sp is not None:
            score = round(W_RET * rp + W_DD * dp + W_SR * sp, 4)
        else:
            score = round(rp, 4)
        if score is not None:
            fund[pk] = score

scored = sum(1 for r in funds if r.get('k3', 0) > 0)
print(f'  有靠谱分的基金: {scored}/{len(funds)}只', flush=True)

# 5. 清空旧数据
print('\n[4] 清空 fund_scores 旧数据...', flush=True)
try:
    pg_query('TRUNCATE TABLE fund_scores')
    print('  已清空', flush=True)
except Exception as e:
    print(f'  清空失败: {e}', flush=True)

# 6. 导入
print(f'\n[5] 导入 {len(funds)} 条到 Supabase...', flush=True)
BATCH = 80
imported = 0
cols = 'c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y'

for i in range(0, len(funds), BATCH):
    batch = funds[i:i+BATCH]
    values = []
    for r in batch:
        vals = [
            esc(r.get('c', '')),
            esc(r.get('n', '')),
            esc(r.get('t0', '')),
            esc(r.get('t1', '')),
            esc(r.get('t2', '')),
            esc(r.get('t6', '')),
            r.get('a', 0) or 0,
            esc_null(r.get('hp')),
            esc_null(r.get('ytd')),
            esc_null(r.get('r0w')),
            esc_null(r.get('r1m')),
            esc_null(r.get('r3m')),
            esc_null(r.get('r6m')),
            esc_null(r.get('r1y')),
            esc_null(r.get('r2y')),
            esc_null(r.get('r3y')),
            esc_null(r.get('r5y')),
            esc_null(r.get('nav')),
            esc(r.get('date', '')),
            esc_null(r.get('k0w')),
            esc_null(r.get('k1m')),
            esc_null(r.get('k3m')),
            esc_null(r.get('k6m')),
            esc_null(r.get('k1')),
            esc_null(r.get('k2')),
            esc_null(r.get('k3')),
            esc_null(r.get('k5')),
            esc_null(r.get('k7')),
            esc_null(r.get('k10')),
            esc_null(r.get('dd1y')),
            esc_null(r.get('dd2y')),
            esc_null(r.get('dd3y')),
            esc_null(r.get('dd5y')),
            esc_null(r.get('sr1y')),
            esc_null(r.get('sr2y')),
            esc_null(r.get('sr3y')),
            esc_null(r.get('sr5y')),
        ]
        values.append('(' + ','.join(str(v) for v in vals) + ')')
    
    sql = f'INSERT INTO fund_scores ({cols}) VALUES\n' + ',\n'.join(values)
    try:
        pg_query(sql)
        imported += len(batch)
        if (i // BATCH) % 20 == 0:
            print(f'  [{i}-{i+len(batch)}] +{len(batch)} (累计{imported})', flush=True)
    except Exception as e:
        print(f'  [{i}-{i+len(batch)}] 错误: {str(e)[:150]}', flush=True)
    
    time.sleep(0.05)

print(f'\n  导入完成: {imported}/{len(funds)}', flush=True)

# 7. 写入 meta
print('\n[6] 写入 fund_scores_meta...', flush=True)
nav_date = funds[0].get('date', '') if funds else ''
try:
    pg_query('TRUNCATE TABLE fund_scores_meta')
    pg_query(
        f"INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) "
        f"VALUES (NOW()::text, {len(funds)}, {scored}, '{nav_date}')"
    )
    print(f'  meta: total={len(funds)}, scored={scored}, date={nav_date}', flush=True)
except Exception as e:
    print(f'  meta写入失败: {e}', flush=True)

# 8. 验证
print('\n[7] 验证...', flush=True)
result = pg_query("SELECT count(*) as cnt FROM fund_scores")
print(f'  fund_scores: {result[0]["cnt"]} 条', flush=True)

stats = pg_query(
    "SELECT t0, count(*) as cnt, count(k3) as scored "
    "FROM fund_scores GROUP BY t0 ORDER BY cnt DESC"
)
print('\n  分类统计:', flush=True)
for s in stats:
    print(f'    {s["t0"]}: {s["cnt"]}只, 有靠谱分{s["scored"]}只', flush=True)

print('\nDone!', flush=True)
