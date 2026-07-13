#!/usr/bin/env python3
"""
sync_tag_funds_full.py — 标签-基金关联全量重拉 + 写入 fund_scores.tags

背景：
  旧 fetch_tag_funds_v2.py 每个标签只拉 15 只产品，导致 fund_tag_funds 数据稀疏，
  热门标签（如"光模块"）真实关联 440+ 只基金却只存 15 只。本脚本修复：
    1. 从东财 ZTJJ 分页拉取每个标签的【全部】关联产品；
    2. TRUNCATE + 重写 fund_tag_funds（保留表结构/RLS/索引）；
    3. 给 fund_scores 增加 tags(text[]) 列，并从 fund_tag_funds 聚合写入，
       使 fund_scores 可直接按标签筛选（.contains('tags', [tagName])）。

  标签数据不在 nightly 工作流内重算（workflow 不调用本类脚本），故一旦写入即稳定；
  promote_staging.py 已改为切换后从 fund_tag_funds 重新应用 tags，夜跑不丢。

用法：
  SUPABASE_PAT="$PAT" python3 scripts/sync_tag_funds_full.py

依赖：标准库 + requests
"""

import os
import sys
import time
import json
import re
import urllib.request
import urllib.parse
import requests

# ── 配置 ──────────────────────────────────────────────
REF = "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{REF}/database/query"

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
if not PAT:
    print("[ERROR] 需设置 SUPABASE_PAT")
    sys.exit(1)

ANON = os.environ.get("VITE_SUPABASE_ANON_KEY", "")
BASE = os.environ.get("VITE_SUPABASE_URL", f"https://{REF}.supabase.co")

# 东财 API
EM_API_BASE = "http://api.fund.eastmoney.com"
EM_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Referer": "https://fund.eastmoney.com/ztjj/",
}


def mgmt(sql: str, label: str = "", timeout: int = 600) -> bool:
    """通过 Management API 执行 SQL（用 requests，避免 urllib 403）。"""
    r = requests.post(
        MGMT_URL,
        headers={"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout,
    )
    ok = r.status_code in (200, 201)
    print(f"  [mgmt:{label}] HTTP {r.status_code} {'OK' if ok else r.text[:200]}")
    return ok


def esc(s: str) -> str:
    return str(s).replace("'", "''")


def em_get(url: str, retries: int = 3) -> dict | None:
    """调用东财 JSONP API，返回解析后的【完整】 dict（带重试）。

    注意：返回完整 dict（含 Data / TotalCount / ErrCode 等），由调用方自行取字段，
    以便分页场景能拿到 TotalCount。
    """
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=EM_HEADERS)
            resp = urllib.request.urlopen(req, timeout=30)
            raw = resp.read().decode("utf-8", errors="ignore")
            m = re.search(r"\((\{.*\})\)", raw, re.DOTALL)
            if m:
                data = json.loads(m.group(1))
                if data.get("ErrCode") == 0:
                    return data
                print(f"    [WARN] API ErrCode={data.get('ErrCode')} msg={data.get('ErrMsg')}")
                return None
            try:
                return json.loads(raw)
            except Exception:
                print(f"    [WARN] 无法解析响应，长度={len(raw)}")
                return None
        except Exception as e:
            print(f"    [ERROR] 第{attempt}次请求失败: {e}")
            if attempt < retries:
                time.sleep(1.0)
    return None


def fetch_all_tags() -> list:
    """从东财获取所有标签列表（含 INDEXCODE）。返回 [(INDEXCODE, INDEXNAME, tag_type), ...]"""
    url = f"{EM_API_BASE}/ZTJJ/GetBKListByBKTypeNew?callback=?"
    resp = em_get(url)
    if not resp or not isinstance(resp, dict):
        print("[ERROR] 无法获取标签列表")
        return []

    tags = []
    type_map = {"hy1": "industry", "hy2": "industry", "gn": "concept"}
    for cat_key, tag_type in type_map.items():
        for item in resp.get("Data", {}).get(cat_key, []):
            code = item.get("INDEXCODE", "")
            name = item.get("INDEXNAME", "")
            if code and name:
                tags.append((code, name, tag_type))

    seen = set()
    unique = []
    for t in tags:
        if t[0] not in seen:
            seen.add(t[0])
            unique.append(t)
    return unique


def fetch_tag_funds_full(index_code: str) -> list:
    """分页拉取某标签的全部关联基金（修复旧脚本只取 15 只）。"""
    all_funds = []
    page = 1
    ps = 200
    while True:
        params = urllib.parse.urlencode({
            "callback": "?",
            "sort": "SYL_D",
            "sorttype": "DESC",
            "pageindex": str(page),
            "pagesize": str(ps),
            "tp": index_code,
            "isbuy": "0",
        })
        url = f"{EM_API_BASE}/ZTJJ/GetBKRelTopicFundNew?{params}"
        d = em_get(url)
        if not d or not isinstance(d, dict):
            break
        data = d.get("Data", []) or []
        if not data:
            break
        all_funds.extend(data)
        total = d.get("TotalCount", 0) or 0
        if len(all_funds) >= total or len(data) < ps:
            break
        page += 1
        time.sleep(0.15)
    return all_funds


def fmt_val(v):
    if v is None:
        return "NULL"
    try:
        return str(float(v))
    except (ValueError, TypeError):
        return "NULL"


def main():
    print("=" * 64)
    print(" 标签-基金关联全量重拉 + 写入 fund_scores.tags")
    print("=" * 64)

    # 1) 标签列表
    print("\n[1/5] 获取东财标签列表...")
    tags = fetch_all_tags()
    print(f"  共 {len(tags)} 个标签")
    if not tags:
        print("[ERROR] 标签列表为空")
        sys.exit(1)
    tc = {}
    for _, _, tt in tags:
        tc[tt] = tc.get(tt, 0) + 1
    print(f"  分布: {tc}")

    # 2) 逐标签全量抓取
    print(f"\n[2/5] 全量抓取标签-基金映射（{len(tags)} 个标签）...")
    rows = []
    empty_tags = []
    for i, (idx_code, tag_name, tag_type) in enumerate(tags):
        funds = fetch_tag_funds_full(idx_code)
        if not funds:
            empty_tags.append(tag_name)
        else:
            for j, f in enumerate(funds):
                code = str(f.get("FCODE", "")).strip()
                fname = str(f.get("SHORTNAME", "")).strip()
                if not code or not fname:
                    continue
                ftype = f.get("FTYPE") or ""
                syl_1n = f.get("SYL_1N")       # 近1年收益率
                syl_d = f.get("SYL_Z")         # 成立以来收益率
                relation = f.get("RELATION")   # 关联度/相关性
                rows.append((
                    esc(tag_name), esc(idx_code), esc(code), esc(fname),
                    esc(ftype),
                    fmt_val(syl_1n), fmt_val(syl_d), fmt_val(relation),
                    j + 1,
                ))
        if (i + 1) % 20 == 0 or i == len(tags) - 1:
            print(f"  进度: {i+1}/{len(tags)} | 累计映射 {len(rows)} 条 | 空标签 {len(empty_tags)}")
        time.sleep(0.2)

    if empty_tags:
        print(f"\n  ⚠ {len(empty_tags)} 个标签无关联基金: {empty_tags[:20]}")

    # 3) 重写 fund_tag_funds
    print(f"\n[3/5] 重写 fund_tag_funds（{len(rows)} 条，先清空再批量写入）...")
    if not mgmt("TRUNCATE TABLE public.fund_tag_funds;", "truncate"):
        sys.exit(1)
    for start in range(0, len(rows), 300):
        chunk = rows[start:start + 300]
        values = ",".join(
            f"('{r[0]}','{r[1]}','{r[2]}','{r[3]}','{r[4]}',{r[5]},{r[6]},{r[7]},{r[8]})"
            for r in chunk
        )
        sql = (
            f"INSERT INTO public.fund_tag_funds "
            f"(tag_name, tag_index_code, fund_code, fund_name, fund_type, syl_1n, syl_d, relation, sort_order) "
            f"VALUES {values};"
        )
        if not mgmt(sql, f"ins{start // 300 + 1}"):
            print(f"  [FATAL] 批次写入失败，中止")
            sys.exit(1)
    print(f"  ✓ fund_tag_funds 写入 {len(rows)} 条")

    # 4) fund_scores 增加 tags 列
    print("\n[4/5] 为 fund_scores 增加 tags(text[]) 列...")
    mgmt("ALTER TABLE public.fund_scores ADD COLUMN IF NOT EXISTS tags text[];", "addcol")

    # 5) 从 fund_tag_funds 聚合写入 fund_scores.tags
    print("  聚合 fund_tag_funds → fund_scores.tags ...")
    mgmt("UPDATE public.fund_scores SET tags = NULL;", "clrtags", timeout=300)
    ok = mgmt(
        """UPDATE public.fund_scores fs
           SET tags = sub.tags
           FROM (SELECT fund_code, array_agg(DISTINCT tag_name) AS tags
                 FROM public.fund_tag_funds GROUP BY fund_code) sub
           WHERE fs.c = sub.fund_code OR fs.c = sub.fund_code || '.OF';""",
        "uptags",
        timeout=600,
    )
    if not ok:
        print("  [ERROR] fund_scores.tags 更新失败")
        sys.exit(1)

    # 6) 校验
    print("\n[5/5] 校验...")
    hdr = requests.get(
        f"{BASE}/rest/v1/fund_scores?select=c&tags=not.is.null",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}", "Prefer": "count=exact"},
        timeout=20,
    ).headers
    tagged = hdr.get("content-range", "/0").split("/")[-1]
    print(f"  fund_scores 已标记标签的基金数: {tagged}")

    tf_hdr = requests.get(
        f"{BASE}/rest/v1/fund_tag_funds?select=tag_name",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}", "Prefer": "count=exact"},
        timeout=20,
    ).headers
    tf_total = tf_hdr.get("content-range", "/0").split("/")[-1]
    print(f"  fund_tag_funds 总映射条数: {tf_total}")

    # 抽查光模块
    vr = requests.get(
        f"{BASE}/rest/v1/fund_tag_funds?tag_name=eq.%E5%85%89%E6%A8%A1%E5%9D%97&select=fund_code,fund_name&order=sort_order.asc",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"},
        timeout=20,
    )
    if vr.ok:
        data = vr.json()
        print(f"  光模块 -> {len(data)} 只（应为 ~440）:")
        for f in data[:5]:
            print(f"    {f['fund_code']} | {f['fund_name']}")

    # 抽查某只有标签的基金在 fund_scores 中的 tags
    vs_params = urllib.parse.urlencode({
        "tags": 'cs.{"光模块"}',
        "select": "c,n,tags",
        "limit": "3",
    })
    vs = requests.get(
        f"{BASE}/rest/v1/fund_scores?{vs_params}",
        headers={"apikey": ANON, "Authorization": f"Bearer {ANON}"},
        timeout=20,
    )
    if vs.ok:
        print(f"  fund_scores 含'光模块'标签示例: {json.dumps(vs.json(), ensure_ascii=False)[:300]}")

    print("\n完成。")


if __name__ == "__main__":
    main()
