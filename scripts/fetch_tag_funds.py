#!/usr/bin/env python3
"""
标签-基金关联数据 ETL 脚本。
从东财 FundGuideAPI (dt=1) 抓取每个标签的关联基金，写入 Supabase fund_tag_funds 表。

用法：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_tag_funds.py

依赖：requests（managed venv 已安装）
"""
import os, sys, time, json, re, urllib.request

# ── 配置 ──────────────────────────────────────────────
REF = "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
if not PAT:
    print("[ERROR] 需设置 SUPABASE_PAT"); sys.exit(1)

ANON = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
BASE = os.environ.get("VITE_SUPABASE_URL", f"https://{REF}.supabase.co")

API_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
               "Referer": "https://fund.eastmoney.com/ztjj/"}


def mgmt(sql: str, label: str = "") -> bool:
    """通过 Management API 执行 SQL（用于 DDL / 大批量写入）"""
    import requests as req_lib
    r = req_lib.post(MGMT_URL,
                     headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                     json={"query": sql}, timeout=120)
    ok = r.status_code == 200
    print(f"  [mgmt:{label}] HTTP {r.status_code} {'OK' if ok else r.text[:200]}")
    return ok


def esc(s: str) -> str:
    return s.replace("'", "''")


def fetch_tags_from_db():
    """从 fund_tags 表读取所有标签"""
    import requests as req_lib
    all_tags = []
    offset = 0
    limit = 200
    while True:
        r = req_lib.get(f"{BASE}/rest/v1/fund_tags?select=name,tag_type&order=sort_order.asc&limit={limit}&offset={offset}",
                        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"}, timeout=20)
        data = r.json()
        if not data:
            break
        all_tags.extend(data)
        if len(data) < limit:
            break
        offset += limit
    return all_tags


def fetch_topic_funds(tag_name: str, max_count: int = 10) -> list:
    """
    从东财 FundGuideAPI (dt=1) 获取标签关联的基金列表。
    返回 [{bzdm, shortname, jjgs, FType, syl}, ...]
    """
    url = (f"https://fund.eastmoney.com/data/FundGuideapi.aspx"
           f"?dt=1&ft=hb&sd=&ed=&sc=dwsyl&st=desc&pi=1&pn={max_count}"
           f"&zf={urllib.request.quote(tag_name)}&sh=list")
    try:
        req = urllib.request.Request(url, headers=API_HEADERS)
        resp = urllib.request.urlopen(req, timeout=20)
        text = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r"rankData\s*=\s*(\[.*?\])\s*;?", text, re.DOTALL)
        if m:
            return json.loads(m.group(1))
        return []
    except Exception as e:
        print(f"    [WARN] {tag_name}: {e}")
        return []


def main():
    # 1) 读标签
    print("[1/4] 从 fund_tags 表读取标签...")
    tags = fetch_tags_from_db()
    print(f"  共 {len(tags)} 个标签")

    if not tags:
        print("[ERROR] fund_tags 表为空，请先运行 setup_fund_tags.py")
        sys.exit(1)

    # 2) 建表
    print("\n[2/4] 创建 fund_tag_funds 表...")
    mgmt("DROP TABLE IF EXISTS public.fund_tag_funds;", "drop_old")
    mgmt(
        "CREATE TABLE public.fund_tag_funds ("
        " id BIGSERIAL PRIMARY KEY,"
        " tag_name TEXT NOT NULL,"
        " fund_code TEXT NOT NULL,"
        " fund_name TEXT NOT NULL,"
        " fund_company TEXT,"
        " fund_type TEXT,"
        " return_pct DOUBLE PRECISION,"
        " sort_order INT DEFAULT 0,"
        " updated_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "create",
    )
    mgmt("CREATE INDEX IF NOT EXISTS idx_ftf_tag ON public.fund_tag_funds(tag_name);", "idx_tag")
    mgmt("CREATE INDEX IF NOT EXISTS idx_ftf_code ON public.fund_tag_funds(fund_code);", "idx_code")
    mgmt("ALTER TABLE public.fund_tag_funds ENABLE ROW LEVEL SECURITY;", "rls")
    mgmt("DROP POLICY IF EXISTS \"anon_select_fund_tag_funds\" ON public.fund_tag_funds;", "drop_pol")
    mgmt("CREATE POLICY \"anon_select_fund_tag_funds\" ON public.fund_tag_funds FOR SELECT USING (true);", "pol")

    # 3) 逐标签抓取关联基金
    print(f"\n[3/4] 抓取标签-基金映射（{len(tags)} 个标签）...")
    all_rows = []
    empty_tags = []
    for i, tag in enumerate(tags):
        tname = tag["name"]
        funds = fetch_topic_funds(tname, max_count=10)
        if funds:
            for j, f in enumerate(funds):
                code = f.get("bzdm", "").strip()
                fname = f.get("shortname", "").strip()
                if not code or not fname:
                    continue
                company = f.get("jjgs", "") or ""
                ftype = f.get("FType", "") or ""
                syl = f.get("syl")
                try:
                    syl_val = float(syl) if syl is not None else None
                except (ValueError, TypeError):
                    syl_val = None
                all_rows.append((
                    esc(tname), esc(code), esc(fname),
                    esc(company), esc(ftype),
                    "NULL" if syl_val is None else str(syl_val),
                    j + 1,
                ))
        else:
            empty_tags.append(tname)

        if (i + 1) % 20 == 0 or i == len(tags) - 1:
            print(f"  进度: {i+1}/{len(tags)} | 累计映射 {len(all_rows)} 条")

        time.sleep(0.15)  # 礼貌限速

    if empty_tags:
        print(f"\n  ⚠ {len(empty_tags)} 个标签未获取到基金: {empty_tags[:20]}")

    # 4) 批量写入
    print(f"\n[4/4] 写入 {len(all_rows)} 条映射...")
    if all_rows:
        for batch_start in range(0, len(all_rows), 200):
            chunk = all_rows[batch_start:batch_start + 200]
            values = ",".join(
                f"('{r[0]}','{r[1]}','{r[2]}','{r[3]}','{r[4]}',{r[5]},{r[6]})"
                for r in chunk
            )
            sql = (f"INSERT INTO public.fund_tag_funds "
                   f"(tag_name, fund_code, fund_name, fund_company, fund_type, return_pct, sort_order) "
                   f"VALUES {values};")
            mgmt(sql, f"insert_batch_{batch_start // 200 + 1}")

    # 5) 验证
    print("\n[验证] 随机抽查...")
    # 查光模块的关联基金
    import requests as req_lib
    vr = req_lib.get(
        f"{BASE}/rest/v1/fund_tag_funds?tag_name=eq.%E5%85%89%E6%A8%A1%E5%9D%97&select=fund_code,fund_name,fund_type,return_pct&order=sort_order.asc",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"}, timeout=20,
    )
    if vr.ok:
        data = vr.json()
        print(f"  光模块 -> {len(data)} 只基金:")
        for f in data[:5]:
            print(f"    {f['fund_code']} | {f['fund_name']} | {f.get('fund_type','')} | {f.get('return_pct')}%")

    # 统计有/无映射的标签数
    vr2 = req_lib.get(
        f"{BASE}/rest/v1/fund_tag_funds?select=tag_name",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}",
                 "Prefer": "count=exact"}, timeout=20,
    )
    total_mapped = int(vr2.headers.get("content-range", "/0").split("/")[-1]) if "/" in vr2.headers.get("content-range", "") else 0
    print(f"\n  总映射条数: ~{total_mapped}")
    print(f"  有基金的标签: {len(tags) - len(empty_tags)}/{len(tags)}")
    print(f"  无基金的标签: {len(empty_tags)}/{len(tags)}")

    print("\n完成。")


if __name__ == "__main__":
    main()
