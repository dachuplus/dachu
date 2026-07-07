#!/usr/bin/env python3
"""
立即回填 fund_scores 中 fund_manager 为空的基金（重点货币基金）。
- 从 Supabase 读取 fund_manager 为空的代码
- 并发抓取 fundf10 jbgk 解析基金经理
- 通过 Management API 批量 UPDATE（绕过 RLS，立即生效）
注意：每晚 CI 会 TRUNCATE 重建；fetch_fund_basic_info.py 已改为
对货币型每次重抓，故回填结果可被流水线保持。
"""
import os, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fund_basic_info import fetch_one
from import_via_rest import pg

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
import requests


def get_missing():
    codes = []
    offset = 0
    while True:
        url = (f'{SUPABASE_URL}/rest/v1/fund_scores'
               f'?select=c,t0&fund_manager=is.null&limit=1000&offset={offset}')
        r = requests.get(url, headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=60)
        if r.status_code != 200:
            print('  [WARN] 读取失败', r.status_code, r.text[:120]); break
        batch = r.json()
        if not batch:
            break
        for x in batch:
            codes.append(x['c'])
        offset += len(batch)
        if len(batch) < 1000:
            break
    return codes


def esc(s):
    return s.replace("'", "''")


def main():
    codes = get_missing()
    print(f'fund_manager 为空的基金: {len(codes)}', flush=True)
    if not codes:
        return

    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c.replace('.OF', '').replace('.of', '')): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            c = futs[fut]
            done += 1
            _, parsed, _ = fut.result()
            if parsed and parsed.get('fund_manager'):
                results[c] = parsed['fund_manager']
            if done % 500 == 0:
                print(f'  抓取进度 {done}/{len(codes)} 成功 {len(results)} ({time.time()-t0:.0f}s)', flush=True)

    print(f'✅ 解析到基金经理: {len(results)} / {len(codes)} ({time.time()-t0:.0f}s)', flush=True)

    # 批量 UPDATE（每批 200，避免单条超长）
    items = list(results.items())
    ok = 0
    for i in range(0, len(items), 200):
        chunk = items[i:i + 200]
        whens = ' '.join(
            f"WHEN c='{esc(k)}' THEN '{esc(v)}'" for k, v in chunk
        )
        sql = (f"UPDATE fund_scores SET fund_manager = CASE {whens} "
               f"ELSE fund_manager END WHERE c IN ({','.join(repr(k) for k, _ in chunk)})")
        try:
            pg(sql)
            ok += len(chunk)
        except Exception as e:
            print(f'  [ERR] 批次 {i} 失败: {str(e)[:120]}', flush=True)
    print(f'✅ 已更新基金经理: {ok} 只', flush=True)


if __name__ == '__main__':
    main()
