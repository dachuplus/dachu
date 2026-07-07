#!/usr/bin/env python3
"""
fetch_fund_basic_info.py — 抓取天天基金 fundf10 基金基本概况页，补充 fund_scores 基本信息

数据源：https://fundf10.eastmoney.com/jbgk_{code}.html
解析字段：
  - fund_manager   基金经理（多个用 "、" 连接）
  - company        管理人（基金管理人）
  - t0 / t1        一级分类 / 二级分类（从"基金类型"拆分，如"债券型-混合二级"）
  - fund_scale     净值规模（亿元）
  - share_scale    份额规模（亿份）
  - manage_fee     管理费率（%/年）
  - custody_fee    托管费率（%/年）
  - sale_fee       销售服务费率（%/年）
  - found_date     成立日期（YYYY-MM-DD）
  - full_name      基金全称
  - short_name     基金简称

用法：
  # 全量抓取（首次回填，约 2 万只，CI 中耗时较长）
  python3 fetch_fund_basic_info.py --full

  # 仅抓取缺失数据的基金（每日 CI 默认）
  python3 fetch_fund_basic_info.py

  # 抽样测试（先验证解析正确性）
  python3 fetch_fund_basic_info.py --sample 50

  # 指定输出文件
  python3 fetch_fund_basic_info.py --output scripts/fund_basic_info.ndjson
"""
import json
import os
import re
import sys
import time
import argparse
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
HEADERS = {'apikey': ANON_KEY, 'Authorization': f'Bearer {ANON_KEY}'}

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OUTPUT = os.path.join(SCRIPT_DIR, 'fund_basic_info.ndjson')

UA_LIST = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
]

# ── 解析工具 ────────────────────────────────────────────────────────────────

def _extract_td(html, label):
    """从 fundf10 表格中提取 <th>label</th><td>...</td> 的 td 内容（含 HTML 标签）"""
    pat = re.escape(label) + r'</th>\s*<td[^>]*>(.*?)</td>'
    m = re.search(pat, html, re.DOTALL)
    return m.group(1) if m else None

def _clean_text(s):
    if s is None:
        return None
    # 去掉 HTML 标签
    s = re.sub(r'<[^>]+>', '', s)
    # 去掉空白
    s = s.strip()
    return s if s else None

def _parse_scale(s):
    """'9.61亿元（截止至：2026年03月31日）' → 9.61 (float)"""
    if not s:
        return None
    m = re.search(r'([\d.]+)\s*亿元', s)
    return float(m.group(1)) if m else None

def _parse_share(s):
    """'5.6742亿份' 或 '<a>5.6742</a>亿份' → 5.6742"""
    if not s:
        return None
    m = re.search(r'([\d.]+)\s*亿份', s)
    return float(m.group(1)) if m else None

def _parse_fee(s):
    """'0.70%（每年）' → 0.70"""
    if not s:
        return None
    m = re.search(r'([\d.]+)\s*%', s)
    return float(m.group(1)) if m else None

def _parse_found_date(s):
    """'2016年09月27日 / 2.911亿份' → '2016-09-27'"""
    if not s:
        return None
    m = re.search(r'(\d{4})年(\d{2})月(\d{2})日', s)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'
    return None

def _parse_managers(s):
    """'<a href="...">柳万军</a> <a href="...">张三</a>' → '柳万军、张三'"""
    if not s:
        return None
    names = re.findall(r'>([^<]+)</a>', s)
    if names:
        return '、'.join(n.strip() for n in names if n.strip())
    # 降级：直接取文本
    txt = _clean_text(s)
    return txt

def _parse_company(s):
    """'<a href="...">华夏基金</a>' → '华夏基金'"""
    if not s:
        return None
    m = re.search(r'>([^<]+)</a>', s)
    if m:
        return m.group(1).strip()
    return _clean_text(s)

def parse_jbgk(html):
    """解析 fundf10 jbgk 页面 HTML，返回字段 dict（仅含成功解析的字段）"""
    result = {}

    # 基金类型 → t0 / t1
    type_html = _extract_td(html, '基金类型')
    if type_html:
        t = _clean_text(type_html)
        if t:
            if '-' in t:
                t0, t1 = t.split('-', 1)
                result['t0'] = t0.strip()
                result['t1'] = t1.strip()
            else:
                result['t0'] = t.strip()
                # t1 留空（与现有 DB 约定一致：无二级时 t1=t0 由下游处理）

    # 基金经理
    mgr_html = _extract_td(html, '基金经理人')
    if mgr_html:
        mgr = _parse_managers(mgr_html)
        if mgr:
            result['fund_manager'] = mgr

    # 管理人
    comp_html = _extract_td(html, '基金管理人')
    if comp_html:
        comp = _parse_company(comp_html)
        if comp:
            result['company'] = comp

    # 净值规模
    scale_html = _extract_td(html, '净资产规模')
    if scale_html:
        v = _parse_scale(scale_html)
        if v is not None:
            result['fund_scale'] = v

    # 份额规模
    share_html = _extract_td(html, '份额规模')
    if share_html:
        v = _parse_share(share_html)
        if v is not None:
            result['share_scale'] = v

    # 管理费率
    mf_html = _extract_td(html, '管理费率')
    if mf_html:
        v = _parse_fee(mf_html)
        if v is not None:
            result['manage_fee'] = v

    # 托管费率
    cf_html = _extract_td(html, '托管费率')
    if cf_html:
        v = _parse_fee(cf_html)
        if v is not None:
            result['custody_fee'] = v

    # 销售服务费率
    sf_html = _extract_td(html, '销售服务费率')
    if sf_html:
        v = _parse_fee(sf_html)
        if v is not None:
            result['sale_fee'] = v

    # 成立日期
    fd_html = _extract_td(html, '成立日期/规模')
    if fd_html:
        v = _parse_found_date(fd_html)
        if v:
            result['found_date'] = v

    # 基金全称 / 简称（备用）
    fn_html = _extract_td(html, '基金全称')
    if fn_html:
        v = _clean_text(fn_html)
        if v:
            result['full_name'] = v
    sn_html = _extract_td(html, '基金简称')
    if sn_html:
        v = _clean_text(sn_html)
        if v:
            result['short_name'] = v

    return result


def fetch_one(code):
    """抓取单只基金 jbgk 页面并解析，返回 (code, result_dict_or_None, error_or_None)"""
    url = f'https://fundf10.eastmoney.com/jbgk_{code}.html'
    try:
        resp = requests.get(url, headers={'User-Agent': UA_LIST[hash(code) % len(UA_LIST)]},
                            timeout=15)
        if resp.status_code != 200:
            return code, None, f'HTTP {resp.status_code}'
        # fundf10 通常为 UTF-8；若关键字段缺失则尝试 GBK 降级
        resp.encoding = 'utf-8'
        html = resp.text
        if '基金类型' not in html and '基金经理' not in html:
            resp.encoding = 'gbk'
            html = resp.text
        if '基金类型' not in html and '基金经理' not in html:
            return code, None, '页面无基金数据（可能代码不存在）'
        parsed = parse_jbgk(html)
        if not parsed:
            return code, None, '解析为空'
        return code, parsed, None
    except Exception as e:
        return code, None, str(e)[:100]


# ── 主流程 ───────────────────────────────────────────────────────────────────

def load_existing_codes():
    """从 Supabase 读取现有 fund_scores 的代码 + 已有基本信息，返回 dict[code] = row"""
    print('读取 fund_scores 现有数据...', flush=True)
    existing = {}
    offset = 0
    limit = 1000
    while True:
        url = (f'{SUPABASE_URL}/rest/v1/fund_scores'
               f'?select=c,fund_manager,company,t0,t1,share_scale,custody_fee,sale_fee,found_date'
               f'&limit={limit}&offset={offset}')
        resp = requests.get(url, headers=HEADERS, timeout=60)
        if resp.status_code != 200:
            print(f'  [WARN] 读取失败 HTTP {resp.status_code}')
            break
        batch = resp.json()
        if not batch:
            break
        for r in batch:
            c = (r.get('c') or '').replace('.OF', '')
            if c:
                existing[c] = r
        offset += len(batch)
        if len(batch) < limit:
            break
    print(f'  共 {len(existing)} 只基金', flush=True)
    return existing


def main():
    parser = argparse.ArgumentParser(description='抓取 fundf10 基金基本概况')
    parser.add_argument('--output', default=DEFAULT_OUTPUT, help='输出 NDJSON 路径')
    parser.add_argument('--full', action='store_true', help='全量抓取（忽略已有数据）')
    parser.add_argument('--sample', type=int, default=0, help='仅抽样 N 只用于测试')
    parser.add_argument('--workers', type=int, default=8, help='并发数')
    parser.add_argument('--delay', type=float, default=0.05, help='每请求间隔（秒）')
    args = parser.parse_args()

    existing = load_existing_codes()

    # 确定需要抓取的代码列表
    if args.full:
        codes = list(existing.keys())
        print(f'全量模式：抓取 {len(codes)} 只', flush=True)
    else:
        # 仅抓取缺失数据的基金（基金经理/管理人/分类/任一新增列缺失即需补）
        need = []
        for c, r in existing.items():
            miss = (not r.get('fund_manager')) or (not r.get('company')) or \
                   (not r.get('t0')) or (r.get('share_scale') is None) or \
                   (r.get('custody_fee') is None) or (r.get('sale_fee') is None) or \
                   (not r.get('found_date'))
            if miss:
                need.append(c)
        codes = need
        print(f'补缺模式：{len(need)} 只基金缺失 基金经理/管理人/分类/份额/费率/成立日期', flush=True)

    if args.sample > 0:
        codes = codes[:args.sample]
        print(f'抽样模式：仅抓取 {len(codes)} 只', flush=True)

    if not codes:
        print('无需抓取，退出')
        return

    # 并发抓取
    results = {}
    errors = 0
    t0 = time.time()
    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(fetch_one, c): c for c in codes}
        for fut in as_completed(futures):
            code, parsed, err = fut.result()
            done += 1
            if parsed:
                results[code] = parsed
            else:
                errors += 1
            if done % 500 == 0:
                print(f'  进度 {done}/{len(codes)} | 成功 {len(results)} | 失败 {errors} | {time.time()-t0:.0f}s', flush=True)
            time.sleep(args.delay)

    print(f'✅ 抓取完成：成功 {len(results)} / {len(codes)}，失败 {errors}（{time.time()-t0:.0f}s）', flush=True)

    # 写入 NDJSON
    count = 0
    with open(args.output, 'w', encoding='utf-8') as f:
        for code, parsed in results.items():
            out = {'c': code, **parsed}
            f.write(json.dumps(out, ensure_ascii=False) + '\n')
            count += 1
    print(f'✅ 写入 {count} 条 → {args.output}', flush=True)


if __name__ == '__main__':
    main()
