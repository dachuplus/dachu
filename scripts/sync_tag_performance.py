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
PAT = os.environ.get('SUPABASE_PAT', '')
if not PAT:
    print('ERROR: SUPABASE_PAT not set')
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
    """从 fund_tag_funds 表获取所有标签的 INDEXCODE（去重）"""
    result = mgmt_query("""
        SELECT DISTINCT tag_index_code, tag_name
        FROM fund_tag_funds
        WHERE tag_index_code IS NOT NULL AND tag_index_code != ''
        ORDER BY tag_index_code
    """)
    rows = result.get('result', {}).get('rows', [])
    print(f'[INFO] fund_tag_funds 共 {len(rows)} 个标签')
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
            updated_at TIMESTAMPTZ DEFAULT now()
        )
    """)

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
            f"{esc(row['total_count'])}, now())"
        )

    # 分批 UPSERT（每批20条，ON CONFLICT 幂等，避免重复键报错；小批量降低 Management API 限流概率）
    BATCH = 20
    for i in range(0, len(values_parts), BATCH):
        batch = values_parts[i:i + BATCH]
        sql = (
            f"INSERT INTO public.fund_tag_perf "
            f"(tag_index_code, tag_name, d, w, m, q, y, sy, rank_w, rank_m, rank_q, rank_y, rank_sy, total_count, updated_at) "
            f"VALUES {','.join(batch)} "
            f"ON CONFLICT (tag_index_code) DO UPDATE SET "
            f"tag_name=EXCLUDED.tag_name, d=EXCLUDED.d, w=EXCLUDED.w, m=EXCLUDED.m, q=EXCLUDED.q, "
            f"y=EXCLUDED.y, sy=EXCLUDED.sy, rank_w=EXCLUDED.rank_w, rank_m=EXCLUDED.rank_m, "
            f"rank_q=EXCLUDED.rank_q, rank_y=EXCLUDED.rank_y, rank_sy=EXCLUDED.rank_sy, "
            f"total_count=EXCLUDED.total_count, updated_at=now()"
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
    print(f'       数据来源: 东财 ZTJJ::GetBKDetailInfoNew')
    print(f'       含字段: d(日涨幅), w(近1周), m(近1月), q(近3月), y(近1年), sy(今年来) + 各周期排名')


if __name__ == '__main__':
    main()
