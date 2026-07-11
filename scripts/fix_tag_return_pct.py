#!/usr/bin/env python3
"""
从 fund_tag_funds.syl_1n 计算每个标签的平均近1年收益，更新 fund_tags.return_pct。
解决 fund_tags 全部正数的问题——真实数据应包含负数（白酒、银行、房地产等）。

用法：
  SUPABASE_PAT="$PAT" VITE_SUPABASE_ANON_KEY="$KEY" VITE_SUPABASE_URL="$URL" python3 scripts/fix_tag_return_pct.py
"""

import json
import os
import subprocess
import sys
from collections import defaultdict

SUPABASE_URL = os.environ.get("VITE_SUPABASE_URL", "")
ANON_KEY = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
PAT = os.environ.get("SUPABASE_PAT", "") or os.environ.get("SUPABASE_MGMT_TOKEN", "")

if not all([SUPABASE_URL, ANON_KEY, PAT]):
    print("[ERROR] 需要 VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, SUPABASE_PAT")
    sys.exit(1)

MGMT_URL = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"


def mgmt_query(sql: str) -> dict:
    """通过 Management API 执行 SQL"""
    cmd = [
        "curl", "-s", "-X", "POST", MGMT_URL,
        "-H", f"Authorization: Bearer {PAT}",
        "-H", "Content-Type: application/json",
        "--max-time", "30",
        "-d", json.dumps({"query": sql}),
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
    if out.stdout.strip():
        return json.loads(out.stdout)
    return {}


def rest_get(path: str) -> list:
    """Supabase REST GET"""
    cmd = [
        "curl", "-s",
        f"{SUPABASE_URL}/rest/v1/{path}",
        "-H", f"apikey: {ANON_KEY}",
        "-H", f"Authorization: Bearer {ANON_KEY}",
    ]
    out = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if out.stdout.strip():
        return json.loads(out.stdout)
    return []


def main():
    print("=" * 55)
    print("fix_tag_return_pct.py - 修复板块收益数据")
    print("=" * 55)

    # Step 1: 拉取 fund_tag_funds 全量 syl_1n
    print("\n[1/3] 拉取 fund_tag_funds 数据...")
    rows = rest_get("fund_tag_funds?select=tag_name,syl_1n")
    print(f"  共 {len(rows)} 条映射记录")

    # 按 tag_name 聚合
    tag_vals = defaultdict(list)
    for r in rows:
        name = r.get("tag_name")
        val = r.get("syl_1n")
        if name and val is not None:
            try:
                tag_vals[name].append(float(val))
            except (ValueError, TypeError):
                pass

    # 计算均值
    tag_avg = {}
    for name, vals in tag_vals.items():
        tag_avg[name] = round(sum(vals) / len(vals), 2)

    print(f"  覆盖 {len(tag_avg)} 个标签")
    negs = sorted(
        [(n, v) for n, v in tag_avg.items() if v < 0], key=lambda x: x[1]
    )
    pos_count = len(tag_avg) - len(negs)
    print(f"  正收益: {pos_count}, 负收益: {len(negs)}")
    if negs:
        print(f"  负收益 TOP10: {negs[:10]}")

    # Step 2: 批量 UPDATE fund_tags
    print(f"\n[2/3] 更新 fund_tags.return_pct...")
    names = list(tag_avg.keys())
    batch_size = 25
    updated = 0
    for i in range(0, len(names), batch_size):
        batch = names[i : i + batch_size]
        # 构建 CASE WHEN
        cases = []
        safe_names = []
        for n in batch:
            v = tag_avg[n]
            sn = n.replace("'", "''")
            cases.append(f" WHEN name='{sn}' THEN {v}")
            safe_names.append(f"'{sn}'")

        sql = (
            f"UPDATE fund_tags SET return_pct = CASE {' '.join(cases)} "
            f"ELSE return_pct END "
            f"WHERE name IN ({','.join(safe_names)});"
        )
        r = mgmt_query(sql)
        # Management API 成功返回 list（受影响行），失败返回 dict{error:...}
        if isinstance(r, dict) and r.get("error"):
            print(f"  警告: {r['error'][:200]}")
        updated += len(batch)
        if (i // batch_size + 1) % 3 == 0 or i + batch_size >= len(names):
            print(f"  进度: {min(i + batch_size, len(names))}/{len(names)}")

    print(f"  已提交更新 {updated} 个标签")

    # Step 3: 验证
    print(f"\n[3/3] 验证...")
    verify = rest_get("fund_tags?select=name,return_pct&order=return_pct.asc&limit=10")
    print(f"  最低10个:")
    for r in verify:
        print(f"    {r['name']}: {r['return_pct']}%")

    verify2 = rest_get("fund_tags?select=name,return_pct&order=return_pct.desc&limit=5")
    print(f"  最高5个:")
    for r in verify2:
        print(f"    {r['name']}: {r['return_pct']}%")

    neg_check = [r for r in verify if r.get("return_pct") is not None and r["return_pct"] < 0]
    pos_check = [r for r in verify if r.get("return_pct") is not None and r["return_pct"] >= 0]
    print(f"\n验证结果: 负收益={len(neg_check)}, 正收益={len(pos_check)}")
    print("=" * 55)


if __name__ == "__main__":
    main()
