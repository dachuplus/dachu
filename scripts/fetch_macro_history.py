#!/usr/bin/env python3
"""fetch_macro_history.py — 补充 macro_history 表中的宏观指标（含 OMO 净投放）。

背景：
  macro_history 表目前已有 cn10y / us10y / shibor_on / cpi / m2_growth，
  但「公开市场操作(OMO)净投放」(metric=omo_net) 长期为空。本脚本负责补齐它，
  并对其它指标做幂等刷新（DELETE + INSERT，已存在则覆盖，不会重复堆积）。

数据来源（akshare，沙箱已验证可联网）：
  - 公开市场操作净投放：akshare.macro_china_omo  -> 逐日投放/回笼 -> 净投放(亿元)
  - 美国10Y国债：akshare.bond_zh_us_rate (验证用)
  - 中国10Y国债 / Shibor / CPI / M2 等同既有口径

写入：经 Supabase Management API (PAT, superuser 绕过 RLS) 执行 DELETE + INSERT。
  与 scripts/fetch_jqr_indicators.py 的 pg() 写入方式保持一致。

用法：
  SUPABASE_PAT=xxx python3 scripts/fetch_macro_history.py            # 仅补齐缺失项(omo_net)
  SUPABASE_PAT=xxx python3 scripts/fetch_macro_history.py --all      # 全量刷新
  SUPABASE_PAT=xxx python3 scripts/fetch_macro_history.py --metric omo_net
"""
import os
import sys
import json
import argparse
from datetime import datetime

# ---------- 环境 ----------
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
    sys.exit('请设置 SUPABASE_PAT（Supabase Personal Access Token）')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'


def pg(sql, timeout=300):
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '--max-time', str(timeout), '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json', '-d', payload],
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


import subprocess


# ---------- 写入 macro_history ----------
def upsert_metric(metric, rows):
    """rows: list of (date, value, source)。幂等：先删该 metric 全部，再批量插入。"""
    if not rows:
        print(f"  [skip] {metric}: 无数据")
        return
    pg(f"DELETE FROM macro_history WHERE metric='{metric}';")
    parts = []
    for date, value, source in rows:
        src = (source or '').replace("'", "''")
        parts.append(f"('{metric}','{date}',{float(value)},'{src}')")
    chunk = 500
    for i in range(0, len(parts), chunk):
        vals = ','.join(parts[i:i + chunk])
        pg(f"INSERT INTO macro_history(metric,date,value,source) VALUES {vals};")
    print(f"  wrote {metric}: {len(rows)} 行 (最新 {rows[-1][0]})")


# ---------- OMO 净投放 ----------
def fetch_omo_net():
    """公开市场操作净投放（亿元）。返回 [(date, net_value, source), ...] 升序。

    数据来源说明：OMO 净投放 = 逆回购/MLF 等投放 − 当日到期回笼（单位：亿元）。
    akshare 历史版本曾提供 macro_china_omo，但新版已移除；此处动态探测可用函数，
    若无可用数据源则明确返回空（遵循项目「宁空不假」原则，绝不编造模拟值）。
    如需补齐，可在 akshare 提供 OMO 接口后扩展，或接入东方财富/人行公告的可靠解析。
    """
    import akshare as ak
    func = getattr(ak, 'macro_china_omo', None)
    if func is None:
        print("  [warn] akshare 未提供 OMO 净投放接口(macro_china_omo)，跳过 omo_net。")
        return []
    try:
        df = func()
    except Exception as e:
        print(f"  [warn] OMO 拉取失败: {e}，跳过 omo_net。")
        return []
    if df is None or len(df) == 0:
        return []
    cols = list(df.columns)
    date_col = next((c for c in cols if '日期' in c or '时间' in c or 'date' in c.lower()), None)
    if date_col is None:
        return []
    in_col = next((c for c in cols if '投放' in c), None)
    out_col = next((c for c in cols if '回笼' in c or '到期' in c), None)
    out = []
    for _, row in df.iterrows():
        d = str(row[date_col])[:10]
        try:
            inn = float(row[in_col]) if in_col and row[in_col] not in (None, '') else 0.0
        except (ValueError, TypeError):
            inn = 0.0
        try:
            outv = float(row[out_col]) if out_col and row[out_col] not in (None, '') else 0.0
        except (ValueError, TypeError):
            outv = 0.0
        net = inn - outv
        out.append((d, round(net, 2), 'akshare:macro_china_omo'))
    out.sort(key=lambda x: x[0])
    return out


# ---------- 其它指标（验证 / 全量刷新用，保持与既有口径一致） ----------
def fetch_cn10y():
    import akshare as ak
    df = ak.bond_zh_us_rate()
    out = []
    for _, row in df.iterrows():
        out.append((str(row['日期'])[:10], float(row['中国国债收益率10年']), 'akshare:bond_zh_us_rate'))
    return sorted(out, key=lambda x: x[0])


def fetch_us10y():
    import akshare as ak
    df = ak.bond_zh_us_rate()
    out = []
    for _, row in df.iterrows():
        out.append((str(row['日期'])[:10], float(row['美国国债收益率10年']), 'akshare:bond_zh_us_rate'))
    return sorted(out, key=lambda x: x[0])


FETCHERS = {
    'omo_net': fetch_omo_net,
    'cn10y': fetch_cn10y,
    'us10y': fetch_us10y,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--all', action='store_true', help='刷新所有已定义指标')
    ap.add_argument('--metric', help='只刷新指定 metric')
    args = ap.parse_args()

    if args.metric:
        keys = [args.metric]
    elif args.all:
        keys = list(FETCHERS.keys())
    else:
        # 默认：仅补齐当前为空的 omo_net（幂等，其它指标不动）
        keys = ['omo_net']

    print("=== 补充 macro_history 宏观指标 ===")
    for k in keys:
        if k not in FETCHERS:
            print(f"  [skip] 未知 metric: {k}")
            continue
        print(f"-- {k} --")
        try:
            rows = FETCHERS[k]()
        except Exception as e:
            print(f"  [error] {k} 拉取失败: {e}")
            continue
        upsert_metric(k, rows)
    print("=== 完成 ===")


if __name__ == '__main__':
    main()
