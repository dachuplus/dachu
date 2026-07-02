"""
计算全量基金的季度靠谱指数评分。

流程：
1. 从 pingzhongdata 抓取每日净值 → 计算 40 个季度指标
2. 横截面排名 → 6个时间窗口评分
3. 导入 Supabase fund_quarterly_scores 表

用法：
  # 全量计算（需要联网，约 15-20 分钟）
  python3 compute_quarterly_scores.py

  # 测试模式（只处理前 N 只）
  python3 compute_quarterly_scores.py --limit 100

  # 只计算评分（跳过数据抓取，从 NDJSON 读取）
  python3 compute_quarterly_scores.py --from-file quarterly_raw.ndjson
"""

import urllib.request
import json
import re
import sys
import os
import time
import math
import statistics
import argparse
import requests as http_requests
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# Supabase 配置
SUPABASE_URL = "https://tqhtegazxykkqfcpejky.supabase.co"
SUPABASE_ANON_KEY = "sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3"
MGMT_PAT = os.environ.get("SUPABASE_MGMT_TOKEN") or ''
PROJECT_REF = "tqhtegazxykkqfcpejky"

# 常量
RF_ANNUAL = 0.02
RF_DAILY = RF_ANNUAL / 250

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

# 评分窗口: (名称, 季度数, 年数)
WINDOWS = [
    ('score_3m', 1, 0.25),
    ('score_6m', 2, 0.5),
    ('score_1y', 4, 1),
    ('score_2y', 8, 2),
    ('score_3y', 12, 3),
    ('score_5y', 20, 5),
    ('score_7y', 28, 7),
    ('score_10y', 40, 10),
]

import bisect
import threading

success_count = 0
fail_count = 0
rate_lock = threading.Lock()
rate_last = [0.0]


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

    return {
        'q_ret': q_ret,
        'q_dd': q_dd,
        'q_sr': q_sr,
        'q_n': n_quarters,
    }


def fetch_and_calc_quarterly(fund_code, delay=0.06):
    """抓取单只基金每日净值，计算季度指标。内部节流。"""
    global success_count, fail_count
    
    # 速率限制
    with rate_lock:
        now = time.time()
        if rate_last[0] > 0:
            elapsed = now - rate_last[0]
            if elapsed < delay:
                time.sleep(delay - elapsed)
        rate_last[0] = time.time()
    
    code = str(fund_code).replace('.OF', '').replace('.of', '').strip()
    url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        js = resp.read().decode('utf-8')

        m = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', js)
        if not m:
            fail_count += 1
            return None

        data = json.loads(m.group(1))
        if not data or len(data) < 60:
            fail_count += 1
            return None

        records = []
        for d in data:
            dt = datetime.fromtimestamp(d['x'] / 1000)
            nav = d['y']
            if nav and nav > 0:
                records.append({'date': dt, 'nav': nav})

        if len(records) < 60:
            fail_count += 1
            return None

        quarterly = compute_quarterly(records)
        if quarterly is None:
            fail_count += 1
            return None

        success_count += 1
        return {'c': code, **quarterly}

    except Exception:
        fail_count += 1
        return None


def compute_scores(all_results):
    """横截面排名计算评分"""
    scores = {}
    for wname, nq, years in WINDOWS:
        # 过滤有足够数据的基金
        valid = [(r, r['q_ret'][:nq], r['q_dd'][:nq], r['q_sr'][:nq])
                 for r in all_results if r['q_n'] >= nq]
        if len(valid) < 2:
            continue

        # 计算年化指标
        metrics = []
        for r, rets, dds, srs in valid:
            # 年化收益
            cum = 1.0
            for v in rets:
                if v is not None:
                    cum *= (1 + v / 100)
            annual_ret = (cum ** (1 / years) - 1) * 100 if cum > 0 else -100

            # 最大回撤
            valid_dds = [d for d in dds if d is not None]
            max_dd = min(valid_dds) if valid_dds else 0

            # 年化夏普
            valid_srs = [s for s in srs if s is not None]
            avg_sr = sum(valid_srs) / len(valid_srs) if valid_srs else 0
            annual_sr = avg_sr * 2

            metrics.append({
                'c': r['c'],
                'ret': annual_ret,
                'dd': max_dd,
                'sr': annual_sr,
            })

        n = len(metrics)
        rets = [m['ret'] for m in metrics]
        dds = [m['dd'] for m in metrics]
        srs = [m['sr'] for m in metrics]

        def build_ranker(vals, reverse=False):
            """预计算排位映射 val→pct，O(n log n)"""
            sorted_u = sorted(set(vals), reverse=reverse)
            n = len(sorted_u)
            rank_map = {}
            prev_rank = 0
            for i, v in enumerate(sorted_u):
                # count how many unique values are strictly worse
                rank_map[v] = round(i / (n - 1) * 100, 2) if n > 1 else 50
            return lambda v: rank_map.get(v, 50)

        rank_ret = build_ranker(rets, False)
        rank_dd = build_ranker(dds, True)
        rank_sr = build_ranker(srs, False)

        for m in metrics:
            k_ret = rank_ret(m['ret'])
            k_dd = rank_dd(m['dd'])
            k_sr = rank_sr(m['sr'])
            k_all = round(k_ret * 0.50 + k_dd * 0.25 + k_sr * 0.25, 2)

            if m['c'] not in scores:
                scores[m['c']] = {}
            scores[m['c']][wname] = k_all

    return scores


def import_to_supabase(all_results, scores):
    """批量导入 Supabase"""
    MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
    headers = {"Authorization": f"Bearer {MGMT_PAT}", "Content-Type": "application/json"}

    # 不清空旧数据，直接 upsert（ON CONFLICT DO UPDATE）
    print(f"  开始导入 {len(all_results)} 条...")

    # 批量插入（每批 500 条）
    batch = []
    total = 0
    for r in all_results:
        code = r['c']
        quarterly_data = {
            'q_ret': r['q_ret'],
            'q_dd': r['q_dd'],
            'q_sr': r['q_sr'],
            'q_n': r['q_n'],
        }
        fund_scores = scores.get(code, {})

        batch.append({
            'c': code,
            'quarterly_data': json.dumps(quarterly_data),
            'score_3m': fund_scores.get('score_3m'),
            'score_6m': fund_scores.get('score_6m'),
            'score_1y': fund_scores.get('score_1y'),
            'score_2y': fund_scores.get('score_2y'),
            'score_3y': fund_scores.get('score_3y'),
            'score_5y': fund_scores.get('score_5y'),
            'score_7y': fund_scores.get('score_7y'),
            'score_10y': fund_scores.get('score_10y'),
        })

        if len(batch) >= 50:
            total += _insert_batch(batch, MGMT_URL, headers)
            batch = []
            if total > 0 and total % 500 == 0:
                print(f"  已入库: {total} 条", flush=True)

    if batch:
        total += _insert_batch(batch, MGMT_URL, headers)

    print(f"  入库完成: {total} 条")


def _insert_batch(batch, url, headers):
    """插入一批数据到 fund_quarterly_scores（用 dollar-quoting 避免 JSON 转义问题）"""
    values_parts = []
    for row in batch:
        vals = []
        vals.append(f"'{row['c']}'")
        # 用 PostgreSQL dollar-quoting 安全插入 JSONB
        if row['quarterly_data']:
            vals.append(f"$json${row['quarterly_data']}$json$::jsonb")
        else:
            vals.append('NULL')
        for wname, _, _ in WINDOWS:
            v = row.get(wname)
            vals.append(str(v) if v is not None else 'NULL')
        vals.append('now()')
        values_parts.append("(" + ", ".join(vals) + ")")

    columns = "c, quarterly_data, score_3m, score_6m, score_1y, score_2y, score_3y, score_5y, score_7y, score_10y, updated_at"
    sql = f"INSERT INTO public.fund_quarterly_scores ({columns}) VALUES {', '.join(values_parts)} ON CONFLICT (c) DO UPDATE SET quarterly_data=EXCLUDED.quarterly_data, score_3m=EXCLUDED.score_3m, score_6m=EXCLUDED.score_6m, score_1y=EXCLUDED.score_1y, score_2y=EXCLUDED.score_2y, score_3y=EXCLUDED.score_3y, score_5y=EXCLUDED.score_5y, score_7y=EXCLUDED.score_7y, score_10y=EXCLUDED.score_10y, updated_at=now()"

    try:
        resp = http_requests.post(url, headers=headers, timeout=60,
                                  json={"query": sql})
        if resp.status_code == 201:
            return len(batch)
        else:
            print(f"  插入失败 [{resp.status_code}]: {resp.text[:300]}")
            return 0
    except Exception as e:
        print(f"  插入异常: {e}")
        return 0


def get_fund_codes_from_supabase(limit=0):
    """从 Supabase fund_scores 表获取基金代码列表（用 Range 分页，anon key 限制 1000/页）"""
    base_url = f"{SUPABASE_URL}/rest/v1/fund_scores?select=c"
    headers = {
        "apikey": SUPABASE_ANON_KEY,
        "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
    }
    codes = []
    page_size = 1000
    offset = 0
    while True:
        h = dict(headers)
        h["Range"] = f"{offset}-{offset + page_size - 1}"
        resp = http_requests.get(base_url, headers=h, timeout=30)
        if resp.status_code not in (200, 206):
            print(f"  获取基金列表失败 [{resp.status_code}]: {resp.text[:200]}")
            break
        data = resp.json()
        if not data:
            break
        for item in data:
            codes.append(item['c'])
        if limit > 0 and len(codes) >= limit:
            codes = codes[:limit]
            break
        if len(data) < page_size:
            break
        offset += page_size
    return codes


def main():
    parser = argparse.ArgumentParser(description='计算全量基金季度靠谱指数评分')
    parser.add_argument('--limit', type=int, default=0, help='限制数量（0=全部）')
    parser.add_argument('--workers', type=int, default=5, help='并发数（默认 5）')
    parser.add_argument('--delay', type=float, default=0.3, help='请求间隔秒数')
    parser.add_argument('--from-file', type=str, default='', help='从 NDJSON 文件读取季度数据（跳过抓取）')
    parser.add_argument('--output', type=str, default='', help='输出季度数据到 NDJSON 文件')
    parser.add_argument('--no-import', action='store_true', help='不导入 Supabase')
    args = parser.parse_args()

    all_results = []

    if args.from_file:
        # 从文件读取季度数据
        print(f"从文件读取: {args.from_file}")
        with open(args.from_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    all_results.append(json.loads(line))
        print(f"读取 {len(all_results)} 条记录")
    else:
        # 从 Supabase 获取基金列表
        print("从 Supabase fund_scores 获取基金列表...")
        fund_codes = get_fund_codes_from_supabase(args.limit)
        print(f"获取到 {len(fund_codes)} 只基金")

        total = len(fund_codes)
        if args.limit > 0:
            fund_codes = fund_codes[:args.limit]

        print(f"{'=' * 60}")
        print(f"季度靠谱指数评分计算")
        print(f"基金总数: {total}, 本次处理: {len(fund_codes)}")
        print(f"并发数: {args.workers}, 节流间隔: {args.delay}s (工作线程内)")
        print(f"{'=' * 60}")

        # 多线程抓取（一次性提交，工作线程内部节流）
        start_time = time.time()
        effective_delay = args.delay / max(args.workers, 1)
        
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for code in fund_codes:
                future = executor.submit(fetch_and_calc_quarterly, code, effective_delay)
                futures[future] = code

            done = 0
            for future in as_completed(futures):
                done += 1
                result = future.result()
                if result:
                    all_results.append(result)

                if done % 500 == 0 or done == len(futures):
                    elapsed = time.time() - start_time
                    rate = done / elapsed if elapsed > 0 else 0
                    eta = (len(futures) - done) / rate if rate > 0 else 0
                    print(f"  进度: {done}/{len(futures)} ({done/len(futures)*100:.1f}%) | "
                          f"成功: {success_count} | 失败: {fail_count} | "
                          f"速率: {rate:.1f}/s | ETA: {eta/60:.1f}min")

        elapsed = time.time() - start_time
        print(f"\n数据抓取完成: {elapsed/60:.1f} 分钟")
        print(f"  成功: {success_count} | 失败: {fail_count} | 总计: {len(all_results)}")

        # 保存原始数据（可选）
        if args.output:
            with open(args.output, 'w') as f:
                for r in all_results:
                    f.write(json.dumps(r, ensure_ascii=False) + '\n')
            print(f"  季度数据已保存: {args.output}")

    if not all_results:
        print("无有效数据，退出")
        return

    # 计算评分
    print(f"\n计算横截面评分（{len(all_results)} 只基金）...")
    scores = compute_scores(all_results)

    # 统计
    for wname, nq, years in WINDOWS:
        count = sum(1 for s in scores.values() if wname in s)
        vals = [s[wname] for s in scores.values() if wname in s]
        if vals:
            print(f"  {wname} ({nq}Q): {count} 只有效, "
                  f"范围 [{min(vals):.1f}, {max(vals):.1f}], 均值 {sum(vals)/len(vals):.1f}")

    # 导入 Supabase
    if not args.no_import:
        print(f"\n导入 Supabase...")
        import_to_supabase(all_results, scores)
    else:
        print(f"\n跳过 Supabase 导入（--no-import）")

    print(f"\n✅ 完成!")


if __name__ == '__main__':
    main()
