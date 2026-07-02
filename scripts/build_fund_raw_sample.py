#!/usr/bin/env python3
"""
全量抓取基金数据，填充 fund_raw_sample 表。
数据来源：天天基金 pingzhongdata API（净值历史 + 基金详情）

用法：
  python3 build_fund_raw_sample.py              # 全量抓取
  python3 build_fund_raw_sample.py --limit 10   # 测试 10 只
  python3 build_fund_raw_sample.py --resume      # 断点续跑
"""

import sys, os, json, re, math, time, threading, argparse
import urllib.request
import requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ── 配置 ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
ANON_KEY     = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
MGMT_URL     = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
MGMT_PAT     = os.environ.get("SUPABASE_MGMT_TOKEN") or ''

MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_PAT}", "Content-Type": "application/json"}
ANON_HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

WORKERS     = 5
RATE_DELAY  = 0.06
RATE_LOCK   = threading.Lock()
RATE_LAST   = [0.0]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

# ── 列名（与 Excel 完全一致，按顺序排列）────────────────────────────────────
BASE_COLS = [
    'c','name','managers','t0','t1','nav','nav_date','daily_change',
    'r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y','ytd','return_launch',
    'dd1y','dd2y','dd3y','dd5y','sr1y','sr2y','sr3y','sr5y','sg',
    'fee_orig_pct','fee_disc_pct','fund_minsg','risk_level','perf_avr',
    'stock_codes','bond_codes','top_industry',
    'stock_pct','bond_pct','cash_pct','position_est',
    'scale_change_amt','inst_pct','inner_pct',
    'is_etf','is_lof','is_fof','is_dk','is_exchange'
]
Q_COLS = [f'q_ret_{i:02d}' for i in range(1,41)] \
       + [f'q_dd_{i:02d}' for i in range(1,41)] \
       + [f'q_sr_{i:02d}' for i in range(1,41)] \
       + [f'q_label_{i:02d}' for i in range(1,41)]
SCORE_COLS = ['score_3m','score_6m','score_1y','score_2y','score_3y','score_5y','score_7y','score_10y']
ALL_COLUMNS = BASE_COLS + Q_COLS + SCORE_COLS

RF_DAILY = 0.02 / 250

# ── 工具函数 ──────────────────────────────────────────────────────────────────

def ts():
    return datetime.now().strftime('%H:%M:%S')

def rate_sleep():
    with RATE_LOCK:
        now = time.time()
        elapsed = now - RATE_LAST[0]
        if elapsed < RATE_DELAY:
            time.sleep(RATE_DELAY - elapsed)
        RATE_LAST[0] = time.time()

def fetch_pingzhong(code: str) -> dict:
    """抓取并解析 pingzhongdata JS，返回解析后的数据字典"""
    rate_sleep()
    code = str(code).replace('.OF', '').replace('.of', '').replace('.SH', '').replace('.SZ', '').strip()
    url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        js = resp.read().decode('utf-8', errors='replace')
    except Exception as e:
        return None

    result = {'code': code}

    # 1. 解析净值历史 Data_netWorthTrend
    m = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', js, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            records = []
            for d in data:
                nav = d.get('y')
                ts = d.get('x')
                if nav and nav > 0 and ts:
                    try:
                        dt = datetime.fromtimestamp(ts / 1000)
                        records.append({'date': dt, 'nav': float(nav)})
                    except:
                        pass
            records.sort(key=lambda x: x['date'])
            result['nav_records'] = records
        except:
            result['nav_records'] = []
    else:
        result['nav_records'] = []

    # 2. 解析基金名称
    m = re.search(r'var fS_name\s*=\s*"([^"]*)"', js)
    if m: result['name'] = m.group(1)

    # 3. 解析费率
    m = re.search(r'var fund_sourceRate\s*=\s*"([^"]*)"', js)
    if m:
        try: result['fee_orig_pct'] = float(m.group(1))
        except: pass
    m = re.search(r'var fund_Rate\s*=\s*"([^"]*)"', js)
    if m:
        try: result['fee_disc_pct'] = float(m.group(1))
        except: pass
    m = re.search(r'var fund_minsg\s*=\s*"([^"]*)"', js)
    if m: result['fund_minsg'] = m.group(1)

    # 4. 解析收益率（短期）
    for key, var in [('r1m','syl_1y'),('r3m','syl_3y'),('r6m','syl_6y'),('r1y','syl_1n')]:
        m = re.search(rf'var {var}\s*=\s*"([^"]*)"', js)
        if m:
            try:
                val = float(m.group(1))
                result[f'_syl_{key}'] = val  # 暂时保存
            except: pass

    # 5. 解析持仓股票代码
    m = re.search(r'var stockCodes\s*=\s*(\[.*?\]);', js)
    if m:
        try:
            result['stock_codes'] = ','.join(json.loads(m.group(1)))
        except: pass
    m = re.search(r'var zqCodes\s*=\s*"([^"]*)"', js)
    if m:
        result['bond_codes'] = m.group(1).replace(',', ',')
    
    # 6. 解析基金经理（从另一个 API 或页面）
    # 暂时留空，后续可通过其他 API 补充

    return result

def compute_metrics(parsed: dict) -> dict:
    """从解析数据计算所有指标，返回一行数据（dict）"""
    row = {col: None for col in ALL_COLUMNS}
    code = parsed['code']
    row['c'] = code

    # 基本信息
    for key in ['name','fee_orig_pct','fee_disc_pct','fund_minsg','stock_codes','bond_codes']:
        if key in parsed:
            row[key] = parsed[key]

    navs = parsed.get('nav_records', [])
    if not navs or len(navs) < 5:
        return row

    # 最新净值
    row['nav'] = navs[-1]['nav']
    row['nav_date'] = navs[-1]['date'].strftime('%Y-%m-%d')

    # ── 收益率 ──
    def ret_over(n_days):
        if len(navs) <= n_days:
            return None
        old = navs[-(n_days+1)]['nav']
        new = navs[-1]['nav']
        return round((new / old - 1) * 100, 2)

    # 按交易日估算（实际交易日约每年250天）
    row['r0w'] = ret_over(5)
    row['r1m'] = ret_over(20)
    row['r3m'] = ret_over(60)
    row['r6m'] = ret_over(120)
    row['r1y'] = ret_over(250)
    row['r2y'] = ret_over(500)
    row['r3y'] = ret_over(750)
    row['r5y'] = ret_over(1250)

    # ytd
    try:
        year = navs[-1]['date'].year
        ytd_date = datetime(year, 1, 1)
        # 找年初第一条
        for r in navs:
            if r['date'] >= ytd_date:
                row['ytd'] = round((navs[-1]['nav'] / r['nav'] - 1) * 100, 2)
                break
    except: pass

    # ── 最大回撤 ──
    def max_dd(nav_sub):
        if not nav_sub: return None
        peak = nav_sub[0]['nav']
        mdd = 0.0
        for r in nav_sub:
            if r['nav'] > peak: peak = r['nav']
            dd = (peak - r['nav']) / peak * 100
            if dd > mdd: mdd = dd
        return round(-mdd, 2)

    n = len(navs)
    if n >= 250: row['dd1y'] = max_dd(navs[-250:])
    if n >= 500: row['dd2y'] = max_dd(navs[-500:])
    if n >= 750: row['dd3y'] = max_dd(navs[-750:])
    if n >= 1250: row['dd5y'] = max_dd(navs[-1250:])

    # ── 夏普比率 ──
    def sharpe(nav_sub):
        if not nav_sub or len(nav_sub) < 20: return None
        rets = []
        for i in range(1, len(nav_sub)):
            r = (nav_sub[i]['nav'] / nav_sub[i-1]['nav'] - 1)
            rets.append(r)
        if not rets: return None
        mean_r = sum(rets) / len(rets)
        var = sum((r - mean_r)**2 for r in rets) / len(rets)
        std = math.sqrt(var) if var > 0 else 0
        if std == 0: return None
        return round((mean_r - RF_DAILY) / std * math.sqrt(250), 4)

    if n >= 250: row['sr1y'] = sharpe(navs[-250:])
    if n >= 500: row['sr2y'] = sharpe(navs[-500:])
    if n >= 750: row['sr3y'] = sharpe(navs[-750:])
    if n >= 1250: row['sr5y'] = sharpe(navs[-1250:])

    # ── 季度指标 ──
    # 按40个季度分组（从近到远）
    Q_DAYS = 63  # 每季度约63个交易日
    for q in range(1, 41):
        start = max(0, n - q * Q_DAYS)
        end = n - (q-1) * Q_DAYS if q > 1 else n
        sub = navs[start:end]
        if len(sub) < 20:
            row[f'q_ret_{q:02d}'] = None
            row[f'q_dd_{q:02d}'] = None
            row[f'q_sr_{q:02d}'] = None
            row[f'q_label_{q:02d}'] = None
            continue

        # 季度收益
        ret = (sub[-1]['nav'] / sub[0]['nav'] - 1) * 100
        row[f'q_ret_{q:02d}'] = round(ret, 2)

        # 季度回撤
        peak = sub[0]['nav']
        mdd = 0.0
        for r in sub:
            if r['nav'] > peak: peak = r['nav']
            dd = (peak - r['nav']) / peak * 100
            if dd > mdd: mdd = dd
        row[f'q_dd_{q:02d}'] = round(-mdd, 2)

        # 季度夏普
        rets = []
        for i in range(1, len(sub)):
            rets.append(sub[i]['nav'] / sub[i-1]['nav'] - 1)
        if rets:
            mean_r = sum(rets) / len(rets)
            var = sum((r - mean_r)**2 for r in rets) / len(rets)
            std = math.sqrt(var) if var > 0 else 0
            if std > 0:
                row[f'q_sr_{q:02d}'] = round((mean_r - RF_DAILY) / std * math.sqrt(250), 4)

        # 季度标签
        try:
            dt = sub[-1]['date']
            row[f'q_label_{q:02d}'] = f"{dt.year}Q{(dt.month-1)//3+1}"
        except: pass

    return row

# ── Supabase 操作 ────────────────────────────────────────────────────────────

def get_all_fund_codes(limit=None):
    codes = []
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/fund_scores?select=c&offset={offset}&limit=1000&order=c"
        r = requests.get(url, headers=ANON_HEADERS, timeout=30)
        if r.status_code != 200: break
        batch = r.json()
        if not batch: break
        codes.extend([row['c'] for row in batch])
        offset += len(batch)
        if len(batch) < 1000 or (limit and len(codes) >= limit):
            break
    return codes[:limit] if limit else codes

def get_existing_codes():
    existing = set()
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/fund_raw_sample?select=c&offset={offset}&limit=1000"
        r = requests.get(url, headers=ANON_HEADERS, timeout=30)
        if r.status_code != 200: break
        for row in r.json():
            existing.add(row['c'])
        if len(r.json()) < 1000: break
        offset += 1000
    return existing

def pg_escape(val):
    if val is None:
        return 'NULL'
    if isinstance(val, (int, float)):
        if isinstance(val, float) and math.isnan(val):
            return 'NULL'
        return str(val)
    s = str(val).replace("\\", "\\\\").replace("'", "''")
    return f"$val${s}$val$"

def import_rows(rows: list):
    if not rows: return 0
    quoted = [f'"{c}"' for c in ALL_COLUMNS]
    col_list = ", ".join(quoted)
    parts = []
    for row in rows:
        vals = [pg_escape(row.get(c)) for c in ALL_COLUMNS]
        parts.append("(" + ", ".join(vals) + ")")
    update_set = ", ".join(f"{qc}=EXCLUDED.{qc}" for qc in quoted)
    sql = f"""INSERT INTO public.fund_raw_sample ({col_list}) VALUES {', '.join(parts)}
              ON CONFLICT (c) DO UPDATE SET {update_set}"""
    r = requests.post(MGMT_URL, headers=MGMT_HEADERS, timeout=120, json={"query": sql})
    if r.status_code in (200, 201):
        return len(rows)
    else:
        print(f"  [{ts()}] Batch import error [{r.status_code}]: {r.text[:150]}")
        return 0

# ── 主流程 ──────────────────────────────────────────────────────────────────

def process_one(code: str, fund_info_map: dict):
    parsed = fetch_pingzhong(code)
    if not parsed or not parsed.get('nav_records'):
        return None
    row = compute_metrics(parsed)
    # 补充 fund_scores 里的信息
    info = fund_info_map.get(code, {})
    for k in ['t0','t1','sg','daily_change']:
        if k in info and not row.get(k):
            row[k] = info[k]
    return row

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()

    print(f"[{ts()}] === build_fund_raw_sample 开始 ===")

    codes = get_all_fund_codes(limit=args.limit)
    print(f"[{ts()}] 基金总数: {len(codes)}")

    if args.resume:
        existing = get_existing_codes()
        codes = [c for c in codes if c not in existing]
        print(f"[{ts()}] 断点续跑，剩余: {len(codes)}")

    # 获取 fund_scores 基本信息
    print(f"[{ts()}] 获取 fund_scores 基本信息...")
    fund_info_map = {}
    offset = 0
    while True:
        url = f"{SUPABASE_URL}/rest/v1/fund_scores?select=c,t0,t1,sg,daily_change&offset={offset}&limit=1000"
        r = requests.get(url, headers=ANON_HEADERS, timeout=30)
        if r.status_code != 200: break
        for row in r.json():
            fund_info_map[row['c']] = row
        if len(r.json()) < 1000: break
        offset += 1000
    print(f"[{ts()}] 基本信息: {len(fund_info_map)} 条")

    # 多线程抓取
    BATCH = 200
    results = []
    processed = [0]
    lock = threading.Lock()

    def worker(batch, wid):
        batch_rows = []
        for code in batch:
            row = process_one(code, fund_info_map)
            if row:
                batch_rows.append(row)
            with lock:
                processed[0] += 1
                if processed[0] % 200 == 0:
                    print(f"  [{ts()}] 进度: {processed[0]}/{len(codes)}")
        with lock:
            results.extend(batch_rows)

    batches = [codes[i:i+BATCH] for i in range(0, len(codes), BATCH)]
    threads = []
    for i, batch in enumerate(batches):
        t = threading.Thread(target=worker, args=(batch, i%WORKERS))
        threads.append(t)
        t.start()
        if len(threads) >= WORKERS:
            for t in threads: t.join()
            threads = []
            if results:
                n = import_rows(results)
                print(f"  [{ts()}] 已导入: {n} 条（{processed[0]}/{len(codes)}）")
                results.clear()

    for t in threads: t.join()
    if results:
        n = import_rows(results)
        print(f"  [{ts()}] 已导入: {n} 条")

    print(f"\n[{ts()}] === 完成! 处理: {processed[0]} ===")

if __name__ == '__main__':
    main()
