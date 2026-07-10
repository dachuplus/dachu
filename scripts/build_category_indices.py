#!/usr/bin/env python3
"""
build_category_indices.py — 从 fund_scores 按一级分类(t0)等权构建基金指数 → fund_category_indices

统一口径：每一类 = 该一级分类下所有基金各周期收益率的等权平均值（同口径、可横比）。
覆盖 7 大类：股票型 / 债券型 / 混合型 / 指数型 / FOF / QDII / 货币型。
指标：YTD / 近1月 / 近3月 / 近6月 / 近1年 / 近3年 / 近5年（按列可用情况自动纳入）。

管道：建表(IF NOT EXISTS) → TRUNCATE → INSERT → 完成。

用法：
  SUPABASE_PAT=... python3 scripts/build_category_indices.py
"""
import os
import sys
import json
import subprocess
import datetime

def _load_env_local():
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

PAT = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN')
if not PAT:
    sys.exit('请设置环境变量 SUPABASE_PAT')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

DDL = """
CREATE TABLE IF NOT EXISTS fund_category_indices (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  wind_code text,
  name_cn text,
  category text,
  basic_info jsonb,
  market_perf jsonb,
  annual_perf jsonb,
  valuation jsonb,
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_fci_cat ON fund_category_indices(category);
ALTER TABLE fund_category_indices ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_fci ON fund_category_indices;
CREATE POLICY anon_read_fci ON fund_category_indices FOR SELECT USING (true);
"""

# 一级分类 t0 → (展示名, 合成代码)
CAT_MAP = [
    ('股票型', '股票型', 'CAT-EQUITY'),
    ('债券型', '债券型', 'CAT-BOND'),
    ('混合型', '混合型', 'CAT-HYBRID'),
    ('指数型', '指数型', 'CAT-INDEX'),
    ('FOF', 'FOF', 'CAT-FOF'),
    ('QDII', 'QDII', 'CAT-QDII'),
    ('货币型', '货币型', 'CAT-MONEY'),
]
PERIODS = [('ytd', 'ytd'), ('r1m', 'r1m'), ('r3m', 'r3m'), ('r6m', 'r6m'),
           ('r1y', 'r1y'), ('r3y', 'r3y'), ('r5y', 'r5y')]


def pg(sql, timeout=300):
    payload = json.dumps({'query': sql})
    r = subprocess.run(['curl', '-s', '--max-time', str(timeout), '-X', 'POST', MGMT_API,
                        '-H', f'Authorization: Bearer {PAT}', '-H', 'Content-Type: application/json',
                        '-d', payload], capture_output=True, text=True, timeout=timeout + 10)
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


def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def main():
    print('== 建表 fund_category_indices ==')
    for stmt in [s.strip() for s in DDL.strip().split(';') if s.strip()]:
        pg(stmt)
    print('  表就绪')

    # 聚合：每类各周期等权平均
    cols = ', '.join(f'AVG({c}) AS {c}' for _, c in PERIODS) + ', COUNT(*) AS cnt'
    sql = f"SELECT t0, {cols} FROM fund_scores WHERE t0 IS NOT NULL GROUP BY t0"
    rows = pg(sql)
    by_t0 = {r['t0']: r for r in rows} if rows else {}

    today = datetime.date.today().isoformat()
    tuples = []
    for t0, disp, code in CAT_MAP:
        r = by_t0.get(t0)
        if not r or not r.get('cnt'):
            print('  跳过 %s（无数据）' % disp)
            continue
        cnt = int(r['cnt'])
        market = {}
        for col, c in PERIODS:
            v = r.get(c)
            if v is not None:
                market[col] = round(float(v), 2)  # 收益率列已为百分比数值(如 30.34 表示 30.34%)
        basic = {
            'ingredient_num': str(cnt),
            'category': disp,
            'weighting_mode': '等权平均',
            'caliber': '一级分类内所有基金各周期收益率等权平均',
            'last_date': today,
        }
        t = (sql_val(code), sql_val(disp), sql_val(t0),
             sql_val(json.dumps(basic, ensure_ascii=False)) + '::jsonb',
             sql_val(json.dumps(market, ensure_ascii=False)) + '::jsonb',
             sql_val(json.dumps({}, ensure_ascii=False)) + '::jsonb',
             sql_val(json.dumps({}, ensure_ascii=False)) + '::jsonb')
        tuples.append('(' + ', '.join(t) + ')')
        print('  %-5s 成分%6d只  近1月=%s%% 近1年=%s%% 近3年=%s%% 近5年=%s%%' % (
            disp, cnt,
            market.get('r1m', '-'), market.get('r1y', '-'),
            market.get('r3y', '-'), market.get('r5y', '-')))

    print('\n== 写入 fund_category_indices (%d 类) ==' % len(tuples))
    pg('TRUNCATE TABLE fund_category_indices;')
    if tuples:
        sql = ('INSERT INTO fund_category_indices (wind_code, name_cn, category, basic_info, market_perf, annual_perf, valuation) '
               'VALUES\n' + ',\n'.join(tuples) + ';')
        pg(sql)
    cnt = pg('SELECT COUNT(*) AS c FROM fund_category_indices')
    print('  完成，fund_category_indices 当前 %s 条' % cnt[0]['c'])


if __name__ == '__main__':
    main()
