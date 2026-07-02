#!/usr/bin/env python3
"""
从天天基金全量拉取基金分类 (f[3] 字段)
→ 解析为 t0(一级) + t1(二级) → 批量更新 fund_raw_sample 表

分类规则:
- FOF-* 只属于 FOF 一级
- 货币型(hb) 使用 rankhandler API
- t1 存储完整 f[3] 值 (如 "债券型-混合一级")
"""
import json
import os
import re
import time
import requests
from collections import defaultdict

# ── Configuration ──
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN", "")
SUPABASE_PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "tqhtegazxykkqfcpejky")
PAGE_SIZE = 5000
BATCH_SIZE = 1000

# 5个 FundGuideapi ft 类型 (货币型单独处理)
FT_TYPES = {
    "gp": "股票型",
    "zq": "债券型",
    "hh": "混合型",
    "qdii": "QDII",
    "fof": "FOF",
}

API_FUNDGUIDE = "https://fund.eastmoney.com/data/FundGuideapi.aspx"
API_RANKHANDLER = "https://fund.eastmoney.com/data/rankhandler.aspx"

HEADERS = {
    "Referer": "https://fund.eastmoney.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def strip_js_var(text):
    """剥离 var rankData ={...}; 外壳"""
    text = text.strip()
    if text.startswith("var rankData ="):
        text = text[len("var rankData ="):].strip()
    if text.endswith(";"):
        text = text[:-1]
    return text


def fetch_fundingguide(ft, page=1):
    """拉取 FundGuideapi 一页"""
    params = {"dt": 0, "ft": ft, "sc": "1nzf", "st": "desc", "pi": page, "pn": PAGE_SIZE, "zf": "diy"}
    try:
        resp = requests.get(API_FUNDGUIDE, params=params, headers=HEADERS, timeout=30)
        resp.encoding = "utf-8"
        data = json.loads(strip_js_var(resp.text))
    except Exception as e:
        print(f"  [ERROR] ft={ft} page={page}: {e}")
        return None

    datas = data.get("datas", "")
    lines = datas if isinstance(datas, list) else [l for l in datas.strip().split("\n") if l.strip()]

    results = []
    for line in lines:
        parts = line.split(",") if isinstance(line, str) else str(line).split(",")
        if len(parts) < 4:
            continue
        code = parts[0].strip()
        name = parts[1].strip()
        t2_raw = parts[3].strip()  # f[3]
        results.append((code, name, t2_raw))

    return results, int(data.get("allPages", 1)), int(data.get("datacount", 0))


def fetch_hb_funds():
    """拉取货币型基金 (使用 rankhandler API)
    
    rankhandler 返回 JavaScript 对象格式 {datas:[...]} 而非合法 JSON，
    需要用正则提取 datas 数组和各字段。
    """
    print("\n📡 拉取 货币型 (hb) via rankhandler...")
    all_funds = {}

    data_body = {
        "op": "ph", "dt": "hb", "ft": "hb", "rs": "", "gs": "0",
        "sc": "1nzf", "st": "desc", "pi": "1", "pn": str(PAGE_SIZE), "zf": "diy"
    }
    hb_headers = {
        "Referer": "https://fund.eastmoney.com/data/fundranking.html",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": HEADERS["User-Agent"],
    }
    
    def parse_rankhandler_page(text):
        """用正则提取 datas 数组和元数据 (JS 对象，非 JSON)"""
        # 提取 datas:["...","..."] 数组
        datas_match = re.search(r'datas:\[(.*?)\](?:,|$)', text, re.DOTALL)
        if not datas_match:
            return [], 0, 0
        
        raw_datas = datas_match.group(1)
        # 提取每个 "..." 字符串内容
        items = re.findall(r'"([^"]*)"', raw_datas)
        
        # 提取 allPages 和 datacount
        pages_m = re.search(r'allPages:"(\d+)"', text)
        count_m = re.search(r'datacount:"(\d+)"', text)
        return items, int(pages_m.group(1)) if pages_m else 1, int(count_m.group(1)) if count_m else 0

    try:
        resp = requests.post(API_RANKHANDLER, data=data_body, headers=hb_headers, timeout=30)
        resp.encoding = "utf-8"
        datas, total_pages, datacount = parse_rankhandler_page(resp.text)
    except Exception as e:
        print(f"  [ERROR] hb: {e}")
        return all_funds

    print(f"  总记录: {datacount}, 总页数: {total_pages}")

    for page in range(1, total_pages + 1):
        if page > 1:
            time.sleep(0.1)
            data_body["pi"] = str(page)
            try:
                resp = requests.post(API_RANKHANDLER, data=data_body, headers=hb_headers, timeout=30)
                resp.encoding = "utf-8"
                datas, _, _ = parse_rankhandler_page(resp.text)
            except Exception as e:
                print(f"  [ERROR] hb page {page}: {e}")
                continue

        for line in datas:
            parts = line.split(",")
            if len(parts) < 3:
                continue
            code = parts[0].strip()
            name = parts[1].strip()
            
            # 货币型分类在较后位置 (rankhandler 字段布局不同)
            t2_raw = ""
            match = re.search(r'货币型-[^,]*', line)
            if match:
                t2_raw = match.group(0)
            else:
                t2_raw = "货币型-普通货币"
            
            if code not in all_funds:
                t0, t1 = parse_classification(t2_raw)
                all_funds[code] = {"fcode": code, "name": name, "t0": t0, "t1": t1, "t2_raw": t2_raw}

        if page % 2 == 0:
            print(f"  进度: {page}/{total_pages} 页")

    print(f"  ✅ 货币型: {len(all_funds)} 条")
    return all_funds


def parse_classification(t2_raw):
    """解析 f[3] 为 t0(一级) + t1(二级)
    
    t0 = 第一个 '-' 前面的部分 (一级分类)
    t1 = 完整的 t2_raw 值 (如 "债券型-混合一级")
    
    FOF-* 的一级必须是 'FOF'
    """
    if not t2_raw or t2_raw == "None":
        return (None, None)
    
    t2_raw = t2_raw.strip()
    
    if "-" in t2_raw:
        idx = t2_raw.index("-")
        t0 = t2_raw[:idx].strip()
    else:
        t0 = t2_raw
    
    # FOF 修正: API 可能把 FOF-* 混入混合型，但一级必须是 FOF
    if t2_raw.startswith("FOF-"):
        t0 = "FOF"
    
    # 货币型修正
    if t2_raw.startswith("货币型-"):
        t0 = "货币型"
    
    # t1 = 完整分类值
    t1 = t2_raw
    
    return (t0, t1)


def fetch_all():
    """主流程: 拉取全部基金分类"""
    all_funds = {}
    stats = {}

    # 1. FundGuideapi 的 5 个类型
    for ft, ft_name in FT_TYPES.items():
        print(f"\n📡 拉取 {ft_name} (ft={ft})...")
        
        result = fetch_fundingguide(ft, 1)
        if result is None:
            print(f"  [SKIP]")
            continue
        
        results, total_pages, total_records = result
        print(f"  总记录: {total_records}, 总页数: {total_pages}")
        
        ft_count = 0
        for code, name, t2 in results:
            t0, t1 = parse_classification(t2)
            if code not in all_funds:
                all_funds[code] = {"fcode": code, "name": name, "t0": t0, "t1": t1, "t2_raw": t2}
                ft_count += 1
        
        for page in range(2, total_pages + 1):
            time.sleep(0.05)
            result = fetch_fundingguide(ft, page)
            if result is None:
                continue
            results, _, _ = result
            for code, name, t2 in results:
                t0, t1 = parse_classification(t2)
                if code not in all_funds:
                    all_funds[code] = {"fcode": code, "name": name, "t0": t0, "t1": t1, "t2_raw": t2}
                    ft_count += 1
            if page % 5 == 0:
                print(f"  进度: {page}/{total_pages} 页")
        
        stats[ft_name] = ft_count
        print(f"  ✅ {ft_name}: {ft_count} 条")

    # 2. 货币型单独拉取
    hb_funds = fetch_hb_funds()
    for code, fund in hb_funds.items():
        if code not in all_funds:
            all_funds[code] = fund
    stats["货币型"] = len(hb_funds)

    return all_funds, stats


def verify(all_funds):
    """验证并打印统计"""
    t0_dist = defaultdict(int)
    t1_by_t0 = defaultdict(lambda: defaultdict(int))

    for f in all_funds.values():
        t0_dist[f["t0"]] += 1
        t1_by_t0[f["t0"]][f["t1"]] += 1

    print("\n" + "=" * 60)
    print("📊 分类统计")
    print("=" * 60)

    for t0 in sorted(t0_dist.keys()):
        print(f"\n  [{t0}] {t0_dist[t0]} 只")
        for t1, n in sorted(t1_by_t0[t0].items(), key=lambda x: -x[1]):
            print(f"    {t1}: {n}")

    # 验证案例
    cases = [
        ("000001", "华夏成长混合", "混合型-灵活", "混合型", "混合型-灵活"),
        ("000047", "华夏双债债券A", "债券型-混合一级", "债券型", "债券型-混合一级"),
        ("110011", "易方达优质精选混合(QDII)", "QDII-混合偏股", "QDII", "QDII-混合偏股"),
        ("530014", "建信利率债债券A", "债券型-利率债", "债券型", "债券型-利率债"),
    ]

    print(f"\n  🔍 验证:")
    for code, name, exp_t2, exp_t0, exp_t1 in cases:
        f = all_funds.get(code)
        if f:
            ok = f["t0"] == exp_t0 and f["t1"] == exp_t1
            icon = "✅" if ok else "❌"
            print(f"  {icon} {code} {name}")
            print(f"     t2={f['t2_raw']} → t0={f['t0']}, t1={f['t1']}")
        else:
            print(f"  ❓ {code} {name}: 未找到")

    # FOF 不应在混合型
    bad = sum(1 for f in all_funds.values() if f["t0"] == "混合型" and f["t2_raw"].startswith("FOF-"))
    print(f"\n  {'✅' if bad == 0 else '⚠️'} FOF 误入混合型: {bad} 只")

    return t0_dist


def update_db(all_funds):
    """批量更新数据库"""
    print("\n" + "=" * 60)
    print("📝 更新数据库...")
    print("=" * 60)

    if not MGMT_TOKEN:
        print("  无 MGMT_TOKEN，跳过更新")
        return 0

    url = f"https://api.supabase.com/v1/projects/{SUPABASE_PROJECT_REF}/database/query"
    auth = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}

    funds_list = list(all_funds.values())
    total_batches = (len(funds_list) + BATCH_SIZE - 1) // BATCH_SIZE
    updated = 0

    for bi in range(total_batches):
        start = bi * BATCH_SIZE
        end = min(start + BATCH_SIZE, len(funds_list))
        batch = funds_list[start:end]

        when_t0, when_t1, codes = [], [], []
        for f in batch:
            code = f["fcode"]
            t0_s = (f["t0"] or "").replace("'", "''")
            t1_s = (f["t1"] or "").replace("'", "''")
            when_t0.append(f"WHEN c = '{code}' THEN '{t0_s}'")
            when_t1.append(f"WHEN c = '{code}' THEN '{t1_s}'")
            codes.append(code)

        sql = (
            f"UPDATE fund_raw_sample SET "
            f"t0 = CASE {' '.join(when_t0)} END, "
            f"t1 = CASE {' '.join(when_t1)} END "
            f"WHERE c IN ({','.join(f"'{c}'" for c in codes)})"
        )

        try:
            resp = requests.post(url, headers=auth, json={"query": sql}, timeout=60)
            if resp.status_code in (200, 201):
                updated += len(batch)
                if (bi + 1) % 5 == 0 or bi == total_batches - 1:
                    print(f"  批次 {bi+1}/{total_batches}: ✅ {len(batch)} 条")
            else:
                print(f"  批次 {bi+1}/{total_batches}: ❌ HTTP {resp.status_code}")
        except Exception as e:
            print(f"  批次 {bi+1}/{total_batches}: ❌ {e}")
        
        time.sleep(0.1)

    print(f"\n  ✅ 总计更新: {updated} 条")
    return updated


def main():
    print("=" * 60)
    print("天天基金分类全量更新")
    print("=" * 60)

    all_funds, stats = fetch_all()
    
    print(f"\n📊 汇总:")
    for k, v in stats.items():
        print(f"  {k}: {v} 条")
    print(f"  总计 (去重): {len(all_funds)} 条")

    t0_dist = verify(all_funds)

    # 保存 JSON
    out_dir = os.path.join(os.path.dirname(__file__), "..", "exports")
    os.makedirs(out_dir, exist_ok=True)
    jp = os.path.join(out_dir, "fund_classification_data.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump({"funds": list(all_funds.values()), "stats": {k: v for k, v in t0_dist.items()}}, f, ensure_ascii=False, indent=2)
    print(f"\n💾 已保存: {jp}")

    update_db(all_funds)


if __name__ == "__main__":
    main()
