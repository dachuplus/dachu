#!/usr/bin/env python3
"""由原始抓取结果生成「大众点评必吃榜 · 上海历年」前端数据模块。

输入：/tmp/musteat/<year>.json（每个年份一个，格式见下）
输出：src/data/mustEatShanghai.js

原始 JSON 格式：
{
  "year": 2024,
  "city": "上海",
  "restaurants": [{ "name": "店名", "district": "静安", "category": "本帮菜", "source": "https://..." }],
  "sources": ["https://..."],
  "coverage": "覆盖情况说明"
}

设计原则：
- **不做任何补全/推测**。原始数据里没有的店，绝不生成。
- 店名做保守规范化（见 canon_name），解决「同一家店被写成两种形态」的问题。
- 同一年内同名只保留一条（规范化后判重），跨年份同名保留（那是不同年份的上榜记录）。
- 年份倒序输出；每年内保持原始顺序（一般即为榜单顺序）。
- 覆盖说明直接沿用抓取阶段写下的 `coverage` 原文（最如实），缺失时才退回 YEAR_FACTS。
- 来源链接只保留每年一份（不逐条重复），避免前端数据臃肿。
"""
import json
import os
import re
import sys
import unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = "/tmp/musteat"
OUT = os.path.join(ROOT, "src", "data", "mustEatShanghai.js")

# 中点类分隔符统一为 U+00B7（不同来源混用 ‧・．·）
_MIDDOTS = "\u2027\u30fb\uff0e\u00b7\u22c5"
_MIDDOT_RE = re.compile("[" + _MIDDOTS + "]")
# 中日文之间的英文句点也当分隔符（大馥.炭火烧肉屋 → 大馥·炭火烧肉屋）
_CJK = "\u4e00-\u9fff\u3400-\u4dbf"
_CJK_DOT_RE = re.compile(f"(?<=[{_CJK}])\\.(?=[{_CJK}])")

# 年份 → 当年榜单口径备注（仅在原始 coverage 缺失时兜底）
YEAR_FACTS = {
    2017: "2017 年为必吃榜首次发榜，全国 77 座城市共 1062 家餐厅上榜。",
    2018: "2018 年全国上榜餐厅 863 家。",
    2019: "2019 年榜单在广州塔发布。",
    2020: "2020 年榜单于 7 月 24 日发布。",
    2021: "2021 年覆盖全国 46 城共 1241 家餐厅。",
    2022: "2022 年新增桂林、泉州、惠州等 9 城，全国 57 城共 1482 家餐厅。",
    2023: "2023 年全国 61 个城市和地区共 2062 家餐厅上榜。",
    2024: "2024 年发榜城市首次破百（119 座城市及地区），全国 2797 家餐厅上榜；上海 144 家居全国第一。",
    2025: "2025 年全国 144 座城市及地区共 3091 家餐厅上榜；上海入围 155 家为全国最多。",
}


def canon_name(name: str) -> str:
    """店名规范化，用于「同一家店」的判定与展示。

    背景：不同年份的榜单来源写法不一致，实测有 30 组同一家店被写成两种形态
    （半角括号 vs 全角括号、`·` vs `.`），若不做规范化会在「按餐厅聚合」里
    被拆成两家、上榜次数被少算。
    规则（保守，只做无损的等价替换）：
      1. NFKC：全角括号/字母/数字 → 半角（（）→()）；不删除、不换字
      2. 中点类字符统一为 `·`
      3. 中日文之间的 `.` 视作分隔符 → `·`
      4. 首尾空白去掉；**不动内部空格**（如「就是泰Just Thai泰式火锅」）
    """
    s = unicodedata.normalize("NFKC", name or "").strip()
    s = _MIDDOT_RE.sub("\u00b7", s)
    s = _CJK_DOT_RE.sub("\u00b7", s)
    return s


def load_year(path):
    """返回 (year, rows, urls, raw_count, coverage)"""
    with open(path, "r", encoding="utf-8") as fh:
        d = json.load(fh)
    year = int(d.get("year") or os.path.splitext(os.path.basename(path))[0])
    seq = d.get("restaurants") or []

    rows = []
    by_name = {}
    for r in seq:
        name = canon_name(r.get("name") or "")
        if not name:
            continue
        if name in by_name:
            # 规范化后重复写法：只在原条为空时补字段，避免丢信息
            t = by_name[name]
            if not t["district"] and (r.get("district") or "").strip():
                t["district"] = r["district"].strip()
            if not t["category"] and (r.get("category") or "").strip():
                t["category"] = r["category"].strip()
            continue
        row = {
            "name": name,
            "district": (r.get("district") or "").strip(),
            "category": (r.get("category") or "").strip(),
        }
        by_name[name] = row
        rows.append(row)

    urls = [u for u in (d.get("sources") or []) if u]
    coverage = (d.get("coverage") or "").strip()
    return year, rows, urls, len(seq), coverage


def js_str(s):
    return json.dumps(s, ensure_ascii=False)


def main():
    if not os.path.isdir(SRC_DIR):
        sys.exit(f"未找到原始数据目录 {SRC_DIR}")
    files = [f for f in os.listdir(SRC_DIR) if re.fullmatch(r"\d{4}\.json", f)]
    if not files:
        sys.exit(f"{SRC_DIR} 下没有 <年份>.json")

    parsed = []
    for f in sorted(files):
        parsed.append(load_year(os.path.join(SRC_DIR, f)))
    parsed.sort(key=lambda x: -x[0])  # 年份倒序

    lines = []
    lines.append("// 「大众点评必吃榜 · 上海历年（2017-2025）」数据")
    lines.append("// 由 scripts/build_must_eat_shanghai.py 从原始抓取结果生成，请勿手工编辑。")
    lines.append("// 每条 = 某家餐厅在某一年上榜一次；未上榜的年份不会出现，也绝不臆造。")
    lines.append("")
    lines.append("export const MUST_EAT_SHANGHAI = [")
    total = 0
    for year, rows, _urls, _raw, _cov in parsed:
        lines.append(f"  // ---- {year} 年（{len(rows)} 家）----")
        for r in rows:
            parts = [f"name: {js_str(r['name'])}", f"year: {year}"]
            if r["district"]:
                parts.append(f"district: {js_str(r['district'])}")
            if r["category"]:
                parts.append(f"category: {js_str(r['category'])}")
            lines.append("  { " + ", ".join(parts) + " },")
        total += len(rows)
    lines.append("]")
    lines.append("")
    lines.append("/** 各年份覆盖情况与来源（前端「数据来源与覆盖说明」用） */")
    lines.append("export const MUST_EAT_SOURCES = [")
    for year, rows, urls, _raw, coverage in parsed:
        note = coverage or YEAR_FACTS.get(year, "")
        lines.append(
            f"  {{ year: {year}, count: {len(rows)}, note: {js_str(note)}, "
            f"fact: {js_str(YEAR_FACTS.get(year, ''))}, "
            f"urls: [{', '.join(js_str(u) for u in urls)}] }},"
        )
    lines.append("]")
    lines.append("")
    lines.append("export const MUST_EAT_YEARS = [" + ", ".join(str(p[0]) for p in parsed) + "]")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"已生成 {OUT}")
    print(f"  年份：{', '.join(str(p[0]) for p in parsed)}")
    print(f"  记录总数：{total}")
    for year, rows, urls, raw, _cov in parsed:
        dedup = raw - len(rows)
        extra = f"（规范化合并 {dedup} 条重复写法）" if dedup else ""
        print(f"    {year}: {len(rows):>3} 家{extra}  来源 {len(urls)} 条")
    uk = sum(1 for _y, rows, _u, _r, _c in parsed for r in rows if not r["district"])
    print(f"  缺区域字段的记录：{uk} / {total}")

    # 自检 1：当年内不应再有重复店名
    per_year_dup = 0
    for _y, rows, _u, _r, _c in parsed:
        c = Counter(r["name"] for r in rows)
        per_year_dup += sum(v - 1 for v in c.values() if v > 1)
    print(f"  自检①：当年内重复 = {per_year_dup}（应为 0）")
    if per_year_dup:
        sys.exit("✗ 当年内仍有重复店名，请检查规范化规则")

    # 自检 2：不应残留明显的同店异写（全角括号 / 中文.中文）
    weird = [
        r["name"]
        for _y, rows, _u, _r, _c in parsed
        for r in rows
        if re.search(r"[（）]", r["name"]) or re.search(f"(?<=[{_CJK}])\\.(?=[{_CJK}])", r["name"])
    ]
    print(f"  自检②：疑似同店异写残留 = {len(weird)}（应为 0）")
    if weird:
        print("     样例：", " | ".join(weird[:5]))
        sys.exit("✗ 仍有未规范化的店名")

    cross = Counter()
    for _y, rows, _u, _r, _c in parsed:
        for r in rows:
            cross[r["name"]] += 1
    multi = sum(1 for v in cross.values() if v > 1)
    print(f"  跨年上榜（≥2 次）的餐厅：{multi} 家；最高 {max(cross.values())} 次")


if __name__ == "__main__":
    main()
