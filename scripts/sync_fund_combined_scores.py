#!/usr/bin/env python3
"""
同步 fund_scores 评分到 fund_combined 表（高效版）
- Phase 1: 单条 SQL 跨表 UPDATE 所有匹配基金
- Phase 2: 批量 INSERT 新基金
- 用于 CI 每日更新和手动修复
"""
import os, sys, time
import requests

sys.stdout.reconfigure(encoding='utf-8', line_buffering=True)

MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN") or os.environ.get("SUPABASE_PAT") or ''
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF") or "tqhtegazxykkqfcpejky"
SUPABASE_URL = f"https://{PROJECT_REF}.supabase.co"
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY") or "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"

HEADERS_REST = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
HEADERS_MGMT = {
    "Authorization": f"Bearer {MGMT_TOKEN}",
    "Content-Type": "application/json",
}

def mgmt_query(query_str):
    """通过 Management API 执行 SQL"""
    resp = requests.post(MGMT_URL, headers=HEADERS_MGMT,
                         json={"query": query_str}, timeout=60)
    if resp.status_code not in (200, 201):
        err_text = resp.text[:300]
        print(f"  SQL ERROR ({resp.status_code}): {err_text}", flush=True)
        return None
    return resp

def escape_sql(val):
    if val is None:
        return "NULL"
    elif isinstance(val, (int, float)):
        return str(val)
    elif isinstance(val, bool):
        return "TRUE" if val else "FALSE"
    else:
        return "'" + str(val).replace("'", "''") + "'"

def rest_get(path, params=""):
    """REST API GET"""
    url = f"{SUPABASE_URL}/rest/v1/{path}"
    if params:
        url += "?" + params
    resp = requests.get(url, headers=HEADERS_REST, timeout=30)
    return resp

def fetch_all(table, select, batch_size=1000):
    """分页拉取全量"""
    all_data = []
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&order=c&limit={batch_size}&offset={offset}"
        resp = requests.get(url, headers=HEADERS_REST, timeout=30)
        batch = resp.json()
        if not batch:
            break
        all_data.extend(batch)
        offset += len(batch)
        if len(batch) < batch_size:
            break
        if len(all_data) % 10000 == 0:
            print(f"  {table}: {len(all_data)}...", flush=True)
    return all_data


def main():
    print("=" * 60, flush=True)
    print(" Sync fund_scores → fund_combined", flush=True)
    print("=" * 60, flush=True)

    # ── Phase 1: Bulk UPDATE all matching funds (single SQL) ──
    print("\n[Phase 1] Bulk UPDATE existing funds...", flush=True)
    
    # Single cross-table UPDATE — handles ALL funds in one query
    # Maps fund_scores → fund_combined columns (only columns that exist in both tables)
    update_sql = """
    UPDATE fund_combined
    SET
        k_all = fs.k_all,
        score_grade = fs.score_grade,
        k0w = fs.k0w,
        k1m = fs.k1m,
        k3m = fs.k3m,
        k6m = fs.k6m,
        k1 = fs.k1,
        k2 = fs.k2,
        k3 = fs.k3,
        k5 = fs.k5
    FROM fund_scores fs
    WHERE fund_combined.c = REPLACE(fs.c, '.OF', '');
    """

    # Unset old/wrong env var that might interfere
    os.environ.pop('SUPABASE_MGMT_TOKEN', None)
    
    resp = mgmt_query(update_sql)
    if resp is None:
        print("  Phase 1 FAILED!", flush=True)
    else:
        print("  Phase 1 DONE (UPDATE all matching funds)", flush=True)

    # ── Phase 2: INSERT new funds (in fund_scores but not fund_combined) ──
    print("\n[Phase 2] Find & INSERT new funds...", flush=True)
    
    # Find codes in fund_scores but NOT in fund_combined
    find_new_sql = """
    SELECT REPLACE(fs.c, '.OF', '') AS code
    FROM fund_scores fs
    WHERE NOT EXISTS (
        SELECT 1 FROM fund_combined fc WHERE fc.c = REPLACE(fs.c, '.OF', '')
    );
    """
    resp = mgmt_query(find_new_sql)
    if resp is None:
        print("  Phase 2: Failed to find new funds", flush=True)
        new_codes = []
    else:
        result = resp.json()
        new_codes = [r["code"] for r in result]
    
    print(f"  New funds to insert: {len(new_codes)}", flush=True)
    
    if not new_codes:
        print("  Phase 2: Nothing to insert", flush=True)
    else:
        # Fetch fund_raw_sample for these new codes
        print("  Fetching fund_raw_sample details...", flush=True)
        raw_map = {}
        # Batch REST queries (max ~100 codes per request due to URL length)
        for i in range(0, len(new_codes), 100):
            batch_codes = new_codes[i:i+100]
            codes_str = ",".join(batch_codes)
            resp = rest_get("fund_raw_sample",
                            f"c=in.({codes_str})&select=c,name,t0,t1,company,fund_scale,risk_level,manage_fee,ytd,r1y,r3y,r5y,dd1y,sr1y,holders_count,total_manage_scale")
            data = resp.json() if resp.status_code == 200 else []
            if isinstance(data, dict) and "message" in data:
                print(f"    Raw sample error: {data.get('message', '')}", flush=True)
                data = []
            if isinstance(data, list):
                for r in data:
                    raw_map[r["c"]] = r
            print(f"    Fetched {len(data)} from raw_sample (batch {i//100+1})", flush=True)
            time.sleep(0.1)

        # Fetch fund_scores for these new codes
        print("  Fetching fund_scores for new codes...", flush=True)
        scores_map = {}
        for i in range(0, len(new_codes), 100):
            batch_codes = new_codes[i:i+100]
            of_codes = ",".join(f"{c}.OF" for c in batch_codes)
            resp = rest_get("fund_scores",
                            f"c=in.({of_codes})&select=c,k_all,score_grade,k0w,k1m,k3m,k6m,k1,k2,k3,k5")
            data = resp.json()
            for s in data:
                code = s["c"].replace(".OF", "")
                scores_map[code] = s
            print(f"    Fetched {len(data)} from fund_scores (batch {i//100+1})", flush=True)
            time.sleep(0.1)

        # Batch INSERT
        columns = [
            "c", "name", "t0", "t1", "company", "fund_scale", "risk_level", "manage_fee",
            "ytd", "r1y", "r3y", "r5y", "dd1y", "sr1y", "holders_count", "total_manage_scale",
            "k_all", "score_grade", "k0w", "k1m", "k3m", "k6m", "k1", "k2", "k3", "k5"
        ]
        update_fields = ["k_all", "score_grade", "k0w", "k1m", "k3m", "k6m", "k1", "k2", "k3", "k5"]

        inserted = 0
        missing = 0
        value_batch = []

        for code in new_codes:
            s = scores_map.get(code)
            r = raw_map.get(code)

            if not s:
                missing += 1
                continue

            row = {
                "c": code,
                "name": (r.get("name") if r else "") or "",
                "t0": r.get("t0", "") if r else "",
                "t1": r.get("t1", "") if r else "",
                "company": r.get("company", "") if r else "",
                "fund_scale": r.get("fund_scale") if r else None,
                "risk_level": r.get("risk_level", "") if r else "",
                "manage_fee": r.get("manage_fee", "") if r else "",
                "ytd": r.get("ytd") if r else None,
                "r1y": r.get("r1y") if r else None,
                "r3y": r.get("r3y") if r else None,
                "r5y": r.get("r5y") if r else None,
                "dd1y": r.get("dd1y") if r else None,
                "sr1y": r.get("sr1y") if r else None,
                "holders_count": r.get("holders_count") if r else None,
                "total_manage_scale": r.get("total_manage_scale", "") if r else "",
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

            vals = [escape_sql(row[col]) for col in columns]
            value_batch.append("(" + ", ".join(vals) + ")")

            if len(value_batch) >= 100:
                query = f'INSERT INTO fund_combined ({", ".join(columns)}) VALUES {", ".join(value_batch)} ON CONFLICT (c) DO UPDATE SET ' + \
                        ", ".join(f'"{f}" = EXCLUDED."{f}"' for f in update_fields) + ";"
                resp = mgmt_query(query)
                if resp is not None:
                    inserted += len(value_batch)
                value_batch = []
                time.sleep(0.1)

        # Final batch
        if value_batch:
            query = f'INSERT INTO fund_combined ({", ".join(columns)}) VALUES {", ".join(value_batch)} ON CONFLICT (c) DO UPDATE SET ' + \
                    ", ".join(f'"{f}" = EXCLUDED."{f}"' for f in update_fields) + ";"
            resp = mgmt_query(query)
            if resp is not None:
                inserted += len(value_batch)

        print(f"  INSERT: {inserted} 条, missing raw={missing}", flush=True)

    # ── Verify ──
    print("\n[Verify] Checking results...", flush=True)

    # Quick count
    resp = rest_get("fund_combined", "select=c&limit=0")
    total = 0
    if "content-range" in resp.headers:
        total = int(resp.headers["content-range"].split("/")[1])
    print(f"  Total rows: {total}", flush=True)

    # Score grade distribution via SQL
    dist_sql = "SELECT score_grade, COUNT(*) AS cnt FROM fund_combined GROUP BY score_grade ORDER BY cnt DESC;"
    resp = mgmt_query(dist_sql)
    if resp is not None:
        print("  Rating distribution:", flush=True)
        for r in resp.json():
            grade = r["score_grade"] or "NULL"
            print(f"    {grade}: {r['cnt']}", flush=True)

    # Null score_grade count (non-货币)
    null_sql = "SELECT COUNT(*) AS cnt FROM fund_combined WHERE score_grade IS NULL AND t0 IS DISTINCT FROM '货币型';"
    resp = mgmt_query(null_sql)
    if resp is not None:
        data = resp.json()
        print(f"  Null score_grade (non-货币): {data[0]['cnt'] if data else '?'}", flush=True)

    # Verify 025457
    resp = rest_get("fund_combined", "c=eq.025457&select=c,name,k3m,k6m,k_all,score_grade")
    data = resp.json()
    if data:
        d = data[0]
        print(f"\n  025457: k3m={d.get('k3m')}, k6m={d.get('k6m')}, k_all={d.get('k_all')}, grade={d.get('score_grade')}", flush=True)

    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
