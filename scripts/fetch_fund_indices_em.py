#!/usr/bin/env python3
"""
基金指数数据填充脚本 v2：使用 akshare stock_zh_index_daily (腾讯源)
精选14只核心市场指数，拉取日线数据，计算各周期收益率，写入 fund_indices 表。
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

# 精选指数清单（腾讯源代码格式: sh=上海, sz=深圳）
INDICES = [
    {"code": "sh000300", "wind_code": "000300", "name": "沪深300",       "category": "宽基指数"},
    {"code": "sh000016", "wind_code": "000016", "name": "上证50",         "category": "宽基指数"},
    {"code": "sh000905", "wind_code": "000905", "name": "中证500",         "category": "宽基指数"},
    {"code": "sh000852", "wind_code": "000852", "name": "中证1000",       "category": "宽基指数"},
    {"code": "sz399006", "wind_code": "399006", "name": "创业板指",       "category": "宽基指数"},
    {"code": "sh000688", "wind_code": "000688", "name": "科创50",         "category": "宽基指数"},
    {"code": "sz399001", "wind_code": "399001", "name": "深证成指",       "category": "宽基指数"},
    {"code": "sh000919", "wind_code": "000919", "name": "沪深300价值",     "category": "策略指数"},
    {"code": "sh000932", "wind_code": "000932", "name": "中证红利",       "category": "策略指数"},
    {"code": "sz399997", "wind_code": "399997", "name": "中证白酒",       "category": "行业指数"},
    {"code": "sz399989", "wind_code": "399989", "name": "中证医药",       "category": "行业指数"},
    {"code": "sz399808", "wind_code": "399808", "name": "中证新能源",     "category": "行业指数"},
    {"code": "sz980017", "wind_code": "980017", "name": "国证芯片",       "category": "行业指数"},
    {"code": "sz399975", "wind_code": "399975", "name": "证券公司",       "category": "行业指数"},
]


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={"query": sql}, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  SQL error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def fetch_and_calc(symbol):
    """拉取单只指数日线 + 计算各周期收益"""
    try:
        df = ak.stock_zh_index_daily(symbol=symbol)
        if df is None or df.empty or len(df) < 10:
            return None, None
        
        df['date'] = df['date'].astype(str).str[:10]
        prices = df['close'].astype(float).tolist()
        dates = df['date'].tolist()
        n = len(prices)
        last_price = prices[-1]
        
        result = {}
        # YTD
        cur_year = str(datetime.date.today().year)
        ytd_prices = [p for p, d in zip(prices, dates) if d.startswith(cur_year)]
        if ytd_prices:
            result['ytd'] = round((last_price / ytd_prices[0] - 1) * 100, 2)
        
        # 各周期
        periods = {'r1w': 5, 'r1m': 22, 'r3m': 66, 'r6m': 125, 'r1y': 252, 'r3y': 756, 'r5y': 1260}
        for key, days in periods.items():
            if n > days + 1:
                result[key] = round((last_price / prices[-days - 1] - 1) * 100, 2)
        
        # 成立以来
        result['since_inception'] = round((last_price / prices[0] - 1) * 100, 2)
        
        # 历年收益
        year_map = {2026:'ytd',2025:'year1',2024:'year2',2023:'year3',2022:'year4',
                   2021:'year5',2020:'year6',2019:'year7',2018:'year8',2017:'year9'}
        for yr, key in year_map.items():
            yr_data = [(p, d) for p, d in zip(prices, dates) if d.startswith(str(yr))]
            if len(yr_data) >= 2:
                result[key] = round((yr_data[-1][0] / yr_data[0][0] - 1) * 100, 2)
        
        return df, result
    except Exception as e:
        print(f"    Error: {e}")
        return None, None


def main():
    print("=== 基金指数数据填充（腾讯源） ===\n")
    print(f"akshare: {ak.__version__} | 指数: {len(INDICES)} 只\n")

    run_sql("TRUNCATE TABLE fund_indices RESTART IDENTITY;")
    
    success, fail = 0, 0
    for i, idx in enumerate(INDICES):
        symbol = idx['code']
        name = idx['name']
        print(f"[{i+1}/{len(INDICES)}] {symbol} {name}", end=" ... ")
        
        df, market_perf = fetch_and_calc(symbol)
        if not market_perf:
            print("❌"); fail += 1; continue
        
        basic_info = json.dumps({
            "ytd": market_perf.get('ytd'),
            "issuing_date": "",
            "ingredient_num": str(len(df)),
            "weighting_mode": "市值加权",
            "return_mode": "价格收益",
        }, ensure_ascii=False)
        
        sql = f"""
        INSERT INTO fund_indices (wind_code, name_cn, category, basic_info, market_perf, annual_perf, valuation)
        VALUES ('{idx["wind_code"]}', '{idx["name"]}', '{idx["category"]}',
                '{basic_info}'::jsonb,
                '{json.dumps(market_perf, ensure_ascii=False)}'::jsonb,
                '{{"ytd":{market_perf.get("ytd","null")}}}'::jsonb,
                '{{}}'::jsonb);
        """
        r = run_sql(sql)
        if r is not None:
            print(f"✅ YTD={market_perf.get('ytd','?')}% 1Y={market_perf.get('r1y','?')}% ({len(df)}d)")
            success += 1
        else:
            print("❌ 写入失败"); fail += 1
        time.sleep(0.2)

    print(f"\n{'='*40}\n✅ {success} 成功 | ❌ {fail} 失败")


if __name__ == "__main__":
    main()
