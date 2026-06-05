#!/usr/bin/env python3
"""
migrate_to_supabase.py - 将微信云数据库数据迁移到 Supabase

用法：
  1. 先在 Supabase Dashboard → SQL Editor 执行 supabase-schema.sql 建表
  2. 配置 SUPABASE_URL 和 SUPABASE_ANON_KEY（或传入环境变量）
  3. python3 migrate_to_supabase.py [--all] [--funds] [--tougu] [--skip-clean]

数据来源：NDJSON 文件（从微信云数据库导出）
  - fund_scores: scripts/funds_full.ndjson (~20000条)
  - tougu_products: scripts/tougu_products.ndjson (~103条)
"""
import json
import os
import sys
import time
import argparse

# Supabase 配置
SUPABASE_URL = os.environ.get('SUPABASE_URL', 'https://tqhtegazxykkqfcpejky.supabase.co')
SUPABASE_ANON_KEY = os.environ.get('SUPABASE_ANON_KEY', 'YOUR_ANON_KEY')

# 数据文件路径
SCRIPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'asset-config-miniapp', 'scripts')
FUNDS_NDJSON = os.path.join(SCRIPT_DIR, 'funds_full.ndjson')
TOUGU_NDJSON = os.path.join(SCRIPT_DIR, 'tougu_products.ndjson')

BATCH_SIZE = 1000  # Supabase REST API 批量插入大小

# ========== Supabase REST API 封装 ==========

def supabase_post(table, data, method='POST'):
    """通过 Supabase REST API 操作数据"""
    import urllib.request
    import urllib.error

    url = f'{SUPABASE_URL}/rest/v1/{table}'
    if method == 'DELETE':
        url += '?c=not.is.null'  # 删除所有（需要一个条件，这里用永真条件）
        if table == 'tougu_products':
            url = f'{SUPABASE_URL}/rest/v1/{table}?name=not.is.null'

    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }

    body = json.dumps(data, ensure_ascii=False).encode('utf-8') if data else b''

    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return e.code, error_body


def supabase_delete_all(table):
    """删除表中所有数据（使用 RPC 或逐批删除）"""
    import urllib.request
    import urllib.error

    # 使用 Supabase RPC 方式（需要先在 SQL Editor 创建 delete_all 函数）
    # 或者直接通过 REST API 删除
    # 先尝试用 POST with filter
    url = f'{SUPABASE_URL}/rest/v1/{table}?id=gt.0'
    headers = {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': f'Bearer {SUPABASE_ANON_KEY}',
    }
    req = urllib.request.Request(url, headers=headers, method='DELETE')
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return True
    except urllib.error.HTTPError as e:
        print(f'  清空失败: {e.code} - {e.read().decode()[:200]}')
        return False


def supabase_insert_batch(table, rows):
    """批量插入数据"""
    status, body = supabase_post(table, rows, method='POST')
    if status in (200, 201):
        return len(rows)
    print(f'  插入失败: {status} - {body[:300]}')
    return 0


# ========== 迁移函数 ==========

def migrate_funds(skip_clean=False):
    """迁移 fund_scores 数据"""
    if not os.path.exists(FUNDS_NDJSON):
        print(f'  文件不存在: {FUNDS_NDJSON}')
        print(f'  请先运行 full_fund_update.py 生成 NDJSON')
        return 0

    # 统计总行数
    total_lines = sum(1 for line in open(FUNDS_NDJSON, 'r', encoding='utf-8') if line.strip())
    print(f'  数据源: {FUNDS_NDJSON}')
    print(f'  总记录: {total_lines}条')

    # 清空旧数据
    if not skip_clean:
        print(f'  清空旧 fund_scores 数据...')
        supabase_delete_all('fund_scores')
        time.sleep(0.5)

    # 字段映射：NDJSON 字段直接对应 Supabase 列
    # 需要去掉 _id（如果存在）
    BATCH_SIZE_FUNDS = 500  # fund_scores 数据量大，减小批次

    batch = []
    batch_num = 0
    total_inserted = 0

    with open(FUNDS_NDJSON, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                # 去掉 _id 字段（Supabase 自增 id）
                doc.pop('_id', None)
                batch.append(doc)
            except json.JSONDecodeError as e:
                print(f'  JSON 解析失败: {e}')
                continue

            if len(batch) >= BATCH_SIZE_FUNDS:
                batch_num += 1
                inserted = supabase_insert_batch('fund_scores', batch)
                total_inserted += inserted
                print(f'  第{batch_num}批: 插入{inserted}条（累计{total_inserted}/{total_lines}）')
                batch = []
                time.sleep(0.1)

    if batch:
        batch_num += 1
        inserted = supabase_insert_batch('fund_scores', batch)
        total_inserted += inserted
        print(f'  第{batch_num}批: 插入{inserted}条（累计{total_inserted}/{total_lines}）')

    return total_inserted


def migrate_tougu(skip_clean=False):
    """迁移 tougu_products 数据"""
    if not os.path.exists(TOUGU_NDJSON):
        print(f'  文件不存在: {TOUGU_NDJSON}')
        print(f'  请先运行 fetch_tougu.py 生成 NDJSON')
        return 0

    total_lines = sum(1 for line in open(TOUGU_NDJSON, 'r', encoding='utf-8') if line.strip())
    print(f'  数据源: {TOUGU_NDJSON}')
    print(f'  总记录: {total_lines}条')

    # 清空旧数据
    if not skip_clean:
        print(f'  清空旧 tougu_products 数据...')
        supabase_delete_all('tougu_products')
        time.sleep(0.5)

    # 字段映射：只保留 Supabase 表中存在的列
    TOUGU_COLUMNS = {
        'name', 'company', 'type', 'typeName', 'desc', 'tags',
        'return3m', 'return1y', 'maxDrawdown', 'url', 'updateDate', 'dataSource'
    }

    batch = []
    batch_num = 0
    total_inserted = 0

    with open(TOUGU_NDJSON, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
                doc.pop('_id', None)

                # 只保留目标列
                cleaned = {k: v for k, v in doc.items() if k in TOUGU_COLUMNS}

                # tags 字段处理：如果是空格分隔的字符串，转成数组
                if 'tags' in cleaned and isinstance(cleaned['tags'], str):
                    cleaned['tags'] = [t.strip() for t in cleaned['tags'].split() if t.strip()]
                elif 'tags' not in cleaned:
                    cleaned['tags'] = []

                batch.append(cleaned)
            except json.JSONDecodeError as e:
                print(f'  JSON 解析失败: {e}')
                continue

    # 一次插入所有投顾产品（只有 103 条）
    if batch:
        inserted = supabase_insert_batch('tougu_products', batch)
        total_inserted += inserted
        print(f'  插入{inserted}条投顾产品')

    return total_inserted


def insert_fund_meta(nav_date, total_count, scored_count):
    """写入 fund_scores_meta"""
    meta = {
        'update_time': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_count': total_count,
        'scored_count': scored_count,
        'nav_date': nav_date,
    }
    status, body = supabase_post('fund_scores_meta', meta)
    if status in (200, 201):
        print(f'  写入元信息: 总数{total_count}, 有分{scored_count}, 日期{nav_date}')
    else:
        print(f'  元信息写入失败: {status} - {body[:200]}')


def main():
    parser = argparse.ArgumentParser(description='迁移微信云数据库数据到 Supabase')
    parser.add_argument('--all', action='store_true', help='迁移全部数据')
    parser.add_argument('--funds', action='store_true', help='迁移 fund_scores')
    parser.add_argument('--tougu', action='store_true', help='迁移 tougu_products')
    parser.add_argument('--skip-clean', action='store_true', help='跳过清空旧数据')
    args = parser.parse_args()

    if not (args.all or args.funds or args.tougu):
        args.all = True

    print('=' * 55)
    print('  微信云数据库 → Supabase 数据迁移')
    print(f'  目标: {SUPABASE_URL}')
    print('=' * 55)

    if args.all or args.funds:
        print('\n[fund_scores] 迁移靠谱基金数据...')
        count = migrate_funds(skip_clean=args.skip_clean)
        print(f'  完成: {count}条\n')

    if args.all or args.tougu:
        print('[tougu_products] 迁移投顾产品数据...')
        count = migrate_tougu(skip_clean=args.skip_clean)
        print(f'  完成: {count}条\n')

    print('=' * 55)
    print('  迁移完成!')
    print('=' * 55)


if __name__ == '__main__':
    main()
