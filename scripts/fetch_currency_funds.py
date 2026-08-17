#!/usr/bin/env python3
"""
fetch_currency_funds.py — 抓取货币基金（货币型）阶段收益数据

数据源：天天基金 rankhandler.aspx (dt=hb, ft=hb, POST)
说明：
  - 货币基金【有】阶段收益（此前误以为没有）；
  - 阶段收益权威来源为 hb 排名页（jdzf 实时接口已下线）；
  - hb 排名页字段布局（已实测验证，2026-07-08）：
      [0]=代码  [1]=名称  [3]=净值日期  [4]=万份收益  [5]=七日年化
      [6]=近1周(r0w)  [7]=近1月(r1m)  [8]=近3月(r3m)  [9]=近6月(r6m)
      [10]=近1年(r1y) [11]=近2年(r2y) [12]=近3年(r3y)
      [13]=今年来(ytd) [14]=成立来(return_all)   ← 旧脚本误把 [14] 当规模导致漏抓
      [24]=二级分类(如"货币型-普通货币")  [25]=规模(亿元)
    ⚠️ hb 排名页【不含】近5年(r5y)，故 r5y 置 NULL。

用法：
  # 全量抓取（默认，覆盖写入 currency_output.ndjson）
  python3 fetch_currency_funds.py

  # 断点续传（追加到已有文件，跳过已抓取代码）
  python3 fetch_currency_funds.py --resume

  # 指定输出
  python3 fetch_currency_funds.py --output scripts/currency_output.ndjson
"""
import json
import os
import re
import sys
import time
import urllib.request
import urllib.parse
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, 'currency_output.ndjson')

HEADERS = {
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}

BASE_DELAY = 0.08  # 每页间隔，避免被限流


def _f(parts, i):
    """安全取第 i 个字段并转 float，缺失/非法返回 None"""
    if i >= len(parts):
        return None
    v = parts[i].strip()
    # 货币型基金在 hb 排名页常用 '0' / '0.0' / '-' / '--' 作为「该期限无数据」占位
    # （并非真实 0% 收益）。必须当缺失（None）处理，否则会被当 0% 排名打分，
    # 造成「无业绩却有评分」。负收益（如 '-1.23'）是真实值，保留。
    if v == '' or v is None or v in ('0', '0.0', '-', '--', '---', '—'):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def fetch_hb_all():
    """分页拉取全部货币型基金，返回 dict[code] = 阶段收益 dict"""
    print('拉取货币基金 hb rankhandler (POST dt=hb ft=hb)...', flush=True)
    all_data = {}

    # 先取第一页，得到总页数/总数
    body = {"op": "ph", "dt": "hb", "ft": "hb", "rs": "", "gs": "0",
            "sc": "1nzf", "st": "desc", "pi": "1", "pn": "100",
            "zf": "diy", "v": "0.1"}
    encoded = urllib.parse.urlencode(body).encode('utf-8')
    req = urllib.request.Request(
        'https://fund.eastmoney.com/data/rankhandler.aspx',
        data=encoded, headers=HEADERS)
    try:
        text = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
    except Exception as e:
        print(f'  [ERR] 初始请求失败: {e}', flush=True)
        return all_data

    pages_m = re.search(r'allPages:"(\d+)"', text)
    count_m = re.search(r'datacount:"(\d+)"', text)
    all_records_m = re.search(r'allRecords:(\d+)', text)
    total_pages = int(pages_m.group(1)) if pages_m else 10
    total_count = int(count_m.group(1)) if count_m else (int(all_records_m.group(1)) if all_records_m else 0)
    print(f'  总记录: {total_count}, 总页数: {total_pages}', flush=True)

    def parse_page(t):
        m = re.search(r'datas:\[(.*?)\]', t, re.DOTALL)
        if not m:
            return
        # 每只基金是 datas 里一个带引号、内部逗号分隔的字符串
        for rec in re.findall(r'"([^"]*)"', m.group(1)):
            parts = rec.split(',')
            if len(parts) < 15:
                continue
            code = parts[0].strip()
            if not code or code in all_data:
                continue
            t1 = parts[24].strip() if len(parts) > 24 else ''
            all_data[code] = {
                'c': code,
                'n': parts[1].strip() if len(parts) > 1 else '',
                't0': '货币型',
                't1': t1 if t1 else '货币型-普通货币',
                'r0w': _f(parts, 6),
                'r1m': _f(parts, 7),
                'r3m': _f(parts, 8),
                'r6m': _f(parts, 9),
                'r1y': _f(parts, 10),
                'r2y': _f(parts, 11),
                'r3y': _f(parts, 12),
                'r5y': None,                       # hb 排名页无近5年
                'ytd': _f(parts, 13),
                'return_all': _f(parts, 14),       # 成立来（此前误抓为 NULL）
                'scale': _f(parts, 25),            # 规模(亿元)，备用
            }

    parse_page(text)

    for page in range(2, total_pages + 1):
        time.sleep(BASE_DELAY)
        body['pi'] = str(page)
        encoded = urllib.parse.urlencode(body).encode('utf-8')
        req = urllib.request.Request(
            'https://fund.eastmoney.com/data/rankhandler.aspx',
            data=encoded, headers=HEADERS)
        try:
            t = urllib.request.urlopen(req, timeout=30).read().decode('utf-8')
            parse_page(t)
        except Exception as e:
            print(f'  [WARN] 第{page}页失败: {e}', flush=True)
        if page % 20 == 0 or page == total_pages:
            print(f'  进度: {page}/{total_pages} 页 ({len(all_data)} 条)', flush=True)

    print(f'  ✓ 共获取 {len(all_data)} 只货币基金阶段收益', flush=True)
    return all_data


def main():
    parser = argparse.ArgumentParser(description='抓取货币基金阶段收益 (hb rankhandler)')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出 NDJSON 路径')
    parser.add_argument('--resume', action='store_true',
                        help='断点续传：追加到已有文件并跳过已抓取代码')
    args = parser.parse_args()

    # 断点续传：读取已完成代码
    done_set = set()
    if args.resume and os.path.exists(args.output):
        with open(args.output, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        done_set.add(json.loads(line).get('c'))
                    except Exception:
                        pass
        if done_set:
            print(f'  断点续传：已抓取 {len(done_set)} 只，本次跳过', flush=True)

    data = fetch_hb_all()

    if not data:
        print('  [ERR] 未获取到任何货币型基金数据，退出', flush=True)
        sys.exit(1)

    # 增量/全量写入
    mode = 'a' if args.resume else 'w'
    written = 0
    skipped = 0
    t0 = time.time()
    with open(args.output, mode, encoding='utf-8') as out:
        for code, row in data.items():
            if code in done_set:
                skipped += 1
                continue
            out.write(json.dumps(row, ensure_ascii=False) + '\n')
            out.flush()  # 逐条落盘，超时也不丢数据
            written += 1
    print(f'  ✓ 写入 {written} 条（跳过 {skipped} 条已存在），耗时 {time.time()-t0:.1f}s', flush=True)
    print(f'  ✓ 输出 → {args.output}', flush=True)


if __name__ == '__main__':
    main()
