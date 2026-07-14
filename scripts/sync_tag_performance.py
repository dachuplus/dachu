#!/usr/bin/env python3
"""
sync_tag_performance.py - 拉取天天基金主题板块各周期涨跌幅，写入 fund_tag_perf 表

数据来源: 东财 ZTJJ 接口 GetBKDetailInfoNew
  URL: http://api.fund.eastmoney.com/ztjj/GetBKDetailInfoNew?callback=cb&tp={INDEXCODE}
  字段: D(日涨幅), W(近1周), M(近1月), Q(近3月), Y(近1年), SY(今年来)
       RANKW/RANKM/RANKQ/RANKY/RANKSY(各周期排名), SEC_NAME(标签名)

目标表: fund_tag_perf (TRUNCATE 全量重写，幂等)
  列: tag_index_code(PK), tag_name, d, w, m, q, y, sy,
      rank_d, rank_w, rank_m, rank_q, rank_y, rank_sy,
      updated_at

用法:
  SUPABASE_PAT=<你的Supabase PAT> \
  python3 scripts/sync_tag_performance.py
"""

import os
import sys
import time
import json
import requests

# ── 配置 ──────────────────────────────────────────────
# 优先 SUPABASE_PAT（沙箱/本地用真实 PAT），回退 SUPABASE_MGMT_TOKEN（CI 以该 Secret 注入）。
# 顺序关键：沙箱 profile 可能注入过期 SUPABASE_MGMT_TOKEN，故 PAT 必须优先。
PAT = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN', '')
if not PAT:
    print('ERROR: SUPABASE_PAT / SUPABASE_MGMT_TOKEN not set')
    sys.exit(1)

MGMT_URL = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'
HEADERS_MGMT = {
    'Authorization': f'Bearer {PAT}',
    'Content-Type': 'application/json',
}

HEADERS_EM = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/ztjj/',
}

BASE_API = 'http://api.fund.eastmoney.com/ztjj/GetBKDetailInfoNew'


def mgmt_query(sql):
    """执行 Management API SQL（SELECT / DDL / DML），含重试应对沙箱网络抖动"""
    last_err = None
    for attempt in range(4):
        try:
            r = requests.post(MGMT_URL, headers=HEADERS_MGMT, json={
                'query': sql,
            }, timeout=90)
            r.raise_for_status()
            data = r.json()
            # SELECT 返回 list，DDL/DML 返回 {"command": ..., "rows_affected": ...}
            if isinstance(data, list):
                return {'result': {'rows': data}}
            return data
        except Exception as e:
            last_err = e
            print(f'  [mgmt_query 重试 {attempt+1}/4] {type(e).__name__}: {str(e)[:80]}')
            time.sleep(3 + attempt * 2)
    raise last_err


def fetch_tag_list():
    """从东财 ZTJJ 完整标签列表获取所有标签（与 sync_fund_tags_full.py 同源）"""
    url = 'http://api.fund.eastmoney.com/ZTJJ/GetBKListByBKTypeNew?callback=?'
    h = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/ztjj/'}
    r = requests.get(url, headers=h, timeout=15)
    r.raise_for_status()
    t = r.text
    s = t.index('(') + 1
    e = t.rindex(')')
    data = json.loads(t[s:e])['Data']

    rows = []
    for group in [data.get('hy1', []), data.get('hy2', []), data.get('gn', [])]:
        for item in group:
            rows.append({'tag_index_code': item['INDEXCODE'], 'tag_name': item['INDEXNAME']})

    print(f'[INFO] 东财 ZTJJ 共 {len(rows)} 个标签')
    return rows


def to_float(v):
    """东财接口部分字段可能为 '—' / '' / None / 字符串，统一收敛为 float 或 None"""
    if v is None:
        return None
    if isinstance(v, str):
        v = v.strip()
        if v in ('', '-', '—', '—', 'N/A', 'nan'):
            return None
        # 去掉百分号等杂质
        v = v.replace('%', '').replace(',', '')
    try:
        f = float(v)
        import math
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    except (ValueError, TypeError):
        return None


def to_int(v):
    """排名字段可能为非数字（无排名），统一收敛为 int 或 None"""
    f = to_float(v)
    if f is None:
        return None
    return int(round(f))


# ── 名称归一化与别名映射（ZTJJ 标签名 ↔ push2 板块名）─────────
# push2 的概念板(t:3)和行业板(t:2)命名与 ZTJJ 标签名存在系统偏差，
# 导致精确匹配率低。此表覆盖已知差异，提升概念板（t:3）匹配覆盖率。
TAG_TO_BOARD_ALIAS = {
    # ZTJJ 标签名 → push2 板块名（优先匹配概念板名）
    '光通信模块': '光模块',
    '元器件': '元件',
    '光刻胶': '光刻胶',
    '第三代半导体': '半导体',
    '消费电子': '消费电子',
    '计算机设备': '计算机设备',
    '国产软件': '国产软件',
    '电网设备': '电网设备',
    '风电设备': '风电',
    '高端装备': '高端装备',
    '高端制造': '高端制造',
    '装修建材': '装修建材',
    '绿色电力': '绿色电力',
    '航空航天': '航天装备',  # 可能需要根据实际push2返回调整
    '脑机接口': '脑机接口',
    '商业航天': '商业航天',
    '卫星互联网': '卫星互联网',
    '低空经济': '低空经济',
    '人形机器人': '人形机器人',
    '智能驾驶': '智能驾驶',
    '无人驾驶': '无人驾驶',
    '智能穿戴': '智能穿戴',
    '智能家居': '智能家居',
    '固态电池': '固态电池',
    '锂电池': '锂电池',
    '锂矿': '锂矿',
    '新能源车': '新能源汽车',
    '算力': '算力',
    '数据要素': '数据要素',
    '数据中心': '数据中心',
    '云计算': '云计算',
    '网络安全': '网络安全',
    '信创': '信创',
    'AI应用': 'AI应用',
    'AI眼镜': 'AI眼镜',
    'AI手机': 'AI手机',
    'DeepSeek': 'DeepSeek',
    'HALO': 'HALO',
    'Web3.0': 'Web3.0',
    '元宇宙': '元宇宙',
    '中特估': '中特估',
    '国企改革': '国企改革',
    '一带一路': '一带一路',
    '东数西算': '东数西算',
    '碳中和': '碳中和',
    '可控核聚变': '可控核聚变',
    '猪肉': '猪肉',
    '农牧主题': '农牧主题',
    '黄金股': '黄金股',
}


def norm_board_name(name):
    """归一化板块名：去除后缀 + 别名查找。"""
    s = (name or '').strip()
    for suf in ('概念', '板块', '行业', '主题', '指数'):
        if s.endswith(suf):
            s = s[: -len(suf)]
    return s


def find_best_board_match(tag_name, flows_norm):
    """多策略匹配：别名 → 精确 → 包含(双向) → 首字前缀。
    
    优先匹配概念板（flows_norm 中概念已覆盖同名行业），
    返回 (normalized_key, value) 或 (None, None)。
    """
    # 策略1：别名表直查
    alias = TAG_TO_BOARD_ALIAS.get(tag_name)
    if alias and alias in flows_norm:
        return alias, flows_norm[alias]

    # 策略2：归一化后精确匹配
    key = norm_board_name(tag_name)
    if key in flows_norm:
        return key, flows_norm[key]

    # 策略3：包含匹配（标签名含板名 或 板名含标签名）
    for bk, val in flows_norm.items():
        if tag_name == bk:
            return bk, val
        if len(bk) >= 2 and (bk in tag_name or tag_name in bk):
            return bk, val

    # 策略4：首字相同且长度接近（兜底）
    if key:
        for bk, val in flows_norm.items():
            if bk and key[0] == bk[0] and abs(len(key) - len(bk)) <= 2:
                return bk, val

    return None, None


def fetch_block_perf(index_code):
    """调用东财接口获取单个板块的各周期涨跌"""
    try:
        r = requests.get(BASE_API, params={
            'callback': 'cb',
            'tp': index_code,
        }, headers=HEADERS_EM, timeout=10)
        r.raise_for_status()
        text = r.text
        # Strip JSONP: cb({...}) -> {...}
        start = text.index('(') + 1
        end = text.rindex(')')
        data = json.loads(text[start:end])
        if data.get('ErrCode') != 0 or not data.get('Data'):
            return None
        return data['Data']
    except Exception as e:
        print(f'  [WARN] {index_code} 请求失败: {e}')
        return None


# ── 板块资金流（主力净流入）——东财 push2 clist 接口 ────────────
# GetBKDetailInfoNew 不含资金流字段，改用东财行情中心板块资金流排行接口，
# 按板块中文名与我们的标签名匹配（东财板块命名跨产品一致）。
# f62 = 当日主力净流入净额(元)；f184 = 主力净流入净占比(%)
PUSH2_HOSTS = [
    'push2.eastmoney.com',
    '1.push2.eastmoney.com',
    '19.push2.eastmoney.com',
    '48.push2.eastmoney.com',
]
HEADERS_PUSH2 = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://data.eastmoney.com/',
    'Accept': '*/*',
}


def _push2_get(path, tries=4):
    """带主机轮换 + 重试的 push2 GET，返回解析后的 JSON（失败返回 {}）"""
    for attempt in range(tries):
        host = PUSH2_HOSTS[attempt % len(PUSH2_HOSTS)]
        try:
            r = requests.get('https://' + host + path, headers=HEADERS_PUSH2, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception:
            time.sleep(2 + attempt)
    return {}


def fetch_board_flows_multi_period(board_type):
    """拉取某类板块（3=概念, 2=行业）今日/近5日/近10日主力净流入。

    返回 {板块名: (今日净流入元, 今日占比%, 近5日净流入元, 近10日净流入元)}。

    字段映射（来源：东财板块资金流 bkzj 页面 /newstatic/js/bkzj/list.js 的
    period->fid 映射：今日=f62，5日=f164，10日=f174）：
      f62  = 当日主力净流入净额(元)
      f164 = 近5日主力净流入净额(元)
      f174 = 近10日主力净流入净额(元)
      f184 = 当日主力净流入净占比(%)
    """
    out = {}
    for pn in range(1, 9):
        path = (
            f'/api/qt/clist/get?fid=f62&po=1&pz=100&pn={pn}&np=1&fltt=2&invt=2'
            f'&fs=m:90+t:{board_type}&fields=f12,f14,f62,f184,f164,f174'
        )
        j = _push2_get(path)
        diff = (j.get('data') or {}).get('diff') or []
        if not diff:
            break
        for it in diff:
            name = (it.get('f14') or '').strip()
            if not name:
                continue
            net = to_float(it.get('f62'))      # 今日主力净流入(元)
            pct = to_float(it.get('f184'))     # 今日主力净占比(%)
            net_5d = to_float(it.get('f164'))  # 近5日主力净流入(元)
            net_10d = to_float(it.get('f174')) # 近10日主力净流入(元)
            out[name] = (net, pct, net_5d, net_10d)
        time.sleep(0.8)
    return out


def fetch_all_board_flows():
    """合并概念+行业板块资金流（今日/近5日/近10日），
    返回 {板块名: (今日亿元, 占比%, 近5日亿元, 近10日亿元)}"""
    print('\n[STEP 2b] 拉取东财板块资金流（今日/近5日/近10日主力净流入）...')
    flows = {}
    try:
        industry = fetch_board_flows_multi_period(2)
        time.sleep(1)
        concept = fetch_board_flows_multi_period(3)
    except Exception as e:
        print(f'  [WARN] 板块资金流拉取异常: {e}')
        return {}
    merged = {**industry, **concept}  # 概念优先覆盖同名
    for name, (net, pct, net5, net10) in merged.items():
        # net 单位元 -> 亿元，保留 4 位；pct 东财返回已是百分数
        flows[name] = (
            round(net / 1e8, 4) if net is not None else None,
            round(pct, 2) if pct is not None else None,
            round(net5 / 1e8, 4) if net5 is not None else None,
            round(net10 / 1e8, 4) if net10 is not None else None,
        )
    print(f'  [INFO] 资金流板块数: 行业 {len(industry)} + 概念 {len(concept)} = {len(merged)} 个')
    return flows


def fetch_existing_net_inflow():
    """TRUNCATE 前读取历史 net_inflow*（限流保护用）。
    仅读取、不修改任何数据源；命中率低时回退到这些值，避免好数据被 NULL 覆盖。"""
    try:
        resp = mgmt_query(
            "SELECT tag_index_code, net_inflow, net_inflow_pct, net_inflow_5d, net_inflow_10d "
            "FROM public.fund_tag_perf"
        )
        rows = (resp.get('result') or {}).get('rows') or []
        out = {}
        for r in rows:
            out[r['tag_index_code']] = (
                r.get('net_inflow'), r.get('net_inflow_pct'),
                r.get('net_inflow_5d'), r.get('net_inflow_10d'),
            )
        return out
    except Exception as e:
        print(f'  [WARN] 读取历史 net_inflow 失败: {e}')
        return {}


def main():
    print('=' * 60)
    print('sync_tag_performance.py - 板块涨跌幅全量同步')
    print('=' * 60)

    # Step 1: 获取标签列表
    tags = fetch_tag_list()
    if not tags:
        print('[ERROR] 无标签数据')
        sys.exit(1)

    # Step 2: 逐个拉取板块性能（串行，控制频率避免被封）
    results = []
    ok = 0
    fail = 0
    total = len(tags)

    # Step 2b（前置）：先拉板块资金流，趁东财限流预算最充足，提升覆盖率
    flows = fetch_all_board_flows()
    flows_norm = {norm_board_name(nm): v for nm, v in flows.items()} if flows else {}

    for i, tag in enumerate(tags):
        code = tag['tag_index_code']
        name = tag['tag_name']
        print(f'  [{i+1}/{total}] {code} {name} ...', end=' ', flush=True)

        perf = fetch_block_perf(code)
        if perf:
            results.append({
                'tag_index_code': code,
                'tag_name': perf.get('SEC_NAME') or name,
                'd': to_float(perf.get('D')),
                'w': to_float(perf.get('W')),
                'm': to_float(perf.get('M')),
                'q': to_float(perf.get('Q')),
                'y': to_float(perf.get('Y')),
                'sy': to_float(perf.get('SY')),
                'rank_w': to_int(perf.get('RANKW')),
                'rank_m': to_int(perf.get('RANKM')),
                'rank_q': to_int(perf.get('RANKQ')),
                'rank_y': to_int(perf.get('RANKY')),
                'rank_sy': to_int(perf.get('RANKSY')),
                'total_count': to_int(perf.get('WSC')) or 0,
            })
            ok += 1
            d_val = perf.get('D')
            d_str = f'{d_val:.2f}%' if d_val is not None else 'N/A'
            print(f'OK (日涨幅={d_str})')
        else:
            fail += 1
            print('FAIL')

        # 控制请求频率：每5个暂停0.5秒，避免触发限制
        if (i + 1) % 5 == 0 and i < total - 1:
            time.sleep(0.5)

    print(f'\n[RESULT] 成功 {ok}/{total}, 失败 {fail}/{total}')

    if ok == 0:
        print('[ERROR] 所有请求均失败')
        sys.exit(1)

    # Step 2b: 按名称匹配板块资金流（多策略：别名→精确→包含→前缀），并做限流保护
    MIN_MATCHED = 15  # 匹配数低于此阈值视为东财限流抓空，保留历史值
    prev = fetch_existing_net_inflow()
    matched = 0
    match_detail = {'alias': 0, 'exact': 0, 'contains': 0, 'prefix': 0}
    if flows_norm:
        for row in results:
            key, fv = find_best_board_match(row['tag_name'], flows_norm)
            row['_match_key'] = key
            row['_new'] = fv
            if fv:
                matched += 1
                # 统计匹配策略分布（用于日志）
                alias = TAG_TO_BOARD_ALIAS.get(row['tag_name'])
                if alias and key == alias:
                    match_detail['alias'] += 1
                elif key == norm_board_name(row['tag_name']):
                    match_detail['exact'] += 1
                elif key and (key in row['tag_name'] or row['tag_name'] in key):
                    match_detail['contains'] += 1
                else:
                    match_detail['prefix'] += 1
        use_new = matched >= MIN_MATCHED
        if use_new:
            print(f'  [INFO] 资金流匹配成功 {matched}/{len(results)} 个'
                  f'(别名{match_detail["alias"]} 精确{match_detail["exact"]}'
                  f' 包含{match_detail["contains"]} 前缀{match_detail["prefix"]})，采用本轮数据')
        else:
            print(f'  [WARN] 资金流匹配仅 {matched} 个 < 阈值 {MIN_MATCHED}，本轮视为限流失败，保留历史值')
    else:
        use_new = False
        print('  [WARN] 未获取到板块资金流（东财限流），保留历史值')

    # 赋值规则：命中且采用新值 -> 新值；否则 -> 历史值；皆无 -> NULL（前端显"数据更新中…"）
    for row in results:
        code = row['tag_index_code']
        nv = row.pop('_new', None)
        if use_new and nv:
            row['net_inflow'], row['net_inflow_pct'], row['net_inflow_5d'], row['net_inflow_10d'] = nv
        elif code in prev:
            row['net_inflow'], row['net_inflow_pct'], row['net_inflow_5d'], row['net_inflow_10d'] = prev[code]
        else:
            row['net_inflow'] = None
            row['net_inflow_pct'] = None
            row['net_inflow_5d'] = None
            row['net_inflow_10d'] = None

    # Step 3: TRUNCATE + 批量写入 fund_tag_perf 表
    print('\n[STEP 3] 写入 fund_tag_perf 表 ...')

    # 确保表存在
    mgmt_query("""
        CREATE TABLE IF NOT EXISTS public.fund_tag_perf (
            tag_index_code TEXT PRIMARY KEY,
            tag_name TEXT NOT NULL,
            d REAL,           -- 日涨幅(%)
            w REAL,           -- 近1周(%)
            m REAL,           -- 近1月(%)
            q REAL,           -- 近3月(%)
            y REAL,           -- 近1年(%)
            sy REAL,          -- 今年来(%)
            rank_w INTEGER,   -- 近1周排名
            rank_m INTEGER,   -- 近1月排名
            rank_q INTEGER,   -- 近3月排名
            rank_y INTEGER,   -- 近1年排名
            rank_sy INTEGER,  -- 今年来排名
            total_count INTEGER, -- 标签总数(用于排名分母)
            net_inflow REAL,      -- 当日主力净流入(亿元)
            net_inflow_pct REAL,  -- 主力净流入净占比(%)
            net_inflow_5d REAL,   -- 近5日主力净流入(亿元)
            net_inflow_10d REAL,  -- 近10日主力净流入(亿元)
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)

    # 兼容已存在的旧表：补齐资金流字段
    mgmt_query("ALTER TABLE public.fund_tag_perf ADD COLUMN IF NOT EXISTS net_inflow REAL")
    mgmt_query("ALTER TABLE public.fund_tag_perf ADD COLUMN IF NOT EXISTS net_inflow_pct REAL")
    mgmt_query("ALTER TABLE public.fund_tag_perf ADD COLUMN IF NOT EXISTS net_inflow_5d REAL")
    mgmt_query("ALTER TABLE public.fund_tag_perf ADD COLUMN IF NOT EXISTS net_inflow_10d REAL")

    # 清空旧数据
    mgmt_query('TRUNCATE TABLE public.fund_tag_perf')

    # 批量插入
    def esc(v):
        if v is None:
            return 'NULL'
        if isinstance(v, float):
            import math
            if math.isnan(v) or math.isinf(v):
                return 'NULL'
            return str(round(v, 4))  # 收敛 double 精度噪声，如 -3.7711560000000013 -> -3.7712
        if isinstance(v, str):
            return "'" + v.replace("'", "''") + "'"
        return str(v)

    values_parts = []
    failed_batches = []
    for row in results:
        # 注意：所有字段都必须经 esc() 处理，None -> 'NULL'，否则 f"{None}" 会变成非法 SQL 字面量 'None' 触发 400
        values_parts.append(
            f"({esc(row['tag_index_code'])}, {esc(row['tag_name'])}, "
            f"{esc(row['d'])}, {esc(row['w'])}, {esc(row['m'])}, {esc(row['q'])}, {esc(row['y'])}, {esc(row['sy'])}, "
            f"{esc(row['rank_w'])}, {esc(row['rank_m'])}, {esc(row['rank_q'])}, {esc(row['rank_y'])}, {esc(row['rank_sy'])}, "
            f"{esc(row['total_count'])}, {esc(row.get('net_inflow'))}, {esc(row.get('net_inflow_pct'))}, "
            f"{esc(row.get('net_inflow_5d'))}, {esc(row.get('net_inflow_10d'))}, now())"
        )

    # 分批 UPSERT（每批20条，ON CONFLICT 幂等，避免重复键报错；小批量降低 Management API 限流概率）
    BATCH = 20
    for i in range(0, len(values_parts), BATCH):
        batch = values_parts[i:i + BATCH]
        sql = (
            f"INSERT INTO public.fund_tag_perf "
            f"(tag_index_code, tag_name, d, w, m, q, y, sy, rank_w, rank_m, rank_q, rank_y, rank_sy, total_count, net_inflow, net_inflow_pct, net_inflow_5d, net_inflow_10d, updated_at) "
            f"VALUES {','.join(batch)} "
            f"ON CONFLICT (tag_index_code) DO UPDATE SET "
            f"tag_name=EXCLUDED.tag_name, d=EXCLUDED.d, w=EXCLUDED.w, m=EXCLUDED.m, q=EXCLUDED.q, "
            f"y=EXCLUDED.y, sy=EXCLUDED.sy, rank_w=EXCLUDED.rank_w, rank_m=EXCLUDED.rank_m, "
            f"rank_q=EXCLUDED.rank_q, rank_y=EXCLUDED.rank_y, rank_sy=EXCLUDED.rank_sy, "
            f"total_count=EXCLUDED.total_count, net_inflow=EXCLUDED.net_inflow, "
            f"net_inflow_pct=EXCLUDED.net_inflow_pct, net_inflow_5d=EXCLUDED.net_inflow_5d, "
            f"net_inflow_10d=EXCLUDED.net_inflow_10d, updated_at=now()"
        )
        try:
            mgmt_query(sql)
        except Exception as e:
            print(f'  [UPSERT 失败] batch {i//BATCH+1}: {e}')
            print(f'  [DEBUG] 完整SQL:')
            print(sql)
            print(f'  [DEBUG] 本批原始行:')
            for rp in values_parts[i:i + BATCH]:
                print('    ', rp)
            # 单批失败不阻塞其余批次，继续写剩余标签
            failed_batches.append((i // BATCH + 1, sql))
        time.sleep(2)  # 降低 Management API 限流风险

    # 验证
    check = mgmt_query('SELECT count(*) as cnt FROM public.fund_tag_perf')
    cnt = check['result']['rows'][0]['cnt']

    # 开放 RLS anon 读权限
    try:
        mgmt_query("GRANT SELECT ON public.fund_tag_perf TO anon")
    except Exception:
        pass  # 可能已授权

    if failed_batches:
        print(f'  [WARN] 有 {len(failed_batches)} 个批次写入失败，建议检查上方 DEBUG 输出')

    print(f'[DONE] fund_tag_perf 写入完成: {cnt} 条记录')
    print(f'ROWS_AFFECTED={cnt}')
    print(f'       数据来源: 东财 ZTJJ::GetBKDetailInfoNew + 东财板块资金流(push2 clist)')
    print(f'       含字段: d(日涨幅), w(近1周), m(近1月), q(近3月), y(近1年), sy(今年来) + 各周期排名')
    print(f'       资金流: net_inflow(今日), net_inflow_5d(近5日), net_inflow_10d(近10日) 主力净流入(亿元)')


if __name__ == '__main__':
    main()
