#!/usr/bin/env python3
"""
create_signal_tables.py — 创建指标信号相关 Supabase 表（生产 + 测试）

表设计：
  index_eva       生产表：蛋卷指数估值（63 个指数），anon 只读 SELECT
  index_eva_test  测试表：抓取/计算先写这里，校验后原子切生产，anon 全开
  factor_scores   生产表：Barra 风格因子性价比评分，anon 只读 SELECT
  factor_scores_test 测试表：同上管道

用法：
  python3 scripts/create_signal_tables.py
（优先 SUPABASE_PAT，回退 SUPABASE_MGMT_TOKEN；旧过期 MGMT_TOKEN 已弃用）
"""
import os
import sys
import json
import subprocess

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
-- ============ index_eva 生产表 ============
CREATE TABLE IF NOT EXISTS index_eva (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  index_code text,
  name text,
  ttype int,
  cat text,
  pe numeric,
  pe_percentile numeric,
  pb numeric,
  pb_percentile numeric,
  dividend_yield numeric,
  roe numeric,
  eva_type text,
  date text,
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_index_eva_cat ON index_eva(cat);
CREATE INDEX IF NOT EXISTS idx_index_eva_ttype ON index_eva(ttype);
ALTER TABLE index_eva ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_index_eva ON index_eva;
CREATE POLICY anon_read_index_eva ON index_eva FOR SELECT USING (true);

-- ============ index_eva_test 测试表 ============
CREATE TABLE IF NOT EXISTS index_eva_test (LIKE index_eva INCLUDING ALL);
ALTER TABLE index_eva_test ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_all_index_eva_test ON index_eva_test;
CREATE POLICY anon_all_index_eva_test ON index_eva_test FOR ALL USING (true) WITH CHECK (true);

-- ============ factor_scores 生产表 ============
CREATE TABLE IF NOT EXISTS factor_scores (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  factor_key text,
  name text,
  percentile numeric,
  value_score numeric,
  value_label text,
  cost_score numeric,
  cost_label text,
  signal text,
  signal_label text,
  color text,
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_factor_scores_key ON factor_scores(factor_key);
ALTER TABLE factor_scores ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_factor_scores ON factor_scores;
CREATE POLICY anon_read_factor_scores ON factor_scores FOR SELECT USING (true);

-- ============ factor_scores_test 测试表 ============
CREATE TABLE IF NOT EXISTS factor_scores_test (LIKE factor_scores INCLUDING ALL);
ALTER TABLE factor_scores_test ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_all_factor_scores_test ON factor_scores_test;
CREATE POLICY anon_all_factor_scores_test ON factor_scores_test FOR ALL USING (true) WITH CHECK (true);
"""


def main():
    print('== 创建信号数据表（index_eva / factor_scores 含测试表）==')
    # 分语句执行，便于定位失败
    for stmt in [s.strip() for s in SQL.strip().split(';') if s.strip()]:
        try:
            pg(stmt)
            print(f'  OK: {stmt[:60]}...')
        except Exception as e:
            print(f'  ERR: {stmt[:60]}... -> {e}')
            sys.exit(1)
    # 校验存在
    rows = pg("SELECT table_name FROM information_schema.tables WHERE table_name IN ('index_eva','index_eva_test','factor_scores','factor_scores_test') ORDER BY table_name")
    names = [r['table_name'] for r in rows] if isinstance(rows, list) else []
    print('存在表:', names)
    missing = set(['index_eva', 'index_eva_test', 'factor_scores', 'factor_scores_test']) - set(names)
    if missing:
        sys.exit(f'缺失表: {missing}')
    print('全部建表成功。')


if __name__ == '__main__':
    main()
