#!/usr/bin/env python3
"""
修复货币型基金数据：从 F10 + pingzhongdata 拉取并写入 fund_combined
"""

import os, json, requests, re, time
from concurrent.futures import ThreadPoolExecutor, as_completed

REF = 'tqhtegazxykkqfcpejky'
MGMT_API = f'https://api.supabase.com/v1/projects/{REF}/database/query'
TOKEN = os.environ.get('SUPABASE_PAT', '')
HTTP_HDR = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}

def mgmt(sql, timeout=60):
    h = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json', 'apikey': TOKEN}
    r = requests.post(MGMT_API, headers=h, json={'query': sql}, timeout=timeout)
    return r.json()

def parse_numeric(s):
    if not s: return None
    m = re.search(r'([\d.]+)', str(s))
    return float(m.group(1)) if m else None

def fetch_one(code):
    result = {'c': code}
    # F10 page
    try:
        r = requests.get(f'http://fundf10.eastmoney.com/jbgk_{code}.html', headers=HTTP_HDR, timeout=10)
        r.encoding = 'utf-8'
        m = re.search(r'基金管理人</th>\s*<td[^>]*><a[^>]*>([^<]+)</a>', r.text)
        if m: result['company'] = m.group(1).strip()
        m = re.search(r'管理费率</th>\s*<td[^>]*>\s*([\d.]+%)', r.text)
        if m: result['manage_fee'] = m.group(1)
        m = re.search(r'净资产规模</th>\s*<td[^>]*>\s*([\d.]+亿元)', r.text)
        if m: result['fund_scale'] = parse_numeric(m.group(1))
        if 'fund_scale' not in result:
            m = re.search(r'成立日期/规模</th>\s*<td[^>]*>\s*[\d/]+\s*/\s*([\d.]+亿份)', r.text)
            if m: result['fund_scale'] = parse_numeric(m.group(1))
    except:
        pass
    
    # pingzhongdata
    try:
        r = requests.get(f'http://fund.eastmoney.com/pingzhongdata/{code}.js', headers=HTTP_HDR, timeout=10)
        # YTD from 万份收益
        m = re.search(r'Data_millionCopiesIncome\s*=\s*(\[\[.*?\]\])', r.text, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            cy = time.localtime().tm_year
            j1 = int(time.mktime((cy, 1, 1, 0, 0, 0, 0, 0, 0))) * 1000
            ytd_sum = sum(p[1] for p in data if p[0] >= j1)
            days = max((time.time() - j1/1000) / 86400, 1)
            if ytd_sum > 0:
                result['ytd'] = round(ytd_sum / 10000 * 100 * (365 / days), 2)
        # 七日年化
        m = re.search(r'Data_sevenDaysYearIncome\s*=\s*(\[\[.*?\]\])', r.text, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            if data: result['r1y'] = round(data[-1][1], 2)
        # Manager scale
        m = re.search(r'Data_currentFundManager\s*=\s*(\[.*?\])', r.text, re.DOTALL)
        if m:
            mgr = json.loads(m.group(1))
            if mgr: result['total_manage_scale'] = mgr[0].get('fundSize', '')
    except:
        pass
    
    return result

# ── 主流程 ──
print('获取货币型基金代码...')
rows = mgmt("SELECT c FROM fund_combined WHERE t0='货币型' ORDER BY c")
codes = [r['c'] for r in rows]
print(f'共 {len(codes)} 只')

print('并发拉取数据 (5线程)...')
results = {}
with ThreadPoolExecutor(max_workers=5) as pool:
    fs = {pool.submit(fetch_one, c): c for c in codes}
    for i, f in enumerate(as_completed(fs)):
        r = f.result()
        results[fs[f]] = r
        if (i+1) % 200 == 0:
            print(f'  进度: {i+1}/{len(codes)}')

print(f'拉取完成，有company: {sum(1 for v in results.values() if v.get("company"))}')

# 构建批量 UPDATE
print('构建批量 SQL...')
# 使用多行 VALUES + UPDATE FROM 来批量更新
B = 100
all_vals = []
for code, r in results.items():
    if not r.get('company'):
        continue
    comp = r['company'].replace("'", "''")
    fee = r.get('manage_fee', '').replace("'", "''")
    tms = r.get('total_manage_scale', '').replace("'", "''")
    scale = r.get('fund_scale', 'NULL')
    ytd = r.get('ytd', 'NULL')
    r1y = r.get('r1y', 'NULL')
    all_vals.append(f"('{code}', '{comp}', '{fee}', {scale}, {ytd}, {r1y}, '低', '{tms}')")

print(f'写入 {len(all_vals)} 条...')

for s in range(0, len(all_vals), B):
    batch = all_vals[s:s+B]
    values_sql = ',\n'.join(batch)
    sql = f"""
    UPDATE fund_combined SET
        company = tmp.company,
        manage_fee = tmp.manage_fee,
        fund_scale = tmp.fund_scale::double precision,
        ytd = tmp.ytd::double precision,
        r1y = tmp.r1y::double precision,
        risk_level = tmp.risk_level,
        total_manage_scale = tmp.total_manage_scale
    FROM (VALUES {values_sql}) AS tmp(c, company, manage_fee, fund_scale, ytd, r1y, risk_level, total_manage_scale)
    WHERE fund_combined.c = tmp.c
    """
    try:
        mgmt(sql, timeout=60)
        print(f'  批次 {s//B + 1}: {min(s+B, len(all_vals))}/{len(all_vals)}')
    except Exception as e:
        print(f'  批次 {s//B + 1} 失败: {e}')

# 验证
print('\n验证...')
rows = mgmt("SELECT c, name, company, fund_scale, risk_level, manage_fee, ytd, r1y FROM fund_combined WHERE t0='货币型' AND company IS NOT NULL LIMIT 5")
for r in rows:
    print(f"  {r['c']} {r['name']} | {r['company']} | scale={r['fund_scale']} | {r['risk_level']} | {r['manage_fee']} | ytd={r['ytd']}% | r1y={r['r1y']}%")

rows = mgmt("SELECT COUNT(*) as t, COUNT(company) as c, COUNT(ytd) as y FROM fund_combined WHERE t0='货币型'")
print(f"\n总计: {rows[0]['t']}, company: {rows[0]['c']}, ytd: {rows[0]['y']}")
print('✓ 完成!')
