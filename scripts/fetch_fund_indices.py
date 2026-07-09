#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
基金指数数据 ETL
================
数据源：万得基金指数官网 https://www.windindices.com/indices/zh/WindIndex
（真实 API 端点已逆向：/indexinfo /indexreturn /IndexAnnualYield /indexValuation）

说明（重要）
----------
万得公共 API 对「逐指数」数据是会话态钉死的：未携带浏览器会话时，
/indexinfo、/indexreturn、/IndexAnnualYield、/indexValuation 均忽略传入的
windcode/indexid 参数，固定返回默认指数（881001.WI 万得全A）或若干热门股票指数，
因此在本无头环境下无法直接抓到 885xxx 基金指数的明细数据。

本脚本的做法：
  1. 内置一份「真实可信的万得基金指数代码清单」（885001~885013、864001 等）；
  2. 逐一对 Wind 真实 API 端点发起请求，若返回的 windCode 与请求一致则解析入库
     （浏览器会话可用时即能自动填充，无需改代码）；
  3. 将「代码 / 名称 / 分类 / 类型」等确定性元数据 + 各模块 JSON（可取时填充，
     暂不可取时为 null）通过 Supabase Management API 以 SQL UPSERT 写入 fund_indices 表。

后续若要全量实时数据，二选一：
  A. 在「能建立浏览器会话」的环境（如带头浏览器/本地浏览器代理）运行本脚本，
     把会话 Cookie 注入请求即可解锁全部 129 个基金指数；
  B. 将 DATA_BACKEND 切换为 'sww'（申万基金指数，akshare 可取，需绕过沙箱 SSL），
     用申万基金指数历史反算市场表现/历年表现。
"""
import os
import sys
import json
import requests
from datetime import datetime

# ===== Supabase Management API（用于执行 DDL/UPSERT，无需 service_role key）=====
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
REF = "tqhtegazxykkqfcpejky"
API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
HEADERS = {"Authorization": f"Bearer {PAT}", "Content-Type": "application/json"}

WIND_API = "https://www.windindices.com/indicesWebsite/api"
WIND_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://www.windindices.com/indices/zh/WindIndex",
}

# 真实可信的万得基金指数代码清单（code, 名称, 分类, 类型）
CURATED = [
    ("864001.WI", "中国基金总指数", "基金总指数", "总指数"),
    ("885001.WI", "普通股票型基金指数", "股票类", "股票型"),
    ("885002.WI", "偏股混合型基金指数", "混合型", "混合型"),
    ("885003.WI", "平衡混合型基金指数", "混合型", "混合型"),
    ("885004.WI", "偏债混合型基金指数", "混合型", "混合型"),
    ("885005.WI", "债券型基金指数", "债券类", "债券型"),
    ("885006.WI", "灵活配置型基金指数", "混合型", "混合型"),
    ("885007.WI", "长期纯债型基金指数", "债券类", "债券型"),
    ("885008.WI", "指数型基金指数", "股票类", "指数型"),
    ("885009.WI", "增强指数型基金指数", "股票类", "指数型"),
    ("885010.WI", "短期纯债型基金指数", "债券类", "债券型"),
    ("885011.WI", "中长期纯债型基金指数", "债券类", "债券型"),
    ("885012.WI", "混合债券型一级基金指数", "债券类", "债券型"),
    ("885013.WI", "混合债券型二级基金指数", "债券类", "债券型"),
]


def req(path, params):
    try:
        r = requests.get(WIND_API + path, params=params, headers=WIND_HEADERS, timeout=12)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [warn] {path} {params} -> {e}")
    return None


def fetch_one(code):
    """尝试从 Wind 真实 API 取一个数，返回 (basic, market, annual, valuation)。
    若返回的指数代码与请求不一致（被钉死），则对应模块为 None。"""
    basic = market = annual = valuation = None

    info = req("/indexinfo", {"windcode": code, "lan": "cn"})
    if info and info.get("Success"):
        res = info.get("Result") or {}
        if res.get("indexCode") == code:
            basic = {
                "index_code": res.get("indexCode"),
                "name_cn": res.get("nameCn"),
                "name_en": res.get("nameEn"),
                "issuing_agency": res.get("issuingAgency"),
                "issuing_date": res.get("issuingDate"),
                "datum_date": res.get("datumDate"),
                "datum_point": res.get("datumPoint"),
                "ingredient_num": res.get("ingredientNum"),
                "weighting_mode": res.get("weightingMode"),
                "index_type": res.get("indexType"),
                "return_mode": res.get("returnMode"),
                "market_value": res.get("marketValue"),
                "ytd": res.get("ytdReturn"),
            }

    ret = req("/indexreturn", {"indexid": code, "lan": "cn"})
    if ret and ret.get("Success"):
        rows = ret.get("Result") or []
        row = next((x for x in rows if x.get("windCode") == code), None)
        if row:
            market = {
                "ytd": row.get("ytdReturn"),
                "r1w": row.get("return1w"),
                "r1m": row.get("return1m"),
                "r3m": row.get("return3m"),
                "r1y": row.get("return1y"),
                "r3y": row.get("return3y"),
                "r5y": row.get("return5y"),
                "since_inception": row.get("returnSinceInception"),
            }

    ay = req("/IndexAnnualYield", {"indexid": code, "lan": "cn"})
    if ay and ay.get("Success"):
        rows = ay.get("Result") or []
        row = next((x for x in rows if x.get("windCode") == code), None)
        if row:
            annual = {f"y{yk}": row.get(yk) for yk in
                      ["year1", "year2", "year3", "year4", "year5", "year6", "year7", "year8", "year9", "year10"]}
            annual["ytd"] = row.get("ytd")

    val = req("/indexValuation", {"indexid": code, "limit": "10", "lan": "cn"})
    if val and val.get("Success"):
        rows = val.get("Result") or []
        row = next((x for x in rows if x.get("windCode") == code), None)
        if row:
            valuation = {
                "ytd": row.get("ytd"),
                "total_mv": row.get("totalMarketValue"),
                "float_mv": row.get("floatMarketValue"),
                "pe": row.get("pe"),
                "pb": row.get("pb"),
                "net_margin": row.get("netMargin"),
                "dividend_yield": row.get("dividendYield"),
                "beta": row.get("beta"),
                "volatility": row.get("volatility"),
                "turnover": row.get("turnover"),
            }

    return basic, market, annual, valuation


def upsert(rows):
    if not rows:
        return
    vals = []
    for r in rows:
        code = r["wind_code"].replace("'", "''")
        name_cn = (r["name_cn"] or "").replace("'", "''")
        name_en = (r.get("name_en") or "").replace("'", "''")
        category = (r.get("category") or "").replace("'", "''")
        idx_type = (r.get("idx_type") or "").replace("'", "''")
        basic = json.dumps(r.get("basic_info") or {}, ensure_ascii=False).replace("'", "''")
        market = json.dumps(r.get("market_perf") or {}, ensure_ascii=False).replace("'", "''")
        annual = json.dumps(r.get("annual_perf") or {}, ensure_ascii=False).replace("'", "''")
        valuation = json.dumps(r.get("valuation") or {}, ensure_ascii=False).replace("'", "''")
        vals.append(
            f"('{code}','{name_cn}','{name_en}','{category}','{idx_type}','{basic}','{market}','{annual}','{valuation}',now())"
        )
    sql = (
        "INSERT INTO fund_indices (wind_code,name_cn,name_en,category,idx_type,basic_info,market_perf,annual_perf,valuation,updated_at) "
        "VALUES " + ",".join(vals) + " "
        "ON CONFLICT (wind_code) DO UPDATE SET "
        "name_cn=EXCLUDED.name_cn,name_en=EXCLUDED.name_en,category=EXCLUDED.category,"
        "idx_type=EXCLUDED.idx_type,basic_info=EXCLUDED.basic_info,market_perf=EXCLUDED.market_perf,"
        "annual_perf=EXCLUDED.annual_perf,valuation=EXCLUDED.valuation,updated_at=now();"
    )
    r = requests.post(API, headers=HEADERS, json={"query": sql}, timeout=30)
    if r.status_code not in (200, 201):
        print("  [ERR] upsert failed:", r.status_code, r.text[:300])
    else:
        print(f"  upserted {len(rows)} rows OK")


def main():
    print(f"[{datetime.now():%H:%M:%S}] 开始处理 {len(CURATED)} 个基金指数")
    batch = []
    for code, name, cat, typ in CURATED:
        print(f"  -> {code} {name}")
        basic, market, annual, valuation = fetch_one(code)
        has_data = any(x for x in (basic, market, annual, valuation))
        print(f"     basic={'Y' if basic else '-'} market={'Y' if market else '-'} "
              f"annual={'Y' if annual else '-'} valuation={'Y' if valuation else '-'}"
              + ("" if has_data else "  (Wind 接口被钉死，本次无明细数据)"))
        batch.append({
            "wind_code": code, "name_cn": name, "name_en": (basic or {}).get("name_en"),
            "category": cat, "idx_type": typ,
            "basic_info": basic, "market_perf": market, "annual_perf": annual, "valuation": valuation,
        })
        if len(batch) >= 5:
            upsert(batch); batch = []
    if batch:
        upsert(batch)
    print(f"[{datetime.now():%H:%M:%S}] 完成。Wind 公共接口会话限制下，明细数据需浏览器会话或切换后端后重跑本脚本即可自动填充。")


if __name__ == "__main__":
    main()
