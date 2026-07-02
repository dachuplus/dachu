#!/usr/bin/env python3
"""
修复全部货币型基金的收益率数据 (ytd/r1y/r3y/r5y)

问题：
  fund_combined 中货币基金（956只）的 ytd/r1y 数据错误，
  因为原始数据来自 pingzhongdata 净值计算，但货币基金净值格式不同（万份收益）。

修复方案：
  使用 rankhandler API 拉取正确的收益率数据。
  rankhandler 返回字段布局（货币基金专用）：
    f[0]=代码, f[1]=名称, f[2]=拼音, f[3]=净值日期,
    f[4]=万份收益?, f[5]=7日年化?,
    f[6]=近1周(%), f[7]=近1月(%), f[8]=近3月(%),
    f[9]=近6月/YTD(%), f[10]=近1年(%), f[11]=近2年(%),
    f[12]=近3年(%), f[13]=今年来(%), f[14]=规模(亿), ...
    f[24]=分类

  映射到 fund_combined:
    ytd = f[9] 或 f[13] (近6月/今年来)
    r1y = f[10] (近1年)
    r3y = f[12] (近3年)
    r5y = 需要从 rankhandler 获取（可能需要更多字段或单独请求）
"""

import sys
import os
import re
import time
import requests

sys.stdout.reconfigure(encoding='utf-8')

# ── Configuration ──
MGMT_TOKEN = os.environ.get("SUPABASE_MGMT_TOKEN") or ''
MGMT_URL = "https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query"
MGMT_HEADERS = {"Authorization": f"Bearer {MGMT_TOKEN}", "Content-Type": "application/json"}

API_RANKHANDLER = "https://fund.eastmoney.com/data/rankhandler.aspx"
HB_HEADERS = {
    "Referer": "https://fund.eastmoney.com/data/fundranking.html",
    "Content-Type": "application/x-www-form-urlencoded",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
}


def mgmt_query(sql):
    """执行 Management API SQL 查询"""
    resp = requests.post(MGMT_URL, headers=MGMT_HEADERS, json={"query": sql}, timeout=60)
    if resp.status_code in (200, 201):
        return resp.json()
    else:
        print(f"  [SQL ERROR {resp.status_code}] {sql[:80]}... → {resp.text[:200]}")
        return None


def fetch_all_hb_funds():
    """全量拉取 rankhandler 货币基金数据"""
    print("📡 全量拉取货币基金数据 via rankhandler...")
    
    all_data = {}  # code -> dict
    
    data_body = {
        "op": "ph", "dt": "hb", "ft": "hb", "rs": "", "gs": "0",
        "sc": "1nzf", "st": "desc", "pi": "1", "pn": "100", "zf": "diy"
    }
    
    # 先拉第一页获取总页数
    try:
        resp = requests.post(API_RANKHANDLER, data=data_body, headers=HB_HEADERS, timeout=30)
        resp.encoding = 'utf-8'
        text = resp.text
        
        # 解析总页数
        pages_m = re.search(r'allPages:"(\d+)"', text)
        count_m = re.search(r'datacount:"(\d+)"', text)
        total_pages = int(pages_m.group(1)) if pages_m else 96
        total_count = int(count_m.group(1)) if count_m else 956
        print(f"  总记录: {total_count}, 总页数: {total_pages}")
        
        # 解析第一页数据
        _parse_page(text, all_data)
        
    except Exception as e:
        print(f"  [ERROR] 初始请求失败: {e}")
        return all_data
    
    # 拉剩余页面
    for page in range(2, total_pages + 1):
        time.sleep(0.08)
        data_body["pi"] = str(page)
        try:
            resp = requests.post(API_RANKHANDLER, data=data_body, headers=HB_HEADERS, timeout=30)
            resp.encoding = 'utf-8'
            _parse_page(resp.text, all_data)
        except Exception as e:
            print(f"  [ERROR] page {page}: {e}")
        
        if page % 20 == 0 or page == total_pages:
            print(f"  进度: {page}/{total_pages} 页 ({len(all_data)} 条)")
    
    print(f"  ✅ 共获取 {len(all_data)} 只货币基金")
    return all_data


def _parse_page(text, all_data):
    """解析一页 rankhandler 响应"""
    datas_match = re.search(r'datas:\[(.*?)\](?:,|$)', text, re.DOTALL)
    if not datas_match:
        return
    
    items = re.findall(r'"([^"]*)"', datas_match.group(1))
    for item in items:
        parts = item.split(',')
        if len(parts) < 15:
            continue
        code = parts[0].strip()
        if not code or code in all_data:
            continue
        
        # rankhandler hb 字段布局（已验证 000330）:
        # f[0]=代码, f[1]=名称, f[2]=拼音缩写, f[3]=净值日期,
        # f[4]=万份收益, f[5]=七日年化,
        # f[6]=近1周%, f[7]=近1月%, f[8]=近3月%,
        # f[9]=近6月%(≈YTD), f[10]=近1年%, f[11]=近2年%,
        # f[12]=近3年%, f[13]=今年来%, f[14]=规模(亿),
        # f[15]=成立日期, ... f[24]=分类
        
        def _f(i):
            v = parts[i].strip() if i < len(parts) else ''
            try:
                return float(v)
            except (ValueError, TypeError):
                return None
        
        all_data[code] = {
            'code': code,
            'name': parts[1].strip() if len(parts) > 1 else '',
            # 收益率 (%)
            'r1w': _f(6),     # 近1周
            'r1m': _f(7),     # 近1月
            'r3m': _f(8),     # 近3月
            'r6m': _f(9),     # 近6月
            'ytd': _f(9),     # 今年来 (= 近6月，因为rankhandler中两者相同或相近)
            'r1y': _f(10),    # 近1年
            'r2y': _f(11),    # 近2年
            'r3y': _f(12),    # 近3年
            'r5y': None,      # rankhandler 不直接返回近5年
            # 规模
            'scale': _f(14),  # 规模(亿)
            # 分类
            't1': parts[24].strip() if len(parts) > 24 else '',
            '_raw': item,      # 保存原始行用于调试
        }
        
        # 如果 f[13] 有值且与 f[9] 不同，用 f[13] 作为 YTD
        r13 = _f(13)
        if r13 is not None and r13 != all_data[code]['ytd']:
            all_data[code]['ytd'] = r13


def fix_hb_returns(hb_data):
    """批量更新 fund_combined 中货币基金的收益率"""
    print(f"\n🔧 更新 fund_combined 中 {len(hb_data)} 只货币基金的收益率...")
    
    updated = 0
    errors = 0
    batch_size = 50
    codes_list = list(hb_data.keys())
    
    for i in range(0, len(codes_list), batch_size):
        batch_codes = codes_list[i:i + batch_size]
        set_clauses = []
        
        for code in batch_codes:
            d = hb_data[code]
            # 构建每个基金的 SET 子句
            vals = []
            if d['ytd'] is not None:
                vals.append(f'WHEN c=\'{code}\' THEN {d["ytd"]}')
            
            parts = []
            if d['r1y'] is not None:
                parts.append(f'r1y={_esc(d["r1y"])}')
            if d['r3y'] is not None:
                parts.append(f'r3y={_esc(d["r3y"])}')
            if d['ytd'] is not None:
                parts.append(f'ytd={_esc(d["ytd"])}')
            
            if parts:
                set_clauses.append((code, ', '.join(parts)))
        
        if set_clauses:
            # 逐条 UPDATE 更安全
            for code, set_str in set_clauses:
                sql = f"UPDATE fund_combined SET {set_str} WHERE c='{code}';"
                result = mgmt_query(sql)
                if result is not None:
                    updated += 1
                else:
                    errors += 1
        
        if (i + batch_size) % 300 == 0 or (i + batch_size) >= len(codes_list):
            print(f"  进度: {min(i + batch_size, len(codes_list))}/{len(codes_list)} (ok={updated}, err={errors})")
        time.sleep(0.03)
    
    print(f"  ✅ UPDATE 完成: updated={updated}, errors={errors}")


def _esc(val):
    """SQL 值转义"""
    if val is None:
        return 'NULL'
    return str(val)


def verify_fix():
    """抽样验证修复结果"""
    print("\n🔍 抽样验证...")
    test_codes = ['000330', '000659', '000324', '000434']
    
    for code in test_codes:
        result = mgmt_query(
            f"SELECT c, name, t0, ytd, r1y, r3y, r5y FROM fund_combined WHERE c='{code}';"
        )
        if result and len(result) > 0:
            row = result[0]
            print(f"  {row['c']} {row['name']:12s} | ytd={row.get('ytd')} r1y={row.get('r1y')} r3y={row.get('r3y')}")
    
    # 统计非 null 的比例
    stats = mgmt_query("""
        SELECT 
          COUNT(*) as total,
          COUNT(ytd) as has_ytd,
          COUNT(r1y) as has_r1y,
          COUNT(r3y) as has_r3y
        FROM fund_combined WHERE t0='货币型';
    """)
    if stats:
        s = stats[0]
        print(f"\n  货币型统计: 总计={s['total']}, ytd={s['has_ytd']}, r1y={s['has_r1y']}, r3y={s['has_r3y']}")


def main():
    start_time = time.time()
    
    # Step 1: 拉取全量货币基金数据
    hb_data = fetch_all_hb_funds()
    if not hb_data:
        print("❌ 未获取到任何货币基金数据，退出")
        return
    
    # Step 2: 抽样检查 000330
    if '000330' in hb_data:
        d = hb_data['000330']
        print(f"\n📋 000330 校验: ytd={d['ytd']} r1y={d['r1y']} r3y={d['r3y']}")
        print(f"   (预期: ytd=0.51, r1y=1.06, r3y=4.38)")
    
    # Step 3: 批量更新数据库
    fix_hb_returns(hb_data)
    
    # Step 4: 验证
    verify_fix()
    
    elapsed = time.time() - start_time
    print(f"\n⏱️  总耗时: {elapsed:.1f}秒")


if __name__ == '__main__':
    main()
