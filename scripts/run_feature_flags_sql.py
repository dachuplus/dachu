#!/usr/bin/env python3
"""一次性初始化 feature_flags 表 + set_feature_flag RPC（幂等，仅建表/函数/初始数据）。

执行通道：
  - 优先 SUPABASE_DB_URL（psycopg2 直连，含数据库密码，长期稳定）。
    CI 的 GitHub runner 无 IPv6 出口，本脚本会把 DSN 主机名强制解析为 IPv4 地址，
    与 scripts/_db.py 的 _ipv4_host 行为一致，避免 'Network is unreachable'。
  - 未设置 SUPABASE_DB_URL 时回退 Management API（仅 SELECT 可用，DDL 会被 1010 拦截），
    此时本脚本会报错退出，提示需在 CI 或控制台执行。

注意：本脚本自带「 Dollar-Quote 感知」的 SQL 拆分器，能正确处理
  CREATE OR REPLACE FUNCTION ... $$ ... $$ 体内的分号，避免被当成多条语句拆断。
"""
import os
import re
import sys
import json
import socket
import psycopg2
import psycopg2.extras


def ipv4_host(dsn):
    """把 DSN 主机名解析成 IPv4 字面量（应对 runner 无 IPv6 出口）。"""
    from urllib.parse import urlparse

    p = urlparse(dsn)
    host = p.hostname
    if not host:
        return None
    try:
        infos = socket.getaddrinfo(host, p.port or 5432, socket.AF_INET, socket.SOCK_STREAM)
        return infos[0][4][0] if infos else None
    except Exception:
        return None


def split_sql(sql):
    """按顶层分号拆分，忽略 ' " 引号内分号，并正确处理 $tag$ ... $tag$ Dollar-Quoting。"""
    out, buf = [], []
    i, n = 0, len(sql)
    in_s = in_d = False
    dollar = None
    while i < n:
        ch = sql[i]
        if dollar:
            end = sql.find(dollar, i)
            if end == -1:
                buf.append(sql[i:])
                break
            buf.append(sql[i : end + len(dollar)])
            i = end + len(dollar)
            dollar = None
            continue
        if ch == "$" and not in_s and not in_d:
            mm = re.match(r"\$[A-Za-z_]*\$", sql[i:])
            if mm:
                dollar = mm.group(0)
                buf.append(dollar)
                i += len(dollar)
                continue
        if ch == "'" and not in_d:
            in_s = not in_s
        elif ch == '"' and not in_s:
            in_d = not in_d
        elif ch == ";" and not in_s and not in_d:
            s = "".join(buf).strip()
            if s:
                out.append(s)
            buf = []
        buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s:
        out.append(s)
    return out


def main():
    sql_path = os.path.join(os.path.dirname(__file__), "..", "supabase_feature_flags.sql")
    sql = open(sql_path).read()
    stmts = split_sql(sql)
    print(f"parsed {len(stmts)} statements")

    db_url = os.environ.get("SUPABASE_DB_URL")
    if not db_url:
        print("ERROR: 缺少 SUPABASE_DB_URL（CI 已配置；本地可临时 export 后运行）")
        sys.exit(1)

    # 重建 DSN：把主机名替换为解析到的 IPv4 地址（避免 runner 无 IPv6 出口导致的连不上）。
    # 直接拼一个新 DSN，而不是 dsn+host 双传（psycopg2 对两者的优先级处理在不同版本不一致）。
    from urllib.parse import urlparse, urlunparse

    p = urlparse(db_url)
    netloc = p.netloc
    if "@" in netloc:
        userinfo, hostport = netloc.split("@", 1)
    else:
        userinfo, hostport = "", netloc
    if ":" in hostport:
        host, port = hostport.rsplit(":", 1)
    else:
        host, port = hostport, ""
    ip = ipv4_host(db_url)
    new_host = ip or host
    new_netloc = f"{userinfo}@{new_host}" + (f":{port}" if port else "")
    new_dsn = urlunparse((p.scheme, new_netloc, p.path, p.params, p.query, p.fragment))
    print("connecting to", new_host)

    conn = psycopg2.connect(new_dsn, sslmode="require")
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    ok = 0
    for i, s in enumerate(stmts):
        try:
            cur.execute(s)
            conn.commit()
            ok += 1
            print(f"  [{i+1}/{len(stmts)}] OK  {s[:52]}...")
        except Exception as e:
            conn.rollback()
            print(f"  [{i+1}/{len(stmts)}] ERR {repr(e)[:200]}")

    cur.execute("SELECT key, open, label FROM public.feature_flags ORDER BY sort_order")
    print("feature_flags:", [dict(r) for r in cur.fetchall()])
    cur.execute("SELECT count(*) AS c FROM pg_proc WHERE proname='set_feature_flag'")
    print("set_feature_flag RPC exists:", cur.fetchone()["c"] == 1)
    cur.close()
    conn.close()
    print(f"executed {ok}/{len(stmts)} statements")


if __name__ == "__main__":
    main()
