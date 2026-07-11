#!/usr/bin/env python3
"""
一次性修复脚本：通过 Supabase Management API（PAT）创建 fund_tags 表并写入标签数据。
绕过 RLS，确保前端 fetchFundTags 能拿到数据。

用法（必须用正确的 PAT 覆盖沙箱里过期的 SUPABASE_MGMT_TOKEN）：
  SUPABASE_PAT="$PAT" SUPABASE_MGMT_TOKEN="$PAT" python3 scripts/setup_fund_tags.py
"""
import os, sys, time
import requests

sys.path.insert(0, os.path.dirname(__file__))
from fetch_fund_tags import get_builtin_tags, fetch_push2_sectors

REF = "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"

# 注意顺序：优先 SUPABASE_PAT（正确的），避免沙箱注入的过期 SUPABASE_MGMT_TOKEN
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
if not PAT:
    print("[ERROR] 需设置 SUPABASE_PAT"); sys.exit(1)

anon = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
base = os.environ.get("VITE_SUPABASE_URL", "https://tqhtegazxykkqfcpejky.supabase.co")


def mgmt(sql: str, label: str = ""):
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=60,
    )
    ok = r.status_code == 200
    print(f"  [{label}] HTTP {r.status_code} {'OK' if ok else r.text[:200]}")
    return ok


def esc(s: str) -> str:
    return s.replace("'", "''")


def main():
    # 1) 选取标签数据：默认优先 push2 实时；FORCE_BUILTIN=1 时强制用内置（来自天天基金 ztjj 页，共158个，return_pct 为百分比收益率）
    tags = []
    print("[1/3] 抓取标签数据源...")
    if os.environ.get("FORCE_BUILTIN"):
        tags = get_builtin_tags()
        print(f"  -> FORCE_BUILTIN：使用内置标签 {len(tags)} 个")
    else:
        try:
            api = fetch_push2_sectors()
            if len(api) >= 20:
                tags = api
                print(f"  -> 使用 push2 实时数据 {len(tags)} 个")
        except Exception as e:
            print(f"  push2 失败: {e}")
    if len(tags) < 50:
        tags = get_builtin_tags()
        print(f"  -> 使用内置标签 {len(tags)} 个")

    # 2) 建表（逐条执行，确保 Management API 全部跑完）
    print("\n[2/3] 创建 fund_tags 表...")
    mgmt("DROP TABLE IF EXISTS public.fund_tags;", "drop")
    mgmt(
        "CREATE TABLE public.fund_tags ("
        " id BIGSERIAL PRIMARY KEY,"
        " name TEXT NOT NULL,"
        " tag_type TEXT NOT NULL CHECK (tag_type IN ('concept','industry')),"
        " return_pct DOUBLE PRECISION,"
        " sort_order INT DEFAULT 0,"
        " updated_at TIMESTAMPTZ DEFAULT NOW(),"
        " UNIQUE(name, tag_type));",
        "create",
    )
    mgmt("ALTER TABLE public.fund_tags ENABLE ROW LEVEL SECURITY;", "rls")
    mgmt('DROP POLICY IF EXISTS "anon_select_fund_tags" ON public.fund_tags;', "drop_policy")
    mgmt(
        'CREATE POLICY "anon_select_fund_tags" ON public.fund_tags FOR SELECT USING (true);',
        "policy",
    )

    # 3) 插入数据
    print(f"\n[3/3] 写入 {len(tags)} 个标签...")
    rows = []
    for t in tags:
        rp = "NULL" if t.get("return_pct") is None else str(t["return_pct"])
        rows.append(f"('{esc(t['name'])}','{t['tag_type']}',{rp},{t['sort_order']})")
    # 分批 INSERT，每批 100
    for i in range(0, len(rows), 100):
        chunk = ",".join(rows[i:i + 100])
        sql = f"INSERT INTO public.fund_tags (name, tag_type, return_pct, sort_order) VALUES {chunk};"
        mgmt(sql, f"insert {i // 100 + 1}")

    # 4) 验证（用 anon key 走 REST，模拟前端）
    print("\n[验证] 用 anon key 查询 fund_tags...")
    try:
        vr = requests.get(
            f"{base}/rest/v1/fund_tags?select=name,tag_type&limit=5&order=sort_order.asc",
            headers={"apikey": anon, "Authorization": f"Bearer {anon}", "Prefer": "count=exact"},
            timeout=20,
        )
        print(f"  anon HTTP {vr.status_code} range={vr.headers.get('content-range')}")
        print(f"  sample: {vr.text[:300]}")
    except Exception as e:
        print(f"  验证失败: {e}")

    print("\n完成。")


if __name__ == "__main__":
    main()
