#!/usr/bin/env python3
"""
基于 data/hspj_classification.json 更新 fund_scores 的 t0/t1（HSPJ 分类）。
逻辑：提取基金主代码（6位），匹配 JSON 映射，批量 UPDATE。
"""
import json, subprocess, time, os, sys, re
from collections import defaultdict

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN', '')
PROJECT_REF = os.environ.get('SUPABASE_PROJECT_REF', 'tqhtegazxykkqfcpejky')
MGMT_API = f'https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(SCRIPT_DIR, '..', 'data', 'hspj_classification.json')

def pg(query):
    r = subprocess.run(['curl', '-s', MGMT_API,
        '-H', f'Authorization: Bearer {MGMT_TOKEN}',
        '-H', 'Content-Type: application/json',
        '-d', json.dumps({'query': query})],
        capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout) if r.stdout else []

def extract_base_code(code):
    c = code.replace('.OF', '').strip()
    m = re.match(r'^(\d{6})', c)
    return m.group(1) if m else None

def main():
    print('[1] 加载 HSPJ 分类映射...')
    if not os.path.exists(JSON_PATH):
        print(f'  ERROR: 找不到 {JSON_PATH}')
        sys.exit(1)
    with open(JSON_PATH) as f:
        data = json.load(f)
    code_map = data['mapping']
    print(f'  映射: {data["total"]} 主代码, 更新日期: {data["updated"]}')

    if not MGMT_TOKEN:
        print('  WARNING: 缺少 SUPABASE_MGMT_TOKEN，跳过更新')
        sys.exit(0)

    print('\n[2] 获取数据库所有基金 code...')
    count_r = subprocess.run(['curl', '-s',
        f'{SUPABASE_URL}/rest/v1/fund_scores?select=count',
        '-H', f'apikey: {ANON_KEY}',
        '-H', 'Accept: application/vnd.pgrst.object+json',
        '-H', 'Prefer: count=exact',
        '-H', f'Authorization: Bearer {ANON_KEY}'],
        capture_output=True, text=True, timeout=30)
    total = json.loads(count_r.stdout).get('count', 0) if count_r.stdout else 0
    print(f'  总数: {total}')

    all_codes = []
    offset = 0
    while offset < total:
        url = (f'{SUPABASE_URL}/rest/v1/fund_scores?select=c&order=c.asc'
               f'&limit=5000&offset={offset}')
        r = subprocess.run(['curl', '-s', url,
            '-H', f'apikey: {ANON_KEY}',
            '-H', f'Authorization: Bearer {ANON_KEY}'],
            capture_output=True, text=True, timeout=60)
        batch = json.loads(r.stdout) if r.stdout else []
        all_codes.extend(f['c'] for f in batch)
        offset += len(batch)
        if not batch: break
        time.sleep(0.3)

    print(f'  共 {len(all_codes)} 只基金')

    print('\n[3] 匹配主代码...')
    updates = {}
    unmatched = 0
    for c in all_codes:
        base = extract_base_code(c)
        if base and base in code_map:
            info = code_map[base]
            updates[c] = (info['t0'], info['t1'])
        else:
            unmatched += 1

    print(f'  匹配: {len(updates)}只, 未匹配: {unmatched}只')

    if not updates:
        print('  无需更新')
        return

    print(f'\n[4] 批量 UPDATE {len(updates)} 条...')
    groups = defaultdict(list)
    for c, (l1, l2) in updates.items():
        groups[(l1, l2)].append(c)

    total_updated = 0
    for (l1, l2), codes in groups.items():
        # Update in chunks of 500 codes to avoid query too long
        for i in range(0, len(codes), 500):
            chunk = codes[i:i+500]
            code_list = "','".join(chunk)
            safe_l1 = l1.replace("'", "''")
            safe_l2 = l2.replace("'", "''")
            q = f"UPDATE fund_scores SET t0 = '{safe_l1}', t1 = '{safe_l2}' WHERE c IN ('{code_list}')"
            pg(q)
            total_updated += len(chunk)
            time.sleep(0.2)

    print(f'  ✅ 已更新 {total_updated} 条')

    print('\n[5] 更新元信息...')
    pg(f"UPDATE fund_scores_meta SET tsq = NOW() WHERE id = 8")
    print('  ✅ 元信息已更新')

if __name__ == '__main__':
    main()
