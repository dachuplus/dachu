#!/usr/bin/env python3
"""
一次性执行：1) 清理管理费 "（每年）" 后缀 2) 同步分类
"""
import json
import subprocess
import os

MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or ''
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

def pg(sql):
    """Execute SQL via Supabase Management API using curl"""
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=120
    )
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:100]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        resp = json.loads(t)
    except json.JSONDecodeError:
        raise RuntimeError(f'Non-JSON response: {t[:200]}')
    if isinstance(resp, dict) and resp.get('message'):
        raise RuntimeError(resp['message'][:200])
    return resp

# ── 步骤 1: 清理管理费 "（每年）" ──────────────────────────────────
print('=' * 60)
print('步骤 1: 清理管理费 "（每年）" 后缀')
print('=' * 60)

# 先统计
result = pg("SELECT count(*) as cnt FROM fund_scores WHERE manage_fee LIKE '%（每年）'")
before = result[0]['cnt'] if result else 0
print(f'  清理前含"（每年）"的记录: {before}')

if before > 0:
    result = pg("UPDATE fund_scores SET manage_fee = REPLACE(manage_fee, '（每年）', '') WHERE manage_fee LIKE '%（每年）'")
    print(f'  ✓ 已清理')

# 验证
result = pg("SELECT manage_fee, count(*) as cnt FROM fund_scores WHERE manage_fee IS NOT NULL GROUP BY manage_fee ORDER BY cnt DESC LIMIT 10")
print('  清理后 TOP 10 管理费:')
for row in result:
    print(f'    {row["manage_fee"]}: {row["cnt"]} 只')

# ── 步骤 2: 同步分类 ──────────────────────────────────────────────
print()
print('=' * 60)
print('步骤 2: 同步分类 fund_combined → fund_scores')
print('=' * 60)

# 2a: 更新不一致的分类
result = pg("""
UPDATE fund_scores fs SET
  t0 = fc.t0,
  t1 = fc.t1
FROM fund_combined fc
WHERE REPLACE(fs.c, '.OF', '') = fc.c
  AND fs.t0 IS DISTINCT FROM fc.t0
""")
print('  ✓ 分类更新完成')

# 2b: 插入 fund_combined 中有但 fund_scores 中没有的基金
result = pg("""
INSERT INTO fund_scores (c, n, t0, t1, company, fund_scale, manage_fee)
SELECT fc.c || '.OF', fc.name, fc.t0, fc.t1, fc.company, fc.fund_scale, fc.manage_fee
FROM fund_combined fc
WHERE NOT EXISTS (
    SELECT 1 FROM fund_scores fs
    WHERE REPLACE(fs.c, '.OF', '') = fc.c
)
RETURNING c
""")
if result:
    print(f'  ✓ 新增 {len(result)} 只基金')
else:
    print('  无需新增（两表基金数量一致）')

# 2c: 验证分类分布
result = pg("SELECT t0, count(*) as cnt, count(k_all) as scored FROM fund_scores GROUP BY t0 ORDER BY cnt DESC")
print('  验证分类分布:')
for row in result:
    print(f'    {row["t0"]}: {row["cnt"]} 只 (评分: {row["scored"]})')

total = pg("SELECT count(*) as cnt FROM fund_scores")
print(f'\n  fund_scores 总计: {total[0]["cnt"]} 只')

print('\n✅ 管理费清理 + 分类同步 完成')
