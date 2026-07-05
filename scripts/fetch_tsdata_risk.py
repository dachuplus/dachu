#!/usr/bin/env python3
"""
补充数据源：从天天基金 tsdata 页面抓取夏普比率和标准差。

对于 pingzhongdata 未覆盖的基金（如部分债券型-混合二级/可转债基金），
tsdata 页面提供了预计算的夏普比率(1y/2y/3y)和标准差(1y/2y/3y)。

工作流程：
1. 读取 risk_indicators.ndjson，找出 sr1y 为 null 的基金
2. 抓取 https://fundf10.eastmoney.com/tsdata_{code}.html
3. 从 HTML 中解析夏普比率和标准差
4. 合并回 risk_indicators.ndjson

使用方式：
  python3 fetch_tsdata_risk.py [--input risk_indicators.ndjson] [--workers 5] [--delay 0.3]
"""

import urllib.request
import json
import re
import sys
import os
import time
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_INPUT = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://fundf10.eastmoney.com/',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}

success_count = 0
fail_count = 0
skip_count = 0


def parse_tsdata_html(html):
    """从 tsdata HTML 页面解析夏普比率和标准差。

    HTML 结构：
    <tr><td>标准差</td><td class='num'>25.88%</td><td class='num'>22.99%</td><td class='num'>20.67%</td></tr>
    <tr><td>夏普比率</td><td class='num'>2.64</td><td class='num'>1.75</td><td class='num'>0.82</td></tr>
    """
    result = {}

    # 提取标准差：近1年/近2年/近3年
    m_std = re.search(r'标准差</td><td[^>]*>([^<]+)</td><td[^>]*>([^<]+)</td><td[^>]*>([^<]+)</td>', html)
    if m_std:
        for i, label in enumerate(['stddev1y', 'stddev2y', 'stddev3y']):
            val = m_std.group(i + 1).strip().rstrip('%')
            try:
                result[label] = round(float(val), 2)
            except (ValueError, TypeError):
                pass

    # 提取夏普比率：近1年/近2年/近3年
    m_sr = re.search(r'夏普比率</td><td[^>]*>([^<]+)</td><td[^>]*>([^<]+)</td><td[^>]*>([^<]+)</td>', html)
    if m_sr:
        for i, label in enumerate(['sr1y', 'sr2y', 'sr3y']):
            val = m_sr.group(i + 1).strip()
            try:
                result[label] = round(float(val), 4)
            except (ValueError, TypeError):
                pass

    return result if result else None


def fetch_tsdata(fund_code):
    """抓取单只基金的 tsdata 页面。"""
    global success_count, fail_count

    code = fund_code.replace('.OF', '').replace('.of', '')
    url = f'https://fundf10.eastmoney.com/tsdata_{code}.html'

    try:
        req = urllib.request.Request(url, headers=HEADERS)
        resp = urllib.request.urlopen(req, timeout=10)
        html = resp.read().decode('utf-8', errors='replace')

        result = parse_tsdata_html(html)
        if result:
            success_count += 1
            return {'c': fund_code, **result}
        else:
            fail_count += 1
            return None
    except Exception as e:
        fail_count += 1
        return None


def main():
    parser = argparse.ArgumentParser(description='从 tsdata 页面补充夏普比率数据')
    parser.add_argument('--input', default=DEFAULT_INPUT, help='输入 risk_indicators.ndjson')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出文件（默认覆盖输入）')
    parser.add_argument('--delay', type=float, default=0.3, help='请求间隔秒数')
    parser.add_argument('--workers', type=int, default=5, help='并发数')
    parser.add_argument('--limit', type=int, default=0, help='限制数量（0=全部）')
    args = parser.parse_args()

    # 1. 读取已有风险指标
    all_records = []
    need_fetch = []

    if not os.path.exists(args.input):
        print(f'错误：输入文件不存在 {args.input}')
        sys.exit(1)

    with open(args.input, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                all_records.append(r)
                # 找出 sr1y 为 null 的基金
                if r.get('sr1y') is None:
                    need_fetch.append(r)

    total = len(all_records)
    missing = len(need_fetch)
    print(f'=' * 60, flush=True)
    print(f'tsdata 补充数据抓取', flush=True)
    print(f'总记录: {total}, 需补充: {missing}', flush=True)
    print(f'并发: {args.workers}, 间隔: {args.delay}s', flush=True)
    print(f'=' * 60, flush=True)

    if missing == 0:
        print('所有基金已有夏普比率数据，无需补充', flush=True)
        return

    if args.limit > 0:
        need_fetch = need_fetch[:args.limit]

    # 2. 并发抓取 tsdata 页面
    tsdata_map = {}
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {}
        for r in need_fetch:
            code = r.get('c', '')
            if not code:
                continue
            future = executor.submit(fetch_tsdata, code)
            futures[future] = code
            time.sleep(args.delay / max(args.workers, 1))

        done = 0
        for future in as_completed(futures):
            done += 1
            result = future.result()
            if result:
                tsdata_map[result['c']] = result
            if done % 100 == 0 or done == len(futures):
                pct = done * 100 / len(futures)
                print(f'  进度: {done}/{len(futures)} ({pct:.1f}%) | 成功: {success_count} | 失败: {fail_count}', flush=True)

    # 3. 合并结果
    merged = 0
    for r in all_records:
        c = r.get('c', '')
        if c in tsdata_map:
            ts = tsdata_map[c]
            # 只补充 null 的字段，不覆盖已有值
            for k in ['sr1y', 'sr2y', 'sr3y', 'stddev1y', 'stddev2y', 'stddev3y']:
                if ts.get(k) is not None and r.get(k) is None:
                    r[k] = ts[k]
                    merged += 1

    # 4. 写回文件
    with open(args.output, 'w') as f:
        for r in all_records:
            f.write(json.dumps(r, ensure_ascii=False) + '\n')

    print(f'\n完成!', flush=True)
    print(f'  抓取成功: {success_count}/{len(need_fetch)}', flush=True)
    print(f'  抓取失败: {fail_count}', flush=True)
    print(f'  合并字段: {merged} 个', flush=True)
    print(f'  输出: {args.output}', flush=True)

    # 验证
    sr_count = sum(1 for r in all_records if r.get('sr1y') is not None)
    print(f'  sr1y 非null: {sr_count}/{len(all_records)} ({sr_count*100/len(all_records):.1f}%)', flush=True)


if __name__ == '__main__':
    main()
