#!/usr/bin/env python3
"""
fix_fund_managers.py — 修复错误的 fund_manager 数据（基金简称→正确经理名）

问题：之前回填脚本从 pingzhongdata/{code}.js 取了 fS_name（实际=基金简称），
     导致约 2012 条 fund_manager 存的是基金名而非经理名。

修复：从 fundf10 jbgk 页面正确解析「基金经理人」字段，覆盖所有错误记录。
"""
import re
import requests
import time
import sys
import os

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)

# ── 读取 token ──
env_path = os.path.join(PROJECT_DIR, '.env.local')
s = open(env_path).read()
PAT = re.search(r'SUPABASE_PAT=([^\n]+)', s).group(1).strip().strip('"').strip("'")
MGT_URL = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'
MGT_HDR = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}


def q(sql):
    r = requests.post(MGT_URL, headers=MGT_HDR, json={'query': sql}, timeout=60)
    if r.status_code not in (200, 201):
        print(f'  SQL ERR {r.status_code}: {r.text[:200]}', file=sys.stderr)
        return None
    return r.json()


# ── jbgk 解析（与 fetch_fund_basic_info.py 一致） ──
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'


def extract_td(html, label):
    pat = re.escape(label) + r'</th>\s*<td[^>]*>(.*?)</td>'
    m = re.search(pat, html, re.DOTALL)
    return m.group(1) if m else None


def clean_text(s):
    if not s:
        return None
    s = re.sub(r'<[^>]+>', '', s).strip()
    return s if s else None


def parse_managers(s):
    if not s:
        return None
    names = re.findall(r'>([^<]+)</a>', s)
    if names:
        return '、'.join(n.strip() for n in names if n.strip())
    return clean_text(s)


def fetch_manager_jbgk(code6):
    """从 jbgk 页面正确解析基金经理"""
    url = f'https://fundf10.eastmoney.com/jbgk_{code6}.html'
    try:
        resp = requests.get(url, headers={'User-Agent': UA}, timeout=15)
        if resp.status_code != 200:
            return None, f'HTTP {resp.status_code}'
        resp.encoding = 'utf-8'
        html = resp.text
        if '基金类型' not in html:
            resp.encoding = 'gbk'
            html = resp.text
        mgr_html = extract_td(html, '基金经理人')
        if not mgr_html:
            # 备选：页面顶部 "基金经理：金梓才"
            m2 = re.search(r'基金经理[：:]\s*<a[^>]*>([^<]+)</a>', html)
            if m2:
                return m2.group(1).strip(), None
            return None, '无基金经理人字段'
        mgr = parse_managers(mgr_html)
        return mgr, None
    except Exception as e:
        return None, str(e)[:80]


def main():
    # 1) 查找所有"看起来错误"的基金代码（含 基金类型后缀）
    print('=== Step 1: 查找所有错误的 fund_manager ===')
    wrong_rows = q("""
        SELECT c FROM fund_scores
        WHERE fund_manager ~ '(混合|债券|股票|指数|QDII|FOF|货币|LOF|ETF联接)'
    """)
    if not wrong_rows:
        print('  无错误记录，无需修复')
        return
    wrong_codes = [r['c'].replace('.OF', '') for r in wrong_rows]
    print(f'  需要修复: {len(wrong_codes)} 只')

    # 2) 批量抓取
    print(f'\n=== Step 2: 从 jbgk 抓取 {len(wrong_codes)} 只正确的基金经理 ===')
    results = {}
    errors = []
    t0 = time.time()

    for i, code6 in enumerate(wrong_codes):
        mgr, err = fetch_manager_jbgk(code6)
        if mgr:
            results[code6] = mgr
        else:
            errors.append((code6, err))

        if (i + 1) % 100 == 0 or i == len(wrong_codes) - 1:
            elapsed = time.time() - t0
            print(f'  进度 {i+1}/{len(wrong_codes)} | 成功 {len(results)} | 失败 {len(errors)} | {elapsed:.0f}s')

        if (i + 1) % 50 == 0:
            time.sleep(0.3)

    print(f'\n  抓取完成: 成功={len(results)}, 失败={len(errors)}')
    if errors:
        print(f'  失败样本: {errors[:5]}')

    if not results:
        print('  无成功结果，终止')
        return

    # 3) 分批 UPDATE
    print(f'\n=== Step 3: 写回数据库 ({len(results)} 条) ===')
    BATCH_SIZE = 200
    code_list = list(results.items())
    total_batches = (len(code_list) + BATCH_SIZE - 1) // BATCH_SIZE

    for bi in range(total_batches):
        batch = code_list[bi * BATCH_SIZE:(bi + 1) * BATCH_SIZE]
        case_parts = []
        codes_in = []
        for c6, mgr in batch:
            c_full = c6 + '.OF'
            safe_mgr = mgr.replace("'", "''")
            case_parts.append("WHEN c='{}' THEN '{}'".format(c_full, safe_mgr))
            codes_in.append(c_full)

        sql = ("UPDATE fund_scores SET fund_manager = CASE {} END "
               "WHERE c IN ({})").format(
                   ' '.join(case_parts),
                   ','.join("'{}'".format(c) for c in codes_in)
               )
        r = requests.post(MGT_URL, headers=MGT_HDR, json={'query': sql}, timeout=60)
        status = '✅' if r.status_code in (200, 201) else '❌{}'.format(r.status_code)
        print(f'  批次 {bi+1}/{total_batches} ({len(batch)}条) {status}')

    # 4) 验证
    print('\n=== Step 4: 最终验证 ===')
    check = q("""
        SELECT
          count(*) AS total,
          count(CASE WHEN fund_manager ~ '(混合|债券|股票|指数|QDII|FOF|货币|LOF|ETF联接)' THEN 1 END) AS still_wrong,
          count(CASE WHEN fund_manager IS NULL THEN 1 END) AS null_cnt
        FROM fund_scores
    """)
    if check:
        row = check[0]
        print(f'  总数={row["total"]}  仍错={row["still_wrong"]}  NULL={row["null_cnt"]}')
        if row['still_wrong'] == 0:
            print('  ✅ 全部修复完成！')
        else:
            print('  ⚠️ 仍有错误，需排查')

    sample = q("SELECT c,n,fund_manager FROM fund_scores ORDER BY random() LIMIT 10")
    print('\n  随机抽样:')
    for r in sample:
        print(f'    {r["c"]:<12} {r["n"]:<24} manager={r["fund_manager"]}')

    print(f'\n总耗时: {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
