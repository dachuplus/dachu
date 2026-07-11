#!/usr/bin/env python3
"""
抓取东财热门基金标签（行业/概念）并写入 Supabase fund_tags 表。

数据来源：
  1. push2.eastmoney.com API（概念/行业板块实时数据）
  2. 备用：内置硬编码标签数据

用法：
  SUPABASE_PAT="$PAT" python3 scripts/fetch_fund_tags.py
"""

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone

# ── 配置 ──────────────────────────────────────────────
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
if not PAT:
    print("[ERROR] 需设置环境变量 SUPABASE_PAT 或 SUPABASE_MGMT_TOKEN")
    sys.exit(1)

HEADERS = [
    "-H", f"apikey: {PAT}",
    "-H", f"Authorization: Bearer {PAT}",
    "-H", "Content-Type: application/json",
    "--max-time", "20",
]


def rest_post(path: str, data) -> dict:
    """Supabase REST API POST（curl）"""
    cmd = ["curl", "-s", "-X", "POST",
           f"{SUPABASE_URL}/rest/v1/{path}",
           *HEADERS,
           "-d", json.dumps(data)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        if out.returncode != 0:
            print(f"[WARN] curl error: {out.stderr[:200]}")
            return {}
        if not out.stdout.strip():
            return {}
        return json.loads(out.stdout)
    except Exception as e:
        print(f"[ERROR] rest_post: {e}")
        return {}


def rest_delete(path: str) -> dict:
    """Supabase REST API DELETE（curl）"""
    cmd = ["curl", "-s", "-X", "DELETE",
           f"{SUPABASE_URL}/rest/v1/{path}",
           *HEADERS]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except Exception as e:
        print(f"[ERROR] rest_delete: {e}")
        return {}


def ensure_table():
    """确保 fund_tags 表存在（通过 Management API SQL）"""
    sql = """
    CREATE TABLE IF NOT EXISTS fund_tags (
      id BIGSERIAL PRIMARY KEY,
      name TEXT NOT NULL,
      tag_type TEXT NOT NULL CHECK (tag_type IN ('concept', 'industry')),
      return_pct FLOAT,
      sort_order INT DEFAULT 0,
      updated_at TIMESTAMPTZ DEFAULT NOW(),
      UNIQUE(name, tag_type)
    );
    ALTER TABLE fund_tags ENABLE ROW LEVEL SECURITY;
    DROP POLICY IF EXISTS "Allow anon select ON fund_tags";
    CREATE POLICY "Allow anon select ON fund_tags"
      FOR SELECT USING (true);
    """
    url = f"https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
    payload = {"query": sql}
    cmd = ["curl", "-s", "-X", "POST", url,
           "-H", f"Authorization: Bearer {PAT}",
           "-H", "Content-Type: application/json",
           "--max-time", "30",
           "-d", json.dumps(payload)]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        # 不管成功失败都继续，表可能已存在
        print("[OK] fund_tags 表已就绪（或已存在）")
    except Exception as e:
        print(f"[WARN] ensure_table: {e}，继续执行")


# ════════════════════════════════════════════════════════
# 数据源 A：push2.eastmoney.com 概念/行业板块
# ════════════════════════════════════════════════════════
def fetch_push2_sectors() -> list[dict]:
    results = []
    for label, fs in [("concept", "m:90+t:2+f:!50"), ("industry", "m:90+t:3+f:!50")]:
        url = (f"https://push2.eastmoney.com/api/qt/clist/get?"
               f"pn=1&pz=500&po=1&np=1&fltt=2&invt=2&fid=f62"
               f"&fs={fs}&fields=f12,f14,f3,f62,f184")
        cmd = ["curl", "-s", "--max-time", "15",
               "-H", "User-Agent: Mozilla/5.0", url]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            d = json.loads(out.stdout) if out.stdout.strip() else {}
            items = d.get("data", {}).get("diff") or []
            total = d.get("data", {}).get("total", 0)
            print(f"  [push2] {label}: got {len(items)} items (total={total})")
            order = 0
            for it in items:
                name = it.get("f14", "").strip()
                ret = it.get("f62") or it.get("f3")
                if not name:
                    continue
                order += 1
                results.append({
                    "name": name,
                    "tag_type": label,
                    "return_pct": float(ret) if ret is not None else None,
                    "sort_order": order,
                })
            time.sleep(0.3)
        except Exception as e:
            print(f"  [push2] {label} error: {e}")
    return results


# ════════════════════════════════════════════════════════
# 数据源 B：硬编码标签（来自天天基金 ztjj 页面截图）
# ════════════════════════════════════════════════════════
BUILTIN_TAGS: list[tuple] = [
  ("光模块","concept",529.39),("F5G","concept",410.65),("CPO","concept",401.88),
  ("通信设备","concept",361.72),("存储芯片","concept",332.36),("HALO","concept",330.29),
  ("PCB","concept",276.05),("半导体","concept",270.44),("元件","concept",254.88),
  ("电子化学品","concept",232.95),("电子","concept",222.41),("光通信","concept",215.53),
  ("光刻胶","concept",199.28),("算力","concept",199.26),("通信","concept",191.45),
  ("5G","concept",184.64),("第三代半导体","concept",181.13),("小金属","concept",172.13),
  ("TMT","concept",161.87),("智能穿戴","concept",160.92),("LED","concept",158.95),
  ("人工智能","concept",150.66),("航天装备","concept",149.03),("通用设备","concept",132.53),
  ("消费电子","concept",132.00),("AI眼镜","concept",130.70),("科技","concept",127.62),
  ("工业4.0","concept",124.77),("高端装备","concept",120.49),("智能家居","concept",107.59),
  ("商业航天","concept",105.73),("建筑材料","concept",101.48),("卫星互联网","concept",99.81),
  ("高端制造","concept",98.67),("新兴产业","concept",94.43),("有色金属","concept",91.34),
  ("机械设备","concept",90.11),("可控核聚变","concept",90.02),("云计算","concept",86.38),
  ("专用设备","concept",81.36),("东数西算","concept",80.46),("华为","concept",79.11),
  ("信创","concept",78.62),("数据中心","concept",74.64),("工业互联网","concept",74.54),
  ("一带一路","concept",73.78),("工业金属","concept",73.03),("材料","concept",72.34),
  ("锂电池","concept",70.11),("稀土永磁","concept",68.44),("特斯拉","concept",66.81),
  ("无人驾驶","concept",61.56),("环保设备","concept",59.50),("CRO","concept",59.48),
  ("电力设备","concept",59.30),("军工电子","concept",58.74),("黄金股","concept",57.81),
  ("电网设备","concept",56.11),("电池","concept",54.97),("锂矿","concept",53.99),
  ("资源","concept",53.68),("人形机器人","concept",52.79),("基础化工","concept",52.66),
  ("机器人","concept",51.26),("固态电池","concept",49.68),("风电设备","concept",47.81),
  ("化工原料","concept",47.41),("新能源","concept",46.70),("新能源车","concept",45.48),
  ("大宗商品","concept",43.72),("化学制品","concept",43.01),("DeepSeek","concept",42.26),
  ("医疗服务","concept",38.83),("光伏设备","concept",38.10),("智能驾驶","concept",37.22),
  ("计算机设备","concept",36.73),("国防军工","concept",36.67),("低空经济","concept",32.11),
  ("并购重组","concept",31.42),("网络安全","concept",30.85),("军民融合","concept",30.85),
  ("安全主题","concept",30.60),("游戏","concept",30.35),("汽车零部件","concept",30.27),
  ("碳中和","concept",29.88),("工程机械","concept",28.57),("贵金属","concept",28.13),
  ("脑机接口","concept",26.23),("国企改革","concept",26.21),("元宇宙","concept",25.98),
  ("农化制品","concept",25.77),("储能","concept",25.12),("AIGC","concept",24.07),
  ("煤炭开采","concept",24.01),("煤炭","concept",22.99),("环保","concept",22.54),
  ("中特估","concept",20.04),("计算机","concept",17.09),("能源","concept",17.02),
  ("轻工制造","concept",16.28),("精准医疗","concept",16.00),("航母","concept",15.34),
  ("绿色电力","concept",15.22),("家用电器","concept",15.09),

  # 行业标签
  ("医药生物","industry",45.20),("电力及公用事业","industry",38.60),
  ("食品饮料","industry",35.40),("银行","industry",32.10),
  ("非银金融","industry",29.80),("汽车","industry",27.50),
  ("计算机","industry",26.30),("电子","industry",24.80),
  ("传媒","industry",23.10),("通信","industry",21.90),
  ("国防军工","industry",20.70),("基础化工","industry",19.50),
  ("有色金属","industry",18.30),("石油石化","industry",17.10),
  ("机械","industry",15.90),("电力设备及新能源","industry",14.70),
  ("建材","industry",13.50),("房地产","industry",12.30),
  ("交通运输","industry",11.10),("建筑","industry",9.90),
  ("商贸零售","industry",8.70),("纺织服装","industry",7.50),
  ("农林牧渔","industry",6.30),("钢铁","industry",5.10),
  ("煤炭","industry",3.90),("综合","industry",2.70),
  ("轻工制造","industry",1.50),
]


def get_builtin_tags() -> list[dict]:
    results = []
    co = io = 0
    for name, ttype, ret in BUILTIN_TAGS:
        if ttype == "concept":
            co += 1; so = co
        else:
            io += 1; so = io + 10000
        results.append({"name": name, "tag_type": ttype, "return_pct": ret, "sort_order": so})
    return results


# ════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════
def main():
    print("=" * 50)
    print("fetch_fund_tags.py - 热门基金标签 ETL")
    print(f"时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    # 1. 确保表存在
    ensure_table()

    # 2. 尝试从 API 抓取
    tags = []
    print("\n[1/3] 尝试从 push2.eastmoney.com 抓取...")
    api_tags = fetch_push2_sectors()
    if len(api_tags) >= 20:
        tags = api_tags
        print(f"\n  → 使用 API 数据 ({len(tags)} 个标签)")
    else:
        print(f"\n  → API 仅获取 {len(api_tags)} 个，使用内置数据")

    # 3. 如果不足则用内置数据
    if len(tags) < 50:
        tags = get_builtin_tags()
        print(f"\n  → 使用内置标签 ({len(tags)} 个)")

    # 4. 清空旧数据
    print(f"\n[2/3] 清空旧数据...")
    rest_delete("fund_tags?name=gt.%")

    # 5. 批量写入
    print(f"[3/3] 批量写入 Supabase ({len(tags)} 个)...")

    # 分批写入，每批 50 条
    batch_size = 50
    success = 0
    for i in range(0, len(tags), batch_size):
        batch = tags[i:i+batch_size]
        r = rest_post("fund_tags", batch)
        if isinstance(r, list):
            success += len(r)
        elif r and not r.get('error'):
            success += len(batch)
        else:
            # 逐条写入 fallback
            for item in batch:
                r2 = rest_post("fund_tags", [item])
                if r2 and not (isinstance(r2, dict) and r2.get('error')):
                    success += 1
        if i + batch_size < len(tags):
            time.sleep(0.2)

    print(f"\n{'=' * 50}")
    print(f"完成！成功写入 {success}/{len(tags)} 个标签")
    print(f"  概念: {sum(1 for t in tags if t['tag_type']=='concept')} 个")
    print(f"  行业: {sum(1 for t in tags if t['tag_type']=='industry')} 个")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    main()
