#!/usr/bin/env python3
"""
修复 fund_scores 表中 fund_manager 字段的错误数据。
问题：153条记录的 fund_manager 存储了基金名称(n)而非真实经理姓名。
数据源：akshare.fund_manager_em() -> 35,200条经理数据，含[现任基金代码, 姓名]
"""

import os
import sys
import time
import requests

PAT = os.environ.get("SUPABASE_PAT") or os.environ.get("SUPABASE_MGMT_TOKEN")
MGMT_API = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
HEADERS = {
    "Authorization": f"Bearer {PAT}",
    "Content-Type": "application/json",
}


def run_sql(sql):
    resp = requests.post(MGMT_API, headers=HEADERS, json={"query": sql}, timeout=30)
    if resp.status_code not in (200, 201):
        print(f"  SQL error {resp.status_code}: {resp.text[:200]}")
        return None
    return resp.json()


def main():
    print("=== 修复 fund_scores.fund_manager (153条) ===\n")

    # 1. 获取错误列表
    wrong = run_sql(
        "SELECT c, n, fund_manager FROM fund_scores WHERE fund_manager = n ORDER BY c;"
    )
    if not wrong:
        print("无需修复"); return
    print(f"共 {len(wrong)} 条需修复\n")

    # 2. 加载全量经理表 (fund_manager_em)
    print("正在加载 akshare 基金经理数据...")
    import akshare as ak
    mgr_df = ak.fund_manager_em()
    print(f"经理表: {mgr_df.shape[0]} 条\n")

    # 构建代码→姓名 映射 (取每个代码的第一个经理)
    code_to_mgr = {}
    for _, row in mgr_df.iterrows():
        code = str(row['现任基金代码']).strip()
        name = str(row['姓名']).strip()
        if code and code not in code_to_mgr and name and len(name) < 20:  # 合理的名字长度
            code_to_mgr[code] = name

    print(f"映射表覆盖 {len(code_to_mgr)} 只基金\n")

    # 3. 逐条修复
    fixed, failed, skipped = [], [], []
    for i, r in enumerate(wrong):
        code_full = r['c']       # "008528.OF"
        code_6 = code_full.replace('.OF', '')  # "008528"
        fund_name = r['n']

        new_mgr = code_to_mgr.get(code_6, '')

        if new_mgr and new_mgr != fund_name:
            safe_new = new_mgr.replace("'", "''")
            sql = f"UPDATE fund_scores SET fund_manager = '{safe_new}' WHERE c = '{code_full}' AND fund_manager = '{fund_name}';"
            result = run_sql(sql)
            if result is not None:
                fixed.append((code_full, fund_name, new_mgr))
                print(f"[{i+1}/{len(wrong)}] ✅ {code_6} => {new_mgr}")
            else:
                failed.append(code_full)
                print(f"[{i+1}/{len(wrong)}] ❌ {code_6} SQL失败")
        elif new_mgr == fund_name:
            skipped.append(code_full)
            print(f"[{i+1}/{len(wrown)}] ⚠️ {code_6} 经理名仍与基金名相同")
        else:
            failed.append(code_full)
            print(f"[{i+1}/{len(wrong)}] ❌ {code_6} 未在经理表中找到")

        if (i + 1) % 10 == 0:
            time.sleep(0.5)

    # 4. 汇总
    print(f"\n{'='*50}")
    print(f"✅ 成功修复: {len(fixed)} 条")
    print(f"⏭️  跳过(同名): {len(skipped)} 条")
    print(f"❌ 失败: {len(failed)} 条")

    if failed:
        print("\n失败列表:")
        for c in failed[:20]:
            print(f"  {c}")


if __name__ == "__main__":
    main()
