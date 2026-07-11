#!/usr/bin/env python3
"""
标签-基金关联数据 ETL 脚本（v2 - 使用正确的东财API）。

使用东财官方 ztjj 页面同款接口：
  1. GetBKListByBKTypeNew → 获取所有标签（含内部 INDEXCODE）
  2. GetBKRelTopicFundNew → 按 INDEXCODE 查询每个标签的真实关联基金

替换旧版 FundGuideAPI（该接口返回错误数据，如光模块→富国医药创新股票C）。

用法：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_tag_funds_v2.py

依赖：标准库（urllib/json/re）
"""

import os, sys, time, json, re, urllib.request, urllib.parse, urllib.error

# ── 配置 ──────────────────────────────────────────────
REF = "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
if not PAT:
    print("[ERROR] 需设置 SUPABASE_PAT"); sys.exit(1)

ANON = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
BASE = os.environ.get("VITE_SUPABASE_URL", f"https://{REF}.supabase.co")

# 东财 API
EM_API_BASE = "http://api.fund.eastmoney.com"
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://fund.eastmoney.com/ztjj/",
}


def mgmt(sql: str, label: str = "") -> bool:
    """通过 Management API 执行 SQL"""
    import requests as req_lib
    r = req_lib.post(MGMT_URL,
                     headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
                     json={"query": sql}, timeout=120)
    ok = r.status_code in (200, 201)
    print(f"  [mgmt:{label}] HTTP {r.status_code} {'OK' if ok else r.text[:200]}")
    return ok


def esc(s: str) -> str:
    return s.replace("'", "''")


def em_get(url: str) -> dict | list | None:
    """调用东财 JSONP API，返回解析后的数据"""
    req = urllib.request.Request(url, headers=EM_HEADERS)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        raw = resp.read().decode("utf-8", errors="ignore")
        m = re.search(r"\((\{.*\})\)", raw, re.DOTALL)
        if m:
            data = json.loads(m.group(1))
            if data.get("ErrCode") == 0:
                return data.get("Data")
            print(f"    [WARN] API ErrCode={data.get('ErrCode')}")
            return None
        # 可能不是JSONP格式
        try:
            return json.loads(raw)
        except:
            print(f"    [WARN] 无法解析响应，长度={len(raw)}")
            return None
    except Exception as e:
        print(f"    [ERROR] {e}")
        return None


def fetch_all_tags() -> list:
    """从东财获取所有标签列表（含 INDEXCODE）

    返回 [(INDEXCODE, INDEXNAME, tag_type), ...]
      tag_type: 'industry' (hy1/hy2) 或 'concept' (gn)
    """
    url = f"{EM_API_BASE}/ZTJJ/GetBKListByBKTypeNew?callback=?"
    data = em_get(url)

    if not data or not isinstance(data, dict):
        print("[ERROR] 无法获取标签列表")
        return []

    tags = []
    # hy1, hy2 = 行业; gn = 概念
    type_map = {"hy1": "industry", "hy2": "industry", "gn": "concept"}

    for cat_key, tag_type in type_map.items():
        items = data.get(cat_key, [])
        for item in items:
            code = item.get("INDEXCODE", "")
            name = item.get("INDEXNAME", "")
            if code and name:
                tags.append((code, name, tag_type))

    # 去重（按INDEXCODE）
    seen = set()
    unique = []
    for t in tags:
        if t[0] not in seen:
            seen.add(t[0])
            unique.append(t)

    return unique


def fetch_tag_funds(index_code: str, max_count: int = 15) -> list:
    """
    用 GetBKRelTopicFundNew 查询标签关联基金。

    返回 [{FCODE, SHORTNAME, FTYPE, SYL_1N, SYL_D, RELATION, ...}, ...]
    """
    params = urllib.parse.urlencode({
        "callback": "?",
        "sort": "SYL_D",       # 成立来收益排序
        "sorttype": "DESC",
        "pageindex": "1",
        "pagesize": str(max_count),
        "tp": index_code,
        "isbuy": "0",         # 包含已下架
    })
    url = f"{EM_API_BASE}/ZTJJ/GetBKRelTopicFundNew?{params}"
    data = em_get(url)

    if isinstance(data, list):
        return data[:max_count]
    elif isinstance(data, dict):
        # 某些情况下可能是 {Datas: [...], Tot: N}
        return data.get("Datas", [])[:max_count]

    return []


def main():
    # 1) 获取标签列表（含ID）
    print("[1/4] 从东财获取标签列表...")
    tags = fetch_all_tags()
    print(f"  共 {len(tags)} 个标签")

    if not tags:
        print("[ERROR] 标签列表为空"); sys.exit(1)

    # 统计类型分布
    type_count = {}
    for _, _, tt in tags:
        type_count[tt] = type_count.get(tt, 0) + 1
    print(f"  分布: {type_count}")

    # 2) 重建表
    print("\n[2/4] 重建 fund_tag_funds 表...")
    mgmt("DROP TABLE IF EXISTS public.fund_tag_funds;", "drop_old")
    mgmt(
        "CREATE TABLE public.fund_tag_funds ("
        " id BIGSERIAL PRIMARY KEY,"
        " tag_name TEXT NOT NULL,"
        " tag_index_code TEXT NOT NULL,"
        " fund_code TEXT NOT NULL,"
        " fund_name TEXT NOT NULL,"
        " fund_type TEXT,"
        " syl_1n DOUBLE PRECISION,"       # 近1年收益率
        " syl_d DOUBLE PRECISION,"        # 成立来收益率
        " relation DOUBLE PRECISION,"     # 关联度/相关性
        " sort_order INT DEFAULT 0,"
        " updated_at TIMESTAMPTZ DEFAULT NOW()"
        ");",
        "create",
    )
    mgmt("CREATE INDEX IF NOT EXISTS idx_ftf_tag ON public.fund_tag_funds(tag_name);", "idx_tag")
    mgmt("CREATE INDEX IF NOT EXISTS idx_ftf_code ON public.fund_tag_funds(fund_code);", "idx_code")
    mgmt("CREATE INDEX IF NOT EXISTS idx_ftf_idxcode ON public.fund_tag_funds(tag_index_code);", "idxcode")
    mgmt("ALTER TABLE public.fund_tag_funds ENABLE ROW LEVEL SECURITY;", "rls")
    mgmt("DROP POLICY IF EXISTS \"anon_select_fund_tag_funds\" ON public.fund_tag_funds;", "drop_pol")
    mgmt("CREATE POLICY \"anon_select_fund_tag_funds\" ON public.fund_tag_funds FOR SELECT USING (true);", "pol")

    # 3) 逐标签抓取
    print(f"\n[3/4] 抓取标签-基金映射（{len(tags)} 个标签）...")
    all_rows = []
    empty_tags = []
    error_tags = []

    for i, (idx_code, tag_name, tag_type) in enumerate(tags):
        funds = fetch_tag_funds(idx_code, max_count=15)

        if funds:
            for j, f in enumerate(funds):
                code = str(f.get("FCODE", "")).strip()
                fname = str(f.get("SHORTNAME", "")).strip()
                if not code or not fname:
                    continue

                ftype = f.get("FTYPE") or ""
                syl_1n = f.get("SYL_1N")
                syl_d = f.get("SYL_D")
                relation = f.get("RELATION")

                def fmt_val(v):
                    if v is None:
                        return "NULL"
                    try:
                        return str(float(v))
                    except (ValueError, TypeError):
                        return "NULL"

                all_rows.append((
                    esc(tag_name), esc(idx_code), esc(code), esc(fname),
                    esc(ftype),
                    fmt_val(syl_1n), fmt_val(syl_d), fmt_val(relation),
                    j + 1,
                ))
        else:
            empty_tags.append(tag_name)

        if (i + 1) % 20 == 0 or i == len(tags) - 1:
            print(f"  进度: {i+1}/{len(tags)} | 累计映射 {len(all_rows)} 条 | 空 {len(empty_tags)}")

        time.sleep(0.12)  # 礼貌限速

    if empty_tags:
        print(f"\n  ⚠ {len(empty_tags)} 个标签无关联基金: {empty_tags[:20]}")
    if error_tags:
        print(f"  ❌ {len(error_tags)} 个标签抓取失败")

    # 4) 批量写入
    print(f"\n[4/4] 写入 {len(all_rows)} 条映射...")
    if all_rows:
        for batch_start in range(0, len(all_rows), 300):
            chunk = all_rows[batch_start:batch_start + 300]
            values = ",".join(
                f"('{r[0]}','{r[1]}','{r[2]}','{r[3]}','{r[4]}',{r[5]},{r[6]},{r[7]},{r[8]})"
                for r in chunk
            )
            sql = (f"INSERT INTO public.fund_tag_funds "
                   f"(tag_name, tag_index_code, fund_code, fund_name, fund_type, syl_1n, syl_d, relation, sort_order) "
                   f"VALUES {values};")
            batch_num = batch_start // 300 + 1
            ok = mgmt(sql, f"insert_batch_{batch_num}")
            if not ok:
                print(f"  [FATAL] 批次 {batch_num} 写入失败，中止")
                sys.exit(1)

    # 5) 验证
    print("\n[验证]")
    import requests as req_lib

    # 验证光模块
    vr = req_lib.get(
        f"{BASE}/rest/v1/fund_tag_funds?tag_name=eq.%E5%85%89%E6%A8%A1%E5%9D%97&select=fund_code,fund_name,fund_type,syl_1n,syl_d&order=sort_order.asc",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"}, timeout=20,
    )
    if vr.ok:
        data = vr.json()
        print(f"  光模块 -> {len(data)} 只基金（正确应为易方达成长动力等科技类）:")
        for f in data[:10]:
            print(f"    {f['fund_code']} | {f['fund_name']} | {f.get('fund_type','')} | 近1年={f.get('syl_1n')}% | 成立来={f.get('syl_d')}%")

    # 验证CPO
    vr2 = req_lib.get(
        f"{BASE}/rest/v1/fund_tag_funds?tag_name=eq.CPO&select=fund_code,fund_name&order=sort_order.asc&limit=5",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"}, timeout=20,
    )
    if vr2.ok:
        data2 = vr2.json()
        print(f"\n  CPO -> {len(data2)} 只基金:")
        for f in data2[:5]:
            print(f"    {f['fund_code']} | {f['fund_name']}")

    # 总统计
    vr3 = req_lib.get(
        f"{BASE}/rest/v1/fund_tag_funds?select=tag_name",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}",
                 "Prefer": "count=exact"}, timeout=20,
    )
    total = int(vr3.headers.get("content-range", "/0").split("/")[-1]) if "/" in vr3.headers.get("content-range", "") else 0
    print(f"\n  总映射条数: ~{total}")
    print(f"  有基金的标签: {len(tags) - len(empty_tags)}/{len(tags)}")
    print(f"  无基金的标签: {len(empty_tags)}/{len(tags)}")

    print("\n完成。")


if __name__ == "__main__":
    main()
