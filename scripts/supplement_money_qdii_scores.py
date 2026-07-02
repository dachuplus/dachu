#!/usr/bin/env python3
"""
补充货币基金和 QDII 基金的收益率数据 + 计算靠谱分

数据源：
  - QDII: 天天基金 rankhandler.aspx (ft=all)
  - 货币型: 天天基金 rankhandler.aspx (ft=hb)
输出：直接更新 fund_scores 表（仅更新 t0='货币型' 和 t0='QDII' 的基金）

收益率字段映射（rankhandler → fund_scores）：
  [7]=r0w, [8]=r1m, [9]=r3m, [10]=r6m
  [11]=r1y, [12]=r2y, [13]=r3y, [14]=ytd, [15]=return_all

评分策略：
  - 货币基金 + QDII：无回撤/夏普，全周期纯收益率排名百分位
  - k_all = 各周期加权平均（同 v7 权重）
  - 在全市场范围内排名（与其他基金可比）
"""

import json
import subprocess
import re
import sys
import os
import time
import urllib.request
import urllib.parse

# ===== 配置 =====
MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or ''
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'

# v7 评分权重
W_RET, W_DD, W_SR = 0.50, 0.25, 0.25
PERIOD_WEIGHTS = {'k0w': 5, 'k1m': 5, 'k3m': 10, 'k6m': 15,
                  'k1': 20, 'k2': 20, 'k3': 15, 'k5': 10}

PERIODS = [
    ('k0w', 'r0w'), ('k1m', 'r1m'), ('k3m', 'r3m'), ('k6m', 'r6m'),
    ('k1', 'r1y'), ('k2', 'r2y'), ('k3', 'r3y'), ('k5', 'r5y'),
]

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
    'Referer': 'https://fund.eastmoney.com/data/',
}


def pg(sql, timeout=120):
    """Execute SQL via Supabase Management API"""
    payload = json.dumps({'query': sql})
    r = subprocess.run(
        ['curl', '-s', '-X', 'POST', MGMT_API,
         '-H', f'Authorization: Bearer {MGMT_TOKEN}',
         '-H', 'Content-Type: application/json',
         '-d', payload],
        capture_output=True, text=True, timeout=timeout
    )
    if r.returncode != 0:
        raise RuntimeError(f'curl fail: {r.stderr[:200]}')
    t = r.stdout.strip()
    if not t:
        return []
    try:
        resp = json.loads(t)
    except json.JSONDecodeError:
        raise RuntimeError(f'Non-JSON: {t[:200]}')
    if isinstance(resp, dict) and resp.get('message'):
        raise RuntimeError(resp['message'][:300])
    return resp


def fetch_rankhandler(ft_type, label):
    """从 rankhandler.aspx (GET) 拉取基金收益率（用于 ft=all 等通用类型）"""
    print(f'拉取 rankhandler (ft={ft_type}) {label}数据...')
    all_data = {}
    page = 1
    total = 0

    while True:
        url = (f'https://fund.eastmoney.com/data/rankhandler.aspx'
               f'?op=ph&dt=kf&ft={ft_type}&rs=&gs=0&sc=dm&st=asc'
               f'&pi={page}&pn=200&v=0.1')
        req = urllib.request.Request(url, headers=HEADERS)
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            raw = resp.read().decode('utf-8')
        except Exception as e:
            print(f'  第{page}页失败: {e}')
            break

        if page == 1:
            m_total = re.search(r'allRecords:(\d+)', raw)
            total = int(m_total.group(1)) if m_total else 0
            print(f'  总记录数: {total}')

        m = re.search(r'datas:\[(.*?)\],allRecords', raw)
        if not m:
            print(f'  第{page}页无数据')
            break

        items = m.group(1).split('"')
        count = 0
        for item in items:
            item = item.strip()
            if not item or item.startswith(',') or len(item) < 20:
                continue
            fields = item.split(',')
            code = fields[0]
            try:
                data = {
                    'c': f'{code}.OF',
                    'r0w': _float(fields[7]) if len(fields) > 7 else None,
                    'r1m': _float(fields[8]) if len(fields) > 8 else None,
                    'r3m': _float(fields[9]) if len(fields) > 9 else None,
                    'r6m': _float(fields[10]) if len(fields) > 10 else None,
                    'r1y': _float(fields[11]) if len(fields) > 11 else None,
                    'r2y': _float(fields[12]) if len(fields) > 12 else None,
                    'r3y': _float(fields[13]) if len(fields) > 13 else None,
                    'ytd': _float(fields[14]) if len(fields) > 14 else None,
                    'return_all': _float(fields[15]) if len(fields) > 15 else None,
                }
                all_data[code] = data
                count += 1
            except Exception:
                pass

        print(f'  第{page}页: +{count}条 (累计 {len(all_data)})')
        if len(all_data) >= total or page >= 200:
            break
        page += 1
        time.sleep(0.3)

    print(f'  ✓ 共获取 {len(all_data)} 只基金收益率')
    return all_data


def fetch_hb_rankhandler():
    """从 rankhandler.aspx (POST) 拉取货币型基金收益率"""
    print('拉取 rankhandler 货币型数据 (POST ft=hb)...')
    all_data = {}

    hb_headers = {
        "Referer": "https://fund.eastmoney.com/data/fundranking.html",
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    }

    data_body = {
        "op": "ph", "dt": "hb", "ft": "hb", "rs": "", "gs": "0",
        "sc": "1nzf", "st": "desc", "pi": "1", "pn": "100",
        "zf": "diy", "v": "0.1"
    }

    # 第一页获取总页数和总记录数
    encoded = urllib.parse.urlencode(data_body).encode('utf-8')
    req = urllib.request.Request(
        'https://fund.eastmoney.com/data/rankhandler.aspx',
        data=encoded, headers=hb_headers
    )
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        text = resp.read().decode('utf-8')
    except Exception as e:
        print(f'  初始请求失败: {e}')
        return all_data

    pages_m = re.search(r'allPages:"(\d+)"', text)
    count_m = re.search(r'datacount:"(\d+)"', text)
    all_records_m = re.search(r'allRecords:(\d+)', text)
    total_pages = int(pages_m.group(1)) if pages_m else 10
    total_count = int(count_m.group(1)) if count_m else int(all_records_m.group(1)) if all_records_m else 0
    print(f'  总记录: {total_count}, 总页数: {total_pages}')

    _parse_hb_page(text, all_data)

    # 拉剩余页面
    for page in range(2, total_pages + 1):
        time.sleep(0.08)
        data_body["pi"] = str(page)
        encoded = urllib.parse.urlencode(data_body).encode('utf-8')
        req = urllib.request.Request(
            'https://fund.eastmoney.com/data/rankhandler.aspx',
            data=encoded, headers=hb_headers
        )
        try:
            resp = urllib.request.urlopen(req, timeout=30)
            text = resp.read().decode('utf-8')
            _parse_hb_page(text, all_data)
        except Exception as e:
            print(f'  第{page}页失败: {e}')

        if page % 20 == 0 or page == total_pages:
            print(f'  进度: {page}/{total_pages} 页 ({len(all_data)} 条)')

    print(f'  ✓ 共获取 {len(all_data)} 只货币基金')
    return all_data


def _parse_hb_page(text, all_data):
    """解析货币型 rankhandler POST 响应页面"""
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
        # hb 字段布局:
        # f[0]=代码, f[1]=名称, f[3]=日期, f[4]=万份收益, f[5]=七日年化
        # f[6]=近1周%, f[7]=近1月%, f[8]=近3月%
        # f[9]=近6月%/YTD, f[10]=近1年%, f[11]=近2年%, f[12]=近3年%
        # f[13]=今年来%, f[14]=规模(亿)
        def _f(i):
            v = parts[i].strip() if i < len(parts) else ''
            try:
                return float(v)
            except (ValueError, TypeError):
                return None

        r6m = _f(9)   # 近6月
        r13 = _f(13)  # 今年来
        ytd_val = r13 if r13 is not None else r6m

        all_data[code] = {
            'code': code,
            'r0w': _f(6),       # 近1周 → r0w
            'r1m': _f(7),       # 近1月
            'r3m': _f(8),       # 近3月
            'r6m': r6m,         # 近6月
            'r1y': _f(10),      # 近1年
            'r2y': _f(11),      # 近2年
            'r3y': _f(12),      # 近3年
            'ytd': ytd_val,     # 今年来
            'return_all': None,  # 货币型无成立以来收益
        }


def _float(v):
    """Safe float conversion, returns None for invalid"""
    try:
        val = float(v)
        return val if val != 0 else None
    except:
        return None


def batch_update_returns(updates, label):
    """Batch UPDATE returns using CASE WHEN, 50 funds per batch"""
    fields_order = ['r0w', 'r1m', 'r3m', 'r6m', 'r1y', 'r2y', 'r3y', 'ytd', 'return_all']
    batch_size = 50
    
    for batch_start in range(0, len(updates), batch_size):
        batch = updates[batch_start:batch_start + batch_size]
        codes = [u['c'] for u in batch]
        code_list = ', '.join([f"'{c}'" for c in codes])
        
        set_parts = []
        for field in fields_order:
            case_lines = []
            for u in batch:
                v = u['returns'].get(field)
                if v is not None:
                    case_lines.append(f"WHEN '{u['c']}' THEN {round(v, 4)}")
            if case_lines:
                case_when = '\n          '.join(case_lines)
                set_parts.append(
                    f'{field} = CASE c\n          {case_when}\n          ELSE {field}\n        END'
                )
        
        if set_parts:
            sql = f"""UPDATE fund_scores SET
        {',\n        '.join(set_parts)}
      WHERE c IN ({code_list})"""
            try:
                pg(sql, timeout=60)
                print(f'  {label}: {batch_start + len(batch)}/{len(updates)}')
            except Exception as e:
                print(f'  ✗ {label} batch {batch_start}: {str(e)[:200]}')
    
    return len(updates)


def batch_update_scores(score_updates, label):
    """Batch UPDATE scores using CASE WHEN, 50 funds per batch"""
    score_fields = ['k0w', 'k1m', 'k3m', 'k6m', 'k1', 'k2', 'k3', 'k5', 'k_all', 'score_grade']
    batch_size = 50
    
    for batch_start in range(0, len(score_updates), batch_size):
        batch = score_updates[batch_start:batch_start + batch_size]
        codes = [f['c'] for f in batch]
        code_list = ', '.join([f"'{c}'" for c in codes])
        
        set_parts = []
        for field in score_fields:
            if field == 'score_grade':
                case_lines = []
                for f in batch:
                    if f.get('_new_grade'):
                        case_lines.append(f"WHEN '{f['c']}' THEN '{f['_new_grade']}'")
                if case_lines:
                    case_when = '\n          '.join(case_lines)
                    set_parts.append(
                        f"score_grade = CASE c\n          {case_when}\n          ELSE score_grade\n        END"
                    )
            else:
                case_lines = []
                for f in batch:
                    if f.get(field) is not None:
                        case_lines.append(f"WHEN '{f['c']}' THEN {round(f[field], 4)}")
                if case_lines:
                    case_when = '\n          '.join(case_lines)
                    set_parts.append(
                        f'{field} = CASE c\n          {case_when}\n          ELSE {field}\n        END'
                    )
        
        if set_parts:
            sql = f"""UPDATE fund_scores SET
        {',\n        '.join(set_parts)}
      WHERE c IN ({code_list})"""
            try:
                pg(sql, timeout=60)
            except Exception as e:
                print(f'  ✗ score batch {batch_start}: {str(e)[:200]}')
        
        print(f'  {label}: {batch_start + len(batch)}/{len(score_updates)}')
    
    return len(score_updates)


def main():
    print('=' * 60)
    print('补充货币基金 + QDII 基金评分 (批量UPDATE版)')
    print('=' * 60)

    # Step 1: 查询需要补充的基金列表
    print('\n步骤1: 查询需要补充的基金...')
    result = pg("""
    SELECT c, n, t0, k_all FROM fund_scores
    WHERE t0 IN ('货币型', 'QDII')
    """)
    
    target_funds = {}
    by_type = {}
    for r in result:
        code = r['c'].replace('.OF', '')
        target_funds[code] = r
        t = r['t0']
        by_type[t] = by_type.get(t, 0) + 1
    
    print(f'  货币型+QDII 合计: {len(target_funds)} 只')
    for t, cnt in sorted(by_type.items()):
        print(f'    {t}: {cnt} 只')

    # ====== Part A: QDII (ft=all) ======
    print('\n' + '=' * 60)
    print('Part A: QDII 基金 (ft=all)')
    print('=' * 60)
    
    qdii_updates = []
    qdii_codes = {code for code, r in target_funds.items() if r['t0'] == 'QDII'}
    
    if qdii_codes:
        # Fetch from ft=all
        all_returns = fetch_rankhandler('all', 'QDII')
        
        # Match QDII funds
        matched = 0
        for code, rdata in all_returns.items():
            if code in qdii_codes:
                # Check if data is valid (has at least one non-None return)
                has_data = any(rdata.get(f) is not None for f in ['r0w','r1m','r3m','r6m','r1y','r2y','r3y','ytd','return_all'])
                if has_data:
                    qdii_updates.append({
                        'c': f'{code}.OF',
                        'returns': rdata
                    })
                    matched += 1
        
        print(f'\n  QDII 匹配成功: {matched}/{len(qdii_codes)}')
        
        if qdii_updates:
            print(f'\n步骤 A2: 批量更新 QDII 收益率字段...')
            batch_update_returns(qdii_updates, 'QDII收益率')
            print(f'  ✓ QDII 收益率更新完成')
        else:
            print('  ⚠ QDII 无匹配数据')
    else:
        print('  QDII 无需补充（已有完整数据）')

    # ====== Part B: 货币型 (ft=hb) ======
    print('\n' + '=' * 60)
    print('Part B: 货币型基金 (ft=hb)')
    print('=' * 60)
    
    hb_updates = []
    hb_codes = {code for code, r in target_funds.items() if r['t0'] == '货币型'}
    
    if hb_codes:
        # Fetch from ft=hb using POST
        hb_returns = fetch_hb_rankhandler()
        
        # Match 货币型 funds
        matched = 0
        for code, rdata in hb_returns.items():
            if code in hb_codes:
                has_data = any(rdata.get(f) is not None for f in ['r0w','r1m','r3m','r6m','r1y','r2y','r3y','ytd'])
                if has_data:
                    # Normalize: map hb keys to standard keys with .OF suffix
                    normalized = {
                        'c': f'{code}.OF',
                        'returns': {
                            'r0w': rdata.get('r0w'),
                            'r1m': rdata.get('r1m'),
                            'r3m': rdata.get('r3m'),
                            'r6m': rdata.get('r6m'),
                            'r1y': rdata.get('r1y'),
                            'r2y': rdata.get('r2y'),
                            'r3y': rdata.get('r3y'),
                            'ytd': rdata.get('ytd'),
                            'return_all': rdata.get('return_all'),
                        }
                    }
                    hb_updates.append(normalized)
                    matched += 1
        
        print(f'\n  货币型 匹配成功: {matched}/{len(hb_codes)}')
        
        if hb_updates:
            print(f'\n步骤 B2: 批量更新货币型收益率字段...')
            batch_update_returns(hb_updates, '货币型收益率')
            print(f'  ✓ 货币型收益率更新完成')
        else:
            print('  ⚠ 货币型无匹配数据')
    else:
        print('  货币型无需补充（已有完整数据）')

    # ====== Part C: 计算评分 ======
    print('\n' + '=' * 60)
    print('Part C: 计算全市场排名靠谱分')
    print('=' * 60)
    
    all_updates = qdii_updates + hb_updates
    all_target_codes = {u['c'] for u in all_updates}
    
    if not all_target_codes:
        print('  ⚠ 没有需要评分的基金，退出')
        return
    
    print(f'\n  需要评分的基金: {len(all_target_codes)} 只')
    
    # 获取全市场基金数据用于排名
    print('  获取全市场基金收益率用于排名...')
    result = pg("""
    SELECT c, r0w, r1m, r3m, r6m, r1y, r2y, r3y, r5y, 
           dd1y, dd2y, dd3y, dd5y, sr1y, sr2y, sr3y, sr5y, 
           k0w, k1m, k3m, k6m, k1, k2, k3, k5, k_all, score_grade, t0
    FROM fund_scores
    """, timeout=300)
    all_funds = result
    print(f'  全市场: {len(all_funds)} 只基金')
    
    # 将目标基金的新收益率数据合并到 all_funds 中
    update_map = {u['c']: u['returns'] for u in all_updates}
    for f in all_funds:
        if f['c'] in update_map:
            for k, v in update_map[f['c']].items():
                f[k] = v
    
    # 对各周期计算排名百分位
    all_indexed = list(range(len(all_funds)))
    
    period_configs = [
        ('k0w', 'r0w', None, None),
        ('k1m', 'r1m', None, None),
        ('k3m', 'r3m', None, None),
        ('k6m', 'r6m', None, None),
        ('k1', 'r1y', 'dd1y', 'sr1y'),
        ('k2', 'r2y', 'dd2y', 'sr2y'),
        ('k3', 'r3y', 'dd3y', 'sr3y'),
        ('k5', 'r5y', 'dd5y', 'sr5y'),
    ]

    print('\n  计算各周期排名百分位...')
    for pk, rk, dk, sk in period_configs:
        valid = [(i, all_funds[i]) for i in all_indexed if all_funds[i].get(rk) is not None]
        vn = len(valid)
        if vn == 0:
            continue

        # 收益排位（降序：越高越好）
        ret_ranked = sorted(valid, key=lambda x: x[1].get(rk, 0) or 0, reverse=True)
        ret_pct = {}
        for rank, (idx, _) in enumerate(ret_ranked):
            ret_pct[idx] = (1 - rank / (vn - 1)) * 100 if vn > 1 else 50.0

        # 回撤排位（升序：回撤越小越好 → 排位越高）
        dd_pct = {}
        if dk:
            dd_valid = [(i, all_funds[i]) for i, f in valid if f.get(dk) is not None]
            dvn = len(dd_valid)
            if dvn > 0:
                dd_ranked = sorted(dd_valid, key=lambda x: x[1].get(dk, 0) or 0, reverse=True)
                for rank, (idx, _) in enumerate(dd_ranked):
                    dd_pct[idx] = (1 - rank / (dvn - 1)) * 100 if dvn > 1 else 50.0

        # 夏普排位（降序：越高越好）
        sr_pct = {}
        if sk:
            sr_valid = [(i, all_funds[i]) for i, f in valid if f.get(sk) is not None]
            svn = len(sr_valid)
            if svn > 0:
                sr_ranked = sorted(sr_valid, key=lambda x: x[1].get(sk, 0) or 0, reverse=True)
                for rank, (idx, _) in enumerate(sr_ranked):
                    sr_pct[idx] = (1 - rank / (svn - 1)) * 100 if svn > 1 else 50.0

        # 合成评分
        for idx, f in valid:
            rp = ret_pct.get(idx)
            if rp is None:
                continue
            dp = dd_pct.get(idx)
            sp = sr_pct.get(idx)
            if dp is not None and sp is not None:
                score = round(W_RET * rp + W_DD * dp + W_SR * sp, 4)
            else:
                score = round(rp, 4)  # 纯收益排名（货币/QDII 无回撤/夏普）
            all_funds[idx][pk] = score

        print(f'    {pk}: {vn} 只有效数据')

    # 计算 k_all 和 score_grade
    print('\n  计算 k_all 和 score_grade...')
    k_all_updated = 0
    scored_funds = []
    
    for idx, f in enumerate(all_funds):
        total_w = 0
        weighted_sum = 0
        for kf, w in PERIOD_WEIGHTS.items():
            val = float(f.get(kf) or 0)
            if val > 0 and w > 0:
                weighted_sum += val * w
                total_w += w
        
        is_target = f['c'] in all_target_codes
        
        if total_w > 0 and is_target:
            f['k_all'] = round(weighted_sum / total_w, 4)
            k_all_updated += 1
        elif is_target:
            f['k_all'] = None

        if f['k_all'] is not None:
            scored_funds.append((idx, float(f['k_all'])))

    # score_grade 全市场排名
    scored_funds.sort(key=lambda x: x[1], reverse=True)
    n_scored = len(scored_funds)
    
    # 为所有有 k_all 的基金重新计算 grade
    grade_by_idx = {}
    for rank, (idx, ka) in enumerate(scored_funds):
        pct = (1 - rank / (n_scored - 1)) * 100 if n_scored > 1 else 50
        if pct >= 80:
            grade_by_idx[idx] = 'green'
        elif pct >= 50:
            grade_by_idx[idx] = 'blue'
        elif pct > 0:
            grade_by_idx[idx] = 'orange'

    for idx, f in enumerate(all_funds):
        if f['c'] in all_target_codes:
            f['_new_grade'] = grade_by_idx.get(idx)

    print(f'  货币/QDII 新评分: {k_all_updated} 只')

    # ====== Part D: 批量更新评分到数据库 ======
    print('\n' + '=' * 60)
    print('Part D: 批量更新评分到数据库')
    print('=' * 60)
    
    score_updates = []
    for f in all_funds:
        if f['c'] not in all_target_codes:
            continue
        score_updates.append(f)
    
    print(f'\n  待更新评分: {len(score_updates)} 只')
    batch_update_scores(score_updates, '评分更新')
    print(f'  ✓ 评分更新完成')

    # ====== Step 7: 验证 ======
    print('\n' + '=' * 60)
    print('步骤7: 验证结果')
    print('=' * 60)
    
    result = pg("""
    SELECT t0, count(*) as cnt, count(k_all) as scored
    FROM fund_scores
    GROUP BY t0 ORDER BY cnt DESC
    """)
    print('  最终分类分布:')
    for row in result:
        print(f'    {row["t0"]:6s}: {row["cnt"]:5d} 只 (评分: {row["scored"]})')

    result = pg("""
    SELECT t0, score_grade, count(*) as cnt
    FROM fund_scores WHERE t0 IN ('货币型', 'QDII')
    GROUP BY t0, score_grade ORDER BY t0, score_grade
    """)
    print('  货币/QDII 评分分布:')
    for row in result:
        grade = row["score_grade"] or 'NULL'
        print(f'    {row["t0"]} {grade}: {row["cnt"]}')

    print(f'\n✅ 货币基金 + QDII 基金评分补充完成！')


if __name__ == '__main__':
    main()
