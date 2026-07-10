#!/usr/bin/env python3
"""
重算 fund_scores 的 k1/k2/k3/k5（及刷新 k_all），修正此前
calc_new_scores_pure.py 的"自成立第N季度"索引 bug。

新算法（与数据中心页文档一致，V7）：
  对每个周期 p ∈ {1y,2y,3y,5y}，取该周期的阶段收益(r_p)、最大回撤(dd_p)、
  夏普(sr_p) 三个字段（均来自 fund_scores，为日历对齐的真实近N年指标）；
  各自在全市场做百分位排名(0~100，越高越好)，再加权：
      k_p = 50% × ret_pct + 25% × dd_pct + 25% × sr_pct
  最后 k_all = (k0w×5 + k1m×5 + k3m×10 + k6m×15 + k1×20 + k2×20 + k3×15 + k5×10)
             按"仅对非空分量加权、权重重新归一化"合成。

仅当某基金该周期的 r/dd/sr 三者均非空时才覆盖其 k_p；否则保留原值，
避免把有旧分但缺新字段的基金置空。k_all 对所有行重算。

用法：
  SUPABASE_MGMT_TOKEN=<PAT> SUPABASE_PAT=<PAT> python3 recompute_k_scores_v7.py
"""
import os, json, bisect, requests, sys
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(SCRIPT_DIR)

# ---- 读取 .env.local ----
ENV = {}
try:
    with open(os.path.join(ROOT, '.env.local')) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            k, v = line.split('=', 1)
            ENV[k.strip()] = v.strip()
except FileNotFoundError:
    pass

SUPABASE_URL = ENV.get('VITE_SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON = ENV.get('VITE_SUPABASE_ANON_KEY', '')
PAT = os.environ.get('SUPABASE_PAT') or ENV.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN') or ''
REF = 'tqhtegazxykkqfcpejky'
MGMT = f'https://api.supabase.com/v1/projects/{REF}/database/query'
mgmt_hdrs = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}
rest_hdrs = {'apikey': ANON, 'Authorization': f'Bearer {ANON}'}

# k_all 权重（与文档一致）
KALL_W = [('k0w',5),('k1m',5),('k3m',10),('k6m',15),('k1',20),('k2',20),('k3',15),('k5',10)]
# 长周期： (目标列, ret列, dd列, sr列)
PERIODS = [
    ('k1','r1y','dd1y','sr1y'),
    ('k2','r2y','dd2y','sr2y'),
    ('k3','r3y','dd3y','sr3y'),
    ('k5','r5y','dd5y','sr5y'),
]
FETCH_COLS = ['c','k0w','k1m','k3m','k6m','k1','k2','k3','k5','k_all'] \
             + [c for p in PERIODS for c in (p[1],p[2],p[3])]


def mgmt(sql):
    r = requests.post(MGMT, headers=mgmt_hdrs, json={'query': sql}, timeout=60)
    if r.status_code >= 400:
        print('  MGMT ERR:', r.status_code, r.text[:300]); return None
    return r.json()


def pct_rank_map(vals):
    """vals: list[float]; 返回 {v: 0~100 百分位(越高越大)}，用 bisect 加速。"""
    uniq = sorted(set(vals))
    n = len(uniq)
    if n <= 1:
        return {v: 50.0 for v in vals}
    rank = {}
    for i, v in enumerate(uniq):
        rank[v] = round(i / (n - 1) * 100, 2)
    return rank


def backup(rows):
    path = os.path.join(ROOT, 'exports', 'k_scores_backup_before_recompute.json')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump([{k: r.get(k) for k in ['c','k0w','k1m','k3m','k6m','k1','k2','k3','k5','k_all']} for r in rows], f, ensure_ascii=False)
    print(f'  备份 {len(rows)} 行 → {path}')


def fetch_all():
    print('【拉取 fund_scores 全量】')
    rows, off = [], 0
    while True:
        r = requests.get(f'{SUPABASE_URL}/rest/v1/fund_scores',
                         params={'select': ','.join(FETCH_COLS), 'offset': off, 'limit': 1000},
                         headers=rest_hdrs, timeout=30)
        if not r.ok or not r.json():
            break
        rows.extend(r.json())
        off += len(r.json())
        if len(r.json()) < 1000:
            break
    print(f'  共 {len(rows)} 行')
    return rows


def compute(rows):
    print('【计算新 k1/k2/k3/k5】')
    # 预计算每个周期的百分位映射
    maps = {}
    for target, rc, dc, sc in PERIODS:
        rets, dds, srs, idxs = [], [], [], []
        for i, r in enumerate(rows):
            rv, dv, sv = r.get(rc), r.get(dc), r.get(sc)
            if rv is not None and dv is not None and sv is not None:
                rets.append(float(rv)); dds.append(float(dv)); srs.append(float(sv)); idxs.append(i)
        if not rets:
            continue
        rm = pct_rank_map(rets); dm = pct_rank_map(dds); sm = pct_rank_map(srs)
        # 按原始顺序映射回索引
        rmap = {rets[j]: rm[rets[j]] for j in range(len(rets))}
        dmap = {dds[j]: dm[dds[j]] for j in range(len(dds))}
        smap = {srs[j]: sm[srs[j]] for j in range(len(srs))}
        maps[target] = (idxs, rmap, dmap, smap)
        print(f'  {target}: 可计算 {len(rets)} 只')

    updated = 0
    for target, rc, dc, sc in PERIODS:
        if target not in maps:
            continue
        idxs, rmap, dmap, smap = maps[target]
        for j, i in enumerate(idxs):
            rv, dv, sv = float(rows[i][rc]), float(rows[i][dc]), float(rows[i][sc])
            kp = round(rmap[rv]*0.5 + dmap[dv]*0.25 + smap[sv]*0.25, 4)
            rows[i][target] = kp
            updated += 1
    print(f'  更新 k_p 单元格 {updated} 个')

    print('【刷新 k_all】')
    n_all = 0
    for r in rows:
        parts = []
        for col, w in KALL_W:
            v = r.get(col)
            if v is not None:
                parts.append((w, float(v)))
        if not parts:
            r['k_all'] = None
        else:
            sw = sum(w for w, _ in parts)
            r['k_all'] = round(sum(w*v for w, v in parts)/sw, 4)
            n_all += 1
    print(f'  k_all 重算 {n_all} 只')
    return rows


def apply_table(table, rows):
    print(f'【写入 {table}】')
    # 分批 400 行一个 UPDATE（CASE 语句）
    B = 400
    done = 0
    # 预分组：有变化才写。这里对全部行写（含未变），简单稳妥
    for s in range(0, len(rows), B):
        batch = rows[s:s+B]
        sets = []
        for col in ['k1','k2','k3','k5','k_all']:
            wc = [f"WHEN '{r['c']}' THEN {r[col]}" for r in batch if r.get(col) is not None]
            wc_null = [f"WHEN '{r['c']}' THEN NULL" for r in batch if r.get(col) is None]
            allwc = wc + wc_null
            if allwc:
                sets.append(f"{col}=CASE c {' '.join(allwc)} ELSE {col} END")
        if not sets:
            continue
        codes = ','.join(f"'{r['c']}'" for r in batch)
        sql = f"UPDATE {table} SET {','.join(sets)} WHERE c IN ({codes})"
        mgmt(sql)
        done += len(batch)
        if s % 4000 == 0:
            print(f'  已写 {done}/{len(rows)}')
    print(f'  ✓ {table} 写入完成')


def verify():
    print('【验证】')
    for code in ['501073.OF','022754.OF']:
        r = requests.get(f'{SUPABASE_URL}/rest/v1/fund_scores',
                         params={'select':'c,n,r1y,dd1y,sr1y,k1,k_all','c':'eq.'+code,'limit':1},
                         headers=rest_hdrs, timeout=30)
        if r.ok and r.json():
            x = r.json()[0]
            print(f"  {x['c']} {x.get('n')}: r1y={x.get('r1y')} dd1y={x.get('dd1y')} sr1y={x.get('sr1y')} -> k1={x.get('k1')} k_all={x.get('k_all')}")
    # Top10 by new k1
    r = requests.get(f'{SUPABASE_URL}/rest/v1/fund_scores',
                     params={'select':'c,n,k1','k1':'not.is.null','order':'k1.desc','limit':10},
                     headers=rest_hdrs, timeout=30)
    print('  Top10 by k1:')
    for x in (r.json() if r.ok else []):
        print(f"    {x['c']} {x.get('n')}: {x.get('k1')}")


if __name__ == '__main__':
    t0 = datetime.now()
    rows = fetch_all()
    backup(rows)
    rows = compute(rows)
    apply_table('fund_scores', rows)
    apply_table('fund_combined', rows)
    verify()
    print(f'\n✅ 完成，耗时 {(datetime.now()-t0).seconds}s')
