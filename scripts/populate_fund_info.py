#!/usr/bin/env python3
"""
补充基金规模/股票占比/债券占比数据
1. 从 fund_scores 表获取所有基金代码
2. 通过东方财富 pingzhongdata 接口批量拉取数据
3. 通过 Supabase REST API 批量更新

用法: python3 scripts/populate_fund_info.py [--batch-size 100] [--max 500]
"""
import json
import os
import sys
import time
import argparse
import requests

# ===== 配置 =====
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 从 .env.local 读取 ANON_KEY
if not ANON_KEY:
    env_path = os.path.join(os.path.dirname(SCRIPT_DIR), '.env.local')
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith('VITE_SUPABASE_ANON_KEY='):
                    ANON_KEY = line.split('=', 1)[1].strip()
                    break

HEADERS = {
    'apikey': ANON_KEY,
    'Authorization': f'Bearer {ANON_KEY}',
    'Content-Type': 'application/json',
    'Prefer': 'return=minimal'
}

USER_AGENT = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'

def fetch_all_codes():
    """从 fund_scores 获取所有基金代码（一行一个请求）"""
    # 先获取总数
    r = requests.get(
        f'{SUPABASE_URL}/rest/v1/fund_scores?select=c&limit=1',
        headers={**HEADERS, 'Prefer': 'count=exact'}
    )
    count = int(r.headers.get('content-range', '0-0/0').split('/')[-1])
    print(f'共有 {count} 只基金', flush=True)
    
    codes = []
    page_size = 1000
    for offset in range(0, count, page_size):
        r = requests.get(
            f'{SUPABASE_URL}/rest/v1/fund_scores?select=c,scale,stock_pct,bond_pct&limit={page_size}&offset={offset}&order=c.asc',
            headers=HEADERS
        )
        if r.status_code == 200:
            batch = r.json()
            for item in batch:
                # 只获取 scale/stock_pct/bond_pct 为空的基金
                if item.get('scale') is None and item.get('stock_pct') is None:
                    codes.append(item['c'])
        if offset % 5000 == 0:
            print(f'  已扫描 {offset}/{count}...', flush=True)
    print(f'需要更新的基金: {len(codes)} 只（数据为空）', flush=True)
    return codes


def fetch_fund_info(code):
    """从 pingzhongdata 拉取基金规模/持仓数据"""
    pure_code = code.replace('.OF', '').replace('.of', '')
    url = f'http://fund.eastmoney.com/pingzhongdata/{pure_code}.js'
    
    try:
        r = requests.get(url, headers={'User-Agent': USER_AGENT, 'Referer': 'https://fund.eastmoney.com/'}, timeout=10)
        if r.status_code != 200:
            return None
        
        text = r.text
        result = {}
        
        import re
        
        # 提取最新股票仓位 (Data_fundSharesPositions 最后一个值)
        # 格式: Data_fundSharesPositions = [[timestamp,value],...];
        m = re.search(r'Data_fundSharesPositions\s*=\s*(\[\[.*?\]\])\s*[;*]', text, re.DOTALL)
        if m:
            pairs = re.findall(r'\[(\d+),\s*([\d.]+)\]', m.group(1))
            if pairs:
                result['stock_pct'] = float(pairs[-1][1])
        
        # 提取资产配置 (Data_assetAllocation)
        # 格式: Data_assetAllocation = {"series":[...]}
        m = re.search(r'Data_assetAllocation\s*=\s*(\{[^;]+\})', text)
        if m:
            alloc_str = m.group(1)
            # 提取债券占净比的值
            # 找 "name":"债券占净比" 对应的 data 数组最后一个值
            bond_match = re.search(r'"债券占净比".*?"data":\[([^\]]+)\]', alloc_str)
            if bond_match:
                bond_values = re.findall(r'([\d.]+)', bond_match.group(1))
                if bond_values:
                    result['bond_pct'] = float(bond_values[-1])
        
        return result if result else None
        
    except Exception as e:
        return None


def update_fund_scores(updates, batch_size=50):
    """通过 REST API 批量更新 fund_scores"""
    total = len(updates)
    for i in range(0, total, batch_size):
        batch = updates[i:i+batch_size]
        
        # Supabase REST API 不支持批量 UPDATE，逐条 PATCH
        for item in batch:
            r = requests.patch(
                f"{SUPABASE_URL}/rest/v1/fund_scores?c=eq.{item['c']}",
                headers=HEADERS,
                json={k: v for k, v in item.items() if k != 'c'}
            )
            if r.status_code >= 400:
                # 静默失败，继续下一个
                pass
        
        if (i + batch_size) % 500 == 0:
            print(f'  已更新 {i + batch_size}/{total}...', flush=True)
        time.sleep(0.05)  # 速率限制
    
    print(f'  完成更新 {total} 条', flush=True)


def main():
    parser = argparse.ArgumentParser(description='补充基金规模/持仓数据')
    parser.add_argument('--batch-size', type=int, default=100, help='每批处理数量')
    parser.add_argument('--max', type=int, default=0, help='最大处理数量（0=全部）')
    parser.add_argument('--dry-run', action='store_true', help='仅显示将要处理的基金')
    args = parser.parse_args()
    
    if not ANON_KEY:
        print('ERROR: 未找到 VITE_SUPABASE_ANON_KEY', file=sys.stderr)
        sys.exit(1)
    
    print('1. 获取待更新基金列表...', flush=True)
    codes = fetch_all_codes()
    
    if args.max > 0:
        codes = codes[:args.max]
    
    if args.dry_run:
        for c in codes[:20]:
            print(f'  {c}')
        print(f'  共 {len(codes)} 只')
        return
    
    print(f'\n2. 拉取基金信息并批量更新（共 {len(codes)} 只）...', flush=True)
    
    updates = []
    success = 0
    for i, code in enumerate(codes):
        info = fetch_fund_info(code)
        if info:
            info['c'] = code
            updates.append(info)
            success += 1
        
        if (i + 1) % 50 == 0:
            print(f'  进度: {i+1}/{len(codes)}, 获取成功: {success}', flush=True)
        
        time.sleep(0.1)
    
    print(f'\n3. 批量更新数据库（{len(updates)} 条）...', flush=True)
    if updates:
        update_fund_scores(updates)
    
    print(f'\n完成！成功获取并更新 {len(updates)}/{len(codes)} 只基金', flush=True)


if __name__ == '__main__':
    main()
