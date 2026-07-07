#!/usr/bin/env python3
"""
立即补全货币基金(货币型)的基金经理/管理人到 fund_scores 与 fund_combined。

根因：fetch_and_import_funds.py 仅抓取 gp/zq/hh/fof/qdii（不含 hb 货币），
supplement_money_qdii_scores.py 只 UPDATE 已存在的货币行（货币从未被 INSERT），
因此货币型基金从不在 fund_scores；fund_combined 虽有货币但无 fund_manager 列。

本脚本（一次性 + 可被 CI 复用）：
- 从 fund_combined 读取 t0='货币型' 的代码+名称
- 并发抓 fundf10 jbgk 解析基金经理/管理人
- ALTER fund_combined 增加 fund_manager/company 列(若不存在)
- UPDATE fund_combined
- 对 fund_scores：先查已存在的货币代码，已存在则 UPDATE（仅填空），不存在则 INSERT
"""
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fund_basic_info import fetch_one
from import_via_rest import pg

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'


def esc(s):
    return (s or '').replace("'", "''")


def get_currency_from_combined():
    out = {}
    offset = 0
    while True:
        url = (f'{SUPABASE_URL}/rest/v1/fund_combined'
               f'?select=c,n&t0=eq.%E8%B4%A7%E5%B8%81%E5%9E%8B&limit=1000&offset={offset}')
        r = requests.get(url, headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=60)
        if r.status_code != 200:
            print('  [WARN] 读 fund_combined 失败', r.status_code, r.text[:120])
            break
        batch = r.json()
        if not batch:
            break
        for x in batch:
            out[x['c']] = x.get('n')
        offset += len(batch)
        if len(batch) < 1000:
            break
    return out


def get_existing_in_scores(codes_of):
    """返回已在 fund_scores 中的代码集合(.OF 后缀)"""
    existing = set()
    for i in range(0, len(codes_of), 500):
        chunk = codes_of[i:i + 500]
        codes_str = ','.join(f"'{c}'" for c in chunk)
        url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=c&c=in.({codes_str})'
        r = requests.get(url, headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=60)
        if r.status_code == 200:
            for x in r.json():
                existing.add(x['c'])
        else:
            print('  [WARN] 查已有货币失败', r.status_code)
    return existing


def main():
    codes = get_currency_from_combined()
    print(f'货币型基金(来自 fund_combined): {len(codes)}', flush=True)
    if not codes:
        return

    # ALTER fund_combined 增加 manager/company 列
    for col in ('fund_manager', 'company'):
        try:
            pg(f"ALTER TABLE fund_combined ADD COLUMN IF NOT EXISTS {col} text")
            print(f'  ✓ fund_combined.{col} 就绪', flush=True)
        except Exception as e:
            print(f'  [ERR] ALTER {col}: {str(e)[:160]}', flush=True)

    # 并发抓 jbgk
    results = {}
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c): c for c in codes}
        done = 0
        for fut in as_completed(futs):
            c = futs[fut]
            done += 1
            _, parsed, _ = fut.result()
            if parsed:
                fm = parsed.get('fund_manager')
                co = parsed.get('company')
                if fm or co:
                    results[c] = (fm, co)
            if done % 200 == 0:
                print(f'  抓取进度 {done}/{len(codes)} 成功 {len(results)} ({time.time() - t0:.0f}s)', flush=True)
    print(f'✅ 解析到经理/管理人: {len(results)}/{len(codes)} ({time.time() - t0:.0f}s)', flush=True)

    # ── UPDATE fund_combined ──
    ok_c = 0
    items = list(results.items())
    for i in range(0, len(items), 200):
        chunk = items[i:i + 200]
        parts = []
        whens_fm = ' '.join(f"WHEN c='{esc(k)}' THEN '{esc(v[0])}'" for k, v in chunk if v[0])
        whens_co = ' '.join(f"WHEN c='{esc(k)}' THEN '{esc(v[1])}'" for k, v in chunk if v[1])
        if whens_fm:
            parts.append(f"fund_manager = CASE {whens_fm} ELSE fund_manager END")
        if whens_co:
            parts.append(f"company = CASE {whens_co} ELSE company END")
        if parts:
            sql = (f"UPDATE fund_combined SET {', '.join(parts)} "
                   f"WHERE c IN ({','.join(repr(k) for k, _ in chunk)})")
            try:
                pg(sql)
                ok_c += len(chunk)
            except Exception as e:
                print(f'  [ERR] fund_combined batch {i}: {str(e)[:160]}', flush=True)
    print(f'✅ fund_combined 更新: {ok_c} 只', flush=True)

    # ── fund_scores: 区分已存在/新增 ──
    codes_of = {f'{k}.OF': k for k in codes}
    existing = get_existing_in_scores(list(codes_of.keys()))
    print(f'  fund_scores 中已存在的货币: {len(existing)}', flush=True)

    # UPDATE 已存在的（仅填空）
    upd_items = [(cof, codes_of[cof]) for cof in existing if codes_of[cof] in results]
    for i in range(0, len(upd_items), 200):
        chunk = upd_items[i:i + 200]
        parts = []
        whens_fm = ' '.join(f"WHEN c='{esc(cof)}' THEN '{esc(results[k][0])}'" for cof, k in chunk if results[k][0])
        whens_co = ' '.join(f"WHEN c='{esc(cof)}' THEN '{esc(results[k][1])}'" for cof, k in chunk if results[k][1])
        if whens_fm:
            parts.append(f"fund_manager = CASE {whens_fm} ELSE fund_manager END")
        if whens_co:
            parts.append(f"company = CASE {whens_co} ELSE company END")
        if parts:
            sql = (f"UPDATE fund_scores SET {', '.join(parts)} "
                   f"WHERE c IN ({','.join(repr(cof) for cof, _ in chunk)})")
            try:
                pg(sql)
            except Exception as e:
                print(f'  [ERR] scores update batch: {str(e)[:160]}', flush=True)
    print(f'✅ fund_scores 已存在货币 UPDATE: {len(upd_items)} 只', flush=True)

    # INSERT 新增的
    new_items = [(cof, codes_of[cof]) for cof in codes_of if cof not in existing and codes_of[cof] in results]
    ins_ok = 0
    for i in range(0, len(new_items), 200):
        chunk = new_items[i:i + 200]
        vals = []
        for cof, k in chunk:
            fm, co = results[k]
            name = codes.get(k) or ''
            vals.append(f"('{esc(cof)}','{esc(name)}','货币型','货币基金','{esc(fm)}','{esc(co)}')")
        sql = (f"INSERT INTO fund_scores (c,n,t0,t1,fund_manager,company) VALUES {','.join(vals)}")
        try:
            pg(sql)
            ins_ok += len(chunk)
        except Exception as e:
            print(f'  [ERR] scores insert batch: {str(e)[:200]}', flush=True)
    print(f'✅ fund_scores 新增货币 INSERT: {ins_ok} 只', flush=True)

    print('🎉 货币基金经理补全完成', flush=True)


if __name__ == '__main__':
    main()
