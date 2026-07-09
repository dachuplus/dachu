#!/usr/bin/env python3
"""
create_jqr_tables.py — 创建「韭圈特色指标」Supabase 表（生产 + 测试）

设计：
  jqr_indicators      生产表：通用指标快照表。每个指标每日一行，detail 存子指标/分位。
    metric: 'fear_greed'(恐贪指数) | 'market_temp'(市场温度) | 'fund_issuance'(基金发行热度)
    date:   数据日期
    value:  指标主值（恐贪/温度 0~100；发行热度用归一化分位或规模）
    detail: jsonb，存子指标明细与历史分位等
  jqr_indicators_test 测试表：抓取/计算先写这里校验，再切生产，anon 全开

用法：
  python3 scripts/create_jqr_tables.py
（优先 SUPABASE_PAT，回退 SUPABASE_MGMT_TOKEN；从 .env.local 载入以避开过期环境变量）
"""
import os
import sys
import json
import subprocess

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

MGMT_TOKEN = os.environ.get('SUPABASE_PAT') or os.environ.get('SUPABASE_MGMT_TOKEN')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_PAT（Supabase Personal Access Token）')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'


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


SQL = """
-- ============ jqr_indicators 生产表 ============
CREATE TABLE IF NOT EXISTS jqr_indicators (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  metric text NOT NULL,
  date text NOT NULL,
  value numeric,
  detail jsonb,
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_jqr_metric_date ON jqr_indicators(metric, date);
ALTER TABLE jqr_indicators ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_jqr_indicators ON jqr_indicators;
CREATE POLICY anon_read_jqr_indicators ON jqr_indicators FOR SELECT USING (true);

-- ============ jqr_indicators_test 测试表 ============
CREATE TABLE IF NOT EXISTS jqr_indicators_test (LIKE jqr_indicators INCLUDING ALL);
ALTER TABLE jqr_indicators_test ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_all_jqr_indicators_test ON jqr_indicators_test;
CREATE POLICY anon_all_jqr_indicators_test ON jqr_indicators_test FOR ALL USING (true) WITH CHECK (true);
"""


def main():
    print('== 创建韭圈特色指标表（jqr_indicators / jqr_indicators_test）==')
    for stmt in [s.strip() for s in SQL.strip().split(';') if s.strip()]:
        try:
            pg(stmt)
            print(f'  OK: {stmt[:60]}...')
        except Exception as e:
            print(f'  ERR: {stmt[:60]}... -> {e}')
            sys.exit(1)
    rows = pg("SELECT table_name FROM information_schema.tables WHERE table_name IN ('jqr_indicators','jqr_indicators_test') ORDER BY table_name")
    names = [r['table_name'] for r in rows] if isinstance(rows, list) else []
    print('存在表:', names)
    missing = set(['jqr_indicators', 'jqr_indicators_test']) - set(names)
    if missing:
        sys.exit(f'缺失表: {missing}')
    print('全部建表成功。')


if __name__ == '__main__':
    main()
