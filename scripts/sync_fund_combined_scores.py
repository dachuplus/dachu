#!/usr/bin/env python3
"""
同步 fund_combined 评分 —— 按「数据模型规则」(docs/data-model-rules.md) 执行：

  • fund_combined 的评分【基于 fund_quarterly_scores】（季度引擎）计算，
    而非从 fund_scores 复制。字段映射：
        fund_quarterly_scores.score_3m → fund_combined.k3m
        fund_quarterly_scores.score_6m → fund_combined.k6m
        fund_quarterly_scores.score_1y → fund_combined.k1
        fund_quarterly_scores.score_2y → fund_combined.k2
        fund_quarterly_scores.score_3y → fund_combined.k3
        fund_quarterly_scores.score_5y → fund_combined.k5
  • 已知例外：fund_quarterly_scores 不提供「成立以来」(k0w) 与「1 个月」(k1m)
    窗口，这两个周期在 fund_combined 中沿用 fund_scores 的对应值。
  • 优雅降级：若某基金在 fund_quarterly_scores 中缺对应评分，则保留 fund_combined
    现有值（即上一次同步值），保证评分列永不为 NULL。
  • k_all 由上述各周期分按 v7 权重重算；score_grade 由 k_all 全市场百分位重算。

  注意：fund_scores 的评分是【独立】引擎（日历对齐百分位），本脚本绝不读写
  fund_scores 的评分来作为 fund_combined 的评分来源（k0w/k1m 例外已在上方说明）。

用法：
  python3 sync_fund_combined_scores.py
（需 SUPABASE_MGMT_TOKEN 环境变量；CI 中由 promote_staging.py 调用）
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

# v7 权重（与 import_via_rest.py 一致）
PERIOD_W = {'k0w': 5, 'k1m': 5, 'k3m': 10, 'k6m': 15, 'k1': 20, 'k2': 20, 'k3': 15, 'k5': 10}

# fund_quarterly_scores → fund_combined 字段映射
QS_MAP = [
    ('score_3m', 'k3m'),
    ('score_6m', 'k6m'),
    ('score_1y', 'k1'),
    ('score_2y', 'k2'),
    ('score_3y', 'k3'),
    ('score_5y', 'k5'),
]


def mgmt_query(query_str):
    """执行 SQL：优先 psycopg2 直连（SUPABASE_DB_URL），否则 PAT 兜底。返回兼容 requests.Response 的包装（含 .json()/.status_code）。"""
    from _db import run_sql as _db_run_sql
    class _JSONResponse:
        def __init__(self, data):
            self.status_code = 200
            self._data = data if data is not None else []
        def json(self):
            return self._data
    try:
        data = _db_run_sql(query_str)
    except Exception as e:
        print(f"  SQL ERROR: {str(e)[:300]}", flush=True)
        class _ErrResp:
            status_code = 500
            def json(self): return []
        return _ErrResp()
    return _JSONResponse(data)


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
    print(" Sync fund_combined ← fund_quarterly_scores (按数据模型规则)", flush=True)
    print("=" * 60, flush=True)

    # ── Phase 0: 确保 fund_combined 含 fund_manager 列 ──
    print("\n[Phase 0] Ensure fund_manager column on fund_combined...", flush=True)
    mgmt_query("ALTER TABLE fund_combined ADD COLUMN IF NOT EXISTS fund_manager text;")
    print("  Phase 0 DONE", flush=True)

    # ── Phase 1: 从 fund_quarterly_scores 派生 k3m/k6m/k1/k2/k3/k5 ──
    # 仅更新在 fund_quarterly_scores 中存在匹配行的基金；缺失时 COALESCE 保留现有值。
    print("\n[Phase 1] UPDATE 评分列 (k3m/k6m/k1/k2/k3/k5) FROM fund_quarterly_scores...", flush=True)
    set_clauses = ", ".join(
        f"{fc} = COALESCE(q.{qs}, fc.{fc})" for qs, fc in QS_MAP
    )
    update_sql = f"""
    UPDATE fund_combined fc
    SET {set_clauses}
    FROM fund_quarterly_scores q
    WHERE fc.c = q.c;
    """
    resp = mgmt_query(update_sql)
    if resp is None:
        print("  Phase 1 FAILED! 保留 fund_combined 现有评分。", flush=True)
    else:
        print("  Phase 1 DONE (已按 fund_quarterly_scores 派生 6 个周期分)", flush=True)

    # ── Phase 1b: 补 fund_manager（来自 fund_scores，属详情字段而非评分）──
    print("\n[Phase 1b] 补 fund_manager FROM fund_scores...", flush=True)
    mgmt_query("""
    UPDATE fund_combined fc
    SET fund_manager = fs.fund_manager
    FROM fund_scores fs
    WHERE fc.c = REPLACE(fs.c, '.OF', '')
      AND (fc.fund_manager IS NULL OR fc.fund_manager = '')
      AND fs.fund_manager IS NOT NULL;
    """)

    # ── Phase 2: 重算 k_all（v7 权重，跨 8 个周期，缺失窗口不计入分母）──
    print("\n[Phase 2] 重算 k_all (v7 权重)...", flush=True)
    num_parts, den_parts = [], []
    for col, w in PERIOD_W.items():
        num_parts.append(f"COALESCE({col},0)*{w}")
        den_parts.append(f"(CASE WHEN {col} IS NOT NULL THEN {w} ELSE 0 END)")
    num = " + ".join(num_parts)
    den = " + ".join(den_parts)
    k_all_sql = f"""
    UPDATE fund_combined
    SET k_all = (
        SELECT ({num}) / NULLIF(({den}), 0)
        FROM fund_combined f2
        WHERE f2.c = fund_combined.c
    )
    WHERE k0w IS NOT NULL OR k1m IS NOT NULL OR k3m IS NOT NULL
       OR k6m IS NOT NULL OR k1 IS NOT NULL OR k2 IS NOT NULL
       OR k3 IS NOT NULL OR k5 IS NOT NULL;
    """
    resp = mgmt_query(k_all_sql)
    if resp is None:
        print("  Phase 2 FAILED!", flush=True)
    else:
        print("  Phase 2 DONE", flush=True)

    # ── Phase 3: 重算 score_grade（k_all 全市场百分位：≥80% 绿 / ≥50% 蓝 / 其余 橙）──
    print("\n[Phase 3] 重算 score_grade (k_all 百分位)...", flush=True)
    grade_sql = """
    WITH ranked AS (
        SELECT c, NTILE(100) OVER (ORDER BY k_all DESC) AS pct
        FROM fund_combined
        WHERE k_all IS NOT NULL
    )
    UPDATE fund_combined fc
    SET score_grade = CASE
        WHEN r.pct <= 20 THEN 'green'
        WHEN r.pct <= 50 THEN 'blue'
        ELSE 'orange'
    END
    FROM ranked r
    WHERE r.c = fc.c;
    """
    resp = mgmt_query(grade_sql)
    if resp is None:
        print("  Phase 3 FAILED!", flush=True)
    else:
        print("  Phase 3 DONE", flush=True)

    # ── Phase 4: INSERT 新基金（在 fund_scores 但不在 fund_combined）──
    print("\n[Phase 4] Find & INSERT new funds...", flush=True)
    find_new_sql = """
    SELECT REPLACE(fs.c, '.OF', '') AS code
    FROM fund_scores fs
    WHERE NOT EXISTS (
        SELECT 1 FROM fund_combined fc WHERE fc.c = REPLACE(fs.c, '.OF', '')
    );
    """
    resp = mgmt_query(find_new_sql)
    if resp is None:
        print("  Phase 4: Failed to find new funds", flush=True)
        new_codes = []
    else:
        result = resp.json()
        new_codes = [r["code"] for r in result]

    print(f"  New funds to insert: {len(new_codes)}", flush=True)

    if not new_codes:
        print("  Phase 4: Nothing to insert", flush=True)
    else:
        # 新基金的季度分：优先 fund_quarterly_scores，缺失则 fund_scores
        q_map = {}
        for i in range(0, len(new_codes), 100):
            batch = new_codes[i:i+100]
            codes_str = ",".join(batch)
            resp = rest_get("fund_quarterly_scores",
                            f"c=in.({codes_str})&select=c,score_3m,score_6m,score_1y,score_2y,score_3y,score_5y")
            data = resp.json() if resp.status_code == 200 else []
            for r in data:
                q_map[r["c"]] = r

        fs_map = {}
        for i in range(0, len(new_codes), 100):
            batch = new_codes[i:i+100]
            of_codes = ",".join(f"{c}.OF" for c in batch)
            resp = rest_get("fund_scores",
                            f"c=in.({of_codes})&select=c,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k_all,score_grade,fund_manager")
            data = resp.json()
            for s in data:
                fs_map[s["c"].replace(".OF", "")] = s

        raw_map = {}
        for i in range(0, len(new_codes), 100):
            batch = new_codes[i:i+100]
            codes_str = ",".join(batch)
            resp = rest_get("fund_raw_sample",
                            f"c=in.({codes_str})&select=c,name,t0,t1,company,fund_scale,risk_level,manage_fee,ytd,r1y,r3y,r5y,dd1y,sr1y,holders_count,total_manage_scale")
            data = resp.json() if resp.status_code == 200 else []
            if isinstance(data, dict) and "message" in data:
                data = []
            for r in data:
                raw_map[r["c"]] = r

        columns = [
            "c", "name", "t0", "t1", "company", "fund_scale", "risk_level", "manage_fee",
            "ytd", "r1y", "r3y", "r5y", "dd1y", "sr1y", "holders_count", "total_manage_scale",
            "k0w", "k1m", "k3m", "k6m", "k1", "k2", "k3", "k5", "k_all", "score_grade",
            "fund_manager"
        ]

        def qval(code, qs, fb):
            """新基金季度分：优先 fund_quarterly_scores，缺失回退 fund_scores"""
            q = q_map.get(code)
            if q and q.get(qs) is not None:
                return q.get(qs)
            fs = fs_map.get(code)
            return fs.get(fb) if fs else None

        def esc(v):
            if v is None:
                return "NULL"
            if isinstance(v, bool):
                return "TRUE" if v else "FALSE"
            if isinstance(v, (int, float)):
                return repr(v)
            return "'" + str(v).replace("'", "''") + "'"

        inserted = 0
        value_batch = []
        for code in new_codes:
            fs = fs_map.get(code)
            r = raw_map.get(code)
            s = {
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
                # 评分：k0w/k1m 仅 fund_scores 有；其余优先 fund_quarterly_scores
                "k0w": fs.get("k0w") if fs else None,
                "k1m": fs.get("k1m") if fs else None,
                "k3m": qval(code, "score_3m", "k3m"),
                "k6m": qval(code, "score_6m", "k6m"),
                "k1": qval(code, "score_1y", "k1"),
                "k2": qval(code, "score_2y", "k2"),
                "k3": qval(code, "score_3y", "k3"),
                "k5": qval(code, "score_5y", "k5"),
                "k_all": fs.get("k_all") if fs else None,
                "score_grade": fs.get("score_grade", "") if fs else "",
                "fund_manager": fs.get("fund_manager") if fs else None,
            }
            vals = [esc(s[col]) for col in columns]
            value_batch.append("(" + ", ".join(vals) + ")")
            if len(value_batch) >= 100:
                query = f'INSERT INTO fund_combined ({", ".join(columns)}) VALUES {", ".join(value_batch)} ON CONFLICT (c) DO NOTHING;'
                resp = mgmt_query(query)
                if resp is not None:
                    inserted += len(value_batch)
                value_batch = []
                time.sleep(0.1)
        if value_batch:
            query = f'INSERT INTO fund_combined ({", ".join(columns)}) VALUES {", ".join(value_batch)} ON CONFLICT (c) DO NOTHING;'
            resp = mgmt_query(query)
            if resp is not None:
                inserted += len(value_batch)
        print(f"  INSERT: {inserted} 条", flush=True)

    # ── Verify ──
    print("\n[Verify] Checking results...", flush=True)
    resp = mgmt_query("SELECT COUNT(*) AS cnt FROM fund_combined")
    total = 0
    if resp is not None:
        data = resp.json()
        if data and isinstance(data, list) and len(data) > 0:
            total = data[0].get('cnt', 0)
    print(f"  Total rows: {total}", flush=True)

    dist_sql = "SELECT score_grade, COUNT(*) AS cnt FROM fund_combined GROUP BY score_grade ORDER BY cnt DESC;"
    resp = mgmt_query(dist_sql)
    if resp is not None:
        print("  Rating distribution:", flush=True)
        for r in resp.json():
            grade = r["score_grade"] or "NULL"
            print(f"    {grade}: {r['cnt']}", flush=True)

    null_sql = "SELECT COUNT(*) AS cnt FROM fund_combined WHERE score_grade IS NULL AND t0 IS DISTINCT FROM '货币型';"
    resp = mgmt_query(null_sql)
    if resp is not None:
        data = resp.json()
        print(f"  Null score_grade (non-货币): {data[0]['cnt'] if data else '?'}", flush=True)

    print("\nDone!", flush=True)


if __name__ == "__main__":
    main()
