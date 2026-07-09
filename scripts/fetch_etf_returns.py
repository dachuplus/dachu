#!/usr/bin/env python3
"""
场内基金(ETF/LOF)区间收益填充脚本

背景：fund_scores / fund_combined 仅收录场外基金（.OF 后缀），
不含 ETF/LOF 等场内基金。用户自建组合里包含 ETF（如 511880、510050），
故其区间收益无法从 fund_scores 计算 → 组合区间收益整段不显示。

方案：从「腾讯 K 线 API」拉取自建组合中所有场内基金（bare code，无 .OF）
的前复权日线，计算 daily_change / r0w / r1m / r3m / r6m / r1y / r2y / r3y / r5y，
UPSERT 进 etf_returns 表。前端 loadPortfolioReturns 合并 fund_scores + etf_returns。

数据源：https://web.ifzq.gtimg.cn/appstock/app/fqkline/get （腾讯，沙箱可用）
"""

import os
import sys
import json
import time

import requests

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
MGMT_API = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
QUOTE_URL = "http://qt.gtimg.cn/q="

# 交易日偏移（约）
PERIODS = {"r0w": 5, "r1m": 22, "r3m": 66, "r6m": 125, "r1y": 252, "r2y": 504, "r3y": 756, "r5y": 1260}


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={"query": sql}, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  SQL error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def tx_symbol(code):
    """bare code -> 腾讯前缀符号。5/6 开头=沪(sh)，1/0/3 开头=深(sz)。"""
    return ("sh" if code[0] in "56" else "sz") + code


def get_name(sym):
    try:
        r = requests.get(QUOTE_URL + sym, timeout=10)
        r.encoding = "gbk"
        parts = r.text.split('="')[1].split("~")
        return parts[1] if len(parts) > 1 else sym
    except Exception:
        return sym


def fetch_kline(sym):
    """返回 [(date, close), ...] 前复权，按日期升序。"""
    url = f"{KLINE_URL}?param={sym},day,,,1700,qfq"
    r = requests.get(url, timeout=15)
    d = r.json()
    node = d.get("data", {}).get(sym, {})
    kline = node.get("qfqday") or node.get("day") or []
    out = []
    for row in kline:
        try:
            out.append((row[0], float(row[2])))
        except Exception:
            continue
    return out


def calc_returns(kline):
    if len(kline) < 6:
        return None
    closes = [c for _, c in kline]
    n = len(closes)
    last = closes[-1]
    result = {}
    # 当日涨跌幅
    if n >= 2 and closes[-2]:
        result["daily_change"] = round((last / closes[-2] - 1) * 100, 2)
    for key, days in PERIODS.items():
        if n > days + 1 and closes[-days - 1]:
            result[key] = round((last / closes[-days - 1] - 1) * 100, 2)
    return result


def load_etf_codes():
    """从 user_portfolios 收集所有场内(bare)代码。"""
    r = run_sql("SELECT portfolio_data FROM user_portfolios WHERE portfolio_data IS NOT NULL")
    codes = set()
    for row in r or []:
        pd = row.get("portfolio_data")
        if isinstance(pd, list):
            for h in pd:
                c = h.get("code")
                if c and "." not in c:  # 场内基金无 .OF 后缀
                    codes.add(c)
    return sorted(codes)


def main():
    print("=== 场内基金区间收益填充（腾讯K线） ===\n")
    codes = load_etf_codes()
    print(f"待处理场内基金: {len(codes)} 只 -> {codes}\n")
    if not codes:
        print("无场内基金，退出。")
        return

    ok, fail = 0, 0
    for i, code in enumerate(codes):
        sym = tx_symbol(code)
        print(f"[{i+1}/{len(codes)}] {code} ({sym})", end=" ... ")
        try:
            kline = fetch_kline(sym)
            ret = calc_returns(kline)
            if not ret:
                print("❌ 无数据"); fail += 1; continue
            name = get_name(sym)
            last_date = kline[-1][0]

            def val(k):
                v = ret.get(k)
                return "NULL" if v is None else str(v)

            name_esc = name.replace("'", "''")
            sql = f"""
            INSERT INTO etf_returns (c, name, daily_change, r0w, r1m, r3m, r6m, r1y, r2y, r3y, r5y, last_date, updated_at)
            VALUES ('{code}', '{name_esc}', {val('daily_change')}, {val('r0w')}, {val('r1m')}, {val('r3m')},
                    {val('r6m')}, {val('r1y')}, {val('r2y')}, {val('r3y')}, {val('r5y')}, '{last_date}', now())
            ON CONFLICT (c) DO UPDATE SET
              name=EXCLUDED.name, daily_change=EXCLUDED.daily_change,
              r0w=EXCLUDED.r0w, r1m=EXCLUDED.r1m, r3m=EXCLUDED.r3m, r6m=EXCLUDED.r6m,
              r1y=EXCLUDED.r1y, r2y=EXCLUDED.r2y, r3y=EXCLUDED.r3y, r5y=EXCLUDED.r5y,
              last_date=EXCLUDED.last_date, updated_at=now();
            """
            if run_sql(sql) is not None:
                print(f"✅ {name} 当日={ret.get('daily_change','-')}% 1年={ret.get('r1y','-')}% ({len(kline)}d)")
                ok += 1
            else:
                print("❌ 写入失败"); fail += 1
        except Exception as e:
            print(f"❌ {str(e)[:60]}"); fail += 1
        time.sleep(0.15)

    print(f"\n{'='*40}\n✅ {ok} 成功 | ❌ {fail} 失败")


if __name__ == "__main__":
    main()
