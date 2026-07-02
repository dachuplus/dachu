#!/usr/bin/env python3
"""
创建 fund_combined 合并表：JOIN fund_raw_sample(分类+详情) + fund_scores(评分)
→ 通过 Supabase Management API 创建表 → 批量导入数据 → 导出 Excel
"""
import json, os, re, sys, time
import requests
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

# ── Configuration ──
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN") or ''  # from GitHub Secrets or env
PROJECT_REF = "tqhtegazxykkqfcpejky"
SUPABASE_URL = f"https://{PROJECT_REF}.supabase.co"
ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

HEADERS_REST = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
HEADERS_MGMT = {
    "Authorization": f"Bearer {MGMT_TOKEN}",
    "Content-Type": "application/json",
}

# ── Step 1: Drop & Create fund_combined table ──
def create_table():
    print("📋 创建 fund_combined 表...")
    
    # Drop if exists
    try:
        resp = requests.post(MGMT_URL, headers=HEADERS_MGMT,
            json={"query": "DROP TABLE IF EXISTS fund_combined CASCADE;"})
        print(f"  DROP: {resp.status_code}")
    except Exception as e:
        print(f"  DROP error: {e}")

    ddl = """
    CREATE TABLE fund_combined (
        c           TEXT PRIMARY KEY,
        name        TEXT,
        t0          TEXT,
        t1          TEXT,
        company     TEXT,
        fund_scale  DOUBLE PRECISION,
        risk_level  TEXT,
        manage_fee  TEXT,
        ytd         DOUBLE PRECISION,
        r1y         DOUBLE PRECISION,
        r3y         DOUBLE PRECISION,
        r5y         DOUBLE PRECISION,
        dd1y        DOUBLE PRECISION,
        sr1y        DOUBLE PRECISION,
        holders_count INTEGER,
        total_manage_scale TEXT,
        -- 评分字段 (来自 fund_scores)
        k_all       DOUBLE PRECISION,
        score_grade TEXT,
        k0w         DOUBLE PRECISION,
        k1m         DOUBLE PRECISION,
        k3m         DOUBLE PRECISION,
        k6m         DOUBLE PRECISION,
        k1          DOUBLE PRECISION,
        k2          DOUBLE PRECISION,
        k3          DOUBLE PRECISION,
        k5          DOUBLE PRECISION
    );
    """
    
    try:
        resp = requests.post(MGMT_URL, headers=HEADERS_MGMT,
            json={"query": ddl})
        print(f"  CREATE: {resp.status_code} {resp.text[:200]}")
    except Exception as e:
        print(f"  CREATE error: {e}")
        return False
    
    # Create index
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_fc_t0 ON fund_combined(t0);",
        "CREATE INDEX IF NOT EXISTS idx_fc_k_all ON fund_combined(k_all DESC);",
        "CREATE INDEX IF NOT EXISTS idx_fc_score_grade ON fund_combined(score_grade);",
    ]
    for idx in indexes:
        try:
            resp = requests.post(MGMT_URL, headers=HEADERS_MGMT, json={"query": idx})
        except:
            pass
    
    print("  ✅ 表创建完成")
    return True

# ── Step 2: Fetch all data from both tables ──
def fetch_all(table, select, batch_size=1000):
    """分页拉取全量数据 (Supabase REST API 每页最多 1000 行)"""
    all_data = []
    offset = 0
    while True:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/{table}?select={select}&order=c&limit={batch_size}&offset={offset}",
            headers=HEADERS_REST
        )
        batch = resp.json()
        if not batch:
            break
        all_data.extend(batch)
        offset += len(batch)  # 按实际返回行数递增 offset
        if len(batch) < batch_size:
            break
        if len(all_data) % 10000 == 0:
            print(f"  {table}: {len(all_data)}...")
    return all_data

# ── Step 3: Join and prepare data ──
def build_combined():
    print("\n📥 拉取 fund_raw_sample...")
    raw = fetch_all("fund_raw_sample", 
        "c,name,t0,t1,company,fund_scale,risk_level,manage_fee,ytd,r1y,r3y,r5y,dd1y,sr1y,holders_count,total_manage_scale")
    raw_map = {r["c"]: r for r in raw}
    print(f"  fund_raw_sample: {len(raw)} 条")

    print("📥 拉取 fund_scores...")
    scores = fetch_all("fund_scores",
        "c,n,k_all,score_grade,k0w,k1m,k3m,k6m,k1,k2,k3,k5")
    print(f"  fund_scores: {len(scores)} 条")

    print("\n🔗 合并数据 (匹配基金代码)...")
    combined = []
    matched = 0
    unmatched = 0
    
    for s in scores:
        # fund_scores code: "000001.OF" → 去掉 ".OF" 后缀
        code = s["c"]
        if code.endswith(".OF"):
            code_clean = code[:-3]
        else:
            code_clean = code
        
        if code_clean in raw_map:
            r = raw_map[code_clean]
            row = {
                "c": code_clean,
                "name": r.get("name") or s.get("n", ""),
                "t0": r.get("t0", ""),
                "t1": r.get("t1", ""),
                "company": r.get("company", ""),
                "fund_scale": r.get("fund_scale"),
                "risk_level": r.get("risk_level", ""),
                "manage_fee": r.get("manage_fee", ""),
                "ytd": r.get("ytd"),
                "r1y": r.get("r1y"),
                "r3y": r.get("r3y"),
                "r5y": r.get("r5y"),
                "dd1y": r.get("dd1y"),
                "sr1y": r.get("sr1y"),
                "holders_count": r.get("holders_count"),
                "total_manage_scale": r.get("total_manage_scale", ""),
                "k_all": s.get("k_all"),
                "score_grade": s.get("score_grade", ""),
                "k0w": s.get("k0w"),
                "k1m": s.get("k1m"),
                "k3m": s.get("k3m"),
                "k6m": s.get("k6m"),
                "k1": s.get("k1"),
                "k2": s.get("k2"),
                "k3": s.get("k3"),
                "k5": s.get("k5"),
            }
            combined.append(row)
            matched += 1
        else:
            unmatched += 1
    
    print(f"  匹配: {matched}, 未匹配: {unmatched}")
    return combined

# ── Step 4: Batch insert via Management API ──
def batch_insert(combined, batch_size=100):
    print(f"\n💾 批量导入 {len(combined)} 条到 fund_combined...")
    
    total = len(combined)
    inserted = 0
    errors = 0
    
    columns = [
        "c", "name", "t0", "t1", "company", "fund_scale", "risk_level", "manage_fee",
        "ytd", "r1y", "r3y", "r5y", "dd1y", "sr1y", "holders_count", "total_manage_scale",
        "k_all", "score_grade", "k0w", "k1m", "k3m", "k6m", "k1", "k2", "k3", "k5"
    ]
    
    for i in range(0, total, batch_size):
        batch = combined[i:i+batch_size]
        
        # Build multi-row INSERT
        values_parts = []
        for row in batch:
            vals = []
            for col in columns:
                v = row.get(col)
                if v is None:
                    vals.append("NULL")
                elif isinstance(v, (int, float)):
                    vals.append(str(v))
                else:
                    # Escape single quotes
                    escaped = str(v).replace("'", "''")
                    vals.append(f"'{escaped}'")
            values_parts.append("(" + ", ".join(vals) + ")")
        
        query = f"INSERT INTO fund_combined ({', '.join(columns)}) VALUES {', '.join(values_parts)} ON CONFLICT (c) DO NOTHING;"
        
        try:
            resp = requests.post(MGMT_URL, headers=HEADERS_MGMT, json={"query": query})
            if resp.status_code in (200, 201):
                inserted += len(batch)
            else:
                errors += 1
                if errors <= 3:
                    print(f"  Batch error {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"  Exception: {e}")
        
        if (i + batch_size) % 1000 == 0:
            print(f"  进度: {i + batch_size}/{total}")
        
        time.sleep(0.05)  # Rate limit
    
    print(f"  ✅ 导入完成: {inserted}/{total} 条")
    return inserted

# ── Step 5: Verify ──
def verify():
    print("\n🔍 验证数据...")
    
    # Row count
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/fund_combined?select=c&limit=0",
                        headers={**HEADERS_REST, "Prefer": "count=exact"})
    total = 0
    if "content-range" in resp.headers:
        parts = resp.headers["content-range"].split("/")
        if len(parts) == 2:
            total = int(parts[1])
    print(f"  总行数: {total}")
    
    # t0 distribution
    all_data = fetch_all("fund_combined", "t0")
    t0s = Counter(r.get("t0", "NULL") for r in all_data)
    print("  一级分类分布:")
    for k, v in sorted(t0s.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}")
    
    # Check key funds
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/fund_combined?select=c,name,t0,t1,k_all,score_grade&c=in.(000001,000047)&limit=5",
        headers=HEADERS_REST
    )
    print("\n  关键基金验证:")
    for r in resp.json():
        print(f"    {r['c']} {r['name']} t0={r['t0']} t1={r['t1']} k_all={r['k_all']} grade={r['score_grade']}")
    
    # score_grade distribution
    grades = fetch_all("fund_combined", "score_grade")
    gs = Counter(r.get("score_grade", "NULL") for r in grades)
    print("\n  评级分布:")
    for k, v in sorted(gs.items(), key=lambda x: -x[1]):
        print(f"    {k}: {v}")
    
    return total

# ── Main ──
def main():
    if not create_table():
        print("❌ 建表失败")
        return
    
    combined = build_combined()
    batch_insert(combined)
    verify()
    
    print("\n✅ fund_combined 合并表创建完成！")

if __name__ == "__main__":
    main()
