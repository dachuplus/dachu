#!/usr/bin/env python3
"""
新评分算法：基于季度滚动评分
- 单季评分 = 收益排名×50% + 回撤排名×25% + 夏普排名×25%
- 多周期 = 对应季度单季评分的均值
- 全市场统一排名（不分类型）
"""

import os, json, requests, math
from itertools import islice

# ── 配置 ─────────────────────────────────────────────────────────────────────
REF = 'tqhtegazxykkqfcpejky'
MGMT = f'https://api.supabase.com/v1/projects/{REF}/database/query'

def mgmt(sql):
    """执行 Supabase Management API 查询"""
    token = os.environ.get('SUPABASE_PAT', '')
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r = requests.post(MGMT, headers=headers, json={'query': sql}, timeout=30)
    data = r.json()
    if isinstance(data, dict) and 'message' in data:
        print(f'  ⚠ SQL错误: {data["message"][:100]}')
        return []
    return data

def percentile_rank(values):
    """计算全市场百分位排名 (0~100)"""
    n = len(values)
    if n == 0:
        return {}
    sorted_vals = sorted(values)
    ranks = {}
    for i, v in enumerate(sorted_vals):
        ranks[v] = (i + 1) / n * 100
    return ranks

print('【Step1】从 fund_quarterly_scores 读取季度数据 ...')
rows = mgmt('SELECT c, quarterly_data FROM fund_quarterly_scores')
print(f'  读取 {len(rows)} 只基金的季度数据')

print('【Step2】计算单季评分（收益50% + 回撤25% + 夏普25%）...')

# 结构: {c: {q_index: score}}
QUARTER_SCORES = {}

for row in rows:
    c = row['c']
    try:
        qd = json.loads(row['quarterly_data']) if isinstance(row['quarterly_data'], str) else row['quarterly_data']
    except:
        continue
    
    q_ret = qd.get('q_ret', [])
    q_dd = qd.get('q_dd', [])
    q_sr = qd.get('q_sr', [])
    
    n = min(len(q_ret), len(q_dd), len(q_sr))
    if n == 0:
        continue
    
    # 计算该基金每个季度的三项指标
    quarters = []
    for i in range(n):
        ret = q_ret[i]  # 季度收益（%）
        dd = q_dd[i]    # 季度最大回撤（%，负数）
        sr = q_sr[i]    # 季度夏普
        
        # 回撤是负数，越小（越负）越差，需要反转
        # 收益和夏普越大越好
        quarters.append({
            'ret': ret if ret is not None else -999,
            'dd': dd if dd is not None else 0,  # 回撤越小越差
            'sr': sr if sr is not None else -999,
        })
    
    QUARTER_SCORES[c] = quarters

print(f'  成功解析 {len(QUARTER_SCORES)} 只基金的季度数据')

print('【Step3】全市场排名，计算单季评分 ...')

# 收集所有基金的季度指标
all_quarters = {}  # {q_index: {c: {ret, dd, sr}}}

for c, quarters in QUARTER_SCORES.items():
    for i, q in enumerate(quarters):
        if i not in all_quarters:
            all_quarters[i] = {}
        all_quarters[i][c] = q

# 对每个季度，计算全市场排名
SINGLE_QUARTER_SCORES = {}  # {c: [score_q0, score_q1, ...]}

for q_idx, funds in all_quarters.items():
    if len(funds) < 10:
        continue
    
    # 收益排名（越大越好）
    ret_values = [q['ret'] for q in funds.values()]
    ret_rank = percentile_rank(ret_values)
    
    # 回撤排名（越小越好，需要反转：用 -dd 排名）
    dd_values = [-q['dd'] for q in funds.values()]  # 反转：回撤越小，-dd越大
    dd_rank = percentile_rank(dd_values)
    
    # 夏普排名（越大越好）
    sr_values = [q['sr'] for q in funds.values()]
    sr_rank = percentile_rank(sr_values)
    
    # 计算单季评分
    for i, (c, q) in enumerate(funds.items()):
        r_key = list(funds.values())[i]['ret']  # 找到对应的排名键
        
    # 重新遍历
    c_list = list(funds.keys())
    ret_list = [funds[c]['ret'] for c in c_list]
    dd_list = [-funds[c]['dd'] for c in c_list]
    sr_list = [funds[c]['sr'] for c in c_list]
    
    # 计算排名
    ret_sorted = sorted(ret_list)
    dd_sorted = sorted(dd_list)
    sr_sorted = sorted(sr_list)
    
    n = len(c_list)
    for j, c in enumerate(c_list):
        # 找到排名（简化：用位置/总数）
        ret_pos = ret_sorted.index(ret_list[j])
        dd_pos = dd_sorted.index(dd_list[j])
        sr_pos = sr_sorted.index(sr_list[j])
        
        ret_pct = ret_pos / n * 100
        dd_pct = dd_pos / n * 100
        sr_pct = sr_pos / n * 100
        
        score = ret_pct * 0.5 + dd_pct * 0.25 + sr_pct * 0.25
        
        if c not in SINGLE_QUARTER_SCORES:
            SINGLE_QUARTER_SCORES[c] = []
        # 补齐前面的季度
        while len(SINGLE_QUARTER_SCORES[c]) < q_idx:
            SINGLE_QUARTER_SCORES[c].append(None)
        SINGLE_QUARTER_SCORES[c].append(score)

print(f'  完成 {len(SINGLE_QUARTER_SCORES)} 只基金单季评分计算')

print('【Step4】计算多周期评分 ...')

# 周期定义：需要多少个季度
PERIOD_QUARTERS = {
    'k3m': 1,   # 3月 = 1季度
    'k6m': 2,   # 6月 = 2季度
    'k1': 4,    # 1年 = 4季度
    'k2': 8,    # 2年 = 8季度
    'k3': 12,   # 3年 = 12季度
    'k5': 20,   # 5年 = 20季度
    'k7': 28,   # 7年 = 28季度
    'k10': 40,  # 10年 = 40季度
}

RESULT = {}  # {c: {k3m: score, k6m: score, ...}}

for c, scores in SINGLE_QUARTER_SCORES.items():
    RESULT[c] = {}
    n_total = len(scores)
    
    for period, q_need in PERIOD_QUARTERS.items():
        if n_total < q_need:
            RESULT[c][period] = None
        else:
            # 取最近 q_need 个季度评分，求均值
            recent = scores[-q_need:]
            recent = [s for s in recent if s is not None]
            if recent:
                RESULT[c][period] = sum(recent) / len(recent)
            else:
                RESULT[c][period] = None

print(f'  完成 {len(RESULT)} 只基金多周期评分')

print('【Step5】写入 fund_combined 表 ...')

# 先删除旧字段，添加新字段
print('  修改表结构...')
mgmt('ALTER TABLE fund_combined DROP COLUMN IF EXISTS k0w')
mgmt('ALTER TABLE fund_combined DROP COLUMN IF EXISTS k1m')
mgmt('ALTER TABLE fund_combined DROP COLUMN IF EXISTS k_all')
mgmt('ALTER TABLE fund_combined ADD COLUMN IF NOT EXISTS k7 NUMERIC')
mgmt('ALTER TABLE fund_combined ADD COLUMN IF NOT EXISTS k10 NUMERIC')

# 批量更新（每批400只）
codes = list(RESULT.keys())
B = 400
for s in range(0, len(codes), B):
    batch = codes[s:s+B]
    sets = []
    for f in ['k3m', 'k6m', 'k1', 'k2', 'k3', 'k5', 'k7', 'k10']:
        wc_parts = []
        for c in batch:
            if f in RESULT[c] and RESULT[c][f] is not None:
                wc_parts.append(f"WHEN '{c}' THEN {RESULT[c][f]}")
        if wc_parts:
            sets.append(f"{f}=CASE c {' '.join(wc_parts)} ELSE {f} END")
    
    if not sets:
        continue
    
    c_list = ','.join([f"'{c}'" for c in batch])
    sql = f"UPDATE fund_combined SET {', '.join(sets)} WHERE c IN ({c_list})"
    mgmt(sql)
    print(f'  已更新 {min(s+B, len(codes))}/{len(codes)} ...')

print('  ✓ 写入完成')

print('【Step6】导出预览 CSV ...')
rows = mgmt('SELECT c, name, t0, t1, k3m, k6m, k1, k2, k3, k5, k7, k10 FROM fund_combined WHERE k1 IS NOT NULL ORDER BY k1 DESC LIMIT 500')

import csv
out = '/Users/maoshanbo/WorkBuddy/20260405093252/allfund/exports/fund_combined_new_scores.csv'
with open(out, 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['基金代码', '基金名称', '一级分类', '二级分类', '3月评分', '6月评分', '1年评分', '2年评分', '3年评分', '5年评分', '7年评分', '10年评分'])
    for row in rows:
        w.writerow([
            row['c'], row['name'], row['t0'], row['t1'],
            row['k3m'], row['k6m'], row['k1'], row['k2'],
            row['k3'], row['k5'], row['k7'], row['k10']
        ])

print(f'  ✓ 已导出: {out}')
print(f'  共 {len(rows)} 行')
