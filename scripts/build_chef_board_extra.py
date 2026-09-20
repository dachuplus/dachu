#!/usr/bin/env python3
"""把「中国大厨榜 · 上海」的扩展批次装配成前端数据模块。

输入：/tmp/chefpool/out_*.json（每个批次一个，由评分环节产出）
输出：src/data/shRestaurantsExtra.js

设计原则：
- **不修改原有 100 家**（src/data/shRestaurants.js 一个字都不动）；本脚本只产出「扩展集」，
  前端把两者拼接展示。这样旧数据永远可回滚。
- 店名做无损规范化（`A.B` → `A·B`、全角括号 → 半角）。
- **品牌去重**：与主表品牌同源的条目会被跳过（主表是品牌级书写，如「新荣记（南京西路店）」，
  避免同一品牌出现两行）。
- **同店异写合并**：历年榜单对同一家店存在全角/半角、简繁、大小写、空格等异写，
  用 MERGE_GROUPS 显式列出并合并（合并后保留第一个写法）。
- **菜系口径归一**：来源菜系写法很杂（66 种），归一到与主表一致的有限类目，保证筛选器可用。
  未能从来源明确得到菜系的条目统一归入「其他」，**不做任何推断**。
- 缺字段一律留空，前端显示 '--'，绝不用占位假数据填充。
- 末尾输出统计与自检；自检不过直接非零退出。

用法：
  python3 scripts/build_chef_board_extra.py
"""
import glob
import json
import os
import re
import sys
import unicodedata
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = "/tmp/chefpool"
OUT = os.path.join(ROOT, "src", "data", "shRestaurantsExtra.js")
MAIN = os.path.join(ROOT, "src", "data", "shRestaurants.js")

DIMS = ["好老板", "好理念", "好团队", "好厨师", "好食材", "好环境", "好地段", "好营收", "好口碑"]

_CJK = "\u4e00-\u9fff\u3400-\u4dbf"
_CJK_DOT_RE = re.compile(f"(?<=[{_CJK}])\\.(?=[{_CJK}])")
_MIDDOTS = "\u2027\u30fb\uff0e\u00b7\u22c5"
_MIDDOT_RE = re.compile("[" + _MIDDOTS + "]")

# ---------------------------------------------------------------- 同店异写合并表
# 历年榜单对同一家店的不同写法（全角/半角、简繁、大小写、空格、省略「店」字等）。
# 每组第一个为保留写法。只列**确信是同一家店**的；分店不合并。
MERGE_GROUPS = [
    # 大小写 / 空格 / 分隔符差异
    ["bistro lenbach兰巴赫(静安店)", "BISTRO LENBACH兰巴赫(静安店)"],
    ["Solo(衡山路店)", "solo(衡山路店)"],
    ["SHANGHAI 春在(陆家嘴店)", "SHANGHAI春在(陆家嘴店)"],
    ["桂满陇·桃花院落(长泰广场店)", "桂满陇-桃花院落(长泰广场店)"],
    ["炙柒Sekinana·精致日料铁板烧(合生汇店)", "炙柒Sekinana 精致日料铁板烧(合生汇店)", "炙柒Sekinana·精致日料(合生汇店)"],
    ["大馥·炭火烧肉屋(五角场店)"],  # 占位（无重复，保留信息）
    # 简繁 / 异体
    ["FAT PHO大发越南粉(徐家汇店)", "FAT PHO大發越南粉(徐家汇店)"],
    ["客觀民间菜(秀沿路店)", "客觀民间菜", "客觀民間菜(秀沿路店)"],
    ["蘇小柳点心专门店(人民广场分院)", "苏小柳点心专门店(人民广场分院)", "蘇小柳点心专门店(人民广场店)"],
    ["大馥·烧肉丼饭(芮欧百货店)", "大馥·烧肉井饭(芮欧百货店)"],
    # 错字 / 省略
    ["人和馆·上海菜(肇嘉浜路店)", "人和馆(肇嘉浜路店)", "人和馆(肇嘉路店)"],
    ["蟹尊苑(巨鹿店)", "蟹尊苑(巨庐店)"],
    ["蟹榭(五角场合生汇商场店)", "蟹榭(五角合生汇商场店)"],
    ["细记港九宵夜大牌档(东湖路总店)", "细记港九大牌档(东湖路总店)"],
    ["香港龙凤楼(巨鹿路洋房店)", "香港龙凤楼(巨鹿路店)"],
    ["玫瑰厅上海菜(长宁来福士广场店)", "玫瑰厅上海菜(来福士广场店)"],
    ["上海滩餐厅(虹桥天地店)", "上海滩餐厅(虹桥店)"],
    ["荟廷·晶萃(陆家嘴尚悦湾店)", "荟廷·晶萃(尚悦湾店)"],
    ["特色椒盐排条(天山西路店)", "特色椒盐排条"],
    ["月湖萃(·夜宵 天津路店)", "月湖萃"],
    # 分店写法补全 / 省略分店
    ["光明邨大酒家(淮海中路总店)", "光明邨大酒家"],
    ["三玛璐酒楼(汉口路店)", "三玛璐酒楼"],
    ["吉品小鲜Jhouse(静安店)", "吉品小鲜Jhouse"],
    ["夏朵花园(复兴西路店)", "夏朵花园"],
    ["妈妈家(总店)", "妈妈家"],
    ["宁国素斋(华泾路店)", "宁国素斋"],
    ["小船日式创作料理(久金广场店)", "小船日式创作料理"],
    ["晓平饭店(嘉善路店)", "晓平饭店"],
    ["沪西老弄堂面馆(定西路店)", "沪西老弄堂面馆"],
    ["清真·贯贯吉穆斯林餐厅(人民广场店)", "清真·贯贯吉穆斯林餐厅"],
    ["HOME'S私房菜(巨鹿店)", "HOME'S私房菜"],
    ["临湖素食(保利·时光里店)", "临湖素食"],
    ["威皇广福和小海鲜(襄阳南路店)", "威皇广福和小海鲜"],
    ["米禾良日料(人民广场店)", "米禾良日料"],
    ["家和面馆(天山路店)", "家和面馆"],
    ["BELLOCO倍乐创意韩国料理(古北店)", "BELLOCo倍乐创意韩国料理(古北店)", "BELLOCO倍乐(古北店)"],
    ["御宝轩(益丰·外滩源店)", "御宝轩(益丰 外滩源店)"],
    ["龙华素斋(龙华路店)", "龙华素斋", "龙华素斋(龙华寺店)"],
    ["珍宝海鲜JUMBO Seafood(环贸iapm商场店)", "珍宝海鲜JUMBO Seafood(环贸店)", "珍宝海鲜JUMBO SEAFOOD(环贸店)"],
]

# ---------------------------------------------------------------- 菜系口径归一
# 来源菜系写法 → 统一类目（与主表 shRestaurants.js 的 22 类对齐，仅按需扩充）。
CAT_MAP = {
    # 本帮 / 江浙
    "本帮江浙菜": "本帮菜", "江浙菜": "本帮菜", "苏浙菜": "本帮菜", "农家菜": "本帮菜",
    "私房菜": "本帮菜", "蟹宴": "本帮菜", "浙菜": "浙菜",
    # 日料
    "日本料理": "日料", "日本菜": "日料", "日式烤肉": "日料", "寿司": "日料", "日式自助": "日料",
    # 面点小吃
    "面馆": "面点小吃", "小吃快餐": "面点小吃", "快餐简餐": "面点小吃", "包子": "面点小吃",
    "小吃/小笼": "面点小吃",
    # 粤菜 / 港式
    "粤菜馆": "粤菜", "粤菜/粥": "粤菜", "顺德菜": "粤菜", "茶餐厅": "港式",
    # 火锅
    "牛羊肉火锅": "火锅", "潮汕牛肉火锅": "火锅", "潮汕火锅": "火锅", "海鲜火锅": "火锅",
    "老北京火锅": "火锅", "泰式火锅": "火锅", "鱼火锅": "火锅", "寿喜锅": "火锅",
    "贵州菜/火锅": "火锅",
    # 韩国菜 / 烧烤
    "韩式烤肉": "韩国菜", "韩式料理": "韩国菜", "韩式小吃": "韩国菜",
    "烤串": "烧烤", "烧烤烤串": "烧烤",
    # 西餐系
    "西餐(牛排)": "西餐", "披萨": "西餐", "西班牙菜": "西餐", "自助餐": "西餐",
    # 东南亚 / 川菜系
    "泰国菜": "东南亚", "越南菜": "东南亚",
    "酸菜鱼": "川菜", "烤鱼": "川菜",
    # 其他收敛
    "特色菜": "其他", "海鲜": "海鲜", "台湾菜": "其他", "印度菜": "其他",
    "陕菜": "西北菜", "西北民间菜": "西北菜", "东北菜": "东北菜",
    "本帮菜/海鲜": "本帮菜", "素食": "素食", "新疆菜": "新疆菜", "云南菜": "云南菜",
    "潮汕菜": "潮汕菜", "意大利菜": "意大利菜", "淮扬菜": "淮扬菜", "粤菜": "粤菜",
    "火锅": "火锅", "川菜": "川菜", "湘菜": "湘菜", "西餐": "西餐", "本帮菜": "本帮菜",
    "日料": "日料", "面点小吃": "面点小吃", "港式": "港式", "京菜": "京菜",
    "创意菜": "创意菜", "法餐": "法餐", "台州菜": "台州菜", "宁波菜": "宁波菜",
    "闽菜": "闽菜", "杭帮菜": "杭帮菜", "西北菜": "西北菜",
}

# 单店口径校正：来源给出的类目过宽或与实际菜系不符时，按该店公认菜系归位
# （仅限依据门店名/公开定位可确定的少数几家，不做批量推断）
CAT_OVERRIDE = {
    "荣小馆(安达仕店)": "台州菜",                    # 新荣记旗下台州菜品牌
    "锦楼·臻选新杭帮(正大广场店)": "杭帮菜",          # 店名即「新杭帮」
    "清真·宁夏印象·盐池滩羊肉体验店(江宁路店)": "西北菜",  # 宁夏盐池滩羊
}

# 与主表做品牌级去重时，需要从店名里剥掉的通用词（避免「X酒家」「X餐厅」误判）
BRAND_STRIP = re.compile(r"(酒家|餐厅|饭店|菜馆|面馆|火锅|烧肉|寿司|料理|小馆|食府|酒楼|大酒家)$")

_TRAD = str.maketrans({
    "發": "发", "蘭": "兰", "蘇": "苏", "觀": "观", "間": "间", "粵": "粤", "點": "点",
    "臺": "台", "樓": "楼", "號": "号", "廚": "厨", "鋪": "铺", "記": "记", "貨": "货",
    "軒": "轩", "東": "东", "齊": "齐", "萬": "万", "會": "会", "興": "兴", "來": "来",
})


def canon_name(name: str) -> str:
    """店名无损规范化：全角→半角、中点类统一为 ·、中日文之间的 . 视作分隔符。"""
    s = unicodedata.normalize("NFKC", (name or "").strip())
    s = _MIDDOT_RE.sub("\u00b7", s)
    s = _CJK_DOT_RE.sub("\u00b7", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def brand_key(name: str) -> str:
    """品牌级归一化 key：去掉分店后缀、大小写、空白、标点、简繁差异。"""
    s = unicodedata.normalize("NFKC", (name or "").strip()).translate(_TRAD).lower()
    s = re.sub(r"[（(][^）)]*[）)]", "", s)
    s = re.sub(r"[\s\u00b7\u30fb\uff0e\u00b7\u22c5\u2027.\-–—&'’\"、,，:：]+", "", s)
    s = BRAND_STRIP.sub("", s)
    return s


def load_main():
    """从主表抓取店名（正则提取，避免在 Python 里执行 JS）。"""
    try:
        with open(MAIN, "r", encoding="utf-8") as fh:
            txt = fh.read()
    except FileNotFoundError:
        return set(), set()
    names, brands = set(), set()
    for pat in (r"\{\s*name:\s*'([^']+)'", r'\{\s*name:\s*"([^"]+)"'):
        for m in re.finditer(pat, txt):
            names.add(canon_name(m.group(1)))
            brands.add(brand_key(m.group(1)))
    return names, brands


def js_str(s: str) -> str:
    return json.dumps(s, ensure_ascii=False)


def build_meta(district: str, cat: str, price: str) -> str:
    """拼 meta 字段：主厨 · 菜系 · 人均 · 区（缺失项显示 --，与主表版式一致）。"""
    return f"主厨团队 · {cat or '--'} · 人均 {price or '--'} · {district or '--'}"


def main():
    files = sorted(glob.glob(os.path.join(SRC_DIR, "out_*.json")))
    if not files:
        sys.exit(f"未找到批次产物 {SRC_DIR}/out_*.json")

    main_names, main_brands = load_main()
    print(f"主表已存在 {len(main_names)} 个店名 / {len(main_brands)} 个品牌（用于去重）")

    # 同店异写表：写法 → 保留写法
    alias = {}
    alias_groups = 0
    for grp in MERGE_GROUPS:
        keep = grp[0]
        for other in grp[1:]:
            alias[canon_name(other)] = canon_name(keep)
        if len(grp) > 1:
            alias_groups += 1
    print(f"同店异写合并表：{alias_groups} 组 / {len(alias)} 个写法将被合并")

    rows = []
    seen = set()
    skip_brand = []
    dup_extra = []
    merged_hits = []
    raw_n = 0
    for f in files:
        with open(f, "r", encoding="utf-8") as fh:
            arr = json.load(fh)
        if not isinstance(arr, list):
            sys.exit(f"✗ {os.path.basename(f)} 不是数组")
        for r in arr:
            raw_n += 1
            name = canon_name(r.get("name") or "")
            if not name:
                continue
            if name in alias:
                merged_hits.append(name)
                name = alias[name]
            # 品牌与主表同源 → 跳过（主表已覆盖该品牌）
            if name in main_names or brand_key(name) in main_brands:
                skip_brand.append(name)
                continue
            if name in seen:
                dup_extra.append(name)
                continue
            seen.add(name)
            cat_raw = (r.get("cat") or "").strip()
            cat = CAT_OVERRIDE.get(name) or CAT_MAP.get(cat_raw, cat_raw) or "其他"
            if cat not in CAT_MAP.values() and cat not in CAT_OVERRIDE.values() and cat != "其他":
                cat = "其他"
            rows.append(
                {
                    "name": name,
                    "district": (r.get("district") or "").strip(),
                    "cat": cat,
                    "price": (r.get("price") or "--").strip() or "--",
                    "scores": [int(x) for x in (r.get("scores") or [])],
                    "bonus": int(r.get("bonus") or 0),
                    "comment": (r.get("comment") or "").strip(),
                    "cat_raw": cat_raw,
                }
            )
        print(f"  ✓ {os.path.basename(f)} → 累计 {len(rows)} 家")

    if not rows:
        sys.exit("✗ 装配后为空")

    for r in rows:
        r["total"] = sum(r["scores"]) + r["bonus"]
    rows.sort(key=lambda r: (-r["total"], r["name"]))

    cats = sorted({r["cat"] for r in rows})
    lines = []
    lines.append("// 「中国大厨榜 · 上海」扩展集（自动生成，请勿手工编辑）")
    lines.append("// 由 scripts/build_chef_board_extra.py 从 /tmp/chefpool/out_*.json 装配。")
    lines.append("//")
    lines.append("// ⚠️ 评分口径：本扩展集为**编辑综合评分**，由统一评分标准生成，")
    lines.append("//    不是官方数据、也不是实测结果。店名与所在区取自公开榜单")
    lines.append("//    （大众点评必吃榜 2017-2025，仅收录公开可溯源的门店）；")
    lines.append("//    人均消费无法逐年核实，统一留空显示 '--'，不做估算。")
    lines.append("//    菜系仅取来源明确标注者，其余归入「其他」，未作推断。")
    lines.append("//")
    lines.append(f"// 共 {len(rows)} 家，与主表 shRestaurants.js 不重复（品牌级去重）。")
    lines.append("")
    lines.append("export const SH_RESTAURANTS_EXTRA = [")
    for r in rows:
        sc = ",".join(str(x) for x in r["scores"])
        parts = [
            f"name:{js_str(r['name'])}",
            f"meta:{js_str(build_meta(r['district'], r['cat'] if r['cat'] != '其他' else '', r['price']))}",
            f"cat:{js_str(r['cat'])}",
            f"scores:[{sc}]",
            f"bonus:{r['bonus']}",
            f"comment:{js_str(r['comment'])}",
        ]
        lines.append("  { " + ", ".join(parts) + " },")
    lines.append("]")
    lines.append("")
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))

    print(f"\n已生成 {OUT}")
    print(f"  批内原始条目：{raw_n}")
    print(f"  扩展集条目数：{len(rows)}")
    print(f"  与主表品牌同源被跳过：{len(skip_brand)}")
    for n in skip_brand:
        print(f"      · {n}")
    print(f"  同店异写被合并：{len(merged_hits)}")
    print(f"  批内重复被合并（同名）：{len(dup_extra)}" + (f" 例：{dup_extra[:3]}" if dup_extra else ""))

    # ---- 自检 ----
    errs = []
    bad_scores = [r["name"] for r in rows if len(r["scores"]) != 9]
    bad_range = [r["name"] for r in rows if any(not (1 <= s <= 10) for s in r["scores"]) or not (0 <= r["bonus"] <= 10)]
    bad_cmt = [r["name"] for r in rows if len(r["comment"]) < 10]
    bad_cat = [r["name"] for r in rows if r["cat"] not in cats or not r["cat"]]
    if bad_scores:
        errs.append(f"{len(bad_scores)} 条 scores 长度不为 9，例：{bad_scores[:3]}")
    if bad_range:
        errs.append(f"{len(bad_range)} 条分数越界，例：{bad_range[:3]}")
    if bad_cmt:
        errs.append(f"{len(bad_cmt)} 条点评过短，例：{bad_cmt[:3]}")
    if bad_cat:
        errs.append(f"{len(bad_cat)} 条菜系非法，例：{bad_cat[:3]}")

    print(f"  自检① scores 长度=9：{'✅' if not bad_scores else '✗'}（{len(bad_scores)} 例外）")
    print(f"  自检② 分数值域合法：{'✅' if not bad_range else '✗'}（{len(bad_range)} 例外）")
    print(f"  自检③ 点评非空：{'✅' if not bad_cmt else '✗'}（{len(bad_cmt)} 例外）")
    print(f"  自检④ 菜系在类目内：{'✅' if not bad_cat else '✗'}（{len(bad_cat)} 例外）")

    tot = [r["total"] for r in rows]
    print(f"  总分：最低 {min(tot)} / 最高 {max(tot)} / 均值 {sum(tot)/len(tot):.1f}")
    dimavg = [sum(r["scores"][i] for r in rows) / len(rows) for i in range(9)]
    print("  各维度均值：" + " ".join(f"{DIMS[i]}{dimavg[i]:.1f}" for i in range(9)))
    dist_c = Counter(r["district"] or "未标注" for r in rows)
    print(f"  覆盖区域 {len([k for k in dist_c if k != '未标注'])} 个，未标注 {dist_c.get('未标注',0)} 家")
    cat_c = Counter(r["cat"] for r in rows)
    print(f"  菜系 {len(cat_c)} 类：" + "、".join(f"{k}{v}" for k, v in cat_c.most_common()))

    if errs:
        print("\n✗ 自检未通过：")
        for e in errs:
            print("   -", e)
        sys.exit(1)
    print("\n✅ 全部自检通过")


if __name__ == "__main__":
    main()
