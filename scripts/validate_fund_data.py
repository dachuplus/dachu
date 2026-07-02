#!/usr/bin/env python3
"""
fund_scores 数据质量校验脚本
用于每日 CI 更新后自动抽样校验数据正确性。

校验项目：
1. 行数比对 — fund_scores vs fund_combined
2. 分类分布 — 7大类分布一致性
3. 评分分布 — green/blue/orange/null 比例合理性
4. 随机抽样 — 抽取20只基金，逐字段比对 fund_scores vs fund_combined
5. 异常检测 — 收益率/回撤/夏普极端值告警

用法：
  python3 validate_fund_data.py [--sample 20] [--tolerance 0.02]

退出码：0=通过，1=告警（非致命），2=错误（需修复）
"""

import json
import sys
import os
import random
import requests
import argparse
from datetime import datetime

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
HEADERS = {'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}'}

# 基金类型简短中文映射
TYPE_CN = {
    '混合型': '混合型', '债券型': '债券型', '指数型': '指数型',
    '股票型': '股票型', 'FOF': 'FOF', 'QDII': 'QDII', '货币型': '货币型',
}

warnings = []
errors = []
passed = 0
total_checks = 0


def warn(msg):
    global warnings
    warnings.append(msg)
    print(f'  ⚠️  {msg}')


def error(msg):
    global errors
    errors.append(msg)
    print(f'  ❌ {msg}')


def ok(msg):
    global passed
    print(f'  ✅ {msg}')


def fetch_json(url):
    resp = requests.get(url, headers=HEADERS, timeout=30)
    if resp.status_code == 200:
        return resp.json()
    return None


def check_row_count(combined_count):
    """校验 1: 行数比对"""
    global total_checks
    total_checks += 1
    print('\n📋 校验1: 行数比对')

    url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count'
    resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                      'Prefer': 'count=exact', 'Range': '0-0'})
    count = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')

    diff = count - combined_count
    if abs(diff) > 5:
        error(f'fund_scores({count}) vs fund_combined({combined_count}) 差异 {diff}')
    elif abs(diff) > 0:
        warn(f'fund_scores({count}) vs fund_combined({combined_count}) 差异 {diff}')
    else:
        ok(f'fund_scores 行数 {count} = fund_combined 行数 {combined_count}')


def check_classification():
    """校验 2: 分类分布"""
    global total_checks
    total_checks += 1
    print('\n📋 校验2: 分类分布')

    # 获取 fund_scores 分类分布
    url = f'{SUPABASE_URL}/rest/v1/rpc/get_fund_scores_distribution'
    resp = requests.post(url, headers=HEADERS, json={}, timeout=30)
    if resp.status_code == 200:
        fs_dist = {r['t0']: r['cnt'] for r in resp.json()} if resp.json() else {}
    else:
        # Fallback: use REST with group
        fs_dist = {}
        for t0_type in ['混合型', '债券型', '指数型', '股票型', 'FOF', 'QDII', '货币型']:
            url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&t0=eq.{t0_type}'
            resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                              'Prefer': 'count=exact', 'Range': '0-0'})
            cnt = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')
            if cnt > 0:
                fs_dist[t0_type] = cnt

    # 获取 fund_combined 分类分布
    fc_dist = {}
    for t0_type in ['混合型', '债券型', '指数型', '股票型', 'FOF', 'QDII', '货币型']:
        url = f'{SUPABASE_URL}/rest/v1/fund_combined?select=count&t0=eq.{t0_type}'
        resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                          'Prefer': 'count=exact', 'Range': '0-0'})
        cnt = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')
        if cnt > 0:
            fc_dist[t0_type] = cnt

    # 也获取各分类评分覆盖
    score_dist = {}
    for t0_type in ['混合型', '债券型', '指数型', '股票型', 'FOF', 'QDII', '货币型']:
        url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&t0=eq.{t0_type}&k_all=not.is.null'
        resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                          'Prefer': 'count=exact', 'Range': '0-0'})
        cnt = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')
        score_dist[t0_type] = cnt

    has_issue = False
    for t0 in ['混合型', '债券型', '指数型', '股票型', 'FOF', 'QDII', '货币型']:
        fs_c = fs_dist.get(t0, 0)
        fc_c = fc_dist.get(t0, 0)
        sc_c = score_dist.get(t0, 0)
        if fs_c == 0 and fc_c > 0:
            error(f'{t0}: fund_scores 为 0 (应有 {fc_c})')
            has_issue = True
        elif abs(fs_c - fc_c) > 3:
            warn(f'{t0}: fund_scores {fs_c} vs fund_combined {fc_c}')
            has_issue = True
        elif sc_c == 0 and t0 not in ('货币型', 'QDII'):
            warn(f'{t0}: 分类有 {fs_c} 只但0只评分 (货币/QDII除外)')
            has_issue = True
        else:
            print(f'  {t0}: {fs_c} (评分: {sc_c})')

    if not has_issue:
        ok('7大类分布一致')


def check_score_grade():
    """校验 3: 评分分布"""
    global total_checks
    total_checks += 1
    print('\n📋 校验3: 评分分布')

    grades = ['green', 'blue', 'orange']
    dist = {}
    for g in grades:
        url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&score_grade=eq.{g}'
        resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                          'Prefer': 'count=exact', 'Range': '0-0'})
        cnt = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')
        dist[g] = cnt
        print(f'  {g}: {cnt}')

    total_scored = sum(dist.values())
    if total_scored > 0:
        green_pct = dist.get('green', 0) / total_scored * 100
        if green_pct < 10:
            warn(f'green 占比过低 ({green_pct:.1f}%)')
        elif green_pct > 30:
            warn(f'green 占比过高 ({green_pct:.1f}%)')
        else:
            ok(f'评分分布合理 (green {green_pct:.1f}%)')
    else:
        error('无评分数据')
        total_checks -= 1


def check_random_sample(sample_size):
    """校验 4: 随机抽样逐字段比对"""
    global total_checks
    total_checks += 1
    print(f'\n📋 校验4: 随机抽样 ({sample_size} 只基金)')

    # 获取有评分的基金列表
    url = (f'{SUPABASE_URL}/rest/v1/fund_scores?'
           f'select=c,n,t0,t1,company,fund_scale,manage_fee,ytd,r1y,r3y,r5y,return_all,'
           f'dd1y,sr1y,k_all,score_grade'
           f'&k_all=not.is.null&limit=1000')
    fs_rows = fetch_json(url) or []
    if not fs_rows:
        warn('无法获取 fund_scores 数据')
        return

    # 随机选 sample_size 只
    sample = random.sample(fs_rows, min(sample_size, len(fs_rows)))

    mismatch_count = 0
    checked_count = 0
    fields_to_check = ['company', 'fund_scale', 'manage_fee', 'ytd', 'r1y', 'r3y', 'r5y']

    for fs in sample:
        c = fs['c'].replace('.OF', '')
        url_fc = f'{SUPABASE_URL}/rest/v1/fund_combined?select={",".join(fields_to_check)}&c=eq.{c}&limit=1'
        fc_rows = fetch_json(url_fc)
        if not fc_rows:
            continue
        fc = fc_rows[0]

        for field in fields_to_check:
            fs_val = fs.get(field)
            fc_val = fc.get(field)
            checked_count += 1

            if fs_val is None and fc_val is None:
                continue
            if fs_val is None or fc_val is None:
                mismatch_count += 1
                continue
            if isinstance(fs_val, (int, float)) and isinstance(fc_val, (int, float)):
                if abs(fs_val - fc_val) > 0.02:
                    mismatch_count += 1
            elif str(fs_val) != str(fc_val):
                mismatch_count += 1

    mismatch_rate = mismatch_count / checked_count * 100 if checked_count > 0 else 0
    print(f'  抽查 {len(sample)} 只基金, 比对 {checked_count} 个字段')

    if mismatch_rate > 5:
        error(f'字段不一致率 {mismatch_rate:.1f}% (>5%)')
    elif mismatch_rate > 2:
        warn(f'字段不一致率 {mismatch_rate:.1f}% (>2%)')
    else:
        ok(f'字段一致率 {100-mismatch_rate:.1f}% (抽样{len(sample)}只)')


def check_extreme_values():
    """校验 5: 极端值检测"""
    global total_checks
    total_checks += 1
    print('\n📋 校验5: 极端值检测')

    checks = {
        'ytd': ('ytd', 200, -80),
        'r1y': ('r1y', 300, -90),
        'dd1y': ('dd1y', 0, -80),
        'sr1y': ('sr1y', 10, -10),
        'k_all': ('k_all', 100.1, -0.1),
    }

    has_extreme = False
    for name, (col, max_ok, min_ok) in checks.items():
        url = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&{col}=gt.{max_ok}'
        resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                          'Prefer': 'count=exact', 'Range': '0-0'})
        high = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')

        url2 = f'{SUPABASE_URL}/rest/v1/fund_scores?select=count&{col}=lt.{min_ok}'
        resp2 = requests.get(url2, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                            'Prefer': 'count=exact', 'Range': '0-0'})
        low = int(resp2.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp2.headers else '0')

        if high > 10:
            warn(f'{name}: {high} 条超出上限 {max_ok}')
            has_extreme = True
        if low > 50:
            warn(f'{name}: {low} 条低于下限 {min_ok}')
            has_extreme = True

    if not has_extreme:
        ok('无极端异常值')


def main():
    parser = argparse.ArgumentParser(description='fund_scores 数据质量校验')
    parser.add_argument('--sample', type=int, default=20, help='抽样数量')
    parser.add_argument('--tolerance', type=float, default=0.02, help='字段差异容忍度')
    args = parser.parse_args()

    print('=' * 60)
    print(f'🔍 fund_scores 数据质量校验')
    print(f'  时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  抽样数量: {args.sample}')
    print('=' * 60)

    # 获取 fund_combined 总数
    url = f'{SUPABASE_URL}/rest/v1/fund_combined?select=count'
    resp = requests.get(url, headers={'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}',
                                      'Prefer': 'count=exact', 'Range': '0-0'})
    combined_count = int(resp.headers.get('content-range', '0').split('/')[-1] if 'content-range' in resp.headers else '0')
    print(f'\nfund_combined 基准总数: {combined_count}')

    check_row_count(combined_count)
    check_classification()
    check_score_grade()
    check_random_sample(args.sample)
    check_extreme_values()

    # 汇总
    print('\n' + '=' * 60)
    print('📊 校验汇总')
    print(f'  通过: {passed}')
    print(f'  告警: {len(warnings)}')
    print(f'  错误: {len(errors)}')

    if warnings:
        for w in warnings:
            print(f'  ⚠️  {w}')

    if errors:
        for e in errors:
            print(f'  ❌ {e}')
        print('\n🔴 数据校验失败！请检查 CI 日志。')
        sys.exit(2)
    elif warnings:
        print('\n🟡 存在告警，建议人工复核。')
        sys.exit(1)
    else:
        print('\n🟢 数据校验全部通过！')
        sys.exit(0)


if __name__ == '__main__':
    main()
