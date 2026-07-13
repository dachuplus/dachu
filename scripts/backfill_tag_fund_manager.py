#!/usr/bin/env python3
"""
backfill_tag_fund_manager.py — 为 fund_tag_funds 回填 fund_manager（基金经理）

背景：
  fund_tag_funds 存储「标签 → 关联基金」映射（来源东财 ZTJJ GetBKRelTopicFundNew）。
  其中大量是场内 ETF / LOF（如 561510 中药ETF华泰柏瑞），这些基金不在 fund_scores
  （fund_scores 仅收录场外 .OF 基金），导致前端标签弹窗 JOIN fund_scores 取不到经理，
  全部显示「经理：—」。

修复策略：
  1) 给 fund_tag_funds 增加 fund_manager 列（幂等）。
  2) 经理来源分两路：
     - 已在 fund_scores 的基金（约 3570 只，含 .OF 场外基金）→ 直接复用 fund_scores.fund_manager。
     - 其余（ETF/LOF 等，约 911 只）→ 抓取东财 fundf10 jbgk 页面解析基金经理（复用 fetch_fund_basic_info.parse_jbgk）。
  3) 按 fund_tag_funds.id 批量 UPDATE，写入 fund_manager。

数据源：
  - fund_scores（Supabase，经理已有）
  - https://fundf10.eastmoney.com/jbgk_{code}.html（东财基金概况，含 ETF 经理）

用法：
  SUPABASE_PAT=<PAT> python3 scripts/backfill_tag_fund_manager.py
"""
import os
import sys
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

# 复用仓库内已有的 fundf10 解析逻辑（避免重复实现）
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)
from fetch_fund_basic_info import parse_jbgk, fetch_one  # noqa: E402

PROJ_REF = 'tqhtegazxykkqfcpejky'
PAT = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN') or ''
MGMT_URL = f'https://api.supabase.com/v1/projects/{PROJ_REF}/database/query'
HEADERS = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}

MAX_RETRY = 4


def mgmt_query(sql, timeout=90):
    last_err = None
    for attempt in range(1, MAX_RETRY + 1):
        try:
            resp = requests.post(MGMT_URL, headers=HEADERS, json={'query': sql},
                                 timeout=timeout)
            if resp.status_code == 200:
                return resp.json()
            if 200 <= resp.status_code < 300:
                # DDL（CREATE/ALTER）常返回 201/204 无 body，视为成功
                try:
                    return resp.json()
                except Exception:
                    return {'command': 'ok', 'rows_affected': 0}
            # 400/其它：可能 SQL 问题，直接抛出由上层处理
            raise RuntimeError(f'HTTP {resp.status_code}: {resp.text[:300]}')
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRY:
                time.sleep(2 * attempt)
    raise last_err


def esc(s):
    if s is None:
        return 'NULL'
    return "'" + str(s).replace("'", "''") + "'"


def _rows(resp):
    """兼容 Management API 两种返回：list 直接是 rows，或 {'result':{'rows':[...]}}"""
    if isinstance(resp, list):
        return resp
    if isinstance(resp, dict):
        inner = resp.get('result')
        if isinstance(inner, dict):
            return inner.get('rows', [])
        if isinstance(inner, list):
            return inner
    return []


def main():
    if not PAT:
        print('[ERROR] 未设置 SUPABASE_PAT 环境变量', flush=True)
        sys.exit(1)

    # 1) 加列（幂等）
    print('[1/5] 确保 fund_tag_funds.fund_manager 列存在...', flush=True)
    mgmt_query('ALTER TABLE public.fund_tag_funds ADD COLUMN IF NOT EXISTS fund_manager text')
    print('       OK', flush=True)

    # 2) 读取 fund_tag_funds 全部行（id, fund_code）
    print('[2/5] 读取 fund_tag_funds 全部基金代码...', flush=True)
    rows = _rows(mgmt_query('SELECT id, fund_code FROM public.fund_tag_funds'))
    print(f'       共 {len(rows)} 行', flush=True)

    # 3) 从 fund_scores 复用经理（覆盖场外 .OF 基金）
    print('[3/5] 从 fund_scores 复用基金经理...', flush=True)
    sc = mgmt_query("SELECT c, fund_manager FROM public.fund_scores WHERE fund_manager IS NOT NULL AND fund_manager != ''")
    sc_rows = _rows(sc)
    scores_map = {}
    for r in sc_rows:
        c = (r.get('c') or '').replace('.OF', '')
        if c and r.get('fund_manager'):
            scores_map[c] = r['fund_manager']
    print(f'       fund_scores 可用经理 {len(scores_map)} 只', flush=True)

    # 4) 未被 fund_scores 覆盖的代码（ETF/LOF 等）→ fundf10 抓取
    codes_in_table = list({r['fund_code'] for r in rows if r.get('fund_code')})
    need = [c for c in codes_in_table if c not in scores_map]
    print(f'[4/5] 需 fundf10 回填的基金（ETF/LOF 等）：{len(need)} 只', flush=True)

    fundf10_map = {}
    if need:
        t0 = time.time()
        done = 0
        ok = 0
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(fetch_one, c): c for c in need}
            for fut in as_completed(futures):
                code, parsed, err = fut.result()
                done += 1
                if parsed and parsed.get('fund_manager'):
                    fundf10_map[code] = parsed['fund_manager']
                    ok += 1
                if done % 200 == 0:
                    print(f'       进度 {done}/{len(need)} | 成功 {ok} | {time.time()-t0:.0f}s', flush=True)
        print(f'       fundf10 成功解析经理 {ok}/{len(need)} 只', flush=True)

    # 合并经理来源
    manager_by_code = {}
    manager_by_code.update(scores_map)
    manager_by_code.update(fundf10_map)

    # 5) 按 id 批量 UPDATE
    print('[5/5] 批量写回 fund_tag_funds.fund_manager...', flush=True)
    updates = []
    for r in rows:
        mgr = manager_by_code.get(r.get('fund_code') or '', '') or ''
        updates.append((r['id'], mgr))

    BATCH = 1000
    total = 0
    for i in range(0, len(updates), BATCH):
        chunk = updates[i:i + BATCH]
        vals = ','.join(f"({rid}, {esc(mgr)})" for rid, mgr in chunk)
        sql = (
            'UPDATE public.fund_tag_funds AS t SET fund_manager = v.manager '
            f'FROM (VALUES {vals}) AS v(id, manager) '
            'WHERE t.id = v.id'
        )
        mgmt_query(sql)
        total += len(chunk)
        print(f'       已更新 {total}/{len(updates)}', flush=True)

    # 验证
    cnt = mgmt_query("SELECT count(*) AS c FROM public.fund_tag_funds WHERE fund_manager IS NOT NULL AND fund_manager != ''")
    cnt_val = _rows(cnt)[0].get('c')
    print(f'✅ 回填完成：fund_tag_funds 中已有经理 {cnt_val} 行', flush=True)


if __name__ == '__main__':
    main()
