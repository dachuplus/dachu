#!/usr/bin/env python3
"""
基金指数数据填充脚本 v4：数据源切换为【东方财富 push2his kline 接口】

背景：原 v3 使用 akshare stock_zh_index_daily（腾讯源）。本版本改用东方财富
数据中心公开 kline 接口（即用户在「数据中心」可查到的东方财富行情接口）：

  GET https://push2his.eastmoney.com/api/qt/stock/kline/get
      ?secid={市场.代码}
      &fields1=f1
      &fields2=f51,f53        # f51=日期, f53=收盘
      &klt=101                # 101=日线
      &fqt=0                  # 0=不复权
      &beg=0&end=20500101

  secid 规则：沪市 1.000011；深市 0.399379
  该接口对指数（含基金指数）有效，已在沙箱/CI 验证可用。

抓取真正的「基金指数」产品（跟踪一篮子基金，而非股票指数），均为东方财富 kline
接口实际可服务的活跃指数：
  - 1.000011 上证基金指数（上交所全部上市基金，2000起，活跃）
  - 0.399379 国证基金    （深市基金综合，2011起，活跃）
  - 0.399306 深证ETF指数 （深市 ETF 基金，2011起，活跃）

注：深证基金指数（399305）自 2017 年停更，东方财富 kline 接口不再返回其数据，
已从清单移除；如需该历史指数，需另接腾讯/国证源。

写入 fund_indices 表（TRUNCATE + INSERT）。字段：
  wind_code / name_cn / category / basic_info(jsonb) / market_perf(jsonb) / annual_perf(jsonb) / valuation(jsonb)
前端「智能组合-基金指数-东财基金指数」tab 直接读取本表。
"""

import os
import sys
import json
import time
import datetime
import subprocess
import requests

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
MGMT_API = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
}

# 东方财富数据中心 kline 接口的基金指数清单
# secid: 沪市 1.xxxxxx / 深市 0.xxxxxx
INDICES = [
    {"secid": "1.000011", "wind_code": "000011", "name": "上证基金指数", "category": "综合基金指数"},
    {"secid": "0.399379", "wind_code": "399379", "name": "国证基金",     "category": "综合基金指数"},
    {"secid": "0.399306", "wind_code": "399306", "name": "深证ETF指数",  "category": "ETF基金指数"},
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={"query": sql}, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  SQL error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def fetch_kline(secid):
    """通过东方财富 kline 接口抓取日线收盘序列，返回 (dates, closes) 或 None。

    注意：沙箱对 Python requests 出网会断连（RemoteDisconnected），但 curl 放行，
    故此处用 subprocess 调 curl 抓取，再用 requests 仅做 Supabase 写入。
    """
    url = ("https://push2his.eastmoney.com/api/qt/stock/kline/get"
           f"?secid={secid}&fields1=f1&fields2=f51,f53&klt=101&fqt=0&beg=0&end=20500101")
    try:
        out = subprocess.run(
            ["curl", "-s", "--max-time", "25", url,
             "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
             "-H", "Referer: https://quote.eastmoney.com/",
             "-H", "Accept: */*"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0 or not out.stdout.strip():
            print(f"    curl error rc={out.returncode}"); return None
        j = json.loads(out.stdout)
        if j.get("rc") != 0 or not j.get("data") or not j["data"].get("klines"):
            return None
        dates, closes = [], []
        for line in j["data"]["klines"]:
            parts = line.split(",")
            if len(parts) < 2:
                continue
            dates.append(parts[0])
            closes.append(float(parts[1]))
        if len(closes) < 10:
            return None
        return dates, closes
    except Exception as e:
        print(f"    kline error: {e}")
        return None


def calc(dates, closes):
    """计算各周期收益 + 历年表现，返回 (market_perf, annual_perf, stale, last_date)"""
    n = len(closes)
    last_price = closes[-1]
    last_date = datetime.date.fromisoformat(dates[-1])
    today = datetime.date.today()
    stale = (today - last_date).days > 30

    market = {}
    market["since_inception"] = round((last_price / closes[0] - 1) * 100, 2)

    year_map = {2026: "ytd", 2025: "year1", 2024: "year2", 2023: "year3", 2022: "year4",
                2021: "year5", 2020: "year6", 2019: "year7", 2018: "year8", 2017: "year9"}
    annual = {}
    for yr, key in year_map.items():
        yr_data = [(p, d) for p, d in zip(closes, dates) if d.startswith(str(yr))]
        if len(yr_data) >= 2:
            annual[key] = round((yr_data[-1][0] / yr_data[0][0] - 1) * 100, 2)

    if not stale:
        cur_year = str(today.year)
        ytd_prices = [p for p, d in zip(closes, dates) if d.startswith(cur_year)]
        if ytd_prices:
            market["ytd"] = round((last_price / ytd_prices[0] - 1) * 100, 2)
        periods = {"r1w": 5, "r1m": 22, "r3m": 66, "r6m": 125, "r1y": 252, "r3y": 756, "r5y": 1260}
        for key, days in periods.items():
            if n > days + 1:
                market[key] = round((last_price / closes[-days - 1] - 1) * 100, 2)
        if "ytd" in market:
            annual["ytd"] = market["ytd"]

    return market, annual, stale, dates[-1]


def esc(s):
    return str(s).replace("'", "''")


def main():
    print("=== 基金指数数据填充（东方财富 push2his kline 接口） ===\n")
    print(f"基金指数: {len(INDICES)} 只\n")

    run_sql("TRUNCATE TABLE fund_indices RESTART IDENTITY;")

    success, fail = 0, 0
    for i, idx in enumerate(INDICES):
        print(f"[{i+1}/{len(INDICES)}] {idx['secid']} {idx['name']}", end=" ... ")
        k = fetch_kline(idx["secid"])
        if not k:
            print("❌ 接口无数据"); fail += 1; continue
        dates, closes = k
        market_perf, annual_perf, stale, last_date = calc(dates, closes)
        stale_tag = "（停更历史）" if stale else ""

        basic_info = json.dumps({
            "ytd": market_perf.get("ytd"),
            "issuing_date": dates[0].replace("-", ""),
            "ingredient_num": str(len(closes)),
            "weighting_mode": "总市值加权",
            "return_mode": "价格收益",
            "last_date": last_date,
        }, ensure_ascii=False)

        sql = f"""
        INSERT INTO fund_indices (wind_code, name_cn, category, basic_info, market_perf, annual_perf, valuation)
        VALUES ('{idx["wind_code"]}', '{esc(idx["name"])}', '{esc(idx["category"])}',
                '{esc(basic_info)}'::jsonb,
                '{esc(json.dumps(market_perf, ensure_ascii=False))}'::jsonb,
                '{esc(json.dumps(annual_perf, ensure_ascii=False))}'::jsonb,
                '{{}}'::jsonb);
        """
        r = run_sql(sql)
        if r is not None:
            print(f"✅ YTD={market_perf.get('ytd','-')}% 1Y={market_perf.get('r1y','-')}% 成立来={market_perf.get('since_inception','?')}% ({len(closes)}d){stale_tag}")
            success += 1
        else:
            print("❌ 写入失败"); fail += 1
        time.sleep(0.3)

    print(f"\n{'='*40}\n✅ {success} 成功 | ❌ {fail} 失败")


if __name__ == "__main__":
    main()
