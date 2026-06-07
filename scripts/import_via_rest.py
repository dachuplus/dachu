#!/usr/bin/env python3
"""
通过 Supabase REST API 批量导入基金数据（anon key，RLS 允许 INSERT）。
比 Management API 逐条 INSERT 快很多。
"""
import json, time, sys, os, subprocess

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY    = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
MGMT_TOKEN  = os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN（Supabase Personal Access Token）')
MGMT_API    = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

BATCH = 1000   # REST API 单次最多 1000 条
COLS = [
    'c','n','t0','t1','t2','t6','a','hp',
    'ytd','r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y',
    'nav','date',
    'k0w','k1m','k3m','k6m','k1','k2','k3','k5','k7','k10',
    'dd1y','dd2y','dd3y','dd5y','sr1y','sr2y','sr3y','sr5y',
    'return_all',
]

# ── 工具函数 ──────────────────────────────────────────────────────────────
def pg(sql):
    """通过 Management API 执行 SQL，用于 TRUNCATE / meta 更新（用 curl 避免 Cloudflare 拦截）"""
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=120
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

def rest_post(path, data, method='POST', params='', prefer=''):
    """调用 Supabase REST API（用 curl 避免 Cloudflare 拦截）"""
    url = f'{SUPABASE_URL}{path}?{params}'
    payload = json.dumps(data, ensure_ascii=False)
    headers = [
        '-H', f'apikey: {ANON_KEY}',
        '-H', f'Authorization: Bearer {ANON_KEY}',
        '-H', 'Content-Type: application/json',
        '-H', 'Accept: application/json',
    ]
    if prefer:
        headers.extend(['-H', f'Prefer: {prefer}'])
    cmd = ['curl', '-s', '-X', method, url] + headers + ['-d', payload]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:100]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        # 某些成功响应可能不是 JSON
        return []

def esc_null(v):
    if v is None:
        return None   # REST API 直接传 null
    try:
        f = float(v)
        return None if f == 0 else round(f, 4)
    except Exception:
        return None

def row_to_rest(r):
    """把 NDJSON 的一行转成 REST API 需要的 dict"""
    d = {}
    # 字符串字段：原样传递，空值传 None（REST API 会存 NULL）
    for col in ('c','n','t0','t1','t2','t6','hp','date'):
        v = r.get(col)
        d[col] = v if v and str(v).strip() else None
    # 布尔字段
    d['a'] = int(r.get('a', 0) or 0)
    # 数值字段：用 esc_null（0→None，让 DB 存 NULL）
    for col in ('ytd','r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y',
                'nav',
                'k0w','k1m','k3m','k6m','k1','k2','k3','k5','k7','k10',
                'dd1y','dd2y','dd3y','dd5y',
                'sr1y','sr2y','sr3y','sr5y',
                'return_all'):
        v = r.get(col)
        d[col] = esc_null(v)
    return d

# ── 主流程 ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
print('开始导入 fund_scores（REST API 批量模式）', flush=True)

# 1. 加载基金数据
t0 = time.time()
funds = []
with open(os.path.join(SCRIPT_DIR, 'funds_output.ndjson'), 'r') as f:
    for line in f:
        line = line.strip()
        if line:
            funds.append(json.loads(line))
print(f'  ✓ 加载 {len(funds)} 只基金 ({time.time()-t0:.1f}s)', flush=True)

# 2. 合并风险指标
risk_path = os.path.join(SCRIPT_DIR, 'risk_indicators.ndjson')
if os.path.exists(risk_path):
    t0 = time.time()
    risk_map = {}
    with open(risk_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                c = r.get('c', '')
                if c:
                    risk_map[c] = r
    merged = 0
    for fund in funds:
        c = fund.get('c', '')
        if c in risk_map:
            r = risk_map[c]
            for k in ['dd1y','dd2y','dd3y','dd5y','sr1y','sr2y','sr3y','sr5y','return_all']:
                fund[k] = r.get(k)
            merged += 1
    print(f'  ✓ 合并风险指标 {merged}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)
else:
    print('  ⚠ 无风险指标文件，跳过', flush=True)

# 2b. 合并成立以来收益（从 rankhandler API 批量抓取，比逐基金爬取快）
return_all_path = os.path.join(SCRIPT_DIR, 'return_all.ndjson')
if os.path.exists(return_all_path):
    t0 = time.time()
    ra_map = {}
    with open(return_all_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                c = r.get('c', '')
                if c:
                    ra_map[c] = r.get('return_all')
    merged = 0
    for fund in funds:
        c = fund.get('c', '')
        if c in ra_map and ra_map[c] is not None:
            fund['return_all'] = ra_map[c]
            merged += 1
    print(f'  ✓ 合并成立以来收益 {merged}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)

# 3. 重新计算靠谱分 v5
t0 = time.time()
W_RET, W_DD, W_SR = 0.60, 0.30, 0.10
periods = [
    ('k0w','r0w',None,None),('k1m','r1m',None,None),
    ('k3m','r3m',None,None),('k6m','r6m',None,None),
    ('k1','r1y','dd1y','sr1y'),('k2','r2y','dd2y','sr2y'),
    ('k3','r3y','dd3y','sr3y'),('k5','r5y','dd5y','sr5y'),
]
for pk, rk, dk, sk in periods:
    valid = [(i, funds[i]) for i in range(len(funds))]
    vn = len(valid)
    # 收益排位
    ret_ranked = sorted(valid, key=lambda x: x[1].get(rk,0) or 0, reverse=True)
    ret_pct = {}
    for rank, (idx, _) in enumerate(ret_ranked):
        ret_pct[idx] = (1 - rank/(vn-1))*100 if vn > 1 else 50.0
    # 回撤排位
    dd_pct = {}
    if dk:
        dd_valid = [(i, funds[i]) for i in range(len(funds)) if funds[i].get(dk) is not None]
        dvn = len(dd_valid)
        dd_ranked = sorted(dd_valid, key=lambda x: x[1].get(dk,0) or 0, reverse=True)
        for rank, (idx, _) in enumerate(dd_ranked):
            dd_pct[idx] = (1 - rank/(dvn-1))*100 if dvn > 1 else 50.0
    # 夏普排位
    sr_pct = {}
    if sk:
        sr_valid = [(i, funds[i]) for i in range(len(funds)) if funds[i].get(sk) is not None]
        svn = len(sr_valid)
        sr_ranked = sorted(sr_valid, key=lambda x: x[1].get(sk,0) or 0, reverse=True)
        for rank, (idx, _) in enumerate(sr_ranked):
            sr_pct[idx] = (1 - rank/(svn-1))*100 if svn > 1 else 50.0
    # 合成靠谱分
    for idx in range(len(funds)):
        rp = ret_pct.get(idx)
        if rp is None:
            continue
        dp = dd_pct.get(idx)
        sp = sr_pct.get(idx)
        if dp is not None and sp is not None:
            score = round(W_RET*rp + W_DD*dp + W_SR*sp, 4)
        else:
            score = round(rp, 4)
        funds[idx][pk] = score

scored = sum(1 for r in funds if r.get('k3',0) > 0)
print(f'  ✓ 靠谱分计算完成 scored={scored}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)

# 4. 通过 REST API 批量导入
# 先清空旧数据
t0 = time.time()
print('  清空旧数据...', flush=True)
pg('TRUNCATE TABLE fund_scores')
print(f'  ✓ 已清空', flush=True)

# 转换为 REST 格式并分批 POST
imported = 0

for i in range(0, len(funds), BATCH):
    batch = funds[i:i+BATCH]
    rows = [row_to_rest(r) for r in batch]
    try:
        rest_post('/rest/v1/fund_scores', rows, prefer='return=minimal')
        imported += len(batch)
        if (i // BATCH) % 5 == 0 or i + BATCH >= len(funds):
            print(f'  导入进度: {imported}/{len(funds)} ({imported*100//len(funds)}%)', flush=True)
    except Exception as e:
        print(f'  ✗ 批次 {i}-{i+len(batch)} 失败: {e}', flush=True)
        # 降级：逐条重试
        for j, row in enumerate(rows):
            try:
                rest_post('/rest/v1/fund_scores', [row], prefer='return=minimal')
                imported += 1
            except Exception as e2:
                print(f'    ✗ 记录 {batch[j].get("c","?")} 失败: {str(e2)[:100]}', flush=True)

print(f'  ✓ 导入完成 {imported}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)

# 5. 写入 meta
nav_date = funds[0].get('date','') if funds else ''
pg('TRUNCATE TABLE fund_scores_meta')
pg(f"INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) "
    f"VALUES (NOW()::text, {len(funds)}, {scored}, '{nav_date}')")
print(f'  ✓ meta 已更新 (total={len(funds)}, scored={scored}, date={nav_date})', flush=True)

# 6. 验证
result = pg('SELECT count(*) as cnt FROM fund_scores')
print(f'  验证: fund_scores 有 {result[0]["cnt"]} 条', flush=True)
result = pg("SELECT t0, count(*) as cnt FROM fund_scores WHERE t0 IS NOT NULL GROUP BY t0 ORDER BY cnt DESC")
print('  t0 分布:', flush=True)
for row in result:
    print(f'    {row["t0"]}: {row["cnt"]} 只', flush=True)

print('\n✅ 全部完成！', flush=True)
