#!/usr/bin/env python3
"""
补充 fund_raw_sample 表的缺失字段：公司名、规模、管理费率、风险等级、经理任职规模等。

数据来源：
- pingzhongdata JS: fund_scale (净资产), total_manage_scale (经理任职规模)
- fundf10/jbgk 页面: company, manage_fee, custody_fee, estab_date
- fundf10/tsdata 页面: risk_level

用法：
  python3 supplement_fund_details.py --limit 10    # 测试10只
  python3 supplement_fund_details.py                # 全量更新
  python3 supplement_fund_details.py --resume        # 断点续跑
"""

import sys, os, re, json, math, time, threading, argparse
import urllib.request
import requests
from datetime import datetime

# ── 配置 ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
ANON_KEY     = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
MGMT_URL     = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
MGMT_PAT     = os.environ.get("SUPABASE_MGMT_TOKEN") or ''

MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_PAT}", "Content-Type": "application/json"}
ANON_HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

WORKERS     = 12
RATE_DELAY  = 0.03
RATE_LOCK   = threading.Lock()
RATE_LAST   = [0.0]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

UPDATE_COLS = [
    'company', 'fund_scale', 'manage_fee', 'total_manage_scale',
    'holders_count', 'risk_level', 'estab_date', 'custody_fee'
]

def ts():
    return datetime.now().strftime('%H:%M:%S')

def rate_sleep():
    with RATE_LOCK:
        now = time.time()
        elapsed = now - RATE_LAST[0]
        if elapsed < RATE_DELAY:
            time.sleep(RATE_DELAY - elapsed)
        RATE_LAST[0] = time.time()

# ── JSON 提取工具 ────────────────────────────────────────────────────────────

def extract_json(text, var_name):
    """从 JS 文本中提取 varName = [...] 或 varName = {...} 的 JSON"""
    idx = text.find(f'var {var_name} = ')
    if idx == -1:
        idx = text.find(f'{var_name} =')
    if idx == -1:
        return None
    # 跳到 `=` 后面
    start = text.index('=', idx) + 1
    raw = text[start:].lstrip()
    if not raw:
        return None

    # 括号计数提取完整 JSON
    bracket_count = 0
    in_string = False
    end_pos = -1
    for i, ch in enumerate(raw):
        if ch == '"' and (i == 0 or raw[i-1] != '\\'):
            in_string = not in_string
        if in_string:
            continue
        if ch in '[{':
            bracket_count += 1
        elif ch in ']}':
            bracket_count -= 1
            if bracket_count == 0:
                end_pos = i + 1
                break
    if end_pos == -1:
        return None
    try:
        return json.loads(raw[:end_pos])
    except:
        return None

# ── 数据抓取 ─────────────────────────────────────────────────────────────────

def fetch_pingzhong_extras(code: str) -> dict:
    """从 pingzhongdata JS 提取额外字段"""
    code = str(code).replace('.OF', '').replace('.of', '').replace('.SH', '').replace('.SZ', '').strip()
    url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        js = resp.read().decode('utf-8', errors='replace')
    except:
        return {}

    result = {}

    # 1. 净资产（规模）from Data_assetAllocation
    alloc = extract_json(js, 'Data_assetAllocation')
    if alloc and isinstance(alloc, dict):
        for s in alloc.get('series', []):
            if s.get('name') == '净资产' and s.get('data'):
                result['fund_scale'] = s['data'][-1]  # 亿元

    # 2. 经理任职规模 from Data_currentFundManager
    mgrs = extract_json(js, 'Data_currentFundManager')
    if mgrs and isinstance(mgrs, list) and len(mgrs) > 0:
        result['total_manage_scale'] = mgrs[0].get('fundSize', '')  # e.g. "78.91亿(4只基金)"

    # 3. 总份额 from Data_buySedemption
    bs = extract_json(js, 'Data_buySedemption')
    if bs and isinstance(bs, dict):
        for s in bs.get('series', []):
            if s.get('name') == '总份额' and s.get('data'):
                result['holders_count'] = s['data'][-1]  # 亿份 (approximation)

    return result


def fetch_jbgk_detail(code: str) -> dict:
    """从 fundf10/jbgk 页面提取基本信息"""
    url = f'https://fundf10.eastmoney.com/jbgk_{code}.html'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
    except:
        return {}

    result = {}

    # 基金管理人（公司名）
    m = re.search(r'基金管理人.*?<a[^>]*?>(.+?)</a>', html)
    if m: result['company'] = m.group(1).strip()

    # 管理费率 (HTML: <th>管理费率</th><td>1.20%（每年）</td>)
    m = re.search(r'管理费率</th><td>(.+?)</td>', html)
    if m: result['manage_fee'] = m.group(1).strip()

    # 托管费率
    m = re.search(r'托管费率</th><td>(.+?)</td>', html)
    if m: result['custody_fee'] = m.group(1).strip()

    # 成立日期
    m = re.search(r'成立日期[：:]\s*(\d{4}-\d{2}-\d{2})', html)
    if m: result['estab_date'] = m.group(1)

    return result


def fetch_risk_level(code: str) -> str:
    """从 fundf10/tsdata 页面提取风险等级"""
    url = f'https://fundf10.eastmoney.com/tsdata_{code}.html'
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        html = resp.read().decode('utf-8', errors='replace')
    except:
        return None

    # 匹配风险等级 - 找到带 chooseLow class 的 span
    m = re.search(r"<span\s+class='[^']*chooseLow[^']*'\s*>(.+?)</span>", html)
    if m:
        return m.group(1).strip()

    # Alternative: look for low1-low5 with chooseLow
    m = re.search(r"<span\s+class='[^']*?(low\d+)\s+chooseLow[^']*'\s*>(.+?)</span>", html)
    if m:
        return m.group(2).strip()

    return None


def process_one(code: str) -> dict:
    """处理一只基金，返回补充数据字典"""
    rate_sleep()
    extras = fetch_pingzhong_extras(code)
    if not extras:
        extras = {}

    jbgk = fetch_jbgk_detail(code)
    for k, v in jbgk.items():
        if v: extras[k] = v

    risk = fetch_risk_level(code)
    if risk:
        extras['risk_level'] = risk

    if extras:
        extras['c'] = code

    return extras if len(extras) > 1 else None


# ── 数据库操作 ────────────────────────────────────────────────────────────────

def get_codes_to_update(limit=None, resume=False):
    """获取需要补充数据的基金代码"""
    codes = []
    offset = 0
    while True:
        # Get codes where company IS NULL (unfilled)
        url = f"{SUPABASE_URL}/rest/v1/fund_raw_sample?select=c,company&offset={offset}&limit=1000&order=c"
        r = requests.get(url, headers=ANON_HEADERS, timeout=60)
        if r.status_code != 200:
            break
        batch = r.json()
        if not batch:
            break

        for row in batch:
            if resume:
                codes.append(row['c'])
            elif row.get('company') is None:
                codes.append(row['c'])

        offset += len(batch)
        if len(batch) < 1000 or (limit and len(codes) >= limit):
            break

    return codes[:limit] if limit else codes


def pg_escape(val):
    if val is None:
        return 'NULL'
    if isinstance(val, (int, float)):
        if isinstance(val, float) and math.isnan(val):
            return 'NULL'
        return str(val)
    s = str(val).replace("\\", "\\\\").replace("'", "''")
    return f"'{s}'"


def batch_update(updates: list):
    """批量更新 fund_raw_sample"""
    if not updates:
        return 0

    # Build CASE WHEN for each column
    codes_in = ", ".join(f"'{u['c']}'" for u in updates)

    set_clauses = []
    for col in UPDATE_COLS:
        when_parts = []
        for u in updates:
            val = u.get(col)
            if val is not None:
                when_parts.append(f"WHEN '{u['c']}' THEN {pg_escape(val)}")
        if when_parts:
            when_str = " ".join(when_parts)
            set_clauses.append(f'"{col}" = CASE c {when_str} END')

    if not set_clauses:
        return 0

    sql = f"UPDATE public.fund_raw_sample SET {', '.join(set_clauses)} WHERE c IN ({codes_in})"

    try:
        r = requests.post(MGMT_URL, headers=MGMT_HEADERS, timeout=120, json={"query": sql})
        if r.status_code in (200, 201):
            return len(updates)
        else:
            # Fallback to per-row update
            for u in updates:
                parts = []
                for col in UPDATE_COLS:
                    if u.get(col) is not None:
                        parts.append(f'"{col}" = {pg_escape(u[col])}')
                if parts:
                    sql2 = f"UPDATE public.fund_raw_sample SET {', '.join(parts)} WHERE c = '{u['c']}'"
                    requests.post(MGMT_URL, headers=MGMT_HEADERS, timeout=30, json={"query": sql2})
            return len(updates)
    except Exception as e:
        print(f"  [{ts()}] Batch update error: {e}")
        return 0


# ── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()

    print(f"[{ts()}] === supplement_fund_details 开始 ===")

    codes = get_codes_to_update(limit=args.limit, resume=args.resume)
    print(f"[{ts()}] 待处理基金: {len(codes)}")

    BATCH = 20
    results = []
    processed = [0]
    lock = threading.Lock()

    def worker(batch, wid):
        for code in batch:
            row = process_one(code)
            with lock:
                if row:
                    results.append(row)
                processed[0] += 1
                if processed[0] % 50 == 0:
                    print(f"  [{ts()}] 进度: {processed[0]}/{len(codes)}, 有数据: {len(results)}")

    batches = [codes[i:i+BATCH] for i in range(0, len(codes), BATCH)]
    threads = []
    for i, batch in enumerate(batches):
        t = threading.Thread(target=worker, args=(batch, i % WORKERS))
        threads.append(t)
        t.start()
        if len(threads) >= WORKERS:
            for t in threads:
                t.join()
            threads = []
            if len(results) >= 200:
                n = batch_update(results)
                print(f"  [{ts()}] 已更新: {n} 条（{processed[0]}/{len(codes)}）")
                results.clear()

    for t in threads:
        t.join()
    if results:
        n = batch_update(results)
        print(f"  [{ts()}] 已更新: {n} 条")

    # Stats
    stats = {}
    AK = ANON_KEY
    AH = {"apikey": AK, "Authorization": f"Bearer {AK}"}
    for col in ['company', 'fund_scale', 'manage_fee', 'total_manage_scale', 'risk_level']:
        r = requests.get(f"{SUPABASE_URL}/rest/v1/fund_raw_sample?select=count&{col}=not.is.null", headers=AH, timeout=30)
        try:
            stats[col] = r.json()[0]['count'] if isinstance(r.json(), list) else r.json()
        except:
            stats[col] = '?'
        print(f"  {col} 非空: {stats[col]}")

    print(f"\n[{ts()}] === 完成! ===")


if __name__ == '__main__':
    main()
