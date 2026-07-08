#!/usr/bin/env python3
"""
calc_style_factors.py — 计算 Barra 风格因子性价比评分 → 测试表 → 校验 → 原子切生产表

设计：
  每个 Barra 风格因子映射到一个/多个蛋卷代表指数（来自 index_eva 生产表），
  以代表指数的"历史估值分位"(0-100) 作为该因子的【估值分 value_score】：
      value_score 高 = 估值贵 = 性价比低
      value_score 低 = 估值便宜 = 性价比高
  cost_score = 100 - value_score（高 = 便宜 = 性价比高）。

  因子清单（宁空不假：动量因子无历史收益数据，暂不包含）：
    size       规模     代表 沪深300          V = pe_percentile
    value      价值     代表 300价值          V = (pe_percentile+pb_percentile)/2
    growth     成长     代表 中证白酒         V = pe_percentile
    quality    质量     代表 标普质量         V = pe_percentile（结合 ROE 解读）
    yield      红利     代表 中证红利         V = 100 - 股息率历史分位（高股息=便宜）
    volatility 波动率   代表 科创50           V = pe_percentile（高波动=贵）

  信号/颜色（估值视角，低估=绿/中性=蓝/高估=红）：
    V<=30  低估·关注    green  #00703c
    30<V<=70 估值适中  blue   #1d70b8
    V>70   高估·谨慎   red    #d4351c

管道同 fetch_index_eva.py：写 factor_scores_test → 校验 → 备份 → 原子切 factor_scores → 校验 → 清理。

用法：
  python3 scripts/calc_style_factors.py
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

FACTOR_COLS = ('factor_key', 'name', 'percentile', 'value_score', 'value_label',
               'cost_score', 'cost_label', 'signal', 'signal_label', 'color')
BACKUP_TABLE = '_factor_scores_backup'

# 因子定义：key / 中文名 / 代表指数代码 / 计算方式
FACTORS = [
    {'key': 'size',       'name': '规模',   'rep': 'SH000300', 'type': 'pe'},
    {'key': 'value',      'name': '价值',   'rep': 'SH000919', 'type': 'pe_pb'},
    {'key': 'growth',     'name': '成长',   'rep': 'SZ399997', 'type': 'pe'},
    {'key': 'quality',    'name': '质量',   'rep': 'SPCQVCP',  'type': 'pe'},
    {'key': 'yield',      'name': '红利',   'rep': 'SH000922', 'type': 'yield_inv'},
    {'key': 'volatility', 'name': '波动率', 'rep': 'SH000688', 'type': 'pe'},
]


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


def load_index_eva():
    rows = pg('SELECT index_code, name, pe_percentile, pb_percentile, dividend_yield, roe FROM index_eva')
    by_code = {r['index_code']: r for r in rows}
    dy_rows = [r for r in rows if r.get('dividend_yield') is not None and float(r['dividend_yield']) > 0]
    return by_code, dy_rows


def dividend_percentile_rank(dy_rows, target_dy):
    """target_dy 在全部有股息率指数中的分位（高股息=高分位）。返回 0-100。"""
    vals = sorted(float(r['dividend_yield']) for r in dy_rows)
    if not vals:
        return 50.0
    below = sum(1 for v in vals if v <= target_dy)
    return round(below / len(vals) * 100, 2)


def compute():
    by_code, dy_rows = load_index_eva()
    if not by_code:
        raise RuntimeError('index_eva 为空，请先运行 fetch_index_eva.py')
    dy_target = 'SH000922'
    dy_rank = dividend_percentile_rank(dy_rows, float(by_code[dy_target]['dividend_yield']))

    out = []
    for f in FACTORS:
        rep = by_code.get(f['rep'])
        if not rep:
            raise RuntimeError(f"代表指数缺失: {f['rep']} ({f['name']})")
        pe_p = float(rep.get('pe_percentile') or 0)
        pb_p = float(rep.get('pb_percentile') or 0)
        dy = float(rep.get('dividend_yield') or 0)
        roe = float(rep.get('roe') or 0)

        if f['type'] == 'pe':
            V = pe_p
        elif f['type'] == 'pe_pb':
            V = (pe_p + pb_p) / 2
        elif f['type'] == 'yield_inv':
            # 高股息 = 便宜 = 低估值分；用股息率分位取反
            V = 100 - dy_rank
        else:
            V = pe_p
        V = round(V, 1)

        value_score = round(V)
        cost_score = round(100 - V)
        if V <= 30:
            signal, signal_label, color = 'cheap', '低估·关注', '#00703c'
            value_label = '低估'
            cost_label = '性价比高'
        elif V <= 70:
            signal, signal_label, color = 'neutral', '估值适中', '#1d70b8'
            value_label = '适中'
            cost_label = '性价比适中'
        else:
            signal, signal_label, color = 'expensive', '高估·谨慎', '#d4351c'
            value_label = '高估'
            cost_label = '性价比低'

        # signal_label 带代表指数名，便于理解
        rep_name = rep.get('name') or f['rep']
        label_full = f'{rep_name} · {signal_label}'
        out.append({
            'factor_key': f['key'],
            'name': f['name'],
            'percentile': V,
            'value_score': value_score,
            'value_label': value_label,
            'cost_score': cost_score,
            'cost_label': cost_label,
            'signal': signal,
            'signal_label': label_full,
            'color': color,
        })
        print(f"  {f['name']:>4} 代表={rep_name:<7} V={V:>5}  估值分={value_score:>3}  性价比分={cost_score:>3}  {value_label}/{cost_label}")
    return out


def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


def build_insert(table, rows):
    cols = ', '.join(FACTOR_COLS)
    tuples = []
    for r in rows:
        vals = ', '.join(sql_val(r.get(c)) for c in FACTOR_COLS)
        tuples.append(f'({vals})')
    return f'INSERT INTO {table} ({cols}) VALUES\n' + ',\n'.join(tuples) + ';'


def validate(table):
    cnt = pg(f'SELECT COUNT(*) AS c FROM {table}')
    n = int(cnt[0]['c']) if cnt else 0
    if n < 6:
        raise RuntimeError(f'{table} 因子数不足: {n} < 6')
    keys = pg(f'SELECT factor_key FROM {table}')
    got = {r['factor_key'] for r in keys}
    for f in FACTORS:
        if f['key'] not in got:
            raise RuntimeError(f'{table} 缺少因子 {f["key"]}')
    print(f'  校验通过 {table}: {n} 个因子')
    return n


def main():
    print('== 计算 Barra 风格因子性价比评分 ==')
    rows = compute()

    print('  写入 factor_scores_test ...')
    pg('TRUNCATE TABLE factor_scores_test;')
    pg(build_insert('factor_scores_test', rows))
    n_test = validate('factor_scores_test')

    print('  备份 factor_scores → ' + BACKUP_TABLE)
    pg(f'CREATE TABLE IF NOT EXISTS {BACKUP_TABLE} (LIKE factor_scores INCLUDING ALL);')
    pg(f'TRUNCATE TABLE {BACKUP_TABLE};')
    pg(f'INSERT INTO {BACKUP_TABLE} OVERRIDING SYSTEM VALUE SELECT * FROM factor_scores;')
    print('  备份完成')

    try:
        pg('TRUNCATE TABLE factor_scores;')
        cols = ', '.join(FACTOR_COLS)
        pg(f'INSERT INTO factor_scores ({cols}) SELECT {cols} FROM factor_scores_test;')
        n_prod = validate('factor_scores')
        if n_prod != n_test:
            raise RuntimeError(f'生产因子数({n_prod})与测试({n_test})不一致')
    except Exception as e:
        print(f'  切换失败，回滚: {e}')
        pg('TRUNCATE TABLE factor_scores;')
        pg(f'INSERT INTO factor_scores OVERRIDING SYSTEM VALUE SELECT * FROM {BACKUP_TABLE};')
        sys.exit(f'已回滚 factor_scores，未切换。错误: {e}')

    pg(f'DROP TABLE IF EXISTS {BACKUP_TABLE};')
    print(f'== 完成：factor_scores 已更新为 {n_prod} 个因子 ==')


if __name__ == '__main__':
    main()
