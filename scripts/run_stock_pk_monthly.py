#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_stock_pk_monthly.py — 股票组合 PK 月度自动重选编排器

顺序：
  1. fetch_stock_scores.py  → stock_scores_staging（抓 A 股沪深300+中证500+中证1000 真实行情）
  2. promote_stock_scores.py → stock_scores（校验+原子切换）
  3. 若任一 LLM key 环境变量存在 → stock_pk_real.py（真实大模型两层选股）
     否则 → seed_stock_pk.py（规则版兜底，保证每月都有可展示的选股结果）
  4. 写 etl_run_log 汇总。

用法（由 .github/workflows/stock-pk-monthly.yml 每月1日调用）：
  python3 scripts/run_stock_pk_monthly.py
"""
import os
import sys
import datetime
import subprocess

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def run(cmd):
    print("\n$ " + " ".join(cmd), flush=True)
    rc = subprocess.run(cmd, cwd=SCRIPT_DIR).returncode
    return rc


def main():
    today = datetime.date.today().isoformat()
    print(f"=== 股票组合 PK 月度重选编排（{today}）===")

    # 1. 抓取
    rc = run([sys.executable, os.path.join(SCRIPT_DIR, "fetch_stock_scores.py")])
    if rc != 0:
        print(f"[WARN] fetch_stock_scores 返回 {rc}，尝试继续 promote（用已有 staging）")

    # 2. 切换
    rc = run([sys.executable, os.path.join(SCRIPT_DIR, "promote_stock_scores.py")])
    if rc != 0:
        print(f"[ERR] promote 失败，终止（保留现有生产 stock_scores）")
        sys.exit(1)

    # 3. 选股：优先真实大模型，缺失 key 则规则兜底
    llm_keys = [k for k in ("DEEPSEEK_API_KEY", "QWEN_API_KEY", "WENXIN_API_KEY",
                            "ZHIPU_API_KEY", "KIMI_API_KEY", "ARK_API_KEY", "OPENAI_API_KEY")
                if os.environ.get(k)]
    if llm_keys:
        print(f"[选股] 检测到 LLM key: {llm_keys}，运行真实大模型两层选股 ...")
        rc = run([sys.executable, os.path.join(SCRIPT_DIR, "stock_pk_real.py")])
        if rc != 0:
            print(f"[WARN] stock_pk_real 返回 {rc}，回退规则版兜底")
            run([sys.executable, os.path.join(SCRIPT_DIR, "seed_stock_pk.py")])
    else:
        print("[选股] 未检测到 LLM key，使用规则版兜底（真实大模型接入后自动切换）...")
        run([sys.executable, os.path.join(SCRIPT_DIR, "seed_stock_pk.py")])

    # 4. 汇总日志
    try:
        import requests
        pat = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
        if pat:
            url = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
            h = {"Authorization": f"Bearer {pat}", "Content-Type": "application/json"}
            now = datetime.datetime.now().isoformat()
            sql = (f"INSERT INTO public.etl_run_log (run_date, step_name, status, start_time, end_time, "
                   f"rows_affected, error_message) VALUES ('{today}','stock_pk_monthly','ok','{now}','{now}',"
                   f"1,'月度重选完成(真实 or 规则兜底)');")
            requests.post(url, headers=h, json={"query": sql}, timeout=60)
    except Exception as e:
        print(f"[WARN] 月度汇总日志写入失败: {e}")

    print("\n=== 股票组合 PK 月度重选编排完成 ===")


if __name__ == "__main__":
    main()
