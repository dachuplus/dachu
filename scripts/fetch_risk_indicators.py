"""
批量抓取天天基金 pingzhongdata 接口，计算阶段最大回撤和夏普比率
输出 NDJSON 文件：{ "c": "110011", "dd1y": -16.58, "sr1y": -0.2522, ... }

使用方式：
  python3 fetch_risk_indicators.py [--input funds_full.ndjson] [--output risk_indicators.ndjson] [--delay 0.3]

参数：
  --input   : 输入 NDJSON 文件（默认 scripts/funds_full.ndjson）
  --output  : 输出 NDJSON 文件（默认 scripts/risk_indicators.ndjson）
  --delay   : 每次请求间隔秒数（默认 0.3，建议 0.2~0.5）
  --workers : 并发数（默认 3，建议 3~5）
  --limit   : 限制抓取数量（默认 0 = 全部）
  --resume  : 断点续传，跳过已存在的输出记录
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
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, 'funds_full.ndjson')
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')

# 阶段定义
PERIODS = [
    {'key': '1y', 'days': 365},
    {'key': '2y', 'days': 730},
    {'key': '3y', 'days': 1095},
    {'key': '5y', 'days': 1825},
]

# 无风险利率（2% 年化）
RF_ANNUAL = 0.02
RF_DAILY = RF_ANNUAL / 250

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://fund.eastmoney.com/',
    'Accept': '*/*',
}

# 全局成功/失败计数
success_count = 0
fail_count = 0
skip_count = 0


def fetch_and_calculate(fund_code):
    """抓取单只基金的历史净值数据，计算回撤和夏普比率。
    注意：return_all 由 step 2b (fetch_return_all.py) 单独抓取，此处不再请求 HTML 页面，
    仅通过累计净值/单位净值做兜底估算。"""
    global success_count, fail_count

    # 去掉 .OF 后缀
    code = fund_code.replace('.OF', '').replace('.of', '')
    url = f'http://fund.eastmoney.com/pingzhongdata/{code}.js'

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=15)
        js = resp.read().decode('utf-8')

        # 提取净值数据
        m = re.search(r'var Data_netWorthTrend\s*=\s*(\[.*?\]);', js)
        if not m:
            fail_count += 1
            return None

        data = json.loads(m.group(1))
        if not data or len(data) < 30:
            fail_count += 1
            return None

        # 解析净值序列
        records = []
        for d in data:
            dt = datetime.fromtimestamp(d['x'] / 1000)
            nav = d['y']
            if nav and nav > 0:
                records.append({'date': dt, 'nav': nav})

        if len(records) < 30:
            fail_count += 1
            return None

        end_date = records[-1]['date']

        # 成立以来收益兜底：用累计净值（含分红），降级用单位净值
        # 精确值由 step 2b (fetch_return_all.py) 通过 rankhandler API 抓取
        return_all = None

        # 方法1：用累计净值（含分红）
        m_ac = re.search(r'var Data_ACWorthTrend\s*=\s*(\[\[.*?\]\])\s*;', js)
        if m_ac:
            ac_data = json.loads(m_ac.group(1))
            if ac_data and len(ac_data) >= 2:
                ac_first_nav = ac_data[0][1]
                ac_last_nav = ac_data[-1][1]
                if ac_first_nav and ac_first_nav > 0:
                    return_all = round((ac_last_nav - ac_first_nav) / ac_first_nav * 100, 2)

        # 方法2：降级用单位净值
        if return_all is None:
            start_nav = records[0]['nav']
            end_nav = records[-1]['nav']
            return_all = round((end_nav - start_nav) / start_nav * 100, 2) if start_nav > 0 else None

        result = {'c': fund_code, 'return_all': return_all}

        # 提取基金经理名（从 Data_currentFundManager）
        try:
            mgr_m = re.search(r'var Data_currentFundManager\s*=\s*(\[.*?\])\s*;', js)
            if mgr_m:
                mgr_data = json.loads(mgr_m.group(1))
                if mgr_data and len(mgr_data) > 0:
                    result['fund_manager'] = mgr_data[0].get('name', '')
        except:
            result['fund_manager'] = None

        for period in PERIODS:
            label = period['key']
            days = period['days']
            start_dt = end_date - timedelta(days=days)

            # 筛选阶段内数据
            sub = [r for r in records if r['date'] >= start_dt]
            if len(sub) < 30:
                result[f'dd{label}'] = None
                result[f'sr{label}'] = None
                continue

            # 计算日收益率
            daily_rets = []
            for i in range(1, len(sub)):
                daily_ret = (sub[i]['nav'] / sub[i-1]['nav']) - 1
                daily_rets.append(daily_ret)

            # 最大回撤
            peak = sub[0]['nav']
            max_dd = 0
            for r in sub:
                if r['nav'] > peak:
                    peak = r['nav']
                dd = (peak - r['nav']) / peak
                if dd > max_dd:
                    max_dd = dd
            result[f'dd{label}'] = round(-max_dd * 100, 2)  # 负数表示回撤

            # 夏普比率
            if len(daily_rets) > 1:
                avg_ret = statistics.mean(daily_rets)
                std_ret = statistics.stdev(daily_rets)
                if std_ret > 0:
                    sharpe = (avg_ret - RF_DAILY) / std_ret * (250 ** 0.5)
                    result[f'sr{label}'] = round(sharpe, 4)
                else:
                    result[f'sr{label}'] = None
            else:
                result[f'sr{label}'] = None

        success_count += 1
        return result

    except Exception as e:
        fail_count += 1
        return None


def main():
    parser = argparse.ArgumentParser(description='批量抓取基金风险指标（最大回撤+夏普比率）')
    parser.add_argument('--input', default=DEFAULT_INPUT, help='输入 NDJSON 文件')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出 NDJSON 文件')
    parser.add_argument('--delay', type=float, default=0.3, help='请求间隔秒数')
    parser.add_argument('--workers', type=int, default=3, help='并发数')
    parser.add_argument('--limit', type=int, default=0, help='限制数量（0=全部）')
    parser.add_argument('--resume', action='store_true', help='断点续传')
    args = parser.parse_args()

    # 读取基金列表
    fund_codes = []
    with open(args.input, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                code = d.get('c', '')
                if code:
                    fund_codes.append(code)

    total = len(fund_codes)
    if args.limit > 0:
        fund_codes = fund_codes[:args.limit]

    print(f'=' * 60)
    print(f'批量抓取基金风险指标')
    print(f'基金总数: {total}, 本次抓取: {len(fund_codes)}')
    print(f'并发数: {args.workers}, 请求间隔: {args.delay}s')
    print(f'输出文件: {args.output}')
    print(f'=' * 60)

    # 断点续传：读取已有记录
    existing = set()
    _skip_count = 0
    if args.resume and os.path.exists(args.output):
        with open(args.output, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    d = json.loads(line)
                    existing.add(d.get('c', ''))
                    _skip_count += 1
        print(f'已有记录: {len(existing)} 条，将跳过')

    # 打开输出文件
    with open(args.output, 'a' if args.resume else 'w') as outf:
        # 用线程池并发抓取（按 delay 间隔提交任务以实现节流）
        with ThreadPoolExecutor(max_workers=args.workers) as executor:
            futures = {}
            for code in fund_codes:
                if code in existing:
                    _skip_count += 1
                    continue
                future = executor.submit(fetch_and_calculate, code)
                futures[future] = code
                # 提交间隔节流（分摊到 workers 个线程）
                time.sleep(args.delay / max(args.workers, 1))

            done = 0
            for future in as_completed(futures):
                done += 1
                code = futures[future]
                result = future.result()

                if result:
                    outf.write(json.dumps(result, ensure_ascii=False) + '\n')
                    outf.flush()

                # 进度显示
                if done % 200 == 0 or done == len(futures):
                    pct = done / len(futures) * 100 if len(futures) > 0 else 0
                    print(f'  进度: {done}/{len(futures)} ({pct:.1f}%) | 成功: {success_count} | 失败: {fail_count} | '
                          f'跳过: {_skip_count}')

    print(f'\n完成!')
    print(f'  成功: {success_count}')
    print(f'  失败: {fail_count}')
    print(f'  跳过(续传): {_skip_count}')
    print(f'  输出: {args.output}')

    # 验证输出
    count = 0
    with open(args.output, 'r') as f:
        for line in f:
            if line.strip():
                count += 1
    print(f'  总记录数: {count}')


if __name__ == '__main__':
    main()
