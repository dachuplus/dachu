#!/usr/bin/env python3
"""
基于聚源基金分类标准Excel，更新 fund_scores 的 t0/t1（HSPJ分类）。
逻辑：
1. 读取Excel，建立 主代码(6位) → (t0, t1) 映射
2. 查询DB所有基金code
3. 对每个基金：提取主代码(去.OF后取前6位)，匹配Excel映射
4. 批量UPDATE t0/t1
"""
import pandas as pd
import subprocess, json, time, os, sys, re
from collections import defaultdict

# ===== 配置 =====
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3')
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN', '')
PROJECT_REF = 'tqhtegazxykkqfcpejky'
MGMT_API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'
BATCH_SIZE = 2000

def pg(query):
    """Execute SQL via Management API"""
    r = subprocess.run(['curl', '-s', MGMT_API,
        '-H', f'Authorization: Bearer {MGMT_TOKEN}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({'query': query})],
        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout) if r.stdout else []
    except:
        print(f'  PG error: {r.stdout[:200]}')
        return []

def supabase_get(endpoint, params):
    qs = '&'.join(f'{k}={v}' for k,v in params.items())
    url = f'{SUPABASE_URL}/rest/v1/{endpoint}?{qs}'
    r = subprocess.run(['curl', '-s', url,
        '-H', f'apikey: {ANON_KEY}',
        '-H', f'Authorization: Bearer {ANON_KEY}'],
        capture_output=True, text=True, timeout=30)
    try:
        return json.loads(r.stdout) if r.stdout else []
    except:
        return []

# ===== Step 1: 加载Excel分类映射 =====
print('[1] 加载聚源分类标准Excel...')
df = pd.read_excel('/Users/maoshanbo/Downloads/聚源基金分类标准20260623.xlsx', skiprows=1)
df = df.iloc[:, 1:]  # drop row index col
df.columns = ['code', 'name', 'manager', 'company', 'level1', 'level2', 'level3', 'level4']

# 建立主代码→分类映射
code_map = {}
for _, row in df.iterrows():
    c = str(row['code']).replace('.OF', '').strip()
    l1 = str(row['level1']).strip() if pd.notna(row['level1']) else ''
    l2 = str(row['level2']).strip() if pd.notna(row['level2']) else ''
    if c and l1 and l1 != 'nan' and l2 and l2 != 'nan':
        code_map[c] = (l1, l2)

print(f'  主代码映射: {len(code_map)}条')
print(f'  一级分类数: {len(set(v[0] for v in code_map.values()))}')

# 统计各分类
l1_cnt = defaultdict(int)
l1_l2_cnt = defaultdict(int)
for l1, l2 in code_map.values():
    l1_cnt[l1] += 1
    l1_l2_cnt[(l1, l2)] += 1
for l1 in sorted(l1_cnt):
    print(f'  {l1}: {l1_cnt[l1]}只')
    for (ll1, ll2), cnt in sorted(l1_l2_cnt.items()):
        if ll1 == l1:
            print(f'    └─ {ll2}: {cnt}只')

# ===== Step 2: 获取DB所有基金code =====
print('\n[2] 获取数据库所有基金...')

# 先获取总数
count_result = subprocess.run(['curl', '-s',
    f'{SUPABASE_URL}/rest/v1/fund_scores?select=count',
    '-H', f'apikey: {ANON_KEY}',
    '-H', 'Accept: application/vnd.pgrst.object+json',
    '-H', 'Prefer: count=exact',
    '-H', f'Authorization: Bearer {ANON_KEY}'],
    capture_output=True, text=True, timeout=30)
total = 0
try:
    total = json.loads(count_result.stdout).get('count', 0)
except:
    pass
print(f'  总数: {total}')

# 批量获取 code + name
all_funds = []
offset = 0
limit = 5000
while offset < total:
    url = (f'{SUPABASE_URL}/rest/v1/fund_scores?select=c,n,t0,t1'
           f'&order=c.asc&limit={limit}&offset={offset}')
    r = subprocess.run(['curl', '-s', url,
        '-H', f'apikey: {ANON_KEY}',
        '-H', f'Authorization: Bearer {ANON_KEY}'],
        capture_output=True, text=True, timeout=60)
    try:
        batch = json.loads(r.stdout)
        if not batch:
            break
        all_funds.extend(batch)
        offset += len(batch)
        print(f'  已获取 {len(all_funds)}/{total}')
    except:
        print(f'  Error at offset {offset}: {r.stdout[:100]}')
        break
    time.sleep(0.5)

print(f'  共获取 {len(all_funds)} 只基金')

# ===== Step 3: 匹配主代码 → HSPJ分类 =====
print('\n[3] 匹配主代码...')

def extract_base_code(code):
    """从DB code提取主代码（6位）"""
    c = code.replace('.OF', '').strip()
    # 如果6位纯数字，直接返回
    if re.match(r'^\d{6}$', c):
        return c
    # 如果前面是6位数字+后缀，取前6位
    m = re.match(r'^(\d{6})', c)
    if m:
        return m.group(1)
    return None

matched = 0
unmatched = 0
updates = []
stats = defaultdict(int)

for fund in all_funds:
    c = fund['c']
    base = extract_base_code(c)
    if base and base in code_map:
        l1, l2 = code_map[base]
        # 检查是否需要更新
        if fund.get('t0') != l1 or fund.get('t1') != l2:
            updates.append((c, l1, l2))
            stats[(l1, l2)] += 1
        matched += 1
    else:
        unmatched += 1

print(f'  匹配成功: {matched} ({len(updates)}只需更新)')
print(f'  匹配失败: {unmatched}')
print(f'\n  待更新分布:')
for (l1, l2), cnt in sorted(stats.items(), key=lambda x: -x[1]):
    print(f'    {l1} → {l2}: {cnt}只')

# ===== Step 4: 批量UPDATE =====
if not updates:
    print('\n✅ t0/t1 已与Excel一致，无需更新')
    if unmatched > 0:
        print(f'  但 {unmatched} 只基金无法匹配主代码（不在Excel中）')
        # 显示一些未匹配的示例
        print('  未匹配示例:')
        for fund in all_funds[:]:
            c = fund['c']
            base = extract_base_code(c)
            if not base or base not in code_map:
                print(f'    {c} ({fund["n"]}) base={base}')
                unmatched -= 1
                if unmatched <= 10:
                    break
    sys.exit(0)

print(f'\n[4] 开始批量更新 {len(updates)} 条记录...')

# 分批执行 UPDATE
for i in range(0, len(updates), BATCH_SIZE):
    batch = updates[i:i+BATCH_SIZE]
    
    # 构建CASE WHEN批量更新（按主代码分组，每组一个UPDATE）
    # 按(l1,l2)分组
    groups = defaultdict(list)
    for c, l1, l2 in batch:
        groups[(l1, l2)].append(c)
    
    for (l1, l2), codes in groups.items():
        # 使用 IN 批量更新
        code_list = "','".join(codes)
        safe_l1 = l1.replace("'", "''")
        safe_l2 = l2.replace("'", "''")
        q = f"UPDATE fund_scores SET t0 = '{safe_l1}', t1 = '{safe_l2}' WHERE c IN ('{code_list}')"
        result = pg(q)
    
    print(f'  [{i+1}-{min(i+BATCH_SIZE, len(updates))}] 已更新 {len(batch)}条')
    time.sleep(0.3)

print(f'\n✅ 全部完成！共更新 {len(updates)} 条')
