#!/usr/bin/env python3
"""log_etl_step.py — ETL 步骤运行日志（写入 public.etl_run_log 表）。

模式:
  --init                                      仅确保表存在 + 授权 anon 读取，然后退出
  --step NAME --mark running                 插入 running 行，打印新行 id 到 stdout
  --step NAME --mark success --id ID [--rows N]   更新为 success
  --step NAME --mark failed  --id ID --error MSG  更新为 failed（记录错误信息）

依赖: SUPABASE_PAT 或 SUPABASE_MGMT_TOKEN（与 fetch_jqr_indicators.py 一致）。
通过 Supabase Management API（PAT，superuser 绕过 RLS）执行 SQL。
"""
import os
import sys
import json
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


def pg(sql):
    if not MGMT_TOKEN:
        sys.stderr.write('WARN: 未设置 SUPABASE_PAT/SUPABASE_MGMT_TOKEN，跳过日志写入\n')
        return None
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '--max-time', '120', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json', '-d', payload],
        capture_output=True, text=True, timeout=130)
    if r.returncode != 0:
        sys.stderr.write(f'curl fail: {r.stderr[:200]}\n')
        return None
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


def ensure_table():
    pg(DDL)
    pg('GRANT SELECT ON public.etl_run_log TO anon;')


def now_iso():
    return datetime.now(CST).isoformat() if CST else datetime.now().isoformat()


def today_cst():
    return (datetime.now(CST) if CST else datetime.now()).strftime('%Y-%m-%d')


def mark_running(step, run_date):
    now = now_iso()
    sql = (f"INSERT INTO public.etl_run_log (run_date, step_name, status, start_time) "
           f"VALUES ('{run_date}', '{step}', 'running', '{now}') RETURNING id")
    resp = pg(sql)
    if isinstance(resp, list) and resp and 'id' in resp[0]:
        return str(resp[0]['id'])
    return ''


def mark_done(step, run_date, status, rid, rows, error):
    now = now_iso()
    if rid:
        where = f"id = {rid}"
    else:
        where = (f"run_date = '{run_date}' AND step_name = '{step}' "
                 f"AND status = 'running'")
    sets = [
        f"status = '{status}'",
        f"end_time = '{now}'",
        "duration_seconds = EXTRACT(EPOCH FROM (now() - start_time))::int",
    ]
    if rows is not None:
        sets.append(f"rows_affected = {rows}")
    if error:
        esc = error.replace("'", "''")
        sets.append(f"error_message = '{esc}'")
    sql = f"UPDATE public.etl_run_log SET {', '.join(sets)} WHERE {where}"
    pg(sql)


def main():
    args = sys.argv[1:]
    mode = None
    step = None
    rid = ''
    rows = None
    error = None
    run_date = today_cst()
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
        elif a == '--id':
            rid = args[i + 1]
            i += 1
        elif a == '--rows':
            try:
                rows = int(args[i + 1])
            except (ValueError, IndexError):
                pass
            i += 1
        elif a == '--error':
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


if __name__ == '__main__':
    main()
