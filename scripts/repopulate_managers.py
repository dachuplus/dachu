#!/usr/bin/env python3
"""
安全回填基金经理/管理人：直接 UPDATE fund_scores 与 fund_combined，不做 TRUNCATE。

背景：最近一次夜跑 fetch_fund_basic_info 步骤超时（continue-on-error），
fund_basic_info.ndjson 未落盘 → import_via_rest TRUNCATE 重建后 fund_manager 全空。

本脚本：
- 读取 fund_scores 中 fund_manager 为 null 的代码（全量 ~19k）
- 读取 fund_combined 中 t0='货币型' 的代码（货币经理进 fund_combined）
- 并发抓 fundf10 jbgk，解析基金经理/管理人
- 增量批量 UPDATE（CASE WHEN）+ 断点续传（checkpoint）
可重复运行，中断后从上次进度继续。
"""
import os
import sys
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_fund_basic_info import fetch_one

# 本地实现 pg()，避免 import import_via_rest 触发其模块级 TRUNCATE+重建副作用
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'


def pg(sql, timeout=180):
    """通过 Management API 执行 SQL（用 curl 避免 Cloudflare 拦截）"""
    import subprocess
    token = os.environ.get('SUPABASE_MGMT_TOKEN')
    if not token:
        raise RuntimeError('缺少 SUPABASE_MGMT_TOKEN 环境变量')
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {token}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=timeout + 10
    )
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:100]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        resp = json.loads(t)
    except json.JSONDecodeError:
        raise RuntimeError(f'非JSON响应: {t[:200]}')
    if isinstance(resp, dict) and resp.get('message'):
        raise RuntimeError(resp['message'][:200])
    return resp

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
CHECKPOINT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.mgr_checkpoint.json')


def get_null_codes():
    out = []
    offset = 0
    while True:
        url = (f'{SUPABASE_URL}/rest/v1/fund_scores'
               f'?select=c&fund_manager=is.null&limit=1000&offset={offset}')
        r = requests.get(url, headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=60)
        if r.status_code != 200:
            print('  [WARN] 读 null 代码失败', r.status_code)
            break
        b = r.json()
        if not b:
            break
        for x in b:
            c = (x.get('c') or '').replace('.OF', '')
            if c:
                out.append(c)
        offset += len(b)
        if len(b) < 1000:
            break
    return out


def get_currency_codes():
    out = []
    offset = 0
    while True:
        url = (f'{SUPABASE_URL}/rest/v1/fund_combined'
               f'?select=c&t0=eq.%E8%B4%A7%E5%B8%81%E5%9E%8B&limit=1000&offset={offset}')
        r = requests.get(url, headers={'apikey': ANON, 'Authorization': f'Bearer {ANON}'}, timeout=60)
        if r.status_code != 200:
            print('  [WARN] 读货币代码失败', r.status_code)
            break
        b = r.json()
        if not b:
            break
        for x in b:
            c = (x.get('c') or '')
            if c:
                out.append(c)
        offset += len(b)
        if len(b) < 1000:
            break
    return out


def esc(s):
    return (s or '').replace("'", "''")


def batch_update_scores(items):
    if not items:
        return
    whens_fm = ' '.join(f"WHEN c='{esc(cof)}' THEN '{esc(fm)}'" for cof, fm, co in items if fm)
    whens_co = ' '.join(f"WHEN c='{esc(cof)}' THEN '{esc(co)}'" for cof, fm, co in items if co)
    parts = []
    if whens_fm:
        parts.append(f"fund_manager = CASE {whens_fm} ELSE fund_manager END")
    if whens_co:
        parts.append(f"company = CASE {whens_co} ELSE company END")
    if parts:
        codes = ','.join(f"'{esc(cof)}'" for cof, _, _ in items)
        sql = f"UPDATE fund_scores SET {', '.join(parts)} WHERE c IN ({codes})"
        try:
            pg(sql)
        except Exception as e:
            print('  [ERR] scores batch:', str(e)[:160], flush=True)


def batch_update_combined(items):
    if not items:
        return
    whens_fm = ' '.join(f"WHEN c='{esc(c)}' THEN '{esc(fm)}'" for c, fm, co in items if fm)
    whens_co = ' '.join(f"WHEN c='{esc(c)}' THEN '{esc(co)}'" for c, fm, co in items if co)
    parts = []
    if whens_fm:
        parts.append(f"fund_manager = CASE {whens_fm} ELSE fund_manager END")
    if whens_co:
        parts.append(f"company = CASE {whens_co} ELSE company END")
    if parts:
        codes = ','.join(f"'{esc(c)}'" for c, _, _ in items)
        sql = f"UPDATE fund_combined SET {', '.join(parts)} WHERE c IN ({codes})"
        try:
            pg(sql)
        except Exception as e:
            print('  [ERR] combined batch:', str(e)[:160], flush=True)


def main():
    try:
        pg("ALTER TABLE fund_combined ADD COLUMN IF NOT EXISTS fund_manager text")
        print('  ✓ fund_combined.fund_manager 就绪', flush=True)
    except Exception as e:
        print('  [ERR] ALTER combined:', str(e)[:160], flush=True)

    done = set()
    if os.path.exists(CHECKPOINT):
        try:
            with open(CHECKPOINT) as f:
                done = set(json.load(f))
        except Exception:
            done = set()
    print(f'断点续传：已完成 {len(done)} 只', flush=True)

    null_codes = get_null_codes()
    print(f'fund_scores 缺失经理: {len(null_codes)} 只', flush=True)
    currency = get_currency_codes()
    print(f'fund_combined 货币型: {len(currency)} 只', flush=True)

    todo = [c for c in null_codes if c not in done]
    print(f'本次待抓(fund_scores): {len(todo)}', flush=True)

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one, c): c for c in todo}
        done_count = 0
        score_items = []
        comb_items = []
        for fut in as_completed(futs):
            c = futs[fut]
            _, parsed, _ = fut.result()
            done_count += 1
            done.add(c)
            if parsed:
                fm = parsed.get('fund_manager')
                co = parsed.get('company')
                if fm or co:
                    score_items.append((f'{c}.OF', fm, co))
                    if c in set(currency):
                        comb_items.append((c, fm, co))
            if done_count % 200 == 0:
                batch_update_scores(score_items)
                score_items = []
                if comb_items:
                    batch_update_combined(comb_items)
                    comb_items = []
                with open(CHECKPOINT, 'w') as f:
                    json.dump(list(done), f)
                print(f'  进度 {done_count}/{len(todo)} ({time.time() - t0:.0f}s)', flush=True)
        batch_update_scores(score_items)
        if comb_items:
            batch_update_combined(comb_items)
        with open(CHECKPOINT, 'w') as f:
            json.dump(list(done), f)

    # 货币型单独补（货币不在 fund_scores，故上面可能未覆盖）
    todo_cur = [c for c in currency if c not in done]
    print(f'货币型待补(fund_combined): {len(todo_cur)}', flush=True)
    if todo_cur:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = {ex.submit(fetch_one, c): c for c in todo_cur}
            items = []
            n = 0
            for fut in as_completed(futs):
                c = futs[fut]
                _, parsed, _ = fut.result()
                done.add(c)
                n += 1
                if parsed and (parsed.get('fund_manager') or parsed.get('company')):
                    items.append((c, parsed.get('fund_manager'), parsed.get('company')))
                if len(items) >= 200:
                    batch_update_combined(items)
                    items = []
                if n % 200 == 0:
                    with open(CHECKPOINT, 'w') as f:
                        json.dump(list(done), f)
            if items:
                batch_update_combined(items)
            with open(CHECKPOINT, 'w') as f:
                json.dump(list(done), f)

    print('🎉 基金经理回填完成', flush=True)


if __name__ == '__main__':
    main()
