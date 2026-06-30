#!/usr/bin/env python3
"""
导出 Supabase 所有 public 表为 Excel 文件到 public/downloads/ 目录
用法: python scripts/export_all_tables.py [--output-dir public/downloads]
"""
import os, sys, json, requests
from datetime import datetime

# ===== 配置 =====
SUPABASE_URL = os.environ.get('SUPABASE_URL') or os.environ.get('VITE_SUPABASE_URL') or 'https://tqhtegazxykkqfcpejky.supabase.co'
SUPABASE_KEY = os.environ.get('SUPABASE_ANON_KEY') or os.environ.get('VITE_SUPABASE_ANON_KEY') or 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'

# 判断是否 CI 环境
IS_CI = os.environ.get('CI') == 'true' or os.environ.get('GITHUB_ACTIONS') == 'true'
if IS_CI:
    import subprocess
    result = subprocess.run(['pip', 'install', 'openpyxl'], capture_output=True, text=True)
    print(f"[CI] pip install openpyxl: {result.returncode}")
else:
    try:
        import openpyxl
    except ImportError:
        print("请先安装 openpyxl: pip install openpyxl requests")
        sys.exit(1)

import openpyxl
from openpyxl.utils import get_column_letter

# 输出目录
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'public', 'downloads')
if '--output-dir' in sys.argv:
    idx = sys.argv.index('--output-dir')
    OUTPUT_DIR = sys.argv[idx + 1]
os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    'apikey': SUPABASE_KEY,
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json',
}

# ===== 表定义 =====
TABLES = {
    'fund_combined': {
        'name': '基金综合数据表',
        'desc': '基金分类(t0/t1)、公司/规模/费率、收益(ytd/r1y/r3y/r5y)、风险指标(dd1y/sr1y)、持有人数、评分(k_all/score_grade/k0w~k10) — 所有数据核心合并表，19+ 周期评分全覆盖',
    },
    'fund_scores': {
        'name': '基金评分表',
        'desc': 'CI 每日更新的核心评分表，11 周期 × 3 维度加权评分（k0w/k1m/k3m/k6m/k1/k2/k3/k5/k_all）、百分位评级(score_grade)、基金分类(t0/t1)、份额类型(sg)',
    },
    'fund_quarterly_scores': {
        'name': '季度评分表',
        'desc': '基于季报数据的各时间窗口评分（score_3m/6m/1y/2y/3y/5y/7y/10y），含原始 quarterly_data JSON',
    },
    'fund_scores_meta': {
        'name': '评分元数据表',
        'desc': '评分更新时间、基金总数、有评分数、净值日期等元信息',
    },
    'config': {
        'name': '配置表',
        'desc': '全站配置项（键值对，含 meta、tsq 时间戳）',
    },
    'macro_history': {
        'name': '宏观历史数据表',
        'desc': '中国10年国债(cn10y)、美国10年国债(us10y)、Shibor、CPI、M2 的历史数据，覆盖 1996-至今',
    },
    'index_pe_history': {
        'name': '指数PE历史表',
        'desc': '沪深300等指数的 PE/PB 历史估值数据',
    },
    'site_stats': {
        'name': '站点统计表',
        'desc': '网站访问量等统计指标',
    },
    'tougu_products': {
        'name': '投顾产品表',
        'desc': '天天基金/华宝/盈米/新浪仓石四来源的基金投顾产品，含收益率、最大回撤、标签分类',
    },
    'user_portfolios': {
        'name': '用户组合表',
        'desc': '用户自建基金组合数据（portfolio_data JSON），关联用户 ID',
    },
    'user_profiles': {
        'name': '用户档案表',
        'desc': '用户注册信息、登录次数、最后登录时间',
    },
}

# 敏感表 / 含用户数据 — 仅在"我的"页面已登录时可见下载
SENSITIVE_TABLES = {'user_portfolios', 'user_profiles'}

# ===== 导出 =====
def get_table_data(table_name):
    """分页获取表数据"""
    all_rows = []
    offset = 0
    limit = 1000  # Supabase REST API default max rows per request
    
    while True:
        resp = requests.get(
            f'{SUPABASE_URL}/rest/v1/{table_name}?select=*&limit={limit}&offset={offset}',
            headers=HEADERS, timeout=60
        )
        if resp.status_code != 200:
            print(f'  ⚠️ {table_name}: HTTP {resp.status_code}')
            break
        rows = resp.json()
        if not rows:
            break
        all_rows.extend(rows)
        offset += len(rows)
        print(f'  📥 {table_name}: {offset} rows...')
        if len(rows) < limit:
            break
    
    return all_rows

def export_to_excel(table_name, rows, output_path):
    """导出为 Excel"""
    if not rows:
        # 空表也导出，至少有个表头
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = table_name[:31]
        ws.append(['(空表)'])
        wb.save(output_path)
        return len(rows)
    
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = table_name[:31]
    
    # 列名
    columns = list(rows[0].keys())
    ws.append(columns)
    
    # 加粗表头
    from openpyxl.styles import Font
    for col_idx in range(1, len(columns) + 1):
        ws.cell(row=1, column=col_idx).font = Font(bold=True)
    
    # 数据行 — 处理非标量值（JSON/对象等）
    import json as _json
    def safe_val(v):
        if v is None: return ''
        if isinstance(v, (int, float, str, bool)): return v
        try: return _json.dumps(v, ensure_ascii=False)
        except: return str(v)
    
    for row in rows:
        ws.append([safe_val(row.get(col, '')) for col in columns])
    
    # 冻结首行
    ws.freeze_panes = 'A2'
    
    wb.save(output_path)
    return len(rows)

def main():
    print(f'📊 导出 allfund 数据库全部表到 {OUTPUT_DIR}/')
    print(f'⏰ {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    
    results = {}
    total_size = 0
    
    for table_name in sorted(TABLES.keys()):
        print(f'⬇️ 导出 {table_name} ...')
        rows = get_table_data(table_name)
        
        output_path = os.path.join(OUTPUT_DIR, f'{table_name}.xlsx')
        count = export_to_excel(table_name, rows, output_path)
        
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        total_size += size_mb
        results[table_name] = {'rows': count, 'size_mb': size_mb, 'path': f'/downloads/{table_name}.xlsx'}
        print(f'  ✅ {table_name}: {count} rows, {size_mb:.2f}MB → {table_name}.xlsx')
    
    # 保存 JSON 索引文件（供前端读取）
    index_path = os.path.join(OUTPUT_DIR, 'index.json')
    with open(index_path, 'w') as f:
        json.dump({
            'updated_at': datetime.now().isoformat(),
            'tables': results,
        }, f, ensure_ascii=False, indent=2)
    
    print(f'\n✅ 全部完成！{len(results)} 张表，总大小 {total_size:.2f}MB')
    print(f'📋 索引文件: {index_path}')

if __name__ == '__main__':
    main()
