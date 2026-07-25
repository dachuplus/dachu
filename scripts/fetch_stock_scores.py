#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_stock_scores.py — 抓取 A 股股票数据写入 stock_scores_staging（三级流水线第1级）

设计要点（与基金 fund_scores 完全隔离，全部新建独立表）：
  - 股票 universe：沪深300(000300) + 中证500(000905) + 中证1000(000852) 成分股（约 1800 只），
    仅限 A 股（沪 60/68 开头、深 00/30 开头、京 8 开头）。
  - 行情/估值：腾讯 qt.gtimg.cn 批量报价（pe/pb/市值/换手/涨跌幅/最新价），稳定可靠。
  - 区间收益/回撤/夏普：新浪日线 K 线（scale=240, datalen=800 ≈ 近3年）实时计算：
        return_1m/3m/6m/1y/3y、max_drawdown(近1年)、sharpe(近1年)、list_date(上市日)。
  - 二级行业(industry)：东财行业板块成员映射（best-effort，失败则留空，不阻塞主流程）。
  - 风控标记：is_st(名称含 ST/*ST)、is_delisted(退市/退市整理)、is_suspended(停牌)、
        list_date(上市<60天 剔除)。
  - 全表分位：k_ret/k_drawdown/k_sharpe/k_all（0-100 百分位；k_drawdown 越大表示回撤越小，
        即按 -max_drawdown 排序；sharpe/return 越大越好）。k_all = 0.5*k_ret+0.25*k_drawdown+0.25*k_sharpe。
  - 优雅容错：单只失败跳过继续；成分股接口失败则降级用全部成分股并集（已含）。
  - 结果写入 stock_scores_staging（TRUNCATE 后整表 INSERT），并写 etl_run_log。

数据源降级说明：
  东财 push2/push2his 在沙箱内对突发批量请求会限流（RemoteDisconnected），
  故优先采用稳定可达的 腾讯报价 + 新浪 K 线；东财 datacenter 成分股接口稳定，仍用于成分股。
  如未来东财限流解除，可无缝切回（接口已封装在 _em_* 函数中）。

用法：
  export SUPABASE_PAT="$(grep -E '^SUPABASE_PAT=' dachu/.env.local | cut -d= -f2-)"
  python3 scripts/fetch_stock_scores.py
"""
import os
import re
import sys
import json
import math
import time
import datetime
import subprocess
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# ===== 凭证 =====
PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
if not PAT:
    raise SystemExit("缺少 SUPABASE_PAT 环境变量（沙箱陈旧 SUPABASE_MGMT_TOKEN 会污染，请显式覆盖）。")
REF = "tqhtegazxykkqfcpejky"
MGMT_API = f"https://api.supabase.com/v1/projects/{REF}/database/query"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

HEADERS_EM = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': 'https://quote.eastmoney.com/',
    'Accept': '*/*', 'Accept-Language': 'zh-CN,zh;q=0.9',
}
HEADERS_TX = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://gu.qq.com/', 'Accept': '*/*'}
HEADERS_SINA = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://finance.sina.com.cn/', 'Accept': '*/*'}

# 成分股指数（东财 INDEX_CODE，无交易所后缀）
INDEX_CODES = ["000300", "000905", "000852"]
EXCHANGE_OF_SUFFIX = {"SH": "SH", "SZ": "SZ", "BJ": "BJ"}

# 交易日近似值（用于区间收益回溯）
TD_1M, TD_3M, TD_6M, TD_1Y, TD_3Y = 21, 63, 126, 252, 756


# ============================================================
# 通用 HTTP（带重试）
# ============================================================
def http_get(url, headers, timeout=20, tries=3):
    last = None
    for _ in range(tries):
        try:
            r = requests.get(url, headers=headers, timeout=timeout)
            if r.status_code == 200:
                return r.text
            last = r.status_code
        except Exception as e:  # noqa
            last = e
        time.sleep(1.0)
    return None


# ============================================================
# 1) 成分股（东财 datacenter，稳定）
# ============================================================
def fetch_constituents():
    """返回 [(code, name, secucode, exchange), ...] 去重并集。"""
    out = {}
    for idx in INDEX_CODES:
        u = ("https://datacenter-web.eastmoney.com/api/data/v1/get"
             f"?reportName=RPT_INDEX_CONSTITUENT&columns=SECURITY_CODE,SECURITY_NAME_ABBR,SECUCODE,INDEX_CODE"
             f"&filter=(INDEX_CODE=%22{idx}%22)&pageSize=2000&sortColumns=SECURITY_CODE&sortTypes=1&source=WEB")
        txt = http_get(u, HEADERS_EM, timeout=25)
        if not txt:
            print(f"  [WARN] 成分股接口失败 INDEX={idx}", flush=True)
            continue
        try:
            j = json.loads(txt)
        except Exception:
            print(f"  [WARN] 成分股 JSON 解析失败 INDEX={idx}", flush=True)
            continue
        rows = (j.get('result') or {}).get('data') or []
        for r in rows:
            code = (r.get('SECURITY_CODE') or '').strip()
            name = (r.get('SECURITY_NAME_ABBR') or '').strip()
            secu = (r.get('SECUCODE') or '').strip()  # 如 600519.SH
            if not code:
                continue
            # 仅限 A 股：沪 60/68、深 00/30、京 8 开头
            if not re.match(r'^(60|68|00|30|8)', code):
                continue
            suffix = secu.split('.')[-1] if '.' in secu else ('SH' if code[:1] in '68' else ('BJ' if code[:1] == '8' else 'SZ'))
            exch = EXCHANGE_OF_SUFFIX.get(suffix, 'SH' if code[:1] in '68' else ('BJ' if code[:1] == '8' else 'SZ'))
            out[code] = (code, name, secu, exch)
    print(f"  [成分股] 沪深300+中证500+中证1000 去重后 A 股成分股: {len(out)} 只", flush=True)
    return list(out.values())


# ============================================================
# 2) 二级行业映射（东财行业板块，best-effort）
# ============================================================
def fetch_industry_map():
    """返回 {code: industry}。东财行业板块 → 成员，best-effort，失败返回空字典。"""
    m = {}
    t0 = time.time()
    BUDGET = 150  # 秒预算，超时即放弃剩余板块
    # 行业板块列表（东财行业）
    u = ("https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=300&po=1&fltt=2&invt=2&fid=f3"
         "&fs=m:90+t:2&fields=f12,f13,f14")
    txt = http_get(u, HEADERS_EM, timeout=20, tries=2)
    if not txt:
        print("  [行业] 板块列表获取失败，industry 留空", flush=True)
        return m
    try:
        boards = (json.loads(txt).get('data') or {}).get('diff') or []
    except Exception:
        print("  [行业] 板块列表解析失败，industry 留空", flush=True)
        return m
    print(f"  [行业] 共 {len(boards)} 个东财行业板块，开始映射成员...", flush=True)
    for b in boards:
        if time.time() - t0 > BUDGET:
            print("  [行业] 超时预算，停止剩余板块映射", flush=True)
            break
        bk = (b.get('f12') or '').strip()      # 板块代码 BKxxxx
        bname = (b.get('f14') or '').strip()   # 板块名称 = 二级行业
        if not bk:
            continue
        # 翻页取该板块全部成员
        pn = 1
        while True:
            if time.time() - t0 > BUDGET:
                break
            ub = ("https://push2.eastmoney.com/api/qt/clist/get?pn=%d&pz=500&po=1&fltt=2&invt=2&fid=f3"
                  f"&fs=b:{bk}&fields=f12,f13,f14" % pn)
            tb = http_get(ub, HEADERS_EM, timeout=20, tries=2)
            if not tb:
                break
            try:
                dd = json.loads(tb).get('data') or {}
                mem = dd.get('diff') or []
                tot = dd.get('total') or 0
            except Exception:
                break
            for x in mem:
                mc = (x.get('f12') or '').strip()
                if mc:
                    m[mc] = bname
            if len(mem) < 500 or pn * 500 >= (tot or 0):
                break
            pn += 1
            time.sleep(0.25)
        time.sleep(0.2)
    print(f"  [行业] 映射完成，覆盖 {len(m)} 只股票行业", flush=True)
    return m


# ============================================================
# 3) 行情报价（腾讯 qt.gtimg.cn，稳定批量）
# ============================================================
def sym_of(code, exch):
    p = {'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj'}.get(exch, 'sh')
    return f"{p}{code}"


def tx_field_map(parts):
    """解析腾讯 qt 字段（~ 分隔）。返回 dict。"""
    def g(i):
        try:
            return parts[i]
        except Exception:
            return ''
    return {
        'name': g(1),
        'code': g(2),
        'close': g(3),
        'change_pct': g(32),   # 涨跌%
        'turnover': g(38),     # 换手率%
        'pe_ttm': g(39),       # 市盈率(TTM)
        'mktcap': g(44),       # 总市值(亿元)
        'circ_mktcap': g(45),  # 流通市值(亿元)
        'pb': g(46),           # 市净率
    }


def fetch_quotes_batch(syms):
    """syms: list of 腾讯 symbol。返回 {sym: fieldmap}。"""
    if not syms:
        return {}
    s = ','.join(syms)
    u = "https://qt.gtimg.cn/q=" + s
    txt = http_get(u, HEADERS_TX, timeout=20, tries=3)
    res = {}
    if not txt:
        return res
    for line in txt.strip().split('\n'):
        if '="' not in line:
            continue
        try:
            prefix = line.split('="')[0]            # v_sh600519
            sym = prefix.split('_')[-1]
            body = line.split('="')[1].rstrip('";')
            parts = body.split('~')
            res[sym] = tx_field_map(parts)
        except Exception:
            continue
    return res


# ============================================================
# 4) 日线 K 线（新浪，稳定）→ 收益/回撤/夏普/上市日
# ============================================================
def fetch_kline(sym):
    """返回 close 价格列表（旧→新）与首日期字符串；失败返回 (None, None)。"""
    u = ("https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/"
         f"CN_MarketData.getKLineData?symbol={sym}&scale=240&ma=no&datalen=800")
    txt = http_get(u, HEADERS_SINA, timeout=20, tries=3)
    if not txt:
        return None, None
    try:
        bars = json.loads(txt)
    except Exception:
        return None, None
    if not bars:
        return None, None
    closes = []
    first_date = None
    for b in bars:
        try:
            closes.append(float(b['close']))
            if first_date is None:
                first_date = b.get('day', '')[:10]
        except Exception:
            pass
    if not closes:
        return None, None
    return closes, first_date


def pct_return(closes, bars_back):
    if len(closes) <= bars_back:
        return None
    old = closes[-(bars_back + 1)]
    new = closes[-1]
    if old in (0, None):
        return None
    return (new - old) / old * 100.0


def max_drawdown(closes, bars_back):
    if len(closes) <= bars_back:
        window = closes
    else:
        window = closes[-(bars_back + 1):]
    if len(window) < 2:
        return None
    peak = window[0]
    mdd = 0.0
    for p in window:
        if p > peak:
            peak = p
        if peak > 0:
            dd = (p - peak) / peak
            if dd < mdd:
                mdd = dd
    return mdd * 100.0  # 负值


def sharpe(closes, bars_back):
    if len(closes) <= bars_back:
        window = closes
    else:
        window = closes[-(bars_back + 1):]
    if len(window) < 3:
        return None
    rets = []
    for i in range(1, len(window)):
        if window[i - 1]:
            rets.append((window[i] - window[i - 1]) / window[i - 1])
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    var = sum((x - mean) ** 2 for x in rets) / (len(rets) - 1)
    std = math.sqrt(var)
    if std == 0:
        return None
    return (mean / std) * math.sqrt(252)


# ============================================================
# 5) 分位计算
# ============================================================
def percentile_ranks(values):
    """values: list of (key, num|None)。返回 {key: 0-100 百分位}。"""
    valid = [(k, v) for k, v in values if v is not None and not (isinstance(v, float) and math.isnan(v))]
    if not valid:
        return {k: None for k, _ in values}
    vs = sorted(v for _, v in valid)
    n = len(vs)
    out = {}
    for k, v in valid:
        # 线性插值百分位
        lo, hi = 0, n - 1
        # 用 bisect 风格计数
        cnt_le = sum(1 for x in vs if x <= v)
        # rank-based percentile (0-100)
        pct = (cnt_le - 1) / (n - 1) * 100.0 if n > 1 else 50.0
        out[k] = round(pct, 2)
    for k, v in values:
        if v is None or (isinstance(v, float) and math.isnan(v)):
            out[k] = None
    return out


# ============================================================
# 6) 风控标记
# ============================================================
def risk_flags(name, list_date, daily_change, volume_zero=False):
    name_u = (name or '').upper()
    is_st = ('ST' in name_u)
    is_delisted = ('退' in (name or ''))  # 退市 / 退市整理
    # 停牌：宽松判定 —— 涨跌幅为空且非交易时间，或名称含「停」
    is_suspended = (('停' in (name or '')) or
                    (daily_change is None and volume_zero))
    listed_recent = False
    if list_date:
        try:
            ld = datetime.date.fromisoformat(list_date)
            if (datetime.date.today() - ld).days < 60:
                listed_recent = True
        except Exception:
            pass
    return is_st, is_delisted, is_suspended, listed_recent


# ============================================================
# 7) 写库（Management API / curl 绕过 Cloudflare）
# ============================================================
def pg(sql, timeout=600):
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {PAT}',
         '-H', 'Content-Type: application/json', '-d', payload],
        capture_output=True, text=True, timeout=timeout + 30)
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:100]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        resp = json.loads(t)
    except json.JSONDecodeError:
        raise RuntimeError(f'非JSON响应: {t[:200]}')
    if isinstance(resp, dict) and resp.get('message'):
        raise RuntimeError(resp['message'][:300])
    return resp


def sql_num(v):
    if v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v))):
        return 'NULL'
    return str(v)


def sql_str(v):
    if v is None:
        return 'NULL'
    return "'" + str(v).replace("'", "''") + "'"


def write_staging(rows):
    """rows: list of dict。TRUNCATE 后分批 INSERT。"""
    pg(f"TRUNCATE TABLE public.stock_scores_staging;")
    cols = ["code", "name", "industry", "industry_code", "exchange", "secid", "close",
            "pe_ttm", "pb", "mktcap", "circ_mktcap", "turnover_rate",
            "return_1m", "return_3m", "return_6m", "return_1y", "return_3y",
            "daily_change", "max_drawdown", "sharpe",
            "k_ret", "k_drawdown", "k_sharpe", "k_all",
            "is_st", "is_delisted", "is_suspended", "list_date", "updated_at"]
    BATCH = 150
    now = datetime.datetime.now().isoformat()
    total = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        val_parts = []
        for r in chunk:
            vals = [sql_str(r.get('code')), sql_str(r.get('name')), sql_str(r.get('industry')),
                    sql_str(r.get('industry_code')), sql_str(r.get('exchange')), sql_str(r.get('secid')),
                    sql_num(r.get('close')), sql_num(r.get('pe_ttm')), sql_num(r.get('pb')),
                    sql_num(r.get('mktcap')), sql_num(r.get('circ_mktcap')), sql_num(r.get('turnover_rate')),
                    sql_num(r.get('return_1m')), sql_num(r.get('return_3m')), sql_num(r.get('return_6m')),
                    sql_num(r.get('return_1y')), sql_num(r.get('return_3y')), sql_num(r.get('daily_change')),
                    sql_num(r.get('max_drawdown')), sql_num(r.get('sharpe')),
                    sql_num(r.get('k_ret')), sql_num(r.get('k_drawdown')), sql_num(r.get('k_sharpe')),
                    sql_num(r.get('k_all')),
                    'true' if r.get('is_st') else 'false', 'true' if r.get('is_delisted') else 'false',
                    'true' if r.get('is_suspended') else 'false', sql_str(r.get('list_date')), sql_str(now)]
            val_parts.append("(" + ",".join(vals) + ")")
        sql = (f"INSERT INTO public.stock_scores_staging ({','.join(cols)}) VALUES "
               + ",".join(val_parts) + ";")
        try:
            pg(sql, timeout=300)
            total += len(chunk)
        except Exception as e:
            print(f"  [ERR] 批量写入失败(跳过该批): {e}", flush=True)
    return total


def write_etl_log(rows, status, detail):
    today = datetime.date.today().isoformat()
    now = datetime.datetime.now().isoformat()
    sql = (f"INSERT INTO public.etl_run_log (run_date, step_name, status, start_time, end_time, "
           f"rows_affected, error_message) VALUES ('{today}','fetch_stock_scores','{status}','{now}','{now}',"
           f"{rows},'{detail.replace(chr(39), chr(39)*2)}');")
    try:
        pg(sql, timeout=120)
    except Exception as e:
        print(f"  [WARN] etl_run_log 写入失败: {e}", flush=True)


# ============================================================
# 主流程
# ============================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='限制处理的成分股数量（调试用）')
    ap.add_argument('--skip-industry', action='store_true', help='跳过行业映射')
    args = ap.parse_args()

    print('=' * 64, flush=True)
    print(' 抓取 A 股股票数据 → stock_scores_staging', flush=True)
    print('=' * 64, flush=True)

    constituents = fetch_constituents()
    if not constituents:
        print('  [ERR] 成分股为空，终止', flush=True)
        write_etl_log(0, 'failed', '成分股接口返回空')
        sys.exit(1)

    industry_map = {} if args.skip_industry else fetch_industry_map()

    # 行情（腾讯批量）
    print('  [行情] 腾讯批量报价...', flush=True)
    syms = [sym_of(c, e) for (c, n, s, e) in constituents]
    quote_map = {}
    for i in range(0, len(syms), 50):
        batch = syms[i:i + 50]
        q = fetch_quotes_batch(batch)
        quote_map.update(q)
        time.sleep(0.15)
    print(f'  [行情] 获取到 {len(quote_map)} 只报价', flush=True)

    # K 线 + 指标（新浪，并发）
    print('  [K线] 新浪日线计算收益/回撤/夏普...', flush=True)
    kline_cache = {}
    with ThreadPoolExecutor(max_workers=12) as ex:
        fut = {ex.submit(fetch_kline, sym): sym for sym in syms}
        for f in as_completed(fut):
            sym = fut[f]
            try:
                closes, first_date = f.result()
                kline_cache[sym] = (closes, first_date)
            except Exception:
                kline_cache[sym] = (None, None)
    print(f'  [K线] 获取到 {sum(1 for v in kline_cache.values() if v[0])} 只有效 K 线', flush=True)

    rows = []
    ok = 0
    for (code, name, secu, exch) in constituents:
        if args.limit and ok >= args.limit:
            break
        sym = sym_of(code, exch)
        q = quote_map.get(sym, {})
        closes, first_date = kline_cache.get(sym, (None, None))
        # 名称优先用腾讯（更准），否则用成分股名
        nm = (q.get('name') or name or '').strip()
        if not nm:
            continue
        # 数值解析
        def fnum(x):
            try:
                return float(x)
            except Exception:
                return None
        close = fnum(q.get('close'))
        daily_change = fnum(q.get('change_pct'))
        pe = fnum(q.get('pe_ttm'))
        pb = fnum(q.get('pb'))
        mktcap = fnum(q.get('mktcap'))
        circ = fnum(q.get('circ_mktcap'))
        turnover = fnum(q.get('turnover'))
        # K 线指标
        r1m = pct_return(closes, TD_1M) if closes else None
        r3m = pct_return(closes, TD_3M) if closes else None
        r6m = pct_return(closes, TD_6M) if closes else None
        r1y = pct_return(closes, TD_1Y) if closes else None
        r3y = pct_return(closes, TD_3Y) if closes else None
        mdd = max_drawdown(closes, TD_1Y) if closes else None
        shp = sharpe(closes, TD_1Y) if closes else None
        # 数据质量 sanity guard（A 股单日涨跌幅限 ±10%，故区间收益存在物理上界；
        # 超出者多为 K 线复权/新股基数失真，置空避免污染评分与展示）
        r1m = None if (r1m is not None and abs(r1m) > 100) else r1m
        r3m = None if (r3m is not None and abs(r3m) > 200) else r3m
        r6m = None if (r6m is not None and abs(r6m) > 350) else r6m
        r1y = None if (r1y is not None and abs(r1y) > 400) else r1y
        r3y = None if (r3y is not None and abs(r3y) > 1000) else r3y
        mdd = None if (mdd is not None and (mdd > 0 or mdd < -100)) else mdd
        # secid：沪 1.code / 深 0.code / 京 0.code
        secid_prefix = '1' if exch == 'SH' else '0'
        secid = f"{secid_prefix}.{code}"
        is_st, is_delisted, is_suspended, listed_recent = risk_flags(nm, first_date, daily_change)
        industry = industry_map.get(code)
        rows.append({
            'code': f"{code}.{exch}", 'name': nm, 'industry': industry, 'industry_code': None,
            'exchange': exch, 'secid': secid, 'close': close, 'pe_ttm': pe, 'pb': pb,
            'mktcap': mktcap, 'circ_mktcap': circ, 'turnover_rate': turnover,
            'return_1m': r1m, 'return_3m': r3m, 'return_6m': r6m, 'return_1y': r1y, 'return_3y': r3y,
            'daily_change': daily_change, 'max_drawdown': mdd, 'sharpe': shp,
            'k_ret': None, 'k_drawdown': None, 'k_sharpe': None, 'k_all': None,
            'is_st': is_st, 'is_delisted': is_delisted, 'is_suspended': is_suspended,
            'list_date': first_date,
        })
        ok += 1

    print(f'  [合并] 构建 {len(rows)} 行（含 K 线 {sum(1 for r in rows if r["return_3y"] is not None)} 只）', flush=True)

    # 风控过滤标记（仅标记，不删除；promote 阶段再过滤）
    # 计算分位
    kret_pairs = [(r['code'], r['return_3y']) for r in rows]   # k_ret 以 return_3y 为代表
    kdd_pairs = [(r['code'], (-r['max_drawdown']) if r['max_drawdown'] is not None else None) for r in rows]
    ksh_pairs = [(r['code'], r['sharpe']) for r in rows]
    pr_ret = percentile_ranks(kret_pairs)
    pr_dd = percentile_ranks(kdd_pairs)
    pr_sh = percentile_ranks(ksh_pairs)
    for r in rows:
        kr = pr_ret.get(r['code'])
        kd = pr_dd.get(r['code'])
        ks = pr_sh.get(r['code'])
        r['k_ret'] = kr
        r['k_drawdown'] = kd
        r['k_sharpe'] = ks
        if kr is not None and kd is not None and ks is not None:
            r['k_all'] = round(0.5 * kr + 0.25 * kd + 0.25 * ks, 2)
        else:
            r['k_all'] = None

    scored = sum(1 for r in rows if r['k_all'] is not None)
    print(f'  [分位] k_all 非空 {scored}/{len(rows)}', flush=True)

    # 写 staging
    print('  [写入] stock_scores_staging ...', flush=True)
    written = write_staging(rows)
    print(f'  [写入] 完成，staging 写入 {written} 行', flush=True)

    status = 'ok' if written >= 1500 else ('partial' if written > 0 else 'failed')
    detail = f"成分股{len(constituents)}只, 报价{len(quote_map)}只, K线有效{sum(1 for r in rows if r['return_3y'] is not None)}只, 行业覆盖{len(industry_map)}只, k_all非空{scored}只"
    write_etl_log(written, status, detail)
    print(f'\n=== 抓取完成：status={status}, rows={written} ===', flush=True)


if __name__ == '__main__':
    main()
