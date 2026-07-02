#!/usr/bin/env python3
"""
新评分算法（纯 Python，无 NumPy 依赖）：
  单季度评分 = 收益排名×50% + 回撤排名×25% + 夏普排名×25%
  多周期评分 = 对应季度单季评分的均值
"""
import os, json, requests, csv, statistics
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────────
SUPABASE_URL  = os.environ.get('VITE_SUPABASE_URL',  'https://tqhtegazxykkqfcpejky.supabase.co')
SUPABASE_ANON = os.environ.get('VITE_SUPABASE_ANON_KEY','')
PAT           = os.environ.get('SUPABASE_PAT', '')
REF           = 'tqhtegazxykkqfcpejky'
MGMT_API      = f'https://api.supabase.com/v1/projects/{REF}/database/query'
mgmt_hdrs    = {'Authorization': f'Bearer {PAT}','Content-Type':'application/json'}

def mgmt(sql):
    r = requests.post(MGMT_API, headers=mgmt_hdrs, json={'query':sql}, timeout=30)
    j = r.json()
    if isinstance(j,dict) and 'message' in j:
        print('  MGMT ERR:', j['message'][:120]); return None
    return j

def rest(params):
    url = f'{SUPABASE_URL}/rest/v1/fund_quarterly_scores'
    hdrs = {'apikey':SUPABASE_ANON,'Authorization':f'Bearer {SUPABASE_ANON}'}
    r = requests.get(url, headers=hdrs, params=params, timeout=30)
    return r.json()

# ── 辅助：百分位排名（越高越好，100=最优）─────────────
def pct_rank(items):
    """items: list of (code, value)]  ->  {code:0~100}"""
    if not items: return {}
    n = len(items)
    if n <= 1: return {c:50.0 for c,_ in items}
    sorted_i = sorted(items, key=lambda x:-x[1])  # 降序
    return {c: round((n-1-i)/(n-1)*100,2) for i,(c,_) in enumerate(sorted_i)}

# ════════════════════════════════════════════════════
# Step1: 拉取 fund_quarterly_scores 全部数据
# ════════════════════════════════════════════════════
print('【Step1】拉取 fund_quarterly_scores ...')
all_rows, offset, BATCH = [], 0, 1000
while True:
    rows = rest({'select':'c,quarterly_data', 'offset':f'{offset}','limit':f'{BATCH}'})
    if not rows: break
    all_rows.extend(rows); offset += len(rows)
    print(f'  已拉取 {len(all_rows)} 条...')
    if len(rows) < BATCH: break
print(f'  ✓ 共 {len(all_rows)} 条')

# ════════════════════════════════════════════════════
# Step2: 解析 + 按季度整理
# ════════════════════════════════════════════════════
fund_data = {}
for row in all_rows:
    c  = row['c']
    qd = row['quarterly_data']
    if isinstance(qd, str): qd = json.loads(qd)
    fund_data[c] = qd
print(f'【Step2】解析完成，{len(fund_data)} 只基金')

max_q_n = max(d.get('q_n',0) for d in fund_data.values())
print(f'  最大季度数: {max_q_n}')

# quarter_data[i] = {ret:{c:v}, dd:{c:v}, sr:{c:v}}
qdata = defaultdict(lambda:{'ret':{},'dd':{},'sr':{}})
for c,qd in fund_data.items():
    qn = qd.get('q_n',0)
    for i in range(qn):
        if 'q_ret' in qd and i<len(qd['q_ret']) and qd['q_ret'][i] is not None:
            qdata[i]['ret'][c] = qd['q_ret'][i]
        if 'q_dd'  in qd and i<len(qd['q_dd'])  and qd['q_dd'][i]  is not None:
            qdata[i]['dd'][c]  = -qd['q_dd'][i]   # 转正数，越高越好
        if 'q_sr'  in qd and i<len(qd['q_sr'])  and qd['q_sr'][i]  is not None:
            qdata[i]['sr'][c]  = qd['q_sr'][i]

# ════════════════════════════════════════════════════
# Step3: 逐季度排名 → 单季评分
# ════════════════════════════════════════════════════
print('【Step3】逐季度排名，计算单季评分...')
single_q = defaultdict(dict)   # c -> {i: score}

for i in range(max_q_n):
    if i not in qdata: continue
    ret_r = pct_rank(list(qdata[i]['ret'].items()))
    dd_r  = pct_rank(list(qdata[i]['dd'].items()))
    sr_r  = pct_rank(list(qdata[i]['sr'].items()))
    common = set(ret_r) & set(dd_r) & set(sr_r)
    for c in common:
        single_q[c][i] = round(ret_r[c]*0.5 + dd_r[c]*0.25 + sr_r[c]*0.25, 4)
    if i % 5 == 0:
        print(f'  季度 {i}/{max_q_n-1} 完成，{len(common)} 只有效')

# ════════════════════════════════════════════════════
# Step4: 多周期评分
# ════════════════════════════════════════════════════
print('【Step4】计算多周期评分...')
RESULT = {}
for c,qd in fund_data.items():
    qn = qd.get('q_n',0)
    sc = {}
    def mean(c, a, b):
        idx = [i for i in range(max(0,a),b) if i in single_q.get(c,{})]
        return round(statistics.mean([single_q[c][i] for i in idx]),4) if idx else None
    for fname,need,slab in [('k3m',1,1),('k6m',2,2),('k1',4,4),
                                 ('k2',8,8),('k3',12,12),('k5',20,20),
                                 ('k7',28,28),('k10',40,40)]:
        if qn >= need:
            v = mean(c, qn-slab, qn)
            if v is not None: sc[fname] = v
    if sc: RESULT[c] = sc
print(f'  ✓ {len(RESULT)} 只基金有评分')

# ── 预览 ────────────────────────────────────────────────
print('\n【预览】前5只:')
for c in list(RESULT)[:5]: print(f'  {c}: {RESULT[c]}')

# ════════════════════════════════════════════════════
# Step5: 分批 UPDATE fund_combined
# ════════════════════════════════════════════════════
print('\n【Step5】写入 fund_combined ...')
codes = list(RESULT)
B = 400
for s in range(0, len(codes), B):
    batch = codes[s:s+B]
    sets = []
    for f in ['k3m','k6m','k1','k2','k3','k5','k7','k10']:
        wc = [f"WHEN '{c}' THEN {RESULT[c][f]}" for c in batch if f in RESULT[c]]
        if wc:
            sets.append(f"{f}=CASE c {' '.join(wc)} ELSE {f} END")
    if not sets: continue
    sql = (f"UPDATE fund_combined SET {','.join(sets)} "
           f"WHERE c IN ({','.join([f\"'{c}'\" for c in batch])})")
    mgmt(sql)
    print(f'  已更新 {min(s+B,len(codes))}/{len(codes)} ...')
print('  ✓ 写入完成')

# ════════════════════════════════════════════════════
# Step6: 导出 CSV 预览（Top500 按 k1 降序）
# ════════════════════════════════════════════════════
print('\n【Step6】导出预览 CSV ...')
rows = mgmt(
    "SELECT c,name,t0,t1,k3m,k6m,k1,k2,k3,k5,k7,k10 "
    "FROM fund_combined WHERE k1 IS NOT NULL "
    "ORDER BY k1 DESC LIMIT 500"
)
if rows:
    PATH = '/Users/maoshanbo/WorkBuddy/20260405093252/allfund/exports/fund_combined_new_scores.csv'
    with open(PATH,'w',newline='',encoding='utf-8-sig') as f:
        csv.DictWriter(f, fieldnames=rows[0].keys()).writeheader()
        csv.DictWriter(f, fieldnames=rows[0].keys()).writerows(rows)
    print(f'  ✓ 已保存: {PATH}')
    # 同时打印前10预览
    print('\n  Top10 按 k1 降序:')
    for r in rows[:10]:
        print(f"    {r['c']} {r['name']}: k3m={r.get('k3m')} k1={r.get('k1')} k3={r.get('k3')}")
else:
    print('  ✗ 导出失败：无法读取 fund_combined')
