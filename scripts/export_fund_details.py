#!/usr/bin/env python3
"""
导出 fund_combined 的基本详情字段为 NDJSON，供 import_via_rest.py 合并使用。
导出字段：c, company, fund_scale, manage_fee

用法：
  python3 export_fund_details.py scripts/fund_details.ndjson
"""
import json, sys, os, requests, argparse

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
HEADERS = {'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}'}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, 'fund_details.ndjson')


def main():
    parser = argparse.ArgumentParser(description='导出 fund_combined 详情到 NDJSON')
    parser.add_argument('output', nargs='?', default=DEFAULT_OUTPUT, help='输出 NDJSON 文件路径')
    args = parser.parse_args()

    print(f'导出 fund_combined 详情 → {args.output}')
    
    all_rows = []
    offset = 0
    limit = 1000
    
    while True:
        url = f'{SUPABASE_URL}/rest/v1/fund_combined?select=c,company,fund_scale,manage_fee&limit={limit}&offset={offset}'
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code != 200:
            print(f'  HTTP {resp.status_code}')
            break
        batch = resp.json()
        if not batch:
            break
        all_rows.extend(batch)
        offset += len(batch)
        print(f'  已读取 {offset} 行...')
        if len(batch) < limit:
            break
    
    print(f'  共 {len(all_rows)} 条')
    
    # 写入 NDJSON
    count = 0
    with open(args.output, 'w', encoding='utf-8') as f:
        for row in all_rows:
            out = {
                'c': row.get('c', '').replace('.OF', ''),
                'company': row.get('company'),
                'fund_scale': row.get('fund_scale'),
                'manage_fee': row.get('manage_fee'),
            }
            f.write(json.dumps(out, ensure_ascii=False) + '\n')
            count += 1
    
    print(f'✅ 导出完成: {count} 条 → {args.output}')


if __name__ == '__main__':
    main()
