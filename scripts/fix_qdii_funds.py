#!/usr/bin/env python3
"""
修复 QDII 基金数据（398只）：通过 pingzhongdata + F10 页面拉取完整数据
1. 抓取 pingzhongdata → 计算季度指标（q_ret/q_dd/q_sr）+ 风险指标（dd/sr）+ return_all
2. 抓取 F10 页面 → company, fund_scale, manage_fee
3. 导入 fund_quarterly_scores（季度原始数据）
4. 更新 fund_combined（详情数据）
5. 重新计算滚动评分（k3m~k10 + score_grade）
"""

import os, json, re, sys, time, math, statistics, argparse
import urllib.request
import requests as http_requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# ── 配置 ─────────────────────────────────────────────────────────────────────
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"

# Read PAT from .env.local
env_path = os.path.join(PROJECT_DIR, '.env.local')
MGMT_PAT = None
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('SUPABASE_PAT='):
                MGMT_PAT = line.strip().split('=', 1)[1]
                break
if not MGMT_PAT:
    print("ERROR: SUPABASE_PAT not found in .env.local")
    sys.exit(1)

PROJECT_REF = "tqhtegazxykkqfcpejky"
MGMT_API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_PAT}", "Content-Type": "application/json"}

# 常量
RF_ANNUAL = 0.02
RF_DAILY = RF_ANNUAL / 250
PERIODS = [('1y', 365), ('2y', 730), ('3y', 1095), ('5y', 1825)]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

# 并发控制
success_net = 0
fail_net = 0
success_f10 = 0
fail_f10 = 0
rate_lock = threading.Lock()
rate_last = [0.0]

# ── 工具函数 ─────────────────────────────────────────────────────────────────

def mgmt_query(sql):
    """执行 Supabase Management API 查询"""
    try:
        resp = http_requests.post(MGMT_API, headers=MGMT_HEADERS, json={"query": sql}, timeout=60)
        data = resp.json()
        if isinstance(data, dict) and 'message' in data:
            print(f"  ⚠ SQL错误: {data['message'][:150]}")
            return []
        return data
    except Exception as e:
        print(f"  ⚠ API异常: {e}")
        return []


def get_qdii_codes():
    """从 fund_combined 获取所有 QDII 基金代码"""
    print("获取 QDII 基金代码...")
    rows = mgmt_query("SELECT c, name, t1 FROM fund_combined WHERE t0 = 'QDII' ORDER BY c")
    codes = [(r['c'], r['name'], r['t1']) for r in rows]
    print(f"  QDII 基金: {len(codes)} 只")
    return codes


def parse_numeric(text):
    """从文本中提取数字，如 '168.00亿元' → 168.0"""
    if text is None:
        return None
    text = str(text).strip().replace(',', '').replace('，', '')
    m = re.search(r'([\d.]+)', text)
    if m:
        val = float(m.group(1))
        if '万' in text:
            val /= 10000  # 万元 → 亿元
        return round(val, 4)
    return None


def parse_percent(text):
    """从文本中提取百分比数字"""
    if text is None:
        return None
    text = str(text).strip().replace('%', '').strip()
    try:
        return float(text)
    except:
        return None


# ── Phase 1: Fetch pingzhongdata ─────────────────────────────────────────────

def get_quarter_range(year, quarter):
    """返回季度的起止日期"""
    start_month = (quarter - 1) * 3 + 1
    start = datetime(year, start_month, 1)
    if quarter == 4:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, quarter * 3 + 1, 1) - timedelta(days=1)
    return start, end


def compute_quarterly(records):
    """从日净值序列计算最近 40 个季度指标"""
    if not records or len(records) < 60:
        return None

    today = datetime.now()
    if today.month <= 3:
        last_q = (today.year - 1, 4)
    elif today.month <= 6:
        last_q = (today.year, 1)
    elif today.month <= 9:
        last_q = (today.year, 2)
    else:
        last_q = (today.year, 3)

    quarters = []
    y, q = last_q
    for _ in range(40):
        quarters.append((y, q))
        q -= 1
        if q == 0:
            q = 4
            y -= 1

    q_ret = [None] * 40
    q_dd = [None] * 40
    q_sr = [None] * 40

    for idx, (y, q) in enumerate(quarters):
        start, end = get_quarter_range(y, q)
        sub = [r for r in records if start <= r['date'] <= end]
        if len(sub) < 30:
            continue

        # 季度收益
        if sub[0]['nav'] > 0:
            ret = (sub[-1]['nav'] - sub[0]['nav']) / sub[0]['nav'] * 100
            q_ret[idx] = round(ret, 2)

        # 季度最大回撤
        peak = sub[0]['nav']
        max_dd = 0
        for r in sub:
            if r['nav'] > peak:
                peak = r['nav']
            dd = (peak - r['nav']) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        q_dd[idx] = round(-max_dd * 100, 2)

        # 季度夏普
        daily_rets = []
        for i in range(1, len(sub)):
            if sub[i - 1]['nav'] > 0:
                daily_rets.append(sub[i]['nav'] / sub[i - 1]['nav'] - 1)
        if len(daily_rets) > 10:
            avg = statistics.mean(daily_rets)
            std = statistics.stdev(daily_rets)
            if std > 0:
                sr = (avg - RF_DAILY) / std * (250 ** 0.5)
                q_sr[idx] = round(sr, 4)

    n_quarters = sum(1 for v in q_ret if v is not None)
    if n_quarters < 4:
        return None

    return {'q_ret': q_ret, 'q_dd': q_dd, 'q_sr': q_sr, 'q_n': n_quarters}


def compute_risk_indicators(records):
    """从日净值序列计算风险指标"""
    if not records or len(records) < 30:
        return {}

    end_date = records[-1]['date']
    result = {}

    for label, days in PERIODS:
        start_dt = end_date - timedelta(days=days)
        sub = [r for r in records if r['date'] >= start_dt]
        if len(sub) < 30:
            result[f'dd{label}'] = None
            result[f'sr{label}'] = None
            continue

        # 最大回撤
        peak = sub[0]['nav']
        max_dd = 0
        for r in sub:
            if r['nav'] > peak:
                peak = r['nav']
            dd = (peak - r['nav']) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        result[f'dd{label}'] = round(-max_dd * 100, 2)

        # 夏普
        daily_rets = []
        for i in range(1, len(sub)):
            if sub[i - 1]['nav'] > 0:
                daily_rets.append(sub[i]['nav'] / sub[i - 1]['nav'] - 1)
        if len(daily_rets) > 1:
            avg_ret = statistics.mean(daily_rets)
            std_ret = statistics.stdev(daily_rets)
            if std_ret > 0:
                sr = (avg_ret - RF_DAILY) / std_ret * (250 ** 0.5)
                result[f'sr{label}'] = round(sr, 4)
            else:
                result[f'sr{label}'] = None
        else:
            result[f'sr{label}'] = None

    # return_all: 用累计净值
    start_nav = records[0]['nav']
    end_nav = records[-1]['nav']
    if start_nav > 0:
        result['return_all'] = round((end_nav - start_nav) / start_nav * 100, 2)
    else:
        result['return_all'] = None

    return result


def fetch_pingzhongdata(fund_code, delay=0.06):
    """抓取单只基金的 pingzhongdata"""
    global success_net, fail_net

    with rate_lock:
        now = time.time()
        if rate_last[0] > 0:
            elapsed = now - rate_last[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
        rate_last[0] = time.time()

    code = str(fund_code).strip()

    try:
        url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        js = resp.read().decode('utf-8')

        m = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', js)
        if not m:
            fail_net += 1
            return None

        data = json.loads(m.group(1))
        if not data or len(data) < 60:
            fail_net += 1
            return None

        records = []
        for d in data:
            dt = datetime.fromtimestamp(d['x'] / 1000)
            nav = d['y']
            if nav and nav > 0:
                records.append({'date': dt, 'nav': nav})

        if len(records) < 60:
            fail_net += 1
            return None

        # 季度指标
        quarterly = compute_quarterly(records)
        if quarterly is None:
            fail_net += 1
            return None

        # 风险指标
        risk = compute_risk_indicators(records)

        # 用累计净值修正 return_all
        m_ac = re.search(r'var Data_ACWorthTrend\s*=\s*(\[\[.*?\]\])\s*;', js)
        if m_ac:
            ac_data = json.loads(m_ac.group(1))
            if ac_data and len(ac_data) >= 2:
                ac_first = ac_data[0][1]
                ac_last = ac_data[-1][1]
                if ac_first and ac_first > 0:
                    risk['return_all'] = round((ac_last - ac_first) / ac_first * 100, 2)

        success_net += 1
        return {'c': code, **quarterly, **risk}

    except Exception as e:
        fail_net += 1
        return None


# ── Phase 2: Fetch F10 ───────────────────────────────────────────────────────

def fetch_f10_info(fund_code):
    """从 F10 页面抓取基金详情"""
    global success_f10, fail_f10

    code = str(fund_code).strip()

    info = {
        'company': None,
        'fund_scale': None,
        'manage_fee': None,
        'manager': None,
    }

    try:
        url = f'http://fundf10.eastmoney.com/jbgk_{code}.html'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')

        # 基金公司
        m = re.search(r'基金管理人</th>\s*<td>\s*<a[^>]*>([^<]+)</a>', html)
        if not m:
            m = re.search(r'基金管理人</th>\s*<td>([^<]+)', html)
        if not m:
            m = re.search(r'基金管理人[：:]?\s*<[^>]*>\s*([^<]+)', html)
        if m:
            info['company'] = m.group(1).strip()

        # 基金规模（天天基金F10使用"净资产规模"）
        m = re.search(r'净资产规模</th>\s*<td>\s*([\d.,]+[亿万])', html)
        if not m:
            m = re.search(r'基金规模</th>\s*<td>\s*([\d.,]+[亿万])', html)
        if not m:
            m = re.search(r'(?:基金规模|净资产规模)[：:]?\s*<[^>]*>\s*([\d.,]+[亿万])', html)
        if m:
            info['fund_scale'] = parse_numeric(m.group(1).strip())

        # 管理费率
        m = re.search(r'管理费率</th>\s*<td>\s*([\d.]+)%', html)
        if not m:
            m = re.search(r'管理费率[：:]?\s*<[^>]*>\s*([\d.]+)%', html)
        if not m:
            m = re.search(r'管理费率[：:]?\s*([\d.]+)%', html)
        if m:
            info['manage_fee'] = parse_percent(m.group(1).strip())

        success_f10 += 1
        return info

    except Exception as e:
        fail_f10 += 1
        return info  # Return partial data


# ── Phase 3: Upload ──────────────────────────────────────────────────────────

def upload_quarterly_scores(all_quarterly):
    """批量上传季度数据到 fund_quarterly_scores"""
    print(f"\n上传季度数据到 fund_quarterly_scores ({len(all_quarterly)} 条)...")

    batch_size = 50
    total_inserted = 0

    for i in range(0, len(all_quarterly), batch_size):
        batch = all_quarterly[i:i + batch_size]
        values_parts = []

        for r in batch:
            code = r['c']
            qd = json.dumps({
                'q_ret': r['q_ret'],
                'q_dd': r['q_dd'],
                'q_sr': r['q_sr'],
                'q_n': r['q_n'],
            })

            vals = []
            vals.append(f"'{code}'")
            vals.append(f"$json${qd}$json$::jsonb")
            vals.append('now()')
            values_parts.append("(" + ", ".join(vals) + ")")

        sql = (
            "INSERT INTO public.fund_quarterly_scores (c, quarterly_data, updated_at) "
            f"VALUES {', '.join(values_parts)} "
            "ON CONFLICT (c) DO UPDATE SET quarterly_data=EXCLUDED.quarterly_data, updated_at=now()"
        )

        rows = mgmt_query(sql)
        total_inserted += batch_size
        if total_inserted % 200 == 0:
            print(f"  已上传: {total_inserted}/{len(all_quarterly)}")

    print(f"  上传完成: {len(all_quarterly)} 条")


def update_fund_combined(all_results, f10_data):
    """批量更新 fund_combined 表（QDII 基金详情数据）"""
    print(f"\n更新 fund_combined ({len(all_results)} 只 QDII 基金)...")

    batch_size = 100
    total_updated = 0

    for i in range(0, len(all_results), batch_size):
        batch = all_results[i:i + batch_size]
        cases_parts = []

        # Company
        comp_cases = []
        for r in batch:
            code = r['c']
            info = f10_data.get(code, {})
            comp = info.get('company', '')
            if comp:
                escaped = comp.replace("'", "''")
                comp_cases.append(f"WHEN c = '{code}' THEN '{escaped}'")
        if comp_cases:
            cases_parts.append("company = CASE " + " ".join(comp_cases) + " ELSE company END")

        # Fund scale
        scale_cases = []
        for r in batch:
            code = r['c']
            info = f10_data.get(code, {})
            scale = info.get('fund_scale')
            if scale is not None:
                scale_cases.append(f"WHEN c = '{code}' THEN {scale}")
        if scale_cases:
            cases_parts.append("fund_scale = CASE " + " ".join(scale_cases) + " ELSE fund_scale END")

        # Manage fee (text column, store as string)
        fee_cases = []
        for r in batch:
            code = r['c']
            info = f10_data.get(code, {})
            fee = info.get('manage_fee')
            if fee is not None:
                fee_cases.append(f"WHEN c = '{code}' THEN '{fee}%'")
        if fee_cases:
            cases_parts.append("manage_fee = CASE " + " ".join(fee_cases) + " ELSE manage_fee END")

        # Return data (only r1y/r3y/r5y exist in fund_combined)
        for ret_period in ['r1y', 'r3y', 'r5y']:
            # For now we only have return_all (cumulative), not individual period returns
            pass

        # Risk indicators (only dd1y/sr1y exist in fund_combined)
        for label in ['1y']:
            dd_cases = []
            for r in batch:
                code = r['c']
                dd = r.get(f'dd{label}')
                if dd is not None:
                    dd_cases.append(f"WHEN c = '{code}' THEN {dd}")
            if dd_cases:
                cases_parts.append(f"dd{label} = CASE " + " ".join(dd_cases) + f" ELSE dd{label} END")

            sr_cases = []
            for r in batch:
                code = r['c']
                sr = r.get(f'sr{label}')
                if sr is not None:
                    sr_cases.append(f"WHEN c = '{code}' THEN {sr}")
            if sr_cases:
                cases_parts.append(f"sr{label} = CASE " + " ".join(sr_cases) + f" ELSE sr{label} END")

        if not cases_parts:
            continue

        where = ", ".join([f"'{r['c']}'" for r in batch])
        sql = f"UPDATE fund_combined SET {', '.join(cases_parts)} WHERE c IN ({where})"
        mgmt_query(sql)
        total_updated += len(batch)

        if total_updated % 300 == 0:
            print(f"  已更新: {total_updated}/{len(all_results)}")

    print(f"  fund_combined 更新完成: {len(all_results)} 只")


# ── Phase 4: Recalculate scores ──────────────────────────────────────────────

def recalc_scores():
    """重新计算所有基金的季度滚动评分（与 calc_quarterly_scores.py 逻辑一致）"""
    print("\n重新计算全市场季度滚动评分...")

    # Step 1: 读取所有基金的季度数据
    rows = mgmt_query("SELECT c, quarterly_data FROM fund_quarterly_scores")
    print(f"  读取 {len(rows)} 只基金的季度数据")

    # Step 2: 计算单季评分
    QUARTER_SCORES = {}

    for row in rows:
        c = row['c'].replace('.OF', '')
        try:
            qd = json.loads(row['quarterly_data']) if isinstance(row['quarterly_data'], str) else row['quarterly_data']
        except:
            continue

        q_ret = qd.get('q_ret', [])
        q_dd = qd.get('q_dd', [])
        q_sr = qd.get('q_sr', [])
        q_n = qd.get('q_n', 0)

        if q_n < 4:
            continue

        # 对每个季度计算单季评分
        for qi in range(min(q_n, 40)):
            if q_ret[qi] is None:
                continue
            if qi not in QUARTER_SCORES:
                QUARTER_SCORES[qi] = {'ret': [], 'dd': [], 'sr': [], 'codes': []}
            QUARTER_SCORES[qi]['ret'].append(q_ret[qi])
            QUARTER_SCORES[qi]['dd'].append(q_dd[qi] if q_dd[qi] is not None else 0)
            QUARTER_SCORES[qi]['sr'].append(q_sr[qi] if q_sr[qi] is not None else 0)
            QUARTER_SCORES[qi]['codes'].append(c)

    print(f"  有效季度数据: {len(QUARTER_SCORES)} 个季度")

    # 计算百分位排名
    SINGLE_Q_SCORES = {}  # {c: {qi: score}}

    for qi, data in QUARTER_SCORES.items():
        n = len(data['codes'])
        if n < 10:
            continue

        # 收益排名 (越高越好)
        ret_vals = sorted(data['ret'])
        ret_rank = {}
        for i, v in enumerate(ret_vals):
            ret_rank[v] = (i + 1) / n * 100

        # 回撤排名 (绝对值越小越好)
        dd_vals = sorted(data['dd'], reverse=True)
        dd_rank = {}
        for i, v in enumerate(dd_vals):
            dd_rank[v] = (i + 1) / n * 100

        # 夏普排名 (越高越好)
        sr_vals = sorted(data['sr'])
        sr_rank = {}
        for i, v in enumerate(sr_vals):
            sr_rank[v] = (i + 1) / n * 100

        for idx, c in enumerate(data['codes']):
            score = round(
                ret_rank.get(data['ret'][idx], 50) * 0.50 +
                dd_rank.get(data['dd'][idx], 50) * 0.25 +
                sr_rank.get(data['sr'][idx], 50) * 0.25, 2
            )
            if c not in SINGLE_Q_SCORES:
                SINGLE_Q_SCORES[c] = {}
            SINGLE_Q_SCORES[c][qi] = score

    print(f"  单季评分计算完成: {len(SINGLE_Q_SCORES)} 只基金")

    # Step 3: 计算多周期评分
    PERIODS_MAP = [
        ('k3m', 1),
        ('k6m', 2),
        ('k1', 4),
        ('k2', 8),
        ('k3', 12),
        ('k5', 20),
        ('k7', 28),
        ('k10', 40),
    ]

    FUND_SCORES = {}  # {c: {k3m: ..., ...}}

    for c, qs in SINGLE_Q_SCORES.items():
        scores = {}
        for pname, nq in PERIODS_MAP:
            vals = [qs.get(qi) for qi in range(nq) if qi in qs]
            if len(vals) >= max(1, nq // 2):
                scores[pname] = round(sum(vals) / len(vals), 2)
        if scores:
            FUND_SCORES[c] = scores

    print(f"  多周期评分计算完成: {len(FUND_SCORES)} 只基金")

    # Step 4: 计算 score_grade
    all_k3m = [s.get('k3m') for s in FUND_SCORES.values() if s.get('k3m') is not None]
    all_k3m.sort()
    n_total = len(all_k3m)
    p80 = all_k3m[int(n_total * 0.8)] if n_total > 0 else 0
    p50 = all_k3m[int(n_total * 0.5)] if n_total > 0 else 0

    for c, s in FUND_SCORES.items():
        if s.get('k3m') is not None:
            if s['k3m'] >= p80:
                s['score_grade'] = 'green'
            elif s['k3m'] >= p50:
                s['score_grade'] = 'blue'
            else:
                s['score_grade'] = 'orange'
        else:
            s['score_grade'] = None

    print(f"  score_grade: green>={p80:.1f}, blue>={p50:.1f}")

    # Step 5: 批量更新 fund_combined
    print(f"\n  更新 fund_combined 评分...")
    batch_size = 500
    codes_list = list(FUND_SCORES.keys())
    total_updated = 0

    for i in range(0, len(codes_list), batch_size):
        batch = codes_list[i:i + batch_size]
        cases = []

        for pname, _ in PERIODS_MAP:
            p_cases = []
            for c in batch:
                s = FUND_SCORES.get(c, {})
                v = s.get(pname)
                if v is not None:
                    p_cases.append(f"WHEN c = '{c}' THEN {v}")
            if p_cases:
                cases.append(f"{pname} = CASE " + " ".join(p_cases) + f" ELSE {pname} END")

        # score_grade
        sg_cases = []
        for c in batch:
            s = FUND_SCORES.get(c, {})
            v = s.get('score_grade')
            if v:
                sg_cases.append(f"WHEN c = '{c}' THEN '{v}'")
        if sg_cases:
            cases.append("score_grade = CASE " + " ".join(sg_cases) + " ELSE score_grade END")

        if cases:
            where = ", ".join([f"'{c}'" for c in batch])
            sql = f"UPDATE fund_combined SET {', '.join(cases)} WHERE c IN ({where})"
            mgmt_query(sql)

        total_updated += len(batch)
        if total_updated % 2000 == 0:
            print(f"  已更新: {total_updated}/{len(codes_list)}")

    print(f"  评分更新完成: {len(codes_list)} 只基金")

    # 统计
    stats = mgmt_query("""
        SELECT score_grade, COUNT(*) as cnt 
        FROM fund_combined 
        WHERE score_grade IS NOT NULL 
        GROUP BY score_grade 
        ORDER BY cnt DESC
    """)
    print("\n  === fund_combined 评分统计 ===")
    for s in stats:
        print(f"  {s['score_grade']}: {s['cnt']}")

    total_with_score = mgmt_query("SELECT COUNT(*) as cnt FROM fund_combined WHERE k3m IS NOT NULL")
    print(f"  有评分: {total_with_score[0]['cnt']} / {len(FUND_SCORES)}")


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='修复 QDII 基金数据')
    parser.add_argument('--workers', type=int, default=5, help='并发数（默认 5）')
    parser.add_argument('--delay', type=float, default=0.3, help='请求间隔')
    parser.add_argument('--limit', type=int, default=0, help='限制数量（0=全部）')
    parser.add_argument('--skip-fetch', action='store_true', help='跳过数据抓取（从已保存文件读取）')
    parser.add_argument('--skip-f10', action='store_true', help='跳过 F10 抓取')
    parser.add_argument('--output', type=str, default='', help='保存季度数据到 NDJSON')
    args = parser.parse_args()

    start_time = time.time()

    # Step 1: 获取 QDII 基金代码
    qdii_codes = get_qdii_codes()
    if args.limit > 0:
        qdii_codes = qdii_codes[:args.limit]

    all_results = []
    f10_data = {}

    if args.skip_fetch:
        # 从文件读取
        ndjson_path = args.output or os.path.join(SCRIPT_DIR, 'qdii_quarterly.ndjson')
        if os.path.exists(ndjson_path):
            print(f"从文件读取季度数据: {ndjson_path}")
            with open(ndjson_path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        all_results.append(json.loads(line))
            print(f"  读取 {len(all_results)} 条")
    else:
        # Step 2: 抓取 pingzhongdata（季度数据 + 风险指标）
        print(f"\n{'=' * 60}")
        print(f"Phase 1: 抓取 pingzhongdata（季度 + 风险指标）")
        print(f"QDII 基金: {len(qdii_codes)} 只 | 并发: {args.workers} | 节流: {args.delay}s")
        print(f"{'=' * 60}")

        codes_only = [c for c, _, _ in qdii_codes]
        effective_delay = args.delay / max(args.workers, 1)

        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for code in codes_only:
                future = executor.submit(fetch_pingzhongdata, code, effective_delay)
                futures[future] = code

            done = 0
            for future in as_completed(futures):
                done += 1
                result = future.result()
                if result:
                    all_results.append(result)

                if done % 100 == 0 or done == len(futures):
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (len(futures) - done) / rate if rate > 0 else 0
                    print(f"  进度: {done}/{len(futures)} ({done/len(futures)*100:.1f}%) | "
                          f"成功: {success_net} | 失败: {fail_net} | "
                          f"速率: {rate:.1f}/s | ETA: {eta/60:.1f}min")

        elapsed1 = time.time() - start_time
        print(f"\n  Phase 1 完成: {elapsed1/60:.1f}min")
        print(f"  成功: {success_net} | 失败: {fail_net} | 总计: {len(all_results)}")

        # 保存季度数据
        if args.output:
            with open(args.output, 'w') as f:
                for r in all_results:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            print(f"  季度数据已保存: {args.output}")

        # Step 3: 抓取 F10 页面
        if not args.skip_f10:
            print(f"\n{'=' * 60}")
            print(f"Phase 2: 抓取 F10 页面（公司/规模/费率）")
            print(f"{'=' * 60}")

            f2_start = time.time()
            with ThreadPoolExecutor(max_workers=args.workers) as executor:
                futures = {}
                for code, _, _ in qdii_codes:
                    future = executor.submit(fetch_f10_info, code)
                    futures[future] = code

                done = 0
                for future in as_completed(futures):
                    done += 1
                    code = futures[future]
                    info = future.result()
                    if info:
                        f10_data[code] = info

                    if done % 100 == 0 or done == len(futures):
                        print(f"  进度: {done}/{len(futures)} | "
                              f"成功: {success_f10} | 失败: {fail_f10}")

            f2_elapsed = time.time() - f2_start
            print(f"\n  Phase 2 完成: {f2_elapsed/60:.1f}min")
            print(f"  成功: {success_f10} | 失败: {fail_f10} | F10数据: {len(f10_data)}")

    if not all_results:
        print("无有效数据，退出")
        return

    # Step 4: 上传季度数据
    upload_quarterly_scores(all_results)

    # Step 5: 更新 fund_combined
    update_fund_combined(all_results, f10_data)

    # Step 6: 重新计算评分
    recalc_scores()

    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"✅ QDII 基金修复完成! 总耗时: {total_elapsed/60:.1f}min")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
