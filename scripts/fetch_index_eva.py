#!/usr/bin/env python3
"""
fetch_index_eva.py — 抓取蛋卷指数估值 → 测试表 → 校验 → 原子切生产表

数据来源：https://danjuanfunds.com/djapi/index_eva/dj （63 个指数）
字段归一化：
  ttype(字符串 "1/2/3") → int + cat(broad/strategy/sector)
  pe_percentile / pb_percentile (0-1 比例) → ×100 百分比
  yeild(股息率 0-1) → dividend_yield 百分比
  roe(0-1) → 百分比
  date("07-08") → 当前年前缀 "2026-07-08"

管道：
  fetch → 增量断点续传写 index_eva_test(按 index_code 幂等 upsert + 进度文件) → 校验
       → 校验通过则备份 index_eva → 原子切 → 校验 → 清理备份与进度
失败则回滚备份，绝不产生空生产表。

断点续传：每次抓取按 index_code 逐条 upsert 到测试表，并写入 index_eva_progress.json
记录已完成项；进程中断后重跑会从断点继续（已写入项跳过），无需重抓全部。

用法：
  python3 scripts/fetch_index_eva.py            # 增量续传（检测到进度则继续）
  python3 scripts/fetch_index_eva.py --reset    # 强制清空测试表与进度，重新全量抓取
（优先 SUPABASE_PAT，回退 SUPABASE_MGMT_TOKEN；旧过期 MGMT_TOKEN 已弃用）
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
from datetime import datetime

def _load_env_local():
    """从项目根目录 .env.local 载入变量，确保使用有效 SUPABASE_PAT，避开可能过期的 SUPABASE_MGMT_TOKEN 环境变量。"""
    p = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env.local')
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())
    except FileNotFoundError:
        pass
_load_env_local()

MGMT_TOKEN = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_PAT（Supabase Personal Access Token）')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

API_URL = 'https://danjuanfunds.com/djapi/index_eva/dj'
CAT_MAP = {'1': 'broad', '2': 'strategy', '3': 'sector'}
EVA_COLS = ('index_code', 'name', 'ttype', 'cat', 'pe', 'pe_percentile',
            'pb', 'pb_percentile', 'dividend_yield', 'roe', 'eva_type', 'date')
BACKUP_TABLE = '_index_eva_backup'
# 断点续传进度文件（记录已写入测试表的 index_code，崩溃后可从此处恢复）
PROGRESS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'index_eva_progress.json'
)


def pg(sql, timeout=300):
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
        raise RuntimeError(resp['message'][:300])
    return resp


def fetch_danjuan(retries=3):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(API_URL, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read().decode('utf-8')
            d = json.loads(raw)
            items = (d.get('data') or {}).get('items') or []
            if not items:
                raise RuntimeError('API 返回空 items')
            return items
        except Exception as e:
            last = e
            print(f'  fetch 重试 {i+1}/{retries}: {e}')
            time.sleep(2)
    raise RuntimeError(f'蛋卷 API 抓取失败: {last}')


def normalize(items):
    year = datetime.now().year
    rows = []
    for it in items:
        ttype = str(it.get('ttype', '1'))
        cat = CAT_MAP.get(ttype, 'broad')
        try:
            pep = round(float(it.get('pe_percentile') or 0) * 100, 2)
        except (TypeError, ValueError):
            pep = 0
        try:
            pbp = round(float(it.get('pb_percentile') or 0) * 100, 2)
        except (TypeError, ValueError):
            pbp = 0
        try:
            dy = round(float(it.get('yeild') or 0) * 100, 2)
        except (TypeError, ValueError):
            dy = 0
        try:
            roe = round(float(it.get('roe') or 0) * 100, 2)
        except (TypeError, ValueError):
            roe = 0
        raw_date = str(it.get('date') or '')
        full_date = f'{year}-{raw_date}' if raw_date else ''
        rows.append({
            'index_code': str(it.get('index_code') or ''),
            'name': str(it.get('name') or ''),
            'ttype': int(ttype) if ttype.isdigit() else 1,
            'cat': cat,
            'pe': _num(it.get('pe')),
            'pe_percentile': pep,
            'pb': _num(it.get('pb')),
            'pb_percentile': pbp,
            'dividend_yield': dy,
            'roe': roe,
            'eva_type': str(it.get('eva_type') or ''),
            'date': full_date,
        })
    return rows


def _num(v):
    if v is None or v == '':
        return 0
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0


def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def build_insert(table, rows):
    cols = ', '.join(EVA_COLS)
    tuples = []
    for r in rows:
        vals = ', '.join(sql_val(r.get(c)) for c in EVA_COLS)
        tuples.append(f'({vals})')
    return f'INSERT INTO {table} ({cols}) VALUES\n' + ',\n'.join(tuples) + ';'


def validate(table, rows_expected):
    cnt = pg(f'SELECT COUNT(*) AS c FROM {table}')
    n = int(cnt[0]['c']) if cnt else 0
    if n < 60:
        raise RuntimeError(f'{table} 行数不足: {n} < 60')
    cats = pg(f"SELECT cat, COUNT(*) AS c FROM {table} GROUP BY cat")
    catmap = {r['cat']: int(r['c']) for r in cats}
    for need in ('broad', 'strategy', 'sector'):
        if catmap.get(need, 0) == 0:
            raise RuntimeError(f'{table} 缺少分类 {need}')
    print(f'  校验通过 {table}: {n} 行, 分类={catmap}')
    return n


# ===== 断点续传进度 =====
def load_progress():
    try:
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_progress(done):
    tmp = PROGRESS_FILE + '.tmp'
    with open(tmp, 'w') as f:
        json.dump({'done': done, 'updated_at': datetime.now().isoformat()},
                  f, ensure_ascii=False)
    os.replace(tmp, PROGRESS_FILE)


def clear_progress():
    try:
        os.remove(PROGRESS_FILE)
    except FileNotFoundError:
        pass


def upsert_row(table, row):
    """按 index_code 幂等写入（先删后插），单条独立，支持断点续传。"""
    code = sql_val(row['index_code'])
    pg(f'DELETE FROM {table} WHERE index_code = {code};')
    pg(build_insert(table, [row]))


def main():
    print('== 抓取蛋卷指数估值（增量断点续传 → 测试表 → 校验 → 同步生产） ==')
    reset = '--reset' in sys.argv

    progress = None if reset else load_progress()
    fresh = reset or not progress

    if fresh:
        print('  初始化：清空测试表与续传进度')
        pg('TRUNCATE TABLE index_eva_test;')
        clear_progress()
        done = []
    else:
        print(f'  发现断点续传进度：已完成 {len(progress.get("done", []))} 个指数，继续写入剩余项')
        done = list(progress.get('done', []))

    done_set = set(done)

    items = fetch_danjuan()
    print(f'  抓到 {len(items)} 个指数')

    # 1) 增量写入测试表（每个指数独立 upsert，写入后立即记录进度，崩溃后可恢复）
    for it in items:
        code = str(it.get('index_code') or '')
        if code in done_set:
            continue
        row = normalize([it])[0]
        upsert_row('index_eva_test', row)
        done.append(code)
        done_set.add(code)
        save_progress(done)
        print(f'    + 写入 {code} {row["name"]}')

    print('  测试表写入完成，开始校验...')
    n_test = validate('index_eva_test', len(items))

    # 2) 备份生产表
    print('  备份 index_eva → ' + BACKUP_TABLE)
    pg(f'CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (LIKE index_eva INCLUDING ALL);')
    pg(f'TRUNCATE TABLE {BACKUP_TABLE};')
    pg(f'INSERT INTO {BACKUP_TABLE} OVERRIDING SYSTEM VALUE SELECT * FROM index_eva;')
    print('  备份完成')

    # 3) 原子切换（测试表校验通过后同步生产；失败回滚，绝不产生空生产表）
    try:
        pg(f'TRUNCATE TABLE index_eva;')
        cols = ', '.join(EVA_COLS)
        pg(f'INSERT INTO index_eva ({cols}) SELECT {cols} FROM index_eva_test;')
        n_prod = validate('index_eva', n_test)
        if n_prod != n_test:
            raise RuntimeError(f'生产行数({n_prod})与测试({n_test})不一致')
    except Exception as e:
        print(f'  切换失败，回滚: {e}')
        pg(f'TRUNCATE TABLE index_eva;')
        pg(f'INSERT INTO index_eva OVERRIDING SYSTEM VALUE SELECT * FROM {BACKUP_TABLE};')
        clear_progress()  # 清理进度，下次运行重新抓取
        sys.exit(f'已回滚 index_eva，未切换。错误: {e}')

    # 4) 清理备份 + 进度
    pg(f'DROP TABLE IF EXISTS {BACKUP_TABLE};')
    clear_progress()
    print(f'== 完成：index_eva 已同步 {n_prod} 个指数（测试表校验通过）==')


if __name__ == '__main__':
    main()
