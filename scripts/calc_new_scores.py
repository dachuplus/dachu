#!/usr/bin/env python3
"""
新评分算法：
  单季度评分 = 收益排名×50% + 回撤排名×25% + 夏普排名×25%
  多周期评分 = 对应季度单季评分的均值
  k3m  = 最近1个季度均值
  k6m  = 最近2个季度均值
  k1   = 最近4个季度均值
  k2   = 最近8个季度均值
  k3   = 最近12个季度均值
  k5   = 最近20个季度均值
  k7   = 最近28个季度均值
  k10  = 最近40个季度均值
  全市场统一排名（不分类型）
"""

import os, json, requests, numpy as np
from collections import defaultdict

# ── 配置 ──────────────────────────────────────────
SUPABASE_URL   = os.environ.get('VITE_SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
SUPABASE_ANON  = os.environ.get('VITE_SUPABASE_ANON_KEY', '')
PAT            = os.environ.get('SUPABASE_PAT', '')
REF            = 'tqhtegazxykkqfcpejky'
MGMT_API       = f'https://api.supabase.com/v1/projects/{REF}/database/query'

mgmt_headers = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}

def mgmt_query(sql):
    r = requests.post(MGMT_API, headers=mgmt_headers, json={'query': sql})
    return r.json()

# ── Step1: 从 fund_quarterly_scores 拉取全部季度数据 ──
print('【Step1】拉取 fund_quarterly_scores 数据...')
rest_url = f'{SUPABASE_URL}/rest/v1/fund_quarterly_scores'
rest_headers = {'apikey': SUPABASE_ANON, 'Authorization': f'Bearer {SUPABASE_ANON}'}

all_rows = []
offset = 0
batch = 1000
while True:
    params = {'select': 'c,quarterly_data', 'offset': f'{offset}', 'limit': f'{batch}'}
    r = requests.get(rest_url, headers=rest_headers, params=params, timeout=30)
    rows = r.json()
    if not rows:
        break
    all_rows.extend(rows)
    offset += len(rows)
    print(f'  已拉取 {len(all_rows)} 条...')
    if len(rows) < batch:
        break

print(f'  共 {len(all_rows)} 条季度数据')

# ── Step2: 解析并整理为 {基金: {q_n, q_ret[], q_dd[], q_sr[]}} ──
fund_data = {}
for row in all_rows:
    c  = row['c']
    qd = row['quarterly_data']
    if isinstance(qd, str):
        qd = json.loads(qd)
    fund_data[c] = qd

print(f'  解析完成，{len(fund_data)} 只基金')

# ── Step3: 按季度整理数据，用于排名 ──
# quarter_data[i] = {'ret':{c:v}, 'dd':{c:v}, 'sr':{c:v}}
print('【Step2】按季度整理数据...')
max_q_n = max(d.get('q_n', 0) for d in fund_data.values())
print(f'  最大季度数: {max_q_n}')

quarter_data = defaultdict(lambda: {'ret': {}, 'dd': {}, 'sr': {}})
for c, qd in fund_data.items():
    q_n = qd.get('q_n', 0)
    for i in range(q_n):
        if 'q_ret' in qd and i < len(qd['q_ret']) and qd['q_ret'][i] is not None:
            quarter_data[i]['ret'][c] = qd['q_ret'][i]
        if 'q_dd' in qd and i < len(qd['q_dd']) and qd['q_dd'][i] is not None:
            # q_dd 是负数（如 -0.05 表示回撤5%），越小越差
            # 转成正数方便排名：用 -q_dd（越大越好）
            quarter_data[i]['dd'][c] = -qd['q_dd'][i]
        if 'q_sr' in qd and i < len(qd['q_sr']) and qd['q_sr'][i] is not None:
            quarter_data[i]['sr'][c] = qd['q_sr'][i]

# ── Step4: 逐季度排名，计算单季评分 ──
print('【Step3】逐季度排名并计算单季评分...')
# single_q[c][i] = 第i季度（从老到新）的单季评分
single_q = defaultdict(dict)

for i in range(max_q_n):
    if i not in quarter_data:
        continue

    # --- 收益排名 (越高越好) ---
    ret_items = list(quarter_data[i]['ret'].items())
    if not ret_items:
        continue
    ret_codes = [x[0] for x in ret_items]
    ret_vals  = np.array([x[1] for x in ret_items])
    # argsort 降序：-ret_vals
    ret_order = np.argsort(-ret_vals)
    n = len(ret_vals)
    ret_rank = np.zeros(n)
    ret_rank[ret_order] = np.linspace(100, 0, n)  # 最高100分，最低0分
    ret_rank_dict = dict(zip(ret_codes, ret_rank))

    # --- 回撤排名 (dd已转成正数，越高越好) ---
    dd_items = list(quarter_data[i]['dd'].items())
    if not dd_items:
        continue
    dd_codes = [x[0] for x in dd_items]
    dd_vals  = np.array([x[1] for x in dd_items])
    dd_order = np.argsort(-dd_vals)
    n = len(dd_vals)
    dd_rank = np.zeros(n)
    dd_rank[dd_order] = np.linspace(100, 0, n)
    dd_rank_dict = dict(zip(dd_codes, dd_rank))

    # --- 夏普排名 (越高越好) ---
    sr_items = list(quarter_data[i]['sr'].items())
    if not sr_items:
        continue
    sr_codes = [x[0] for x in sr_items]
    sr_vals  = np.array([x[1] for x in sr_items])
    sr_order = np.argsort(-sr_vals)
    n = len(sr_vals)
    sr_rank = np.zeros(n)
    sr_rank[sr_order] = np.linspace(100, 0, n)
    sr_rank_dict = dict(zip(sr_codes, sr_rank))

    # --- 单季评分 = ret*50% + dd*25% + sr*25% ---
    all_codes = set(ret_rank_dict) & set(dd_rank_dict) & set(sr_rank_dict)
    for c in all_codes:
        score = ret_rank_dict[c]*0.5 + dd_rank_dict[c]*0.25 + sr_rank_dict[c]*0.25
        single_q[c][i] = round(score, 4)

    if i % 5 == 0:
        print(f'  季度 {i}/{max_q_n-1} 完成，{len(all_codes)} 只基金有完整排名')

# ── Step5: 计算多周期评分 ──
print('【Step4】计算多周期评分...')
RESULT = {}  # c -> {k3m, k6m, k1, k2, k3, k5, k7, k10}

for c, qd in fund_data.items():
    q_n = qd.get('q_n', 0)
    scores = {}

    def mean_scores(c, start_idx, end_idx):
        idxs = [i for i in range(max(0, start_idx), end_idx) if i in single_q.get(c, {})]
        if not idxs:
            return None
        return round(np.mean([single_q[c][i] for i in idxs]), 4)

    # k3m: 最近1个季度
    if q_n >= 1:
        v = mean_scores(c, q_n-1, q_n)
        if v is not None:
            scores['k3m'] = v

    # k6m: 最近2个季度
    if q_n >= 2:
        v = mean_scores(c, q_n-2, q_n)
        if v is not None:
            scores['k6m'] = v

    # k1: 最近4个季度
    if q_n >= 4:
        v = mean_scores(c, q_n-4, q_n)
        if v is not None:
            scores['k1'] = v

    # k2: 最近8个季度
    if q_n >= 8:
        v = mean_scores(c, q_n-8, q_n)
        if v is not None:
            scores['k2'] = v

    # k3: 最近12个季度
    if q_n >= 12:
        v = mean_scores(c, q_n-12, q_n)
        if v is not None:
            scores['k3'] = v

    # k5: 最近20个季度
    if q_n >= 20:
        v = mean_scores(c, q_n-20, q_n)
        if v is not None:
            scores['k5'] = v

    # k7: 最近28个季度
    if q_n >= 28:
        v = mean_scores(c, q_n-28, q_n)
        if v is not None:
            scores['k7'] = v

    # k10: 最近40个季度
    if q_n >= 40:
        v = mean_scores(c, q_n-40, q_n)
        if v is not None:
            scores['k10'] = v

    if scores:
        RESULT[c] = scores

print(f'  计算完成，{len(RESULT)} 只基金有评分')

# ── Step6: 预览 ────────────────────────────────────
print('\n【预览】随机5只基金评分:')
sample_codes = list(RESULT.keys())[:5]
for c in sample_codes:
    print(f'  {c}: {RESULT[c]}')

# ── Step7: 写入 fund_combined ─────────────────────
print('\n【Step5】写入 fund_combined...')

# 分批 UPDATE（每批500）
codes_list = list(RESULT.keys())
batch_size = 500
updated = 0

for start in range(0, len(codes_list), batch_size):
    batch_codes = codes_list[start:start+batch_size]
    # 构造 CASE 语句批量更新
    sets = []
    for field in ['k3m','k6m','k1','k2','k3','k5','k7','k10']:
        when_clauses = []
        for c in batch_codes:
            if field in RESULT[c]:
                when_clauses.append(f"WHEN '{c}' THEN {RESULT[c][field]}")
        if when_clauses:
            sets.append(f'{field} = CASE c {" ".join(when_clauses)} ELSE {field} END')

    if not sets:
        continue

    sql = f"""
    UPDATE fund_combined SET
        {', '.join(sets)}
    WHERE c IN ({','.join([f"'{c}'" for c in batch_codes])})
    """
    r = mgmt_query(sql)
    updated += len(batch_codes)
    print(f'  已更新 {updated}/{len(codes_list)}...')

print(f'\n✅ 全部完成！共更新 {len(RESULT)} 只基金')

# ── Step8: 导出 Excel 预览 ───────────────────────
print('\n【Step6】导出 Excel 预览...')
try:
    import pandas as pd
    # 从 DB 拉取最新 fund_combined 预览
    preview_codes = codes_list[:500]  # 先导出500只预览
    rows = mgmt_query(
        f"SELECT c, name, t0, t1, k3m, k6m, k1, k2, k3, k5, k7, k10 "
        f"FROM fund_combined WHERE c IN ({','.join([f"'{c}'" for c in preview_codes])}) "
        f"ORDER BY k1 DESC NULLS LAST LIMIT 500"
    )
    df = pd.DataFrame(rows)
    df.to_excel('/Users/maoshanbo/WorkBuddy/20260405093252/allfund/exports/fund_combined_new_scores.xlsx', index=False)
    print('  Excel 已保存到 exports/fund_combined_new_scores.xlsx')
except Exception as e:
    print(f'  导出 Excel 失败: {e}')
