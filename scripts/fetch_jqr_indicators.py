#!/usr/bin/env python3
"""fetch_jqr_indicators.py — 计算韭圈特色指标并写入 Supabase jqr_indicators 表。

指标:
  fear_greed   恐惧贪婪指数 0~100 (0=极度恐惧, 100=极度贪婪)
  market_temp  市场温度(估值温度计) 0~100 (0=极冷/低估, 100=极热/高估)
  fund_issuance 基金发行热度 0~100 (0=冰点, 100=狂热)

数据源(全部基于 akshare, 沙箱已验证可联网):
  - 沪深300日线 stock_zh_index_daily        -> 动量 / 波动率
  - 沪深300日线(东财) stock_zh_index_daily_em -> 成交额(量能)
  - 全市场PE历史 stock_index_pe_lg           -> 估值分位 / 市场温度
  - 新发基金 fund_new_found_em               -> 基金发行热度

写入: 经 Supabase Management API (PAT, superuser 绕过 RLS) 执行 DELETE+INSERT。

用法:
  SUPABASE_PAT=xxx python3 scripts/fetch_jqr_indicators.py
"""
import os
import sys
import json
import bisect
import math
import subprocess
from datetime import datetime, timedelta

def _load_env_local():
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass
_load_env_local()

MGMT_TOKEN = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置 SUPABASE_PAT（Supabase Personal Access Token）')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'


def pg(sql, timeout=300):
    from _db import run_sql as _db_run_sql
    return _db_run_sql(sql, timeout=timeout)


def pct_rank(history, current):
    """返回 current 在 history 中的升序分位 0~100（越大=越热/越高）。"""
    if not history or current is None:
        return None
    h = sorted(history)
    pos = bisect.bisect_right(h, current)
    return round(pos / len(h) * 100, 1)


def write_metric(metric, date, value, detail):
    pg(f"DELETE FROM jqr_indicators WHERE metric='{metric}' AND date='{date}';")
    detail_str = json.dumps(detail, ensure_ascii=False).replace("'", "''")
    val_sql = f"{value}" if value is not None else 'NULL'
    pg(f"INSERT INTO jqr_indicators(metric,date,value,detail) VALUES ('{metric}','{date}',{val_sql},'{detail_str}'::jsonb);")
    print(f"  wrote {metric} {date} value={value}")


# ============ 1. 恐惧贪婪指数 ============
def calc_fear_greed():
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol="sh000300").sort_values('date')
    closes = [float(x) for x in df['close'].tolist()]
    dates = [str(x)[:10] for x in df['date'].tolist()]
    n = len(closes)
    if n < 250:
        return None, {}, dates[-1]
    # 动量 (近1M/3M/6M 收益)
    def ret(back):
        return closes[-1] / closes[-1 - back] - 1 if n > back else 0
    m1, m3, m6 = ret(20), ret(60), ret(120)
    mom_hist = [closes[i] / closes[i - 60] - 1 for i in range(60, n)]
    mom_pct = pct_rank(mom_hist, m3) or 50  # 高收益=贪婪
    # 波动率 (近20日 realized vol 年化) + 历史分位
    roll = []
    for i in range(21, n):
        w = closes[i - 20:i + 1]
        rr = [math.log(w[j] / w[j - 1]) for j in range(1, len(w))]
        roll.append((sum(x * x for x in rr) / len(rr)) ** 0.5 * math.sqrt(252))
    vol20 = roll[-1]
    vol_pct = pct_rank(roll, vol20) or 50  # 高波动=恐慌
    # 估值 (全市场PE历史分位)
    pe_df = ak.stock_index_pe_lg().sort_values('日期')
    pe = [float(x) for x in pe_df['滚动市盈率'].dropna().tolist()]
    pe_cur = pe[-1]
    pe_pct = pct_rank(pe, pe_cur) or 50  # 高PE=贵=恐贪低
    # 量能 (东财指数日线成交额)
    amt_pct = None
    try:
        em = ak.stock_zh_index_daily_em(symbol="sh000300").sort_values('date')
        if 'amount' in em.columns:
            amt = [float(x) for x in em['amount'].tolist()]
            aw = [sum(amt[i - 20:i]) / 20 for i in range(20, len(amt))]
            amt_pct = pct_rank(aw, sum(amt[-20:]) / 20)  # 高量=活跃=贪婪
    except Exception as e:
        print("  [warn] 量能子项失败:", e)
    # 子项映射 0~100 (贪婪方向为正)
    sub = {
        'momentum_3m': round(mom_pct, 1),
        'volatility_inv': round(100 - vol_pct, 1),
        'valuation_inv': round(100 - pe_pct, 1),
    }
    if amt_pct is not None:
        sub['amount'] = round(amt_pct, 1)
    vals = list(sub.values())
    fg = round(sum(vals) / len(vals), 1)
    detail = {
        'value': fg, 'sub': sub,
        'pe': round(pe_cur, 2), 'pe_percentile': pe_pct,
        'momentum_1m_return': round(m1 * 100, 2),
        'momentum_3m_return': round(m3 * 100, 2),
        'momentum_6m_return': round(m6 * 100, 2),
        'vol_20d_annualized': round(vol20 * 100, 2),
    }
    return fg, detail, dates[-1]


# ============ 2. 市场温度 ============
def calc_market_temp():
    import akshare as ak
    pe_df = ak.stock_index_pe_lg().sort_values('日期')
    pe = [float(x) for x in pe_df['滚动市盈率'].dropna().tolist()]
    dates = [str(x)[:10] for x in pe_df['日期'].tolist()]
    pe_cur = pe[-1]
    pct = pct_rank(pe, pe_cur)
    temp = pct if pct is not None else 50
    detail = {
        'pe': round(pe_cur, 2),
        'pe_percentile': temp,
        'history_min': round(min(pe), 2),
        'history_max': round(max(pe), 2),
        'history_mean': round(sum(pe) / len(pe), 2),
        'count': len(pe),
        'label': '低估' if temp < 30 else ('适中' if temp < 70 else '高估'),
    }
    return temp, detail, dates[-1]


# ============ 3. 基金发行热度 ============
def calc_fund_issuance():
    import akshare as ak
    today = datetime.now()
    today_s = today.strftime('%Y-%m-%d')
    try:
        df = ak.fund_new_found_em()
    except Exception as e:
        print("  [warn] 基金新发接口失败:", e)
        return None, {}, today_s
    if df is None or len(df) == 0:
        return None, {}, today_s
    cols = list(df.columns)
    date_col = next((c for c in cols if '日期' in c or '时间' in c), None)
    share_col = next((c for c in cols if '份额' in c or '规模' in c), None)
    if date_col is None:
        return None, {'cols': cols}, today_s
    df['_d'] = df[date_col].astype(str).str[:10]
    all_dates = sorted(df['_d'].tolist())
    # 滚动90日窗口新发数量分布 -> 当前分位
    counts = []
    for d in all_dates:
        start = (datetime.strptime(d, '%Y-%m-%d') - timedelta(days=90)).strftime('%Y-%m-%d')
        counts.append(sum(1 for x in all_dates if start <= x <= d))
    window_start = (today - timedelta(days=90)).strftime('%Y-%m-%d')
    cur_cnt = sum(1 for x in all_dates if window_start <= x <= today_s)
    heat = pct_rank(counts, cur_cnt) if counts else 50
    detail = {
        'recent_90d_count': int(cur_cnt),
        'heat_percentile': heat,
        'share_col': share_col,
        'total_rows': int(len(df)),
        'date_col': date_col,
        'date_min': all_dates[0],
        'date_max': all_dates[-1],
    }
    # 若有份额列，补充近期规模
    if share_col:
        try:
            recent = df[df['_d'] >= window_start]
            recent[share_col] = recent[share_col].astype(float)
            detail['recent_90d_share_sum'] = round(float(recent[share_col].sum()), 2)
        except Exception as e:
            detail['share_err'] = str(e)[:80]
    return heat, detail, today_s


# ============ 4. 股债风险溢价 (equity_bond_gap) ============
# 用 macro_history 同源的真实数据计算：盈利收益率(1/沪深300PE) − 10Y国债收益率(cn10y)。
# cn10y 与 macro_history 表同源(均为 akshare bond_zh_us_rate)；沪深300 PE 取全市场滚动市盈率。
def calc_equity_bond_gap():
    import akshare as ak
    # 沪深300 滚动市盈率历史
    pe = ak.stock_index_pe_lg().sort_values('日期')
    pe_map = {}
    for _, r in pe.iterrows():
        v = r['滚动市盈率']
        if v == v and v and v > 0:
            pe_map[str(r['日期'])[:10]] = float(v)
    # 10Y 国债收益率（与 macro_history cn10y 同源）
    bd = ak.bond_zh_us_rate().sort_values('日期')
    cn_map = {}
    for _, r in bd.iterrows():
        v = r['中国国债收益率10年']
        if v == v and v is not None:
            cn_map[str(r['日期'])[:10]] = float(v)
    # 逐日风险溢价 = 盈利收益率(1/PE) − 10Y国债收益率(%)，历史分位 -> 0~100
    series = []
    for d, pev in pe_map.items():
        if d in cn_map:
            series.append((d, 1.0 / pev * 100 - cn_map[d]))
    if not series:
        return None, {}, None
    series.sort()
    dates = [s[0] for s in series]
    vals = [s[1] for s in series]
    cur = vals[-1]
    pct = pct_rank(vals, cur) or 50
    e_yield = 1.0 / pe_map[dates[-1]] * 100
    bond_yield = cn_map[dates[-1]]
    detail = {
        'e_yield': round(e_yield, 2),
        'bond_yield': round(bond_yield, 2),
        'gap': round(cur, 2),
        'score': pct,
        'history_min': round(min(vals), 2),
        'history_max': round(max(vals), 2),
        'count': len(vals),
    }
    return pct, detail, dates[-1]


def main():
    print("=== 计算韭圈特色指标 ===")
    fg, fg_d, fg_date = calc_fear_greed()
    print(f"恐贪指数: {fg} ({fg_date})")
    if fg is not None:
        write_metric('fear_greed', fg_date, fg, fg_d)

    tp, tp_d, tp_date = calc_market_temp()
    print(f"市场温度: {tp} ({tp_date})")
    if tp is not None:
        write_metric('market_temp', tp_date, tp, tp_d)

    fi, fi_d, fi_date = calc_fund_issuance()
    print(f"基金发行热度: {fi} ({fi_date})")
    if fi is not None:
        write_metric('fund_issuance', fi_date, fi, fi_d)

    ebg, ebg_d, ebg_date = calc_equity_bond_gap()
    print(f"股债风险溢价: {ebg} ({ebg_date})")
    if ebg is not None:
        write_metric('equity_bond_gap', ebg_date, ebg, ebg_d)
    print("=== 完成 ===")


if __name__ == '__main__':
    main()
