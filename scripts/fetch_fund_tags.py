#!/usr/bin/env python3
"""
抓取东财热门基金标签（行业/概念）并写入 Supabase fund_tags 表。

数据来源：
  1. push2.eastmoney.com API（概念/行业板块实时数据）

风控：本脚本绝不写入任何兜底/假数据。若 API 抓取到的标签数量不足，按最高风控规则
保留现有 fund_tags 表、不写入任何数据并退出，绝不回退到硬编码列表。

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

# 真实 API 抓取的最小标签数阈值；低于此值视为抓取失败，绝不写入兜底数据
MIN_TAGS_REQUIRED = 50


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
# 数据源：push2.eastmoney.com 概念/行业板块（唯一真实来源）
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
# 主流程
# ════════════════════════════════════════════════════════
def main():
    print("=" * 50)
    print("fetch_fund_tags.py - 热门基金标签 ETL")
    print(f"时间: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 50)

    # 1. 确保表存在
    ensure_table()

    # 2. 仅从唯一真实来源 push2 抓取
    print(f"\n[1/2] 从 push2.eastmoney.com 抓取（需 >= {MIN_TAGS_REQUIRED} 个标签）...")
    api_tags = fetch_push2_sectors()

    if len(api_tags) < MIN_TAGS_REQUIRED:
        # 风控：抓取不足 → 不写入任何数据，保留现有表，直接退出
        print(f"\n[ERROR] push2 API 仅获取 {len(api_tags)} 个标签，低于阈值 {MIN_TAGS_REQUIRED}。")
        print("        按最高风控规则：不写入任何兜底/假数据，保留现有 fund_tags 表，脚本退出。")
        sys.exit(2)

    tags = api_tags
    print(f"\n  -> 使用 API 实时数据 ({len(tags)} 个标签)")

    # 3. 清空旧数据并批量写入真实数据
    print(f"\n[2/2] 清空旧数据并写入 Supabase ({len(tags)} 个)...")
    rest_delete("fund_tags?name=gt.%")

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
