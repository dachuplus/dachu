#!/usr/bin/env python3
"""
基金经理空值回填 + 真无经理标记（'--'）

每日 CI 在 promote_staging 之后运行：
  - 读取 fund_scores / fund_combined 中 fund_manager 为空的基金
  - 对每只重新抓取 天天基金 fundf10 jbgk（fetch_one）：
      * 抓到经理        → 回填（属于"漏抓"，非真无）
      * 页面有但无经理  → 置 '--'（确属"无基金经理"，如极少部分特殊基金）
      * 抓取失败(网络)  → 保持不变，计入 fetch_failed（避免把瞬时限流误判为"无经理"）
  - 批量 UPDATE fund_scores 与 fund_combined（两表均补齐，保持下载数据一致）

用法：
  python3 fix_manager_blanks.py
（需 SUPABASE_MGMT_TOKEN 环境变量；CI 中 promote_staging 之后调用）
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fund_basic_info import fetch_one

MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN") or os.environ.get("SUPABASE_PAT") or ''
PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF") or "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
ANON_KEY = os.environ.get("SUPABASE_ANON_KEY") or os.environ.get("VITE_SUPABASE_ANON_KEY") or "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
SUPABASE_URL = f"https://{PROJECT_REF}.supabase.co"
HEADERS_REST = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}
HEADERS_MGMT = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}


def mgmt_query(sql):
    r = __import__("requests").post(MGMT_URL, headers=HEADERS_MGMT, json={"query": sql}, timeout=120)
    if r.status_code not in (200, 201):
        print(f"  SQL ERROR ({r.status_code}): {r.text[:300]}", flush=True)
        return None
    return r


def rest_get_all(table, select, batch=1000):
    out, offset = [], 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/{table}?select={select}&limit={batch}&offset={offset}"
        r = __import__("requests").get(url, headers=HEADERS_REST, timeout=30)
        if r.status_code != 200:
            break
        batch_rows = r.json()
        if not batch_rows:
            break
        out.extend(batch_rows)
        offset += len(batch_rows)
        if len(batch_rows) < batch:
            break
    return out


def get_empty_codes():
    """返回 fund_scores 中 fund_manager 为空的代码（带 .OF）"""
    rows = rest_get_all("fund_scores", "c,fund_manager")
    return [x["c"] for x in rows if not x.get("fund_manager")]


def esc(s):
    return str(s).replace("'", "''")


def main():
    print("=" * 60, flush=True)
    print(" 基金经理空值回填 + '--' 标记（基于 jbgk 复核）", flush=True)
    print("=" * 60, flush=True)

    codes = get_empty_codes()
    print(f"\nfund_manager 为空: {len(codes)} 只", flush=True)
    if not codes:
        print("无需处理，退出。", flush=True)
        return

    # 并发复核：抓 jbgk 确认"漏抓"还是"真无经理"
    backfill = {}     # code(.OF) -> 经理名
    genuine = set()   # code(.OF) 确无经理
    fetch_failed = 0
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c.replace(".OF", "")): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            c = futs[fut]
            done += 1
            _, parsed, err = fut.result()
            if parsed and parsed.get("fund_manager"):
                backfill[c] = parsed["fund_manager"]
            elif parsed and not parsed.get("fund_manager"):
                genuine.add(c)            # 页面有数据但无经理字段 → 确无
            else:
                fetch_failed += 1         # 抓取失败 → 不轻信为"无经理"
            if done % 500 == 0:
                print(f"  复核进度 {done}/{len(codes)} 回填{len(backfill)} 真无{len(genuine)} 失败{fetch_failed} ({time.time()-t0:.0f}s)", flush=True)

    print(f"\n复核完成: 回填 {len(backfill)} | 真无经理 '--' {len(genuine)} | 抓取失败(保留) {fetch_failed}", flush=True)

    # 批量 UPDATE fund_scores
    def batch_update(mapping, marker_set):
        if not mapping and not marker_set:
            return 0
        items = list(mapping.items())
        ok = 0
        # 回填
        for i in range(0, len(items), 200):
            chunk = items[i:i + 200]
            whens = " ".join(f"WHEN c='{esc(k)}' THEN '{esc(v)}'" for k, v in chunk)
            sql = (f"UPDATE fund_scores SET fund_manager = CASE {whens} "
                   f"ELSE fund_manager END WHERE c IN ({','.join(repr(k) for k, _ in chunk)});")
            if mgmt_query(sql) is not None:
                ok += len(chunk)
        # 真无经理 → '--'
        if marker_set:
            codes_str = ",".join(repr(c) for c in marker_set)
            sql = f"UPDATE fund_scores SET fund_manager = '--' WHERE c IN ({codes_str});"
            if mgmt_query(sql) is not None:
                ok += len(marker_set)
        return ok

    n1 = batch_update(backfill, genuine)
    print(f"✅ fund_scores 已更新: {n1} 只", flush=True)

    # 同步 fund_combined（c 不带 .OF）
    def batch_update_combined(mapping, marker_set):
        if not mapping and not marker_set:
            return 0
        ok = 0
        items = [(c.replace(".OF", ""), v) for c, v in mapping.items()]
        for i in range(0, len(items), 200):
            chunk = items[i:i + 200]
            whens = " ".join(f"WHEN c='{esc(k)}' THEN '{esc(v)}'" for k, v in chunk)
            sql = (f"UPDATE fund_combined SET fund_manager = CASE {whens} "
                   f"ELSE fund_manager END WHERE c IN ({','.join(repr(k) for k, _ in chunk)});")
            if mgmt_query(sql) is not None:
                ok += len(chunk)
        if marker_set:
            codes_str = ",".join(repr(c.replace(".OF", "")) for c in marker_set)
            sql = f"UPDATE fund_combined SET fund_manager = '--' WHERE c IN ({codes_str});"
            if mgmt_query(sql) is not None:
                ok += len(marker_set)
        return ok

    n2 = batch_update_combined(backfill, genuine)
    print(f"✅ fund_combined 已更新: {n2} 只", flush=True)

    print(f"\nDone. 回填{len(backfill)} 真无经理{len(genuine)} 抓取失败{fetch_failed}", flush=True)


if __name__ == "__main__":
    main()
