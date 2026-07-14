#!/usr/bin/env python3
"""
sync_fund_tags_full.py - 从东财 ZTJJ 拉取完整标签列表，重建 fund_tags 表

数据来源: 东财 ZTJJ 接口 GetBKListByBKTypeNew
  URL: http://api.fund.eastmoney.com/ZTJJ/GetBKListByBKTypeNew?callback=?
  返回: hy1(行业一级), hy2(行业二级), gn(概念) 三组标签

目标表: fund_tags (TRUNCATE 全量重写，幂等)
  列: id(SERIAL PK), name, tag_type(industry/concept), return_pct, sort_order, updated_at

用法:
  SUPABASE_PAT=<你的Supabase PAT> python3 scripts/sync_fund_tags_full.py
"""

import os
import sys
import time
import json
import requests

PAT = os.environ.get('SUPABASE_PAT', '')
if not PAT:
    print('ERROR: SUPABASE_PAT not set')
    sys.exit(1)

MGMT_URL = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'
MGMT_H = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}

ZTJJ_URL = 'http://api.fund.eastmoney.com/ZTJJ/GetBKListByBKTypeNew?callback=?'
ZTJJ_H = {'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/ztjj/'}


def mgmt_query(sql):
    """执行 Supabase Management SQL，带重试"""
    for attempt in range(4):
        try:
            r = requests.post(MGMT_URL, headers=MGMT_H, json={'query': sql}, timeout=90)
            r.raise_for_status()
            return r.json()
        except requests.exceptions.RequestException as e:
            if attempt < 3:
                wait = (attempt + 1) * 5
                print(f'  [retry {attempt+1}] {e}, 等待{wait}s...')
                time.sleep(wait)
            else:
                raise


def esc(v):
    """SQL 值转义：None/空→NULL，字符串转义单引号"""
    if v is None:
        return 'NULL'
    if isinstance(v, str):
        if v == '':
            return "''"
        return "'" + v.replace("'", "''") + "'"
    if isinstance(v, float):
        import math
        if math.isnan(v) or math.isinf(v):
            return 'NULL'
        return str(round(v, 4))
    return str(v)


def fetch_tag_list():
    """从东财拉取完整标签列表"""
    print('[STEP 1] 拉取东财 ZTJJ 完整标签列表...')
    r = requests.get(ZTJJ_URL, headers=ZTJJ_H, timeout=15)
    r.raise_for_status()
    t = r.text
    s = t.index('(') + 1
    e = t.rindex(')')
    data = json.loads(t[s:e])['Data']

    hy1 = data.get('hy1', [])  # 行业一级 → tag_type='industry'
    hy2 = data.get('hy2', [])  # 行业二级 → tag_type='industry'
    gn = data.get('gn', [])    # 概念     → tag_type='concept'

    tags = []
    sort_order = 0
    for group, ttype in [(hy1, 'industry'), (hy2, 'industry'), (gn, 'concept')]:
        for item in group:
            sort_order += 1
            tags.append({
                'index_code': item['INDEXCODE'],
                'name': item['INDEXNAME'],
                'tag_type': ttype,
                'sort_order': sort_order,
            })

    print(f'  hy1(行业): {len(hy1)}, hy2(行业二级): {len(hy2)}, gn(概念): {len(gn)}')
    print(f'  合计: {len(tags)} 个标签')
    return tags


def main():
    tags = fetch_tag_list()

    # STEP 2: 清空旧数据 + 重写
    print('\n[STEP 2] TRUNCATE fund_tags 并重写...')
    mgmt_query('TRUNCATE TABLE public.fund_tags')

    # 批量插入（BATCH=50，间隔 1s）
    BATCH = 50
    total_inserted = 0
    for i in range(0, len(tags), BATCH):
        batch = tags[i:i + BATCH]
        values_parts = []
        for row in batch:
            name = esc(row['name'])
            ttype = esc(row['tag_type'])
            so = row['sort_order']
            values_parts.append(f"({name}, {ttype}, NULL, {so}, now())")

        sql = (
            "INSERT INTO public.fund_tags (name, tag_type, return_pct, sort_order, updated_at) "
            "VALUES " + ",".join(values_parts)
        )
        try:
            mgmt_query(sql)
            total_inserted += len(batch)
            print(f'  [{i//BATCH+1}] 写入 {len(batch)} 条 (累计 {total_inserted})')
        except Exception as e:
            print(f'  [INSERT 失败] batch {i//BATCH+1}: {e}')
            print(f'  SQL前300字符: {sql[:300]}')
            raise
        time.sleep(1)

    # 校验
    result = mgmt_query('SELECT count(*) AS c FROM public.fund_tags')
    cnt = result[0]['c'] if result else 0
    print(f'\n[DONE] fund_tags 重建完成: {cnt} 条记录')
    print(f'ROWS_AFFECTED={cnt}')

    # 抽查中药
    zy = mgmt_query("SELECT id, name, tag_type FROM public.fund_tags WHERE name = '中药'")
    print(f'  中药标签: {zy}')

    # 类型分布
    dist = mgmt_query("SELECT tag_type, count(*) AS c FROM public.fund_tags GROUP BY tag_type ORDER BY tag_type")
    print(f'  类型分布: {dist}')


if __name__ == '__main__':
    main()
