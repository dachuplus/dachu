#!/usr/bin/env python3
"""应用「内容」功能权限迁移到 Supabase。

用法:
  SUPABASE_PAT=<pat> python3 scripts/add_content_permission.py
  （PAT 也可从项目根 .env.local 读取；SUPABASE_MGMT_TOKEN 作为兜底）
"""
import os
import sys
import requests

PROJECT_REF = "tqhtegazxykkqfcpejky"
MGMT_URL = f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query"
SQL_FILE = os.path.join(os.path.dirname(__file__), "..", "supabase-articles-content-permission.sql")


def load_env_local():
    """从项目根 .env.local 读取键值到环境变量（仅当尚未设置时）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(here, "..", ".env.local")
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            if k not in os.environ:
                os.environ[k] = v


def main():
    load_env_local()
    pat = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN", "")
    if not pat:
        print("[ERROR] 需设置 SUPABASE_PAT / SUPABASE_MGMT_TOKEN")
        sys.exit(1)

    with open(SQL_FILE, "r", encoding="utf-8") as f:
        sql = f.read()

    headers = {
        "Authorization": f"Bearer {pat}",
        "Content-Type": "application/json",
    }
    resp = requests.post(MGMT_URL, headers=headers, timeout=120, json={"query": sql})
    print("HTTP", resp.status_code)
    try:
        print(resp.text[:2000])
    except Exception:
        print(resp.text[:2000])
    if resp.status_code >= 400:
        sys.exit(1)
    print("[OK] content permission migration applied")


if __name__ == "__main__":
    main()
