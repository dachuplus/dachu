#!/usr/bin/env python3
"""
通过 Supabase REST API 批量导入基金数据（anon key，RLS 允许 INSERT）。
比 Management API 逐条 INSERT 快很多。

=====================================================================
  ⚠️ 数据模型规则护栏（详见 docs/data-model-rules.md）
  fund_scores 的评分（k0w/k1m/k3m/k6m/k1/k2/k3/k5/k_all/score_grade）
  必须由本脚本基于【基础数据】独立计算：
      · 输入仅来自 funds_output.ndjson / risk_indicators.ndjson /
        return_all.ndjson / fund_details.ndjson / fund_basic_info.ndjson
        （即阶段收益 r* / 回撤 dd* / 夏普 sr* / 基金经理等）
      · 日历对齐全市场百分位排名（收益50% + 回撤25% + 夏普25%）+ v7 加权
  【禁止】读取 fund_quarterly_scores 的任何列来计算 fund_scores 评分。
  fund_scores 与 fund_quarterly_scores 是两套独立引擎，不得耦合。
  （fund_combined 的评分才应基于 fund_quarterly_scores，由
   sync_fund_combined_scores.py 负责。）
=====================================================================
"""
import json, time, sys, os, subprocess, argparse

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY    = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
MGMT_TOKEN  = os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN（Supabase Personal Access Token）')
MGMT_API    = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

BATCH = 500    # SQL INSERT 批量大小（从1000降到500，避免payload过大）
# fund_scores 表实际列（完整版：评分 + 分类 + 收益 + 回撤 + 夏普 + 详情）
FUND_SCORES_COLS = [
    'c','n','t0','t1','t1_tt',
    'sg','daily_change',
    # 基本信息
    'company','fund_scale','manage_fee','fund_manager',
    'share_scale','custody_fee','sale_fee','found_date',
    # 阶段收益
    'ytd','r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y','r7y','r10y','return_all',
    # 阶段回撤
    'dd1y','dd2y','dd3y','dd5y',
    # 阶段夏普
    'sr1y','sr2y','sr3y','sr5y',
    # 评分
    'k0w','k1m','k3m','k6m','k1','k2','k3','k5',
    'k_all','score_grade',
]

# ── 工具函数 ──────────────────────────────────────────────────────────────
def pg(sql, timeout=180):
    """通过 Management API 执行 SQL，用于 TRUNCATE / meta 更新 / 批量 INSERT（用 curl 避免 Cloudflare 拦截）"""
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
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
    """把 NDJSON 的一行转成 REST API 需要的 dict（fund_scores 全部列）"""
    d = {}
    # 字符串字段
    for col in ('c','n','t0','t1','t1_tt','score_grade','company','manage_fee','fund_manager','found_date'):
        v = r.get(col)
        d[col] = v if v and str(v).strip() else None
    # 数值字段：申购状态
    for col in ('sg',):
        v = r.get(col)
        if v is not None and str(v).strip() not in ('', '0'):
            try: d[col] = int(float(v))
            except: d[col] = None
        else:
            d[col] = None
    # 数值字段：评分相关
    for col in ('k0w','k1m','k3m','k6m','k1','k2','k3','k5','k_all','daily_change'):
        v = r.get(col)
        d[col] = esc_null(v)
    # 数值字段：收益
    for col in ('ytd','r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y','r7y','r10y','return_all'):
        v = r.get(col)
        d[col] = esc_null(v)
    # 数值字段：回撤
    for col in ('dd1y','dd2y','dd3y','dd5y'):
        v = r.get(col)
        d[col] = esc_null(v)
    # 数值字段：夏普
    for col in ('sr1y','sr2y','sr3y','sr5y'):
        v = r.get(col)
        d[col] = esc_null(v)
    # 浮点数：规模 / 费率 / 份额
    for col in ('fund_scale','share_scale','custody_fee','sale_fee'):
        v = r.get(col)
        if v is not None:
            try: d[col] = float(v)
            except: d[col] = None
        else:
            d[col] = None
    return d

# ── 主流程 ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# 命令行参数
parser = argparse.ArgumentParser(description='合并风险指标 + 重算靠谱分 + 导入 Supabase')
parser.add_argument('--staging', action='store_true',
                    help='写入临时表 fund_scores_staging（不触碰生产 fund_scores），'
                         '并额外种子货币型 + 合并货币基金阶段收益')
args = parser.parse_args()
STAGING = args.staging
TARGET_TABLE = 'fund_scores_staging' if STAGING else 'fund_scores'

print(f'开始导入 {"[STAGING] " if STAGING else ""}fund_scores（REST API 批量模式）', flush=True)

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
            for k in ['dd1y','dd2y','dd3y','dd5y','sr1y','sr2y','sr3y','sr5y','return_all','fund_manager']:
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

# 2c. 合并基金详情（公司名/规模/费率）
details_path = os.path.join(SCRIPT_DIR, 'fund_details.ndjson')
if os.path.exists(details_path):
    t0 = time.time()
    details_map = {}
    with open(details_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                d = json.loads(line)
                c = d.get('c', '')
                if c:
                    details_map[c] = d
    merged = 0
    for fund in funds:
        c = fund.get('c', '').replace('.OF', '')
        if c in details_map:
            d = details_map[c]
            for k in ['company', 'fund_scale', 'manage_fee']:
                v = d.get(k)
                if v is not None and not fund.get(k):
                    fund[k] = v
            merged += 1
    print(f'  ✓ 合并基金详情 {merged}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)
else:
    print('  ⚠ 无基金详情文件，跳过', flush=True)

# 2c2. 合并基金基本概况（fundf10 jbgk 页面：基金经理/管理人/分类/份额/费率/成立日期）
basic_info_path = os.path.join(SCRIPT_DIR, 'fund_basic_info.ndjson')
if os.path.exists(basic_info_path):
    t0 = time.time()
    basic_map = {}
    with open(basic_info_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                b = json.loads(line)
                c = b.get('c', '').replace('.OF', '')
                if c:
                    basic_map[c] = b
    # 仅填补 null/空值（不覆盖已有好数据）：管理人/分类/规模/费率
    # 注：t0/t1 分类当前已 100% 完整，且 FundGuideapi 为既有权威来源，不覆盖
    fill_if_empty = ['company', 't0', 't1', 'fund_scale', 'manage_fee']
    # 始终取 jbgk（天天基金官方档案，数据最权威且一致）：基金经理 + 4 个新增列
    # 基金经理以 jbgk 为准（覆盖风险指标里不可靠的净值的基金经理提取）
    always_take = ['fund_manager', 'share_scale', 'custody_fee', 'sale_fee', 'found_date']
    merged = 0
    for fund in funds:
        c = fund.get('c', '').replace('.OF', '')
        if c in basic_map:
            b = basic_map[c]
            changed = False
            for k in fill_if_empty:
                v = b.get(k)
                if v is not None and not fund.get(k):
                    fund[k] = v
                    changed = True
            for k in always_take:
                v = b.get(k)
                if v is not None:
                    fund[k] = v
                    changed = True
            if changed:
                merged += 1
    print(f'  ✓ 合并基金基本概况(jbgk) {merged}/{len(funds)} ({time.time()-t0:.1f}s)', flush=True)
else:
    print('  ⚠ 无基金基本概况文件，跳过', flush=True)

# 2e. [STAGING] 种子货币型（主管道 fetch_and_import_funds 仅含 5 大类，不含 hb）
#     从 fund_combined 取货币型基础信息（c/name/t0/t1/company/scale/fee/manager），
#     阶段收益在 2f 由 currency_output.ndjson 填充。
if STAGING:
    t0e = time.time()
    try:
        hb_rows = pg("SELECT c, name, t0, t1, company, fund_scale, manage_fee, fund_manager "
                     "FROM fund_combined WHERE t0 = '货币型'")
    except Exception as e:
        hb_rows = []
        print(f'  [WARN] 读取 fund_combined 货币型失败: {str(e)[:160]}', flush=True)
    seeded = 0
    if hb_rows:
        existing_codes = {f.get('c', '').replace('.OF', '') for f in funds}
        for r in hb_rows:
            c = (r.get('c') or '').replace('.OF', '')
            if c in existing_codes:
                continue
            funds.append({
                'c': f'{c}.OF',
                'n': r.get('name') or '',
                't0': r.get('t0') or '货币型',
                't1': r.get('t1') or '货币型-普通货币',
                'company': r.get('company'),
                'fund_scale': r.get('fund_scale'),
                'manage_fee': r.get('manage_fee'),
                'fund_manager': r.get('fund_manager'),
            })
            seeded += 1
    print(f'  ✓ 种子货币型 {seeded} 只（来自 fund_combined）({time.time()-t0e:.1f}s)', flush=True)

# 2f. [STAGING] 合并货币基金阶段收益（currency_output.ndjson，hb rankhandler）
#     填充 r0w~r3y / ytd / return_all；r5y 在 hb 排名页不存在，保持 NULL。
if STAGING:
    cur_path = os.path.join(SCRIPT_DIR, 'currency_output.ndjson')
    if os.path.exists(cur_path):
        t0f = time.time()
        cur_map = {}
        with open(cur_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    r = json.loads(line)
                    c = r.get('c', '')
                    if c:
                        cur_map[c] = r
        merged = 0
        for fund in funds:
            c = fund.get('c', '').replace('.OF', '')
            if c in cur_map:
                r = cur_map[c]
                for k in ['r0w', 'r1m', 'r3m', 'r6m', 'r1y', 'r2y', 'r3y', 'r5y', 'ytd', 'return_all']:
                    v = r.get(k)
                    if v is not None:
                        fund[k] = v
                if r.get('t1'):
                    fund['t1'] = r['t1']
                merged += 1
        print(f'  ✓ 合并货币基金阶段收益 {merged}/{len(funds)} ({time.time()-t0f:.1f}s)', flush=True)
    else:
        print('  ⚠ 无 currency_output.ndjson，货币型将缺阶段收益（请先运行 fetch_currency_funds.py）', flush=True)

# 2d. 合并基金经理（已内嵌在 risk_indicators.ndjson 的 fund_manager 字段中）
# fund_manager 已在步骤 2 通过 risk_indicators 合并，此处无需额外处理

# 2g. 归一化 t0 → 天天 7 大类命名（与生产表/前端默认视图一致）
#     修复：聚源命名（股票型基金）与历史生产（股票型）不一致；指数基金此前被并入
#     「股票型基金」导致缺失独立的「指数型」大类，promote 校验会整批拒绝。
#     优先级（关键）：
#       1) QDII 优先于 指数型 —— QDII 与指数型存在交叉（如「指数型-海外股票」），
#          必须先归 QDII，否则 173 只 QDII 海外指数基金会被错判为指数型，
#          导致 staging QDII 数量远低于生产（395→220），promote 校验整批拒绝。
#          QDII 判定信号：t0 ∈ {QDII, QDII基金} 或 t1_tt 含 'QDII' / '海外'。
#       2) t1_tt 以「指数型」开头→指数型；t1_tt 非空→取 t1_tt 前缀；否则保留原 t0。
_t0_fixed = 0
for _f in funds:
    _t0 = _f.get('t0')
    _t1tt = _f.get('t1_tt')
    _new = None
    _is_qdii = (_t0 in ('QDII', 'QDII基金')
                or (isinstance(_t1tt, str) and ('QDII' in _t1tt or '海外' in _t1tt)))
    if _is_qdii:
        _new = 'QDII'
    elif isinstance(_t1tt, str) and _t1tt.startswith('指数型'):
        _new = '指数型'
    elif _t1tt:
        _new = _t1tt.split('-')[0]
    elif _t0:
        _new = _t0
    if _new and _new != _t0:
        _f['t0'] = _new
        _t0_fixed += 1
print(f'  ✓ t0 归一化: {_t0_fixed} 只调整为天天 7 大类命名', flush=True)

# 3. 重新计算靠谱分 v7（权重 50/25/25）
t0 = time.time()
W_RET, W_DD, W_SR = 0.50, 0.25, 0.25
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

# 3b. 计算 k_all (v7 加权综合分) 和 score_grade
t0 = time.time()
PERIOD_W = {'k0w':5, 'k1m':5, 'k3m':10, 'k6m':15, 'k1':20, 'k2':20, 'k3':15, 'k5':10}
k_all_cnt = 0
for f in funds:
    total_w = 0
    weighted_sum = 0
    for kf, w in PERIOD_W.items():
        val = float(f.get(kf) or 0)
        if val > 0 and w > 0:
            weighted_sum += val * w
            total_w += w
    if total_w > 0:
        f['k_all'] = round(weighted_sum / total_w, 4)
        k_all_cnt += 1
    else:
        f['k_all'] = None

# score_grade: 全市场百分位
scored_funds = [f for f in funds if f['k_all'] is not None]
scored_funds.sort(key=lambda x: x['k_all'], reverse=True)
n_scored = len(scored_funds)
for rank, f in enumerate(scored_funds):
    pct = (1 - rank / (n_scored - 1)) * 100 if n_scored > 1 else 50
    if pct >= 80:
        f['score_grade'] = 'green'
    elif pct >= 50:
        f['score_grade'] = 'blue'
    else:
        f['score_grade'] = 'orange'
for f in funds:
    if 'score_grade' not in f:
        f['score_grade'] = 'gray'

grades = {}
for f in funds:
    g = f['score_grade']
    grades[g] = grades.get(g, 0) + 1
print(f'  ✓ k_all 计算完成: {k_all_cnt}/{len(funds)} 只有分 ({time.time()-t0:.1f}s)', flush=True)
print(f'    grade分布: green={grades.get("green",0)}, blue={grades.get("blue",0)}, orange={grades.get("orange",0)}, gray={grades.get("gray",0)}', flush=True)

# 4. 通过 Management API 批量 SQL INSERT（比 REST API 快且更可靠）
t0 = time.time()
if STAGING:
    # 临时表：CREATE LIKE + TRUNCATE，不触碰生产 fund_scores
    print(f'  创建/清空临时表 {TARGET_TABLE}（LIKE fund_scores）...', flush=True)
    pg(f'CREATE TABLE IF NOT EXISTS {TARGET_TABLE} (LIKE fund_scores INCLUDING DEFAULTS)')
    pg(f'TRUNCATE TABLE {TARGET_TABLE}')
    print(f'  ✓ {TARGET_TABLE} 已清空', flush=True)
else:
    # 先快照已有基金经理/管理人（兜底：防止基本概况抓取失败时清空）
    print('  快照已有基金经理(兜底)...', flush=True)
    pg('CREATE TABLE IF NOT EXISTS _mgr_snapshot (c text primary key, fund_manager text, company text)')
    pg('TRUNCATE TABLE _mgr_snapshot')
    pg("INSERT INTO _mgr_snapshot (c, fund_manager, company) SELECT c, fund_manager, company FROM fund_scores WHERE fund_manager IS NOT NULL OR company IS NOT NULL")
    try:
        snap_n = pg('SELECT count(*) as cnt FROM _mgr_snapshot')[0]['cnt']
    except Exception:
        snap_n = '?'
    print(f'  ✓ 快照 {snap_n} 条', flush=True)
    print('  清空旧数据...', flush=True)
    pg('TRUNCATE TABLE fund_scores')
    print(f'  ✓ 已清空', flush=True)

# SQL 值转义
def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, bool):
        return 'true' if v else 'false'
    if isinstance(v, (int, float)):
        if v != v:  # NaN
            return 'NULL'
        return repr(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"

INSERT_COLS = [
    'c','n','t0','t1','t1_tt','sg','daily_change',
    'company','fund_scale','manage_fee','fund_manager',
    'share_scale','custody_fee','sale_fee','found_date',
    'ytd','r0w','r1m','r3m','r6m','r1y','r2y','r3y','r5y','r7y','r10y','return_all',
    'dd1y','dd2y','dd3y','dd5y',
    'sr1y','sr2y','sr3y','sr5y',
    'k0w','k1m','k3m','k6m','k1','k2','k3','k5',
    'k_all','score_grade',
]
COLS_STR = ', '.join(INSERT_COLS)

def build_insert_sql(batch):
    parts = []
    for r in batch:
        d = row_to_rest(r)
        vals = ', '.join(sql_val(d.get(col)) for col in INSERT_COLS)
        parts.append(f'({vals})')
    return f'INSERT INTO {TARGET_TABLE} ({COLS_STR}) VALUES {", ".join(parts)}'

imported = 0
failed = 0

def insert_batch(batch, label=''):
    global imported, failed
    if not batch:
        return
    try:
        sql = build_insert_sql(batch)
        pg(sql)
        imported += len(batch)
        pct = imported * 100 // len(funds)
        print(f'  导入进度: {imported}/{len(funds)} ({pct}%) {label}', flush=True)
    except Exception as e:
        if len(batch) <= 25:
            failed += len(batch)
            print(f'  ✗ 批次{label} {len(batch)}条最终失败: {str(e)[:150]}', flush=True)
        else:
            mid = len(batch) // 2
            print(f'  ↹ 批次{label} {len(batch)}条拆分重试: {str(e)[:100]}', flush=True)
            insert_batch(batch[:mid], f'{label}a')
            insert_batch(batch[mid:], f'{label}b')

total_batches = (len(funds) + BATCH - 1) // BATCH
for i in range(0, len(funds), BATCH):
    batch = funds[i:i+BATCH]
    batch_num = i // BATCH + 1
    insert_batch(batch, f'[{batch_num}/{total_batches}]')

print(f'  ✓ 导入完成: 成功={imported}/{len(funds)}, 失败={failed} ({time.time()-t0:.1f}s)', flush=True)

# 4b. 恢复快照里的基金经理/管理人（兜底：仅填 NULL，不覆盖本次已合并的值）
if not STAGING:
    print('  恢复快照基金经理(兜底)...', flush=True)
    pg("""UPDATE fund_scores fs
    SET fund_manager = s.fund_manager,
        company = COALESCE(fs.company, s.company)
    FROM _mgr_snapshot s
    WHERE fs.c = s.c AND (fs.fund_manager IS NULL OR fs.fund_manager = '')""")
    try:
        restored_n = pg('SELECT count(*) as cnt FROM fund_scores WHERE fund_manager IS NOT NULL')[0]['cnt']
    except Exception:
        restored_n = '?'
    print(f'  ✓ 恢复后 fund_manager 非空: {restored_n}', flush=True)

# 5. 写入 meta（UPSERT id=8）—— 仅生产模式；staging 不篡改生产 meta
if not STAGING:
    nav_date = funds[0].get('date','') if funds else ''
    scored_count = k_all_cnt  # 使用 k_all 计分统计
    result = pg("SELECT nav_date, tsq FROM fund_scores_meta WHERE id = 8")
    existing_nav = ''
    if result and len(result) > 0:
        existing_nav = result[0].get('nav_date', '') or ''
    # 合并 nav_date：保留已有的（来自 fetch 阶段），如果当前有新的则覆盖
    final_nav = nav_date or existing_nav
    pg(f"""UPDATE fund_scores_meta
        SET total_count = {len(funds)}, scored_count = {scored_count},
            nav_date = '{final_nav}', tsq = NOW()
        WHERE id = 8""")
    if not result or len(result) == 0:
        pg(f"""INSERT INTO fund_scores_meta (id, total_count, scored_count, nav_date, tsq)
            VALUES (8, {len(funds)}, {scored_count}, '{final_nav}', NOW())""")
    print(f'  ✓ meta 已更新 (id=8, total={len(funds)}, scored={scored_count}, date={final_nav})', flush=True)
else:
    print(f'  [STAGING] 已写入临时表 {TARGET_TABLE}，生产 fund_scores / meta 未改动', flush=True)

# 6. 验证
result = pg(f'SELECT count(*) as cnt FROM {TARGET_TABLE}')
print(f'  验证: {TARGET_TABLE} 有 {result[0]["cnt"]} 条', flush=True)
result = pg(f"SELECT t0, count(*) as cnt FROM {TARGET_TABLE} WHERE t0 IS NOT NULL GROUP BY t0 ORDER BY cnt DESC")
print('  t0 分布:', flush=True)
for row in result:
    print(f'    {row["t0"]}: {row["cnt"]} 只', flush=True)

print('\n✅ 全部完成！', flush=True)
