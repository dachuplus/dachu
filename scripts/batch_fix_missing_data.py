#!/usr/bin/env python3
"""
综合修复脚本：补充缺失基金数据（QDII/债基/新基金）
1. 从 fund_combined 找出缺少 fund_quarterly_scores 的基金（排除货币型）
2. 通过 pingzhongdata 拉取净值 → 计算季度指标 + 风险指标 + 多周期收益
3. 上传 fund_quarterly_scores，更新 fund_combined
4. 对41只无数据的QDII：额外拉取F10页面获取基础信息
5. 全市场重算评分

用法：
  python3 scripts/batch_fix_missing_data.py --workers 8 --delay 0.2
  python3 scripts/batch_fix_missing_data.py --limit 50 --test   # 测试模式
"""

import os, json, re, sys, time, math, statistics, argparse
import urllib.request
import requests as http_requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Supabase 配置
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"

env_path = os.path.join(PROJECT_DIR, '.env.local')
MGMT_PAT = None
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            if line.startswith('SUPABASE_PAT='):
                MGMT_PAT = line.strip().split('=', 1)[1]
                break
if not MGMT_PAT:
    print("ERROR: SUPABASE_PAT not found")
    sys.exit(1)

PROJECT_REF = "tqhtegazxykkqfcpejky"
MGMT_API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_PAT}", "Content-Type": "application/json"}

# 常量
RF_ANNUAL = 0.02
RF_DAILY = RF_ANNUAL / 250
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

# 并发统计
success_net = 0
fail_net = 0
success_f10 = 0
fail_f10 = 0
rate_lock = threading.Lock()
rate_last = [0.0]


def mgmt_query(sql):
    """执行 Supabase Management API 查询"""
    try:
        resp = http_requests.post(MGMT_API, headers=MGMT_HEADERS, json={"query": sql}, timeout=60)
        data = resp.json()
        if isinstance(data, dict) and 'message' in data:
            print(f"  SQL错误: {data['message'][:150]}")
            return []
        return data
    except Exception as e:
        print(f"  API异常: {e}")
        return []


# ── 工具函数 ──────────────────────────────────────────────

def parse_numeric(text):
    """从文本提取数字"""
    if text is None:
        return None
    text = str(text).strip().replace(',', '').replace('，', '')
    m = re.search(r'([\d.]+)', text)
    if m:
        val = float(m.group(1))
        if '万' in text:
            val /= 10000
        return round(val, 4)
    return None


def get_quarter_range(year, quarter):
    """季度起止日期"""
    start_month = (quarter - 1) * 3 + 1
    start = datetime(year, start_month, 1)
    if quarter == 4:
        end = datetime(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = datetime(year, quarter * 3 + 1, 1) - timedelta(days=1)
    return start, end


def compute_returns(records):
    """从净值序列计算多周期收益 (YTD, r1y, r3y, r5y)"""
    if not records or len(records) < 30:
        return {}
    
    result = {}
    last_date = records[-1]['date']
    last_nav = records[-1]['nav']
    
    # YTD: 今年以来
    ytd_start = datetime(last_date.year, 1, 1)
    sub = [r for r in records if r['date'] >= ytd_start]
    if len(sub) >= 2 and sub[0]['nav'] > 0:
        result['ytd'] = round((sub[-1]['nav'] - sub[0]['nav']) / sub[0]['nav'] * 100, 2)
    
    # 近1年/近3年/近5年
    for label, days in [('1y', 365), ('3y', 1095), ('5y', 1825)]:
        start_dt = last_date - timedelta(days=days)
        sub = [r for r in records if r['date'] >= start_dt]
        if len(sub) >= 20 and sub[0]['nav'] > 0:
            result[f'r{label}'] = round((last_nav - sub[0]['nav']) / sub[0]['nav'] * 100, 2)
    
    # return_all: 累计收益
    if records[0]['nav'] > 0:
        result['return_all'] = round((last_nav - records[0]['nav']) / records[0]['nav'] * 100, 2)
    
    return result


def compute_risk_indicators(records):
    """计算风险指标 dd1y/sr1y"""
    if not records or len(records) < 60:
        return {}
    
    result = {}
    last_date = records[-1]['date']
    
    # 1年回撤和夏普
    start_dt = last_date - timedelta(days=365)
    sub = [r for r in records if r['date'] >= start_dt]
    if len(sub) < 30:
        return result
    
    # 最大回撤
    peak = sub[0]['nav']
    max_dd = 0
    for r in sub:
        if r['nav'] > peak:
            peak = r['nav']
        dd = (peak - r['nav']) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    result['dd1y'] = round(-max_dd * 100, 2)
    
    # 夏普比率
    daily_rets = []
    for i in range(1, len(sub)):
        if sub[i-1]['nav'] > 0:
            daily_rets.append(sub[i]['nav'] / sub[i-1]['nav'] - 1)
    if len(daily_rets) > 1:
        avg_ret = statistics.mean(daily_rets)
        std_ret = statistics.stdev(daily_rets)
        if std_ret > 0:
            sr = (avg_ret - RF_DAILY) / std_ret * (250 ** 0.5)
            result['sr1y'] = round(sr, 4)
    
    return result


def compute_quarterly(records):
    """计算40个季度的收益/回撤/夏普"""
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
        if len(sub) < 15:  # 降低门槛：原来30，改为15
            continue
        
        if sub[0]['nav'] > 0:
            ret = (sub[-1]['nav'] - sub[0]['nav']) / sub[0]['nav'] * 100
            q_ret[idx] = round(ret, 2)
        
        peak = sub[0]['nav']
        max_dd = 0
        for r in sub:
            if r['nav'] > peak:
                peak = r['nav']
            dd = (peak - r['nav']) / peak if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        q_dd[idx] = round(-max_dd * 100, 2)
        
        daily_rets = []
        for i in range(1, len(sub)):
            if sub[i-1]['nav'] > 0:
                daily_rets.append(sub[i]['nav'] / sub[i-1]['nav'] - 1)
        if len(daily_rets) > 5:
            avg = statistics.mean(daily_rets)
            std = statistics.stdev(daily_rets) if len(daily_rets) > 1 else 0
            if std > 0:
                sr = (avg - RF_DAILY) / std * (250 ** 0.5)
                q_sr[idx] = round(sr, 4)
    
    n_q = sum(1 for v in q_ret if v is not None)
    if n_q < 2:  # 至少需要2个季度
        return None
    
    return {'q_ret': q_ret, 'q_dd': q_dd, 'q_sr': q_sr, 'q_n': n_q}


# ── 数据抓取 ────────────────────────────────────────────

def fetch_pingzhongdata(code, delay=0.05):
    """抓取单只基金的 pingzhongdata → 完整指标计算"""
    global success_net, fail_net
    
    with rate_lock:
        now = time.time()
        if rate_last[0] > 0:
            elapsed = now - rate_last[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
        rate_last[0] = time.time()
    
    code = str(code).strip()
    try:
        url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=12)
        js = resp.read().decode('utf-8')
        
        m = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', js)
        if not m:
            fail_net += 1
            return None
        
        data = json.loads(m.group(1))
        if not data or len(data) < 30:
            fail_net += 1
            return None
        
        records = []
        for d in data:
            dt = datetime.fromtimestamp(d['x'] / 1000)
            nav = d['y']
            if nav and nav > 0:
                records.append({'date': dt, 'nav': nav})
        
        if len(records) < 30:
            fail_net += 1
            return None
        
        result = {'c': code}
        
        # 收益
        rets = compute_returns(records)
        result.update(rets)
        
        # 风险指标
        risk = compute_risk_indicators(records)
        result.update(risk)
        
        # 季度数据（降低门槛到30天+2个季度）
        quarterly = compute_quarterly(records)
        if quarterly:
            result.update(quarterly)
        
        # 累计净值（用于return_all修正）
        m_ac = re.search(r'var Data_ACWorthTrend\s*=\s*(\[\[.*?\]\])\s*;', js)
        if m_ac:
            ac_data = json.loads(m_ac.group(1))
            if ac_data and len(ac_data) >= 2:
                ac_first = ac_data[0][1]
                ac_last = ac_data[-1][1]
                if ac_first and ac_first > 0:
                    result['return_all'] = round((ac_last - ac_first) / ac_first * 100, 2)
        
        success_net += 1
        return result
        
    except Exception as e:
        fail_net += 1
        return None


def fetch_f10_info(code):
    """从F10获取公司/规模/费率"""
    global success_f10, fail_f10
    
    info = {'company': None, 'fund_scale': None, 'manage_fee': None}
    
    try:
        url = f'http://fundf10.eastmoney.com/jbgk_{code}.html'
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='ignore')
        
        # 公司
        m = re.search(r'基金管理人</th>\s*<td>\s*<a[^>]*>([^<]+)</a>', html)
        if not m:
            m = re.search(r'基金管理人</th>\s*<td>([^<]+)', html)
        if not m:
            m = re.search(r'基金管理人[：:]?\s*<[^>]*>\s*([^<]+)', html)
        if m:
            info['company'] = m.group(1).strip()
        
        # 规模（净资产规模）
        m = re.search(r'净资产规模</th>\s*<td>\s*([\d.,]+[亿万])', html)
        if not m:
            m = re.search(r'基金规模</th>\s*<td>\s*([\d.,]+[亿万])', html)
        if not m:
            m = re.search(r'(?:基金规模|净资产规模)[：:]?\s*<[^>]*>\s*([\d.,]+[亿万])', html)
        if m:
            info['fund_scale'] = parse_numeric(m.group(1).strip())
        
        # 费率
        m = re.search(r'管理费率</th>\s*<td>\s*([\d.]+)%', html)
        if not m:
            m = re.search(r'管理费率[：:]?\s*<[^>]*>\s*([\d.]+)%', html)
        if not m:
            m = re.search(r'管理费率[：:]?\s*([\d.]+)%', html)
        if m:
            info['manage_fee'] = float(m.group(1))
        
        success_f10 += 1
        return info
    except:
        fail_f10 += 1
        return info


# ── 上传和更新 ──────────────────────────────────────────

def upload_quarterly(all_quarterly):
    """上传季度数据到 fund_quarterly_scores"""
    print(f"\n上传季度数据 ({len(all_quarterly)} 条)...")
    
    batch_size = 50
    total = 0
    for i in range(0, len(all_quarterly), batch_size):
        batch = all_quarterly[i:i+batch_size]
        values_parts = []
        for r in batch:
            qd = json.dumps({
                'q_ret': r.get('q_ret', []),
                'q_dd': r.get('q_dd', []),
                'q_sr': r.get('q_sr', []),
                'q_n': r.get('q_n', 0),
            })
            c = r['c']
            values_parts.append(f"('{c}', $json${qd}$json$::jsonb, now())")
        
        sql = (
            "INSERT INTO public.fund_quarterly_scores (c, quarterly_data, updated_at) "
            f"VALUES {', '.join(values_parts)} "
            "ON CONFLICT (c) DO UPDATE SET quarterly_data=EXCLUDED.quarterly_data, updated_at=now()"
        )
        mgmt_query(sql)
        total += len(batch)
        if total % 200 == 0:
            print(f"  已上传: {total}/{len(all_quarterly)}")
    
    print(f"  上传完成: {total} 条")


def update_fund_combined_details(results, f10_data_map):
    """更新 fund_combined 的详情字段（YTD/r1y/r3y/r5y/dd1y/sr1y）"""
    print(f"\n更新 fund_combined 详情 ({len(results)} 只)...")
    
    batch_size = 200
    total = 0
    for i in range(0, len(results), batch_size):
        batch = results[i:i+batch_size]
        cases_parts = []
        
        # YTD
        yt_cases = []
        for r in batch:
            v = r.get('ytd')
            if v is not None:
                yt_cases.append(f"WHEN c='{r['c']}' THEN {v}")
        if yt_cases:
            cases_parts.append("ytd = CASE " + " ".join(yt_cases) + " ELSE ytd END")
        
        # Returns
        for col in ['r1y', 'r3y', 'r5y']:
            c_cases = []
            for r in batch:
                v = r.get(col)
                if v is not None:
                    c_cases.append(f"WHEN c='{r['c']}' THEN {v}")
            if c_cases:
                cases_parts.append(f"{col} = CASE " + " ".join(c_cases) + f" ELSE {col} END")
        
        # Risk indicators
        for col in ['dd1y', 'sr1y']:
            c_cases = []
            for r in batch:
                v = r.get(col)
                if v is not None:
                    c_cases.append(f"WHEN c='{r['c']}' THEN {v}")
            if c_cases:
                cases_parts.append(f"{col} = CASE " + " ".join(c_cases) + f" ELSE {col} END")
        
        # F10 data for those that don't have company yet
        comp_cases = []
        scale_cases = []
        fee_cases = []
        for r in batch:
            code = r['c']
            f10 = f10_data_map.get(code, {})
            if f10.get('company') and not f10.get('_skip_company'):
                esc = f10['company'].replace("'", "''")
                comp_cases.append(f"WHEN c='{code}' THEN '{esc}'")
            if f10.get('fund_scale') is not None:
                scale_cases.append(f"WHEN c='{code}' THEN {f10['fund_scale']}")
            if f10.get('manage_fee') is not None:
                fee_val = f10['manage_fee']
                fee_cases.append(f"WHEN c='{code}' THEN '{fee_val}%'")
        
        if comp_cases:
            cases_parts.append("company = CASE " + " ".join(comp_cases) + " ELSE company END")
        if scale_cases:
            cases_parts.append("fund_scale = CASE " + " ".join(scale_cases) + " ELSE fund_scale END")
        if fee_cases:
            cases_parts.append("manage_fee = CASE " + " ".join(fee_cases) + " ELSE manage_fee END")
        
        if not cases_parts:
            continue
        
        where = ",".join([f"'{r['c']}'" for r in batch])
        sql = f"UPDATE fund_combined SET {', '.join(cases_parts)} WHERE c IN ({where})"
        mgmt_query(sql)
        total += len(batch)
        if total % 500 == 0:
            print(f"  已更新: {total}/{len(results)}")
    
    print(f"  详情更新完成: {total} 只")


def recalc_all_scores():
    """重新计算全市场评分（与 fix_qdii_funds.py 一致）"""
    print("\n重新计算全市场季度滚动评分...")
    
    rows = mgmt_query("SELECT c, quarterly_data FROM fund_quarterly_scores")
    print(f"  读取 {len(rows)} 条季度数据")
    
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
        if q_n < 2:
            continue
        
        for qi in range(min(q_n, 40)):
            if q_ret[qi] is None:
                continue
            if qi not in QUARTER_SCORES:
                QUARTER_SCORES[qi] = {'ret': [], 'dd': [], 'sr': [], 'codes': []}
            QUARTER_SCORES[qi]['ret'].append(q_ret[qi])
            QUARTER_SCORES[qi]['dd'].append(q_dd[qi] if q_dd[qi] is not None else 0)
            QUARTER_SCORES[qi]['sr'].append(q_sr[qi] if q_sr[qi] is not None else 0)
            QUARTER_SCORES[qi]['codes'].append(c)
    
    print(f"  有效季度: {len(QUARTER_SCORES)}")
    
    SINGLE_Q_SCORES = {}
    for qi, data in QUARTER_SCORES.items():
        n = len(data['codes'])
        if n < 10:
            continue
        
        ret_vals = sorted(data['ret'])
        ret_rank = {}
        for i, v in enumerate(ret_vals):
            ret_rank[v] = (i + 1) / n * 100
        
        dd_vals = sorted(data['dd'], reverse=True)
        dd_rank = {}
        for i, v in enumerate(dd_vals):
            dd_rank[v] = (i + 1) / n * 100
        
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
    
    print(f"  单季评分: {len(SINGLE_Q_SCORES)} 只")
    
    PERIODS_MAP = [
        ('k3m', 1), ('k6m', 2), ('k1', 4), ('k2', 8),
        ('k3', 12), ('k5', 20), ('k7', 28), ('k10', 40),
    ]
    
    FUND_SCORES = {}
    for c, qs in SINGLE_Q_SCORES.items():
        scores = {}
        for pname, nq in PERIODS_MAP:
            vals = [qs.get(qi) for qi in range(nq) if qi in qs]
            if len(vals) >= max(1, nq // 2):
                scores[pname] = round(sum(vals) / len(vals), 2)
        if scores:
            FUND_SCORES[c] = scores
    
    print(f"  多周期评分: {len(FUND_SCORES)} 只")
    
    all_k3m = sorted([s.get('k3m') for s in FUND_SCORES.values() if s.get('k3m') is not None])
    n_total = len(all_k3m)
    p80 = all_k3m[int(n_total * 0.8)] if n_total > 0 else 0
    p50 = all_k3m[int(n_total * 0.5)] if n_total > 0 else 0
    
    for c, s in FUND_SCORES.items():
        if s.get('k3m') is not None:
            s['score_grade'] = 'green' if s['k3m'] >= p80 else ('blue' if s['k3m'] >= p50 else 'orange')
        else:
            s['score_grade'] = None
    
    print(f"  阈值: green>={p80:.1f}, blue>={p50:.1f}")
    
    # 批量更新
    print(f"\n  更新 fund_combined 评分...")
    codes_list = list(FUND_SCORES.keys())
    batch_size = 500
    total_updated = 0
    
    for i in range(0, len(codes_list), batch_size):
        batch = codes_list[i:i+batch_size]
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
        
        sg_cases = []
        for c in batch:
            s = FUND_SCORES.get(c, {})
            v = s.get('score_grade')
            if v:
                sg_cases.append(f"WHEN c = '{c}' THEN '{v}'")
        if sg_cases:
            cases.append("score_grade = CASE " + " ".join(sg_cases) + " ELSE score_grade END")
        
        if cases:
            where = ",".join([f"'{c}'" for c in batch])
            sql = f"UPDATE fund_combined SET {', '.join(cases)} WHERE c IN ({where})"
            mgmt_query(sql)
        
        total_updated += len(batch)
        if total_updated % 3000 == 0:
            print(f"  已更新: {total_updated}/{len(codes_list)}")
    
    print(f"  评分更新完成: {total_updated} 只")
    
    stats = mgmt_query("""
        SELECT score_grade, COUNT(*) as cnt FROM fund_combined 
        WHERE score_grade IS NOT NULL GROUP BY score_grade ORDER BY cnt DESC
    """)
    print("\n  === 评级分布 ===")
    total_scored = 0
    for s in stats:
        print(f"    {s['score_grade']}: {s['cnt']}")
        total_scored += s['cnt']
    
    ts = mgmt_query("SELECT COUNT(*) as cnt FROM fund_combined WHERE k3m IS NOT NULL")
    print(f"  有评分总计: {ts[0]['cnt']}")


# ── Main ─────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='综合修复缺失数据')
    parser.add_argument('--workers', type=int, default=8, help='并发数')
    parser.add_argument('--delay', type=float, default=0.2, help='请求间隔')
    parser.add_argument('--limit', type=int, default=0, help='限制数量')
    parser.add_argument('--test', action='store_true', help='测试模式（不写入DB）')
    args = parser.parse_args()
    
    start_time = time.time()
    
    # Step 1: 获取缺失的基金列表
    print("=" * 60)
    print("Step 1: 获取缺失基金列表")
    print("=" * 60)
    
    missing_rows = mgmt_query("""
        SELECT fc.c, fc.name, fc.t0, fc.t1, fc.company
        FROM fund_combined fc
        WHERE NOT EXISTS (
            SELECT 1 FROM fund_quarterly_scores qs 
            WHERE qs.c = CONCAT(fc.c, '.OF') OR qs.c = fc.c
        )
        AND fc.t0 != '货币型'
        ORDER BY fc.c
    """)
    
    # 过滤出真正需要处理的
    to_process = [(r['c'], r['name'], r['t0'], r.get('company')) for r in missing_rows]
    print(f"  缺失季度数据的基金: {len(to_process)} 只 (排除货币型)")
    
    if args.limit > 0:
        to_process = to_process[:args.limit]
        print(f"  限制为前 {args.limit} 只")
    
    # Step 2: 并发抓取 pingzhongdata
    print(f"\n{'=' * 60}")
    print(f"Step 2: 抓取 pingzhongdata ({len(to_process)} 只)")
    print(f"{'=' * 60}")
    
    all_results = []
    codes_only = [c for c, _, _, _ in to_process]
    effective_delay = args.delay / max(args.workers, 1)
    
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(fetch_pingzhongdata, c, effective_delay): c for c in codes_only}
        
        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                all_results.append(result)
            
            if done % 200 == 0 or done == len(futures):
                elapsed = time.time() - start_time
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  进度: {done}/{len(futures)} ({done/len(futures)*100:.1f}%) | "
                      f"成功: {success_net} | 失败: {fail_net} | {rate:.1f}/s")
    
    elapsed1 = time.time() - start_time
    print(f"\n  Phase 1 完成: {elapsed1/60:.1f}min | 成功: {success_net} | 失败: {fail_net} | 有效: {len(all_results)}")
    
    if not all_results:
        print("\n无有效数据，退出")
        return
    
    # Step 3: 对完全无数据的QDII/新基金，尝试F10
    print(f"\n{'=' * 60}")
    print(f"Step 3: 补充 F10 数据（无pingzhongdata的基金）")
    print(f"{'=' * 60}")
    
    fetched_codes = set(r['c'] for r in all_results)
    need_f10 = [c for c, _, t0, _ in to_process if c not in fetched_codes]
    print(f"  需要F10: {len(need_f10)} 只")
    
    f10_data_map = {}
    if need_f10:
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {executor.submit(fetch_f10_info, c): c for c in need_f10}
            
            for future in as_completed(futures):
                code = futures[future]
                info = future.result()
                if info:
                    f10_data_map[code] = info
    
        print(f"  F10 完成: 成功={success_f10}, 失败={fail_f10}")
    
    if args.test:
        print("\n=== TEST MODE - 不写入数据库 ===")
        print(f"有效结果: {len(all_results)}")
        print(f"F10数据: {len(f10_data_map)}")
        for r in all_results[:3]:
            print(json.dumps(r, ensure_ascii=False))
        return
    
    # Step 4: 上传季度数据
    has_quarterly = [r for r in all_results if 'q_ret' in r]
    upload_quarterly(has_quarterly)
    
    # Step 5: 更新 fund_combined 详情
    update_fund_combined_details(all_results, f10_data_map)
    
    # Step 6: 重算评分
    recalc_all_scores()
    
    total_elapsed = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"✅ 综合修复完成! 总耗时: {total_elapsed/60:.1f}min")
    print(f"  pingzhongdata: {success_net} 成功, {fail_net} 失败")
    print(f"  F10: {success_f10} 成功, {fail_f10} 失败")
    print(f"  季度数据新增: {len(has_quarterly)}")
    print(f"{'=' * 60}")


if __name__ == '__main__':
    main()
