"""
统一 SQL 执行层 —— 根治 Supabase PAT 过期导致每日更新失败的问题。

背景：
    项目里大量脚本通过 Supabase Management API 的 /database/query 端点执行 SQL，
    该端点只认「Personal Access Token (PAT)」，而 PAT 会过期。只要走这条路，
    CI 的每日更新就永远绕不开手动刷新 token。

用法：
    from _db import run_sql
    rows = run_sql("SELECT * FROM fund_scores LIMIT 1")   # 返回 list[dict]
    cnt  = run_sql("SELECT count(*) AS cnt FROM fund_scores")[0]["cnt"]

返回值约定（与 Management API 行为保持一致，业务代码无需感知后端）：
    - SELECT  →  list[dict]，每个 dict 是一行（列名 → 值）。
    - DDL/DML →  未返回结果集时返回 []。
    - 出错     →  抛 RuntimeError（含服务端错误信息）。
    数值类型保持为 int/float（不转字符串），时间戳转为 ISO 字符串，便于下游算术。

后端选择（自动，业务代码无感）：
    - 若设置了 SUPABASE_DB_URL（postgres 直连串）→ 走 psycopg2 直连数据库。
      数据库密码长期稳定（除非手动重置），彻底摆脱会过期的 PAT。
    - 否则 → 回退到 Management API（需要 SUPABASE_PAT / SUPABASE_MGMT_TOKEN）。
"""
import os
import sys

import psycopg2
import psycopg2.extras

PROJECT_REF = os.environ.get("SUPABASE_PROJECT_REF", "tqhtegazxykkqfcpejky")
MGMT_API = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"


def _split_statements(sql):
    """按顶层分号拆分多条 SQL（忽略引号内的分号），便于 psycopg2 逐条执行。"""
    out, buf = [], []
    in_s = in_d = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == ";" and not in_s and not in_d:
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


def _jsonable(o):
    """psycopg2 返回 Decimal/datetime，转为 JSON 友好且可算术的类型。"""
    import datetime
    import decimal

    if isinstance(o, decimal.Decimal):
        f = float(o)
        return int(f) if f.is_integer() else f
    if isinstance(o, (datetime.datetime, datetime.date, datetime.time)):
        return o.isoformat()
    if isinstance(o, (bytes, bytearray)):
        return o.decode("utf-8", "replace")
    return str(o)


def _mgmt_query(sql, params=None, timeout=60):
    """回退路径：通过 Management API 执行 SQL（只认 PAT）。返回 list[dict] 或 []。"""
    import json
    import requests

    token = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
    if not token:
        raise RuntimeError("缺少 SUPABASE_PAT / SUPABASE_MGMT_TOKEN（且未配置 SUPABASE_DB_URL）")
    r = requests.post(
        MGMT_API,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"query": sql},
        timeout=timeout,
    )
    try:
        r.raise_for_status()
    except Exception:
        raise RuntimeError(f"MGMT API HTTP {r.status_code}: {r.text[:300]}")
    data = r.json()
    # Management API 对 SELECT 返回行数组；对 DDL 通常返回 [] 或 {"status":"OK"}；
    # 对错误返回 {"message": "..."}。统一为 list[dict] / []，错误抛异常。
    if isinstance(data, dict):
        if data.get("message"):
            raise RuntimeError(data["message"][:300])
        return []
    if isinstance(data, list):
        return data
    return []


def _ipv4_host(dsn):
    """把 DSN 里的主机名解析成 IPv4 地址字面量。

    GitHub Actions 的 runner 默认 DNS 优先返回 IPv6，而 runner 没有 IPv6 出口，
    直连会报 'Network is unreachable'。这里强制解析出 IPv4 地址覆盖 DSN 中的主机名，
    每次连接实时解析，故 Supabase 后端 IP 变更也不影响。
    """
    import socket
    from urllib.parse import urlparse

    try:
        p = urlparse(dsn)
        host = p.hostname
        if not host:
            return None
        infos = socket.getaddrinfo(host, p.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except Exception:
        return None
    return None


def _db_query(sql, params=None, timeout=300):
    """直连路径：psycopg2 直连 postgres。返回 list[dict]（其余与 _mgmt_query 对齐）。

    注：Supabase 的数据库主机只提供 IPv6，而 GitHub Actions runner 无 IPv6 出口，
    直连在 CI 里会 'Network is unreachable'。本层会先尝试直连（有 IPv6 的环境用数据库密码），
    调用方 run_sql 在连接失败时自动回退到 Management API（IPv4 + PAT）。
    """
    import json

    dsn = os.environ["SUPABASE_DB_URL"]
    statements = _split_statements(sql)
    if not statements:
        return []
    out_rows = []
    conn_kwargs = {"dsn": dsn, "sslmode": "require"}
    # 强制 IPv4：runner 解析到 IPv6 但无 IPv6 出口会导致 Network is unreachable。
    ipv4 = _ipv4_host(dsn)
    if ipv4:
        conn_kwargs["host"] = ipv4
    if timeout:
        try:
            conn_kwargs["connect_timeout"] = int(timeout)
        except Exception:
            pass
    with psycopg2.connect(**conn_kwargs) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            for stmt in statements:
                cur.execute(stmt, params)
                if cur.description:
                    out_rows = [dict(r) for r in cur.fetchall()]
        conn.commit()
    # 数值/时间类型规整，避免下游算术因 Decimal/date 出错，且与 API 的 JSON 类型对齐
    return json.loads(json.dumps(out_rows, default=_jsonable))


def run_sql(sql, params=None, timeout=None):
    """
    执行 SQL，返回 list[dict]（SELECT）或 []（DDL/DML）。

    后端选择（自动，业务代码无感）：
      1. 若设置了 SUPABASE_DB_URL → 先试 psycopg2 直连（数据库密码，长期稳定）。
      2. 直连失败（典型：CI runner 无 IPv6 出口，连不上 Supabase 的 IPv6-only 数据库）
         → 自动回退到 Management API（走 IPv4 HTTPS，认 SUPABASE_PAT / SUPABASE_MGMT_TOKEN）。

    这样同一套代码：本地/有 IPv6 的环境用「不会过期的数据库密码」，
    GitHub Actions 等无 IPv6 的环境透明回退到 Management API，每日更新都不会因
    单一通道问题而失败。

    兼容各脚本既有的 pg() / run_sql() / pg_query() 调用签名：
    可传入 timeout 关键字参数（直连路径会用作 connect_timeout，API 路径用作请求超时）。
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    if db_url:
        try:
            return _db_query(sql, params, timeout)
        except psycopg2.OperationalError as e:
            # 仅连接/网络/认证类错误才回退；SQL 语法等错误不该静默回退。
            pat = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
            if pat:
                sys.stderr.write(f"[_db] 直连失败，回退 Management API(PAT): {e}\n")
                return _mgmt_query(sql, params, timeout or 60)
            raise
    return _mgmt_query(sql, params, timeout or 60)
