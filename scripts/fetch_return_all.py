#!/usr/bin/env python3
"""从天天基金 rankhandler.aspx 批量抓取"成立以来"收益率。

rankhandler.aspx 字段映射（按排名接口）：
[0]=基金代码 [1]=名称 [2]=拼音 [3]=净值日期 [4]=单位净值 [5]=累计净值
[6]=日涨幅 [7]=近1周 [8]=近1月 [9]=近3月 [10]=近6月
[11]=近1年 [12]=近2年 [13]=近3年 [14]=今年来 [15]=成立来
[16]=成立日期 [18]=成立来(精确)

输出 NDJSON 格式，每行：{"c": "519087.OF", "return_all": 2095.19}
"""

import urllib.request
import json
import re
import sys
import time

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/data/',
}

BASE_URL = 'https://fund.eastmoney.com/data/rankhandler.aspx'


def fetch_page(page, page_size=200):
    """抓取一页基金排名数据"""
    url = f'{BASE_URL}?op=ph&dt=kf&ft=all&rs=&gs=0&sc=dm&st=asc&pi={page}&pn={page_size}&v=0.1'
    req = urllib.request.Request(url, headers=HEADERS)
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read().decode('utf-8')

    # 提取 allRecords 总数
    total = 0
    m_total = re.search(r'allRecords:(\d+)', raw)
    if m_total:
        total = int(m_total.group(1))

    # 提取 datas 数组
    m = re.search(r'datas:\[(.*?)\],allRecords', raw)
    if not m:
        return [], total

    results = []
    items = m.group(1).split('"')
    for item in items:
        item = item.strip()
        if not item or item.startswith(',') or len(item) < 20:
            continue
        fields = item.split(',')
        code = fields[0]
        return_all_str = fields[15] if len(fields) > 15 else ''
        # 只有有效的收益率才输出
        if return_all_str and return_all_str.strip():
            try:
                return_all = float(return_all_str)
                results.append({'c': f'{code}.OF', 'return_all': return_all})
            except ValueError:
                pass

    return results, total


def main():
    output_file = sys.argv[1] if len(sys.argv) > 1 else 'return_all.ndjson'
    delay = float(sys.argv[2]) if len(sys.argv) > 2 else 0.3

    print('Fetching page 1 to get total count...')
    _, total = fetch_page(1)
    total_pages = (total + 199) // 200
    print(f'Total funds: {total}, pages: {total_pages}')

    all_results = []
    for page in range(1, total_pages + 1):
        results, _ = fetch_page(page)
        all_results.extend(results)
        if page % 20 == 0 or page == total_pages:
            print(f'  Page {page}/{total_pages}: {len(all_results)} funds so far')
        time.sleep(delay)

    # 写入 NDJSON
    with open(output_file, 'w') as f:
        for r in all_results:
            f.write(json.dumps(r) + '\n')

    print(f'Done: {len(all_results)} funds written to {output_file}')


if __name__ == '__main__':
    main()
