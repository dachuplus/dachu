#!/usr/bin/env python3
"""
基金指数数据填充脚本 v3：使用 akshare stock_zh_index_daily (腾讯源)

拉取「腾讯源里面真正的基金指数」（tracking baskets of funds, 非股票指数），
计算各周期收益率与历年表现，写入 fund_indices 表。

腾讯源可用的基金指数（经 qt.gtimg.cn 实时API核对名称）：
  - sh000011 上证基金指数（2000起，活跃）  —— 上交所全部上市基金
  - sz399379 国证基金（2011起，活跃）      —— 深市基金综合
  - sz399306 深证ETF指数（2011起，活跃）   —— 深市 ETF 基金
  - sz399305 深证基金指数（1997起，停更2017-06-30）—— 保留历史
注：sz399307 为「深证转债」（可转债），非基金指数，已排除。

对于停更指数（last_date 距今 > 30 天），只保留成立以来 + 历年表现，
不计算 YTD/近N期收益（避免用陈旧价格误导）。
"""

import os
import sys
import json
import time
import datetime

import akshare as ak
import requests

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
MGMT_API = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
}

# 腾讯源真正的基金指数清单（code=腾讯格式 sh/sz 前缀；wind_code=纯数字展示码）
INDICES = [
    {"code": "sh000011", "wind_code": "000011", "name": "上证基金指数", "category": "综合基金指数"},
    {"code": "sz399379", "wind_code": "399379", "name": "国证基金",     "category": "综合基金指数"},
    {"code": "sz399306", "wind_code": "399306", "name": "深证ETF指数",  "category": "ETF基金指数"},
    {"code": "sz399305", "wind_code": "399305", "name": "深证基金指数", "category": "综合基金指数"},
]


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={"query": sql}, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  SQL error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def fetch_and_calc(symbol):
    """拉取单只指数日线 + 计算各周期收益（对停更指数做防陈旧处理）"""
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty or len(df) < 10:
            return None, None

        df['date'] = df['date'].astype(str).str[:10]
        prices = df['close'].astype(float).tolist()
        dates = df['date'].tolist()
        n = len(prices)
        last_price = prices[-1]
        last_date = datetime.date.fromisoformat(dates[-1])
        today = datetime.date.today()
        stale = (today - last_date).days > 30  # 停更指数

        result = {}

        # 成立以来（始终有效）
        result['since_inception'] = round((last_price / prices[0] - 1) * 100, 2)

        # 历年收益（始终有效，取每年首末交易日）
        year_map = {2026: 'ytd', 2025: 'year1', 2024: 'year2', 2023: 'year3', 2022: 'year4',
                    2021: 'year5', 2020: 'year6', 2019: 'year7', 2018: 'year8', 2017: 'year9'}
        annual = {}
        for yr, key in year_map.items():
            yr_data = [(p, d) for p, d in zip(prices, dates) if d.startswith(str(yr))]
            if len(yr_data) >= 2:
                annual[key] = round((yr_data[-1][0] / yr_data[0][0] - 1) * 100, 2)

        if not stale:
            # YTD
            cur_year = str(today.year)
            ytd_prices = [p for p, d in zip(prices, dates) if d.startswith(cur_year)]
            if ytd_prices:
                result['ytd'] = round((last_price / ytd_prices[0] - 1) * 100, 2)
            # 各滚动周期
            periods = {'r1w': 5, 'r1m': 22, 'r3m': 66, 'r6m': 125, 'r1y': 252, 'r3y': 756, 'r5y': 1260}
            for key, days in periods.items():
                if n > days + 1:
                    result[key] = round((last_price / prices[-days - 1] - 1) * 100, 2)
            # 历年表现中的 ytd 用真实 ytd
            if 'ytd' in result:
                annual['ytd'] = result['ytd']

        return df, {"market": result, "annual": annual, "stale": stale, "last_date": dates[-1]}
    except Exception as e:
        print(f"    Error: {e}")
        return None, None


def main():
    print("=== 基金指数数据填充（腾讯源·真正基金指数） ===\n")
    print(f"akshare: {ak.__version__} | 基金指数: {len(INDICES)} 只\n")

    run_sql("TRUNCATE TABLE fund_indices RESTART IDENTITY;")

    success, fail = 0, 0
    for i, idx in enumerate(INDICES):
        symbol = idx['code']
        name = idx['name']
        print(f"[{i+1}/{len(INDICES)}] {symbol} {name}", end=" ... ")

        df, calc = fetch_and_calc(symbol)
        if not calc:
            print("❌"); fail += 1; continue

        market_perf = calc['market']
        annual_perf = calc['annual']
        stale_tag = "（停更历史）" if calc['stale'] else ""

        basic_info = json.dumps({
            "ytd": market_perf.get('ytd'),
            "issuing_date": df['date'].iloc[0].replace('-', ''),
            "ingredient_num": str(len(df)),
            "weighting_mode": "总市值加权",
            "return_mode": "价格收益",
            "last_date": calc['last_date'],
        }, ensure_ascii=False)

        def esc(s):
            return str(s).replace("'", "''")

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
            print(f"✅ YTD={market_perf.get('ytd','-')}% 1Y={market_perf.get('r1y','-')}% 成立来={market_perf.get('since_inception','?')}% ({len(df)}d){stale_tag}")
            success += 1
        else:
            print("❌ 写入失败"); fail += 1
        time.sleep(0.2)

    print(f"\n{'='*40}\n✅ {success} 成功 | ❌ {fail} 失败")


if __name__ == "__main__":
    main()
