#!/usr/bin/env python3
"""抓取上证指数历史日线数据并上传到 Supabase macro_history 表
用法: /usr/bin/python3 scripts/fetch_index_history.py
"""

import json, os, sys, time
from datetime import date
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
SUPABASE_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"

def supabase_request(method, path, body=None):
    url = f"{SUPABASE_URL}/rest/v1{path}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    data_bytes = json.dumps(body).encode() if body else None
    req = Request(url, data=data_bytes, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            if resp.status < 300:
                raw = resp.read().decode()
                return json.loads(raw) if raw and method == "GET" else None
            return None
    except HTTPError as e:
        err = e.read().decode() if e.fp else ""
        print(f"  API error {e.code}: {err[:200]}")
        return None

def main():
    print("=== Fetching 上证指数 (sh000001) daily history ===")

    # 1. Check existing data range
    path_check = f"/macro_history?select=date&metric=eq.sh000001&order=date.desc&limit=1"
    existing = supabase_request("GET", path_check)
    latest_db = existing[0]["date"] if existing else None
    print(f"  Existing latest date in DB: {latest_db}")

    # 2. Fetch from akshare
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol="sh000001")
    df = df.sort_values("date")
    print(f"  Fetched {len(df)} rows from akshare, range: {df['date'].iloc[0]} ~ {df['date'].iloc[-1]}")

    # 3. Filter only new data
    if latest_db:
        latest_db_date = str(latest_db)
        df = df[df["date"].astype(str) > latest_db_date]
        print(f"  New rows to insert: {len(df)}")
    else:
        print(f"  All {len(df)} rows are new (first import)")

    if len(df) == 0:
        print("  Nothing to insert. Done.")
        return

    # 4. Insert in batches
    rows = []
    for _, row in df.iterrows():
        rows.append({
            "date": str(row["date"])[:10],
            "metric": "sh000001",
            "value": round(float(row["close"]), 2),
            "source": "akshare:stock_zh_index_daily",
        })

    BATCH = 500
    total_inserted = 0
    for i in range(0, len(rows), BATCH):
        batch = rows[i:i+BATCH]
        supabase_request("POST", "/macro_history", batch)
        total_inserted += len(batch)
        pct = min(100, round((i + len(batch)) / len(rows) * 100))
        print(f"  Progress: {pct}% ({total_inserted}/{len(rows)})")
        if i + BATCH < len(rows):
            time.sleep(0.5)

    print(f"=== Done! Inserted {total_inserted} rows ===")

if __name__ == "__main__":
    main()
