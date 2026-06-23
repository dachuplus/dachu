#!/usr/bin/env python3
"""
验证 Supabase fund_scores 数据完整性
"""
import json
import subprocess
import os
import sys

SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', '')

if not ANON_KEY:
    print('WARNING: 未设置 SUPABASE_ANON_KEY，跳过验证')
    sys.exit(0)


def supabase_get(path, params=None):
    """通过 Supabase REST API 查询"""
    url = f'{SUPABASE_URL}/rest/v1/{path}'
    if params:
        qs = '&'.join(f'{k}={v}' for k, v in params.items())
        url += '?' + qs

    result = subprocess.run(
        ['curl', '-s', url,
         '-H', f'apikey: {ANON_KEY}',
         '-H', f'Authorization: Bearer {ANON_KEY}'],
        capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        print(f'ERROR: curl 失败: {result.stderr[:100]}')
        return None
    try:
        return json.loads(result.stdout)
    except:
        print(f'ERROR: JSON 解析失败: {result.stdout[:200]}')
        return None


def main():
    print('=' * 60)
    print('数据完整性验证')
    print('=' * 60)

    errors = 0

    # 1. 检查 fund_scores 数量
    print('\n[1] fund_scores 数量检查...')
    # 用 count 精确查询（需要 Accept: application/vnd.pgrst.object+json）
    url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count'
    result = subprocess.run(
        ['curl', '-s', url,
         '-H', f'apikey: {ANON_KEY}',
         '-H', f'Authorization: Bearer {ANON_KEY}',
         '-H', 'Accept: application/vnd.pgrst.object+json',
         '-H', 'Prefer: count=exact'],
        capture_output=True, text=True, timeout=15
    )
    try:
        data = json.loads(result.stdout)
        count = data.get('count', 0)
        print(f'  基金总数: {count}')
        if count < 15000:
            print(f'  WARNING: 基金数量少于预期（通常 ~19000 只）')
            errors += 1
    except:
        print(f'  ERROR: 无法解析响应: {result.stdout[:200]}')
        errors += 1

    # 2. 检查有靠谱分的基金
    print('\n[2] 靠谱分覆盖率检查...')
    # 随机抽样检查 k_all 和 score_grade
    sample = supabase_get('fund_scores', {
        'select': 'c,k1,k3,k_all,score_grade',
        'k_all': 'gt.0',
        'limit': '5',
        'order': 'k_all.desc'
    })
    if sample and len(sample) > 0:
        print(f'  抽查 Top 5 (k_all):')
        for s in sample:
            print(f'    {s["c"]}: k1={s.get("k1")}, k3={s.get("k3")}, k_all={s.get("k_all")}, grade={s.get("score_grade")}')
    else:
        print(f'  WARNING: 未找到有 k_all 分的基金')
        errors += 1

    # 2b. 检查 score_grade 分布
    print('\n[2b] score_grade 分布...')
    for grade in ['green', 'blue', 'orange', 'gray']:
        url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&score_grade=eq.{grade}'
        result = subprocess.run(
            ['curl', '-s', url,
             '-H', f'apikey: {ANON_KEY}',
             '-H', f'Authorization: Bearer {ANON_KEY}',
             '-H', 'Accept: application/vnd.pgrst.object+json',
             '-H', 'Prefer: count=exact'],
            capture_output=True, text=True, timeout=15
        )
        try:
            data = json.loads(result.stdout)
            cnt = data.get('count', 0)
            print(f'  {grade}: {cnt}只')
        except:
            print(f'  {grade}: 查询失败')

    # 3. 检查 meta 信息
    print('\n[3] fund_scores_meta 检查...')
    meta = supabase_get('fund_scores_meta', {'select': '*', 'limit': '1'})
    if meta and len(meta) > 0:
        m = meta[0]
        print(f'  更新时间: {m.get("tsq") or m.get("update_time")}')
        print(f'  总数: {m.get("total_count")}')
        print(f'  有分: {m.get("scored_count")}')
        print(f'  净值日期: {m.get("nav_date")}')
    else:
        print(f'  WARNING: 未找到元信息')
        errors += 1

    # 4. 分类统计
    print('\n[4] 分类覆盖检查...')
    categories = supabase_get('fund_scores', {
        'select': 't0',
        'limit': '100',
        'order': 'c'
    })
    if categories:
        cats = set()
        for c in categories:
            cats.add(c.get('t0', ''))
        print(f'  覆盖分类: {sorted(cats)}')
    else:
        print(f'  WARNING: 无法查询分类')
        errors += 1

    print('\n' + '=' * 60)
    if errors == 0:
        print('✅ 数据完整性验证通过！')
    else:
        print(f'⚠️  发现 {errors} 个问题，请检查日志。')
    print('=' * 60)


if __name__ == '__main__':
    main()
