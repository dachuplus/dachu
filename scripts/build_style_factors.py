#!/usr/bin/env python3
"""
build_style_factors.py — 计算指标信号·风格因子全部三类信号 → style_factors 表

设计（统一口径：全部用中证/公开指数，5年历史分位算估值分）：
  category = 'stock'   股票风格（Barra 六因子，全用中证指数）
      规模  沪深300 (000300)        估值分 = 现价近5年分位
      价值  中证800价值 (000824)
      成长  中证800成长 (000944)
      质量  中证质量 (候选 000969/000979/000915，失败则跳过宁空不假)
      红利  中证红利 (000922)        高股息=便宜 → 估值分反取
      波动率 中证500 (000905)        高波动指数=贵
  category = 'bond'    债券风格（明确三信号：久期/信用/杠杆）
      久期风格 / 信用风格 / 杠杆风格，各给明确信号结论 + 依据
  category = 'commodity' 大宗商品（十几种主流期货，5年价格分位）
      每只商品：估值分(价格分位) + 性价比分(100-分位) + 信号 + 依据
      并标注性价比最高者及依据

估值分 V(0-100, 高=贵=性价比低)；性价比分 = 100 - V。
信号/颜色：V<=30 低估·关注 green；30<V<=70 适中 blue；V>70 高估·谨慎 red。
（债券三类信号复用 signal 字段表达方向：cheap=利好绿 / neutral=中性蓝 / expensive=谨慎红）

管道：建表(IF NOT EXISTS) → TRUNCATE style_factors → 插入全部三类 → 完成。

用法：
  SUPABASE_PAT=... python3 scripts/build_style_factors.py
（优先 SUPABASE_PAT，回退 SUPABASE_MGMT_TOKEN）
"""
import os
import sys
import json
import subprocess
import datetime
import time

import akshare as ak
import requests

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
HEADERS = {'Authorization': f'Bearer {PAT}', 'Content-Type': 'application/json'}

DDL = """
CREATE TABLE IF NOT EXISTS style_factors (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category text,
  factor_key text,
  name text,
  sub_style text,
  percentile numeric,
  value_score numeric,
  value_label text,
  cost_score numeric,
  cost_label text,
  signal text,
  signal_label text,
  reason text,
  color text,
  updated_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_style_factors_cat ON style_factors(category);
CREATE INDEX IF NOT EXISTS idx_style_factors_key ON style_factors(factor_key);
ALTER TABLE style_factors ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS anon_read_style_factors ON style_factors;
CREATE POLICY anon_read_style_factors ON style_factors FOR SELECT USING (true);
"""

# ============ 指数代码（全部中证/公开） ============
# 股票风格：key / 中文名 / 候选腾讯代码(试到成功) / 类型
STOCK_FACTORS = [
    {'key': 'size',       'name': '规模',   'symbols': ['sh000300'], 'type': 'pe',   'idx': '沪深300'},
    {'key': 'value',      'name': '价值',   'symbols': ['sh000824'], 'type': 'pe',   'idx': '中证800价值'},
    {'key': 'growth',     'name': '成长',   'symbols': ['sh000944'], 'type': 'pe',   'idx': '中证800成长'},
    {'key': 'quality',    'name': '质量',   'symbols': ['sh000969', 'sh000979', 'sh000915'], 'type': 'pe', 'idx': '中证质量'},
    {'key': 'yield',      'name': '红利',   'symbols': ['sh000922'], 'type': 'yield_inv', 'idx': '中证红利'},
    {'key': 'volatility', 'name': '波动率', 'symbols': ['sh000905'], 'type': 'pe',   'idx': '中证500'},
]
# 债券：久期/信用用长期&短期国债指数；信用用信用债指数；杠杆用carry(10Y-shibor)
BOND_IDX = {
    'long':   ['sh000833', 'sh000012'],   # 长期国债(7-10年 / 总国债)
    'short':  ['sh000829', 'sh000827'],   # 1-3年国债 / 短融
    'credit': ['sh000786', 'sh000820'],   # 信用债指数 / 企业债指数
    'gov':    ['sh000012', 'sh000833'],   # 国债指数(总)
}
# 大宗商品（新浪期货主力连续）：代码/中文名
COMMODITIES = [
    ('AU0', '沪金'), ('AG0', '沪银'), ('CU0', '沪铜'), ('AL0', '沪铝'),
    ('ZN0', '沪锌'), ('NI0', '沪镍'), ('RB0', '螺纹钢'), ('I0', '铁矿石'),
    ('HC0', '热卷'), ('J0', '焦炭'), ('JM0', '焦煤'), ('M0', '豆粕'),
    ('Y0', '豆油'), ('P0', '棕榈油'), ('SR0', '白糖'), ('CF0', '棉花'),
    ('RU0', '橡胶'), ('C0', '玉米'), ('SC0', '原油'), ('TA0', 'PTA'),
]


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


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={'query': sql}, timeout=60)
    return resp


def fetch_index_close(symbol):
    """拉取指数日线收盘价序列（腾讯源 akshare），返回 (prices, dates)"""
    df = ak.stock_zh_index_daily(symbol=symbol)
    if df is None or df.empty or len(df) < 30:
        return None, None
    df['date'] = df['date'].astype(str).str[:10]
    prices = df['close'].astype(float).tolist()
    dates = df['date'].tolist()
    return prices, dates


def fetch_futures_close(symbol):
    """拉取期货主力日线（新浪源 akshare）"""
    df = ak.futures_zh_daily_sina(symbol=symbol)
    if df is None or df.empty or len(df) < 30:
        return None, None
    df['date'] = df['date'].astype(str).str[:10]
    prices = df['close'].astype(float).tolist()
    dates = df['date'].tolist()
    return prices, dates


def percentile_of_current(prices, window=1250):
    """当前价在历史(window日)中的分位(0-100)，高=贵"""
    series = prices[-window:] if len(prices) > window else prices
    cur = series[-1]
    below = sum(1 for p in series if p <= cur)
    return round(below / len(series) * 100, 1), len(series)


def signal_from_v(v):
    if v <= 30:
        return 'cheap', '低估·关注', '#00703c', '低估', '性价比高'
    elif v <= 70:
        return 'neutral', '估值适中', '#1d70b8', '适中', '性价比适中'
    else:
        return 'expensive', '高估·谨慎', '#d4351c', '高估', '性价比低'


# ============ 股票风格 ============
def build_stock():
    out = []
    for f in STOCK_FACTORS:
        prices = None
        used = None
        for sym in f['symbols']:
            try:
                p, _ = fetch_index_close(sym)
                if p:
                    prices, used = p, sym
                    break
            except Exception as e:
                print(f'    {sym} 失败: {e}')
            time.sleep(0.1)
        if not prices:
            print(f'  ⚠ 跳过 {f["name"]}（无可用指数数据，宁空不假）')
            continue
        V, n = percentile_of_current(prices)
        # 估值分 = 当前价格近5年分位（高=贵）；红利指数同理：价格处于低位=便宜=估值分低
        V = round(V, 1)
        sig, slabel, color, vlabel, clabel = signal_from_v(V)
        rep = f['idx']
        out.append({
            'category': 'stock', 'factor_key': f['key'], 'name': f['name'], 'sub_style': None,
            'percentile': V, 'value_score': round(V), 'value_label': vlabel,
            'cost_score': round(100 - V), 'cost_label': clabel,
            'signal': sig, 'signal_label': f'{rep} · {slabel}',
            'reason': f'代表指数{rep}（{used}）当前价格处于近5年{V}%分位（样本{n}个交易日），{"估值偏低、性价比占优" if V<=30 else ("估值适中" if V<=70 else "估值偏高、性价比偏弱")}。',
            'color': color,
        })
        print(f'  {f["name"]:>4} 代表={rep:<8} 分位V={V:>5}  估值分={round(V)}  性价比分={round(100-V)}  {vlabel}/{clabel}')
        time.sleep(0.15)
    return out


# ============ 债券风格（久期/信用/杠杆） ============
def _try_fetch(syms):
    for s in syms:
        try:
            p, d = fetch_index_close(s)
            if p:
                return p, d, s
        except Exception:
            pass
        time.sleep(0.1)
    return None, None, None


def _ret_1m(prices):
    if not prices or len(prices) < 22:
        return None
    return round((prices[-1] / prices[-22] - 1) * 100, 2)


def _last(macro_metric):
    """从 macro_history 取最新值（收益率/利率，单位已是小数或%）"""
    try:
        rows = pg(f"SELECT value FROM macro_history WHERE metric='{macro_metric}' ORDER BY date DESC LIMIT 1")
        if rows and rows[0].get('value') is not None:
            return float(rows[0]['value'])
    except Exception:
        pass
    return None


def build_bond():
    out = []
    long_p, _, long_s = _try_fetch(BOND_IDX['long'])
    short_p, _, short_s = _try_fetch(BOND_IDX['short'])
    credit_p, _, credit_s = _try_fetch(BOND_IDX['credit'])
    gov_p, _, gov_s = _try_fetch(BOND_IDX['gov'])

    long_r = _ret_1m(long_p)
    short_r = _ret_1m(short_p)
    credit_r = _ret_1m(credit_p)
    gov_r = _ret_1m(gov_p)

    y10 = _last('cn10y')      # 10Y国债收益率(%)
    shibor = _last('shibor_on')  # Shibor隔夜(%)

    print(f'  债券数据: 长期国债近1月={long_r} 短期国债近1月={short_r} 信用债近1月={credit_r} 国债近1月={gov_r} 10Y={y10}% shibor={shibor}%')

    # 久期风格
    if long_r is not None and short_r is not None:
        if long_r > short_r + 0.5:
            sig, slabel, color, reason = 'cheap', '拉长久期', '#00703c', f'近1月长期利率债({long_r}%)显著跑赢短端({short_r}%)，曲线牛平、利率下行，可适度拉长久期获取资本利得。'
            score = 75
        elif long_r < short_r - 0.5:
            sig, slabel, color, reason = 'expensive', '缩短久期', '#d4351c', f'近1月短端({short_r}%)强于长端({long_r}%)，曲线熊陡/资金偏紧，建议缩短久期、控制利率风险。'
            score = 25
        else:
            sig, slabel, color, reason = 'neutral', '久期中性', '#1d70b8', f'长端({long_r}%)与短端({short_r}%)近1月表现接近，曲线形态平稳，久期保持中性即可。'
            score = 50
    else:
        sig, slabel, color, reason, score = 'neutral', '久期中性', '#1d70b8', '利率数据暂缺，久期保持中性。', 50
    out.append({'category': 'bond', 'factor_key': 'duration', 'name': '久期风格', 'sub_style': 'duration',
                'percentile': score, 'value_score': score, 'value_label': '—', 'cost_score': 100 - score,
                'cost_label': '—', 'signal': sig, 'signal_label': slabel, 'reason': reason, 'color': color})

    # 信用风格
    if credit_r is not None and gov_r is not None:
        if credit_r > gov_r + 0.3:
            sig, slabel, color, reason = 'cheap', '信用下沉', '#00703c', f'近1月信用债({credit_r}%)跑赢利率债({gov_r}%)，利差压缩、carry占优，可适度信用下沉增厚收益。'
            score = 75
        elif credit_r < gov_r - 0.3:
            sig, slabel, color, reason = 'expensive', '提升资质', '#d4351c', f'近1月信用债({credit_r}%)弱于利率债({gov_r}%)，避险情绪下利差走阔，建议提升资质、规避低评级。'
            score = 25
        else:
            sig, slabel, color, reason = 'neutral', '信用中性', '#1d70b8', f'信用债({credit_r}%)与利率债({gov_r}%)近1月表现接近，信用利差平稳，保持中性。'
            score = 50
    else:
        sig, slabel, color, reason, score = 'neutral', '信用中性', '#1d70b8', '信用数据暂缺，信用保持中性。', 50
    out.append({'category': 'bond', 'factor_key': 'credit', 'name': '信用风格', 'sub_style': 'credit',
                'percentile': score, 'value_score': score, 'value_label': '—', 'cost_score': 100 - score,
                'cost_label': '—', 'signal': sig, 'signal_label': slabel, 'reason': reason, 'color': color})

    # 杠杆风格（套息 = 10Y收益率 - Shibor）
    if y10 is not None and shibor is not None:
        carry = y10 - shibor
        if carry > 0.8:
            sig, slabel, color, reason = 'cheap', '适度加杠杆', '#00703c', f'10Y国债收益率({y10}%)与Shibor隔夜({shibor}%)套息空间约{carry:.2f}%，正carry充足，可适度加杠杆增厚收益。'
            score = 75
        elif carry < 0.3:
            sig, slabel, color, reason = 'expensive', '降低杠杆', '#d4351c', f'套息空间仅约{carry:.2f}%，杠杆收益薄、资金波动风险大，建议降低杠杆。'
            score = 25
        else:
            sig, slabel, color, reason = 'neutral', '杠杆中性', '#1d70b8', f'套息空间约{carry:.2f}%，杠杆收益中性，保持当前杠杆水平。'
            score = 50
    else:
        sig, slabel, color, reason, score = 'neutral', '杠杆中性', '#1d70b8', '利率数据暂缺，杠杆保持中性。', 50
    out.append({'category': 'bond', 'factor_key': 'leverage', 'name': '杠杆风格', 'sub_style': 'leverage',
                'percentile': score, 'value_score': score, 'value_label': '—', 'cost_score': 100 - score,
                'cost_label': '—', 'signal': sig, 'signal_label': slabel, 'reason': reason, 'color': color})
    return out


# ============ 大宗商品 ============
def build_commodity():
    out = []
    for code, name in COMMODITIES:
        try:
            prices, dates = fetch_futures_close(code)
        except Exception as e:
            print(f'    {code} 失败: {e}')
            prices, dates = None, None
        if not prices:
            print(f'  ⚠ 跳过 {name}({code})')
            time.sleep(0.1)
            continue
        V, n = percentile_of_current(prices)
        sig, slabel, color, vlabel, clabel = signal_from_v(V)
        out.append({
            'category': 'commodity', 'factor_key': code, 'name': name, 'sub_style': None,
            'percentile': V, 'value_score': round(V), 'value_label': vlabel,
            'cost_score': round(100 - V), 'cost_label': clabel,
            'signal': sig, 'signal_label': slabel,
            'reason': f'当前价格处于近5年{V}%分位（样本{n}个交易日），{"处于历史低位、性价比高" if V<=30 else ("估值适中" if V<=70 else "处于历史高位、性价比偏弱")}。',
            'color': color,
        })
        print(f'  {name:<5}({code}) 分位V={V:>5}  估值分={round(V)}  性价比分={round(100-V)}  {vlabel}')
        time.sleep(0.12)

    # 标注性价比最高者（cost_score 最大）
    if out:
        best = max(out, key=lambda x: x['cost_score'])
        best['signal_label'] = '★ 性价比最高'
        best['color'] = '#00703c'
        best['reason'] = (f'在全部{len(out)}只样本商品中，{best["name"]}当前价格处于近5年{best["percentile"]}%分位，'
                          f'性价比分{best["cost_score"]}为最高，处于历史相对低位，配置性价比最优。')
        print(f'  ★ 性价比最高：{best["name"]} 性价比分={best["cost_score"]}（分位{best["percentile"]}%）')
    return out


def sql_val(v):
    if v is None:
        return 'NULL'
    if isinstance(v, (int, float)):
        return str(v)
    s = str(v).replace("'", "''")
    return f"'{s}'"


COLS = ('category', 'factor_key', 'name', 'sub_style', 'percentile', 'value_score',
        'value_label', 'cost_score', 'cost_label', 'signal', 'signal_label', 'reason', 'color')


def main():
    print('== 建表 style_factors ==')
    for stmt in [s.strip() for s in DDL.strip().split(';') if s.strip()]:
        pg(stmt)
    print('  表就绪')

    print('\n== 计算 股票风格（中证指数）==')
    stock = build_stock()
    print('\n== 计算 债券风格（久期/信用/杠杆）==')
    bond = build_bond()
    print('\n== 计算 大宗商品（十几种期货）==')
    commodity = build_commodity()

    all_rows = stock + bond + commodity
    print(f'\n== 共 {len(all_rows)} 条信号，写入 style_factors ==')
    pg('TRUNCATE TABLE style_factors;')
    tuples = []
    for r in all_rows:
        vals = ', '.join(sql_val(r.get(c)) for c in COLS)
        tuples.append(f'({vals})')
    sql = f"INSERT INTO style_factors ({', '.join(COLS)}) VALUES\n" + ',\n'.join(tuples) + ';'
    pg(sql)
    cnt = pg('SELECT COUNT(*) AS c FROM style_factors')
    print(f'  写入完成，style_factors 当前 {cnt[0]["c"]} 条')
    print('== 完成 ==')


if __name__ == '__main__':
    main()
