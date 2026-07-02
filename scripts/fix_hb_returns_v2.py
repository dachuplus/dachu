#!/usr/bin/env python3
"""
高效修复全部货币型基金收益率数据 v2（批量 SQL）
使用 rankhandler API 获取正确数据，单条 CASE WHEN 批量更新。
"""

import os, sys, re, time, requests

sys.stdout.reconfigure(encoding='utf-8')

MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN") or ''
MGMT_URL = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
H = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}

API_URL = "https://fund.eastmoney.com/data/rankhandler.aspx"
HB_H = {
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0",
}

def mgmt(sql, retries=2):
    for i in range(retries + 1):
        try:
            r = requests.post(MGMT_URL, headers=H, json={"query": sql}, timeout=60)
            if r.status_code in (200, 201):
                return r.json()
            print(f"  [SQL ERR {r.status_code}] {r.text[:120]}")
        except Exception as e:
            if i < retries:
                print(f"  [retry {i+1}] {e}")
                time.sleep(2)
            else:
                print(f"  [FAIL] {e}")
    return None

# ── Step 1: 全量拉取 rankhandler ──
print("📡 拉取货币基金数据...")
all_hb = {}
body = {"op":"ph","dt":"hb","ft":"hb","rs":"","gs":"0","sc":"1nzf","st":"desc","pi":"1","pn":"100","zf":"diy"}

for page in range(1, 97):
    if page > 1:
        body["pi"] = str(page)
        time.sleep(0.06)
    try:
        r = requests.post(API_URL, data=body, headers=HB_H, timeout=30)
        r.encoding = 'utf-8'
        m = re.search(r'datas:\[(.*?)\](?:,|$)', r.text, re.DOTALL)
        if not m: continue
        for item in re.findall(r'"([^"]*)"', m.group(1)):
            p = item.split(',')
            if len(p) < 13 or p[0].strip() in all_hb: continue
            code = p[0].strip()
            def fv(i):
                try: return float(p[i].strip()) if i < len(p) else None
                except: return None
            all_hb[code] = {
                'ytd': fv(9), 'r1y': fv(10), 'r3y': fv(12),
                # also try f[13] as YTD alternative
                '_ytd_alt': fv(13),
            }
            # Use f[13] if it's a reasonable ytd value (< 20%)
            alt = all_hb[code]['_ytd_alt']
            if alt is not None and 0 < alt < 20:
                all_hb[code]['ytd'] = alt
    except: pass
    if page % 30 == 0 or page == 96:
        print(f"  page {page}/96 ({len(all_hb)} funds)")

print(f"✅ 获取 {len(all_hb)} 只货币基金")

if '000330' in all_hb:
    d = all_hb['000330']
    print(f"  000330 验证: ytd={d['ytd']} r1y={d['r1y']} r3y={d['r3y']} (预期 0.51 / 1.06 / 4.38)")

# ── Step 2: 分批构建 CASE WHEN UPDATE（每批200只）──
print("\n🔧 批量更新 fund_combined...")
codes = list(all_hb.keys())
batch_size = 200
total_ok = 0
total_err = 0

for bi in range(0, len(codes), batch_size):
    batch = codes[bi:bi+batch_size]
    
    # Build case expressions for each field
    for field in ['ytd', 'r1y', 'r3y']:
        whens = []
        for code in batch:
            val = all_hb[code][field]
            if val is not None:
                whens.append(f"WHEN c='{code}' THEN {val}")
        
        if not whens:
            continue
        
        sql = f"""UPDATE fund_combined SET "{field}" = CASE {' '.join(whens)} ELSE "{field}" END 
               WHERE c IN ({','.join(f"'{c}'" for c in batch)});"""
        
        result = mgmt(sql)
        if result is not None:
            total_ok += len(batch)
        else:
            total_err += len(batch)
    
    if (bi + batch_size) % 600 == 0 or (bi + batch_size) >= len(codes):
        print(f"  进度: {min(bi + batch_size, len(codes))}/{len(codes)}")
    time.sleep(0.05)

print(f"✅ 完成: ok≈{total_ok/3:.0f} updates, err≈{total_err/3:.0f}")

# ── Step 3: 验证 ──
print("\n🔍 验证:")
for code in ['000330', '000324', '000659', '000434', '004121']:
    row = mgmt(f"SELECT c,name,ytd,r1y,r3y FROM fund_combined WHERE c='{code}';")
    if row and len(row) > 0:
        r = row[0]
        print(f"  {r['c']} {r.get('name','')[:12]:12s} | ytd={r.get('ytd')} r1y={r.get('r1y')} r3y={r.get('r3y')}")

row = mgmt("SELECT COUNT(*) t,COUNT(ytd) y,COUNT(r1y) r1,COUNT(r3y) r3 FROM fund_combined WHERE t0='货币型';")
if row: print(f"\n统计: {row[0]}")
