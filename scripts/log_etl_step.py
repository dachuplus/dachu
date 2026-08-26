#!/usr/bin/env python3
"""log_etl_step.py — ETL 步骤运行日志（写入 public.etl_run_log 表）。

模式:
  --init                                                 仅确保表存在 + 授权 anon 读取，然后退出
  --step NAME --mark running                            插入 running 行，打印新行 id 到 stdout
  --step NAME --mark success --id ID [--rows N]         更新为 success（兼容旧 run_etl_step.sh）
  --step NAME --mark failed  --id ID --error MSG        更新为 failed（兼容旧 run_etl_step.sh）

  # 流水线「末尾一次性记录」模式（推荐，GitHub Actions 每个 job 末尾 if: always() 调用）:
  --step NAME --status STATUS [--rows N] [--duration S] [--message MSG] [--run-date DATE]
      STATUS ∈ { success | error | running | cancelled | skipped }
      （写库时 failed/ok/done 等会被规整为 error/success；running 通常仅手动步骤使用）

依赖: SUPABASE_PAT 或 SUPABASE_MGMT_TOKEN（与 fetch_jqr_indicators.py 一致）。
通过 Supabase Management API（PAT，superuser 绕过 RLS）执行 SQL（curl 直连，避免 urllib 被 Cloudflare 403）。
"""
import os
import sys
import json
import time
import subprocess
from datetime import datetime, date

try:
    from zoneinfo import ZoneInfo
    CST = ZoneInfo('Asia/Shanghai')
except Exception:
    CST = None


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
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

DDL = """
CREATE TABLE IF NOT EXISTS public.etl_run_log (
    id SERIAL PRIMARY KEY,
    run_date DATE NOT NULL,
    step_name TEXT NOT NULL,
    status TEXT NOT NULL,
    start_time TIMESTAMPTZ,
    end_time TIMESTAMPTZ,
    duration_seconds INTEGER,
    rows_affected INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);
"""


def pg(sql, tries=3, delay=5):
    """经 Management API（curl 直连，避开 urllib 被 Cloudflare 403）执行 SQL。

    自愈重试：GitHub Actions runner → Supabase 网关间歇性超时（curl connect
    timeout / 5xx）。此前 pg() 对 curl 超时既未捕获异常也未重试，导致简报写入
    静默失败（bash step 无 set -e 误判 success）——这正是「更新简报看不到失败
    原因」的根因。现改为重试 3 次、间隔 5s，瞬时抽风也能写进去。
    """
    if not MGMT_TOKEN:
        sys.stderr.write('WARN: 未设置 SUPABASE_PAT/SUPABASE_MGMT_TOKEN，跳过日志写入\n')
        return None
    payload = json.dumps({'query': sql})
    last_err = None
    for attempt in range(tries):
        try:
            r = subprocess.run(
                ['curl', '-s', '--max-time', '120', '-X', 'POST', MGMT_API,
                 '-H', f'Authorization: Bearer {MGMT_TOKEN}',
                 '-H', 'Content-Type: application/json', '-d', payload],
                capture_output=True, text=True, timeout=130)
        except subprocess.TimeoutExpired as e:
            last_err = f'curl 超时: {e}'
            sys.stderr.write(f'  [log] curl 超时（第{attempt+1}/{tries}次，{delay}s 后重试）\n')
            time.sleep(delay)
            continue
        if r.returncode != 0:
            last_err = f'curl returncode={r.returncode}: {r.stderr[:200]}'
            sys.stderr.write(f'  [log] curl 失败（第{attempt+1}/{tries}次，{delay}s 后重试）: {last_err}\n')
            time.sleep(delay)
            continue
        t = r.stdout.strip()
        if not t:
            return None
        try:
            resp = json.loads(t)
        except json.JSONDecodeError:
            sys.stderr.write(f'非JSON响应: {t[:200]}\n')
            return None
        if isinstance(resp, dict) and resp.get('message'):
            sys.stderr.write(f'SQL错误: {resp["message"][:300]}\n')
            return None
        return resp
    sys.stderr.write(f'  [log] pg 重试 {tries} 次仍失败: {last_err}\n')
    return None


def ensure_table():
    pg(DDL)
    pg('GRANT SELECT ON public.etl_run_log TO anon;')


def now_iso():
    return datetime.now(CST).isoformat() if CST else datetime.now().isoformat()


def today_cst():
    return (datetime.now(CST) if CST else datetime.now()).strftime('%Y-%m-%d')


def sanitize(text, limit=1000):
    """清理写入字段：去控制字符、转义单引号、截断，防止 SQL 注入与超长。"""
    if text is None:
        return ''
    t = str(text)
    # 仅保留可打印字符 + 换行/回车/制表
    t = ''.join(ch for ch in t if ch in '\n\r\t' or ord(ch) >= 32)
    t = t.replace("'", "''")
    return t[:limit]


def norm_status(s):
    m = {
        'success': 'success', 'ok': 'success', 'done': 'success',
        'error': 'error', 'failed': 'error', 'fail': 'error',
        'running': 'running', 'pending': 'pending',
        'cancelled': 'cancelled', 'canceled': 'cancelled',
        'skipped': 'skipped',
    }
    return m.get(str(s or '').lower(), 'pending')


def mark_running(step, run_date):
    now = now_iso()
    sql = (f"INSERT INTO public.etl_run_log (run_date, step_name, status, start_time) "
           f"VALUES ('{run_date}', '{sanitize(step, 200)}', 'running', '{now}') RETURNING id")
    resp = pg(sql)
    if isinstance(resp, list) and resp and 'id' in resp[0]:
        return str(resp[0]['id'])
    return ''


def mark_done(step, run_date, status, rid, rows, error):
    status = norm_status(status)
    now = now_iso()
    if rid:
        where = f"id = {rid}"
    else:
        where = (f"run_date = '{run_date}' AND step_name = '{sanitize(step, 200)}' "
                 f"AND status = 'running'")
    sets = [
        f"status = '{status}'",
        f"end_time = '{now}'",
        "duration_seconds = EXTRACT(EPOCH FROM (now() - start_time))::int",
    ]
    if rows is not None:
        sets.append(f"rows_affected = {rows}")
    if error:
        sets.append(f"error_message = '{sanitize(error)}'")
    else:
        sets.append("error_message = NULL")
    sql = f"UPDATE public.etl_run_log SET {', '.join(sets)} WHERE {where}"
    pg(sql)


def record(step, run_date, status, rows, duration, message):
    """末尾一次性记录：按 (run_date, step_name) UPSERT（先删后插，幂等可重跑）。"""
    status = norm_status(status)
    step_safe = sanitize(step, 200)
    # 计算 start_time 与 duration_seconds
    if duration is not None and str(duration).isdigit() and int(duration) >= 0:
        dur_val = int(duration)
        start_expr = f"(now() - interval '{dur_val} seconds')"
    else:
        dur_val = None
        start_expr = 'now()'
    dur_sql = str(dur_val) if dur_val is not None else f"EXTRACT(EPOCH FROM (now() - {start_expr}))::int"
    rows_sql = str(int(rows)) if rows is not None else 'NULL'
    msg_sql = f"'{sanitize(message)}'" if message else 'NULL'

    # 先清旧行（同一 run_date+step_name 仅保留一条，避免重跑累积）
    pg(f"DELETE FROM public.etl_run_log WHERE run_date = '{run_date}' AND step_name = '{step_safe}'")
    cols = ['run_date', 'step_name', 'status', 'start_time', 'end_time',
            'duration_seconds', 'rows_affected', 'error_message']
    vals = [f"'{run_date}'", f"'{step_safe}'", f"'{status}'", start_expr, 'now()',
            dur_sql, rows_sql, msg_sql]
    sql = ("INSERT INTO public.etl_run_log (" + ', '.join(cols) +
           ") VALUES (" + ', '.join(vals) + ")")
    pg(sql)


def main():
    args = sys.argv[1:]
    mode = None
    step = None
    rid = ''
    rows = None
    error = None
    run_date = today_cst()
    status = None
    duration = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == '--init':
            mode = 'init'
        elif a == '--step':
            step = args[i + 1]
            i += 1
        elif a == '--mark':
            mode = args[i + 1]
            i += 1
        elif a == '--status':
            status = args[i + 1]
            mode = 'record'
            i += 1
        elif a == '--id':
            rid = args[i + 1]
            i += 1
        elif a == '--rows':
            try:
                rows = int(args[i + 1])
            except (ValueError, IndexError):
                pass
            i += 1
        elif a == '--duration':
            try:
                duration = int(args[i + 1])
            except (ValueError, IndexError):
                pass
            i += 1
        elif a == '--error':
            error = args[i + 1]
            i += 1
        elif a == '--message':
            error = args[i + 1]
            i += 1
        elif a == '--run-date':
            run_date = args[i + 1]
            i += 1
        i += 1

    if mode == 'init':
        ensure_table()
        print('etl_run_log 表已就绪')
        return

    # 执行/更新前确保表存在（幂等，兜底独立运行某步骤时表尚未创建）
    ensure_table()

    if mode == 'running':
        rid = mark_running(step, run_date)
        print(rid)
        return
    if mode in ('success', 'failed'):
        mark_done(step, run_date, mode, rid, rows, error)
        return
    if mode == 'record':
        if not step:
            sys.stderr.write('缺少 --step\n')
            sys.exit(2)
        record(step, run_date, status or 'success', rows, duration, error)
        return

    sys.stderr.write('未知模式，使用 --init / --mark / --status\n')
    sys.exit(2)


if __name__ == '__main__':
    main()
