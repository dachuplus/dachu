#!/usr/bin/env python3
"""
聚源基金分类映射脚本
- 加载 Excel 分类标准（主代码→一级/二级分类）
- 查询 Supabase 全量基金代码和名称
- 通过基金名称匹配，将 B/C/D/E/Y 等份额映射到主代码的分类
- 通过 REST API 批量更新 fund_scores.t1 列
"""
import json, subprocess, sys, os, time

SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
BATCH = 500  # REST API 批量更新每批条数

# ── 1. 加载 Excel 分类映射 ───────────────────────────────────────────
def load_excel_mapping():
    """加载 /tmp/juyuan_classify.json → {code: (t0, t1)}"""
    with open('/tmp/juyuan_classify.json', 'r') as f:
        data = json.load(f)
    mapping = {}
    for code, info in data.items():
        mapping[code] = (info['l1'], info['l2'])
    print(f'[1/5] 加载 Excel 分类映射: {len(mapping)} 条主代码')
    return mapping

# ── 2. 查询 Supabase 全量基金 ─────────────────────────────────────────
def fetch_all_funds():
    """查询 fund_scores 表所有基金的 c(代码) 和 n(名称)，使用 Range 分页"""
    print('[2/5] 查询 Supabase 全量基金数据...', flush=True)
    all_funds = []
    offset = 0
    limit = 1000  # Supabase REST API 单次最大 1000
    while True:
        range_header = f'{offset}-{offset + limit - 1}'
        r = subprocess.run(
            ['curl', '-s', '-D', '-',
             '-H', f'apikey: {ANON_KEY}',
             '-H', f'Authorization: Bearer {ANON_KEY}',
             '-H', f'Range: {range_header}',
             f'{SUPABASE_URL}/rest/v1/fund_scores?select=c,n,t0,t1&order=c'],
            capture_output=True, text=True, timeout=60
        )
        # 分离 headers 和 body
        parts = r.stdout.split('\r\n\r\n', 1)
        body = parts[1] if len(parts) > 1 else r.stdout
        try:
            batch = json.loads(body)
        except json.JSONDecodeError:
            # Body 可能包含 headers 残余
            body = body.split('\n\n')[-1] if '\n\n' in body else body
            try:
                batch = json.loads(body)
            except json.JSONDecodeError:
                print(f'  ERROR: JSON解析失败，offset={offset}, body前200字符: {body[:200]}')
                break
        if not batch:
            break
        all_funds.extend(batch)
        offset += len(batch)
        if len(batch) < limit:
            break
        if offset % 5000 == 0:
            print(f'  已查询 {len(all_funds)} 条...', flush=True)
    print(f'  ✓ 总计 {len(all_funds)} 条基金记录')
    return all_funds

# ── 3. 构建名称匹配索引 ─────────────────────────────────────────────
SHARE_SUFFIXES = ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'O', 'Y', 'R']

def normalize_name(name):
    """标准化基金名称：去掉份额后缀"""
    if not name:
        return ''
    name = name.strip()
    # 尝试去掉末尾的份额后缀
    for suffix in sorted(SHARE_SUFFIXES, key=len, reverse=True):
        if name.endswith(suffix) and len(name) > len(suffix) + 1:
            # 确保后缀前至少有一个非字母字符或者是基金名尾部
            return name[:-len(suffix)]
    return name

def build_name_index(excel_mapping, all_funds):
    """
    通过 Excel 主代码对应的基金名称，构建名称→分类映射
    思路：
    1. 找到 Excel 主代码在 DB 中的名称
    2. 标准化这些名称（去后缀）
    3. 构建反向索引：basename → (t0, t1)
    """
    print('[3/5] 构建基金名称匹配索引...', flush=True)

    # 去除 .OF 后缀的代码对照
    code_to_info = {}  # 纯数字代码 → (t0, t1)
    for code, (t0, t1) in excel_mapping.items():
        code_to_info[code] = (t0, t1)

    # DB 基金：{纯数字代码 → name}
    db_code_to_name = {}
    for f in all_funds:
        c = (f.get('c') or '').replace('.OF', '')
        if c:
            db_code_to_name[c] = f.get('n', '')

    # 找 Excel 主代码在 DB 中的名称，构建名称索引
    basename_to_classify = {}
    matched_codes = 0
    for code, (t0, t1) in excel_mapping.items():
        if code in db_code_to_name:
            basename = normalize_name(db_code_to_name[code])
            if basename:
                basename_to_classify[basename] = (t0, t1)
                matched_codes += 1

    print(f'  ✓ {matched_codes}/{len(excel_mapping)} 个主代码在 DB 中找到匹配名称')
    print(f'  ✓ 构建 {len(basename_to_classify)} 个名称索引条目')
    return basename_to_classify, code_to_info

# ── 4. 为所有基金分配分类 ────────────────────────────────────────────
def assign_classifications(all_funds, basename_to_classify, code_to_info):
    """为每只基金分配 HSPJ 分类"""
    print('[4/5] 为全量基金分配分类...', flush=True)

    updates = []  # [(code, new_t0, new_t1)]
    direct_match = 0
    name_match = 0
    unmatched = 0

    for f in all_funds:
        code = (f.get('c') or '').replace('.OF', '')
        name = f.get('n', '')
        current_t0 = f.get('t0', '')
        current_t1 = f.get('t1', '')

        # 策略1: 直接代码匹配
        if code in code_to_info:
            t0, t1 = code_to_info[code]
            if t1 != current_t1:
                updates.append((code, t0, t1))
            direct_match += 1
            continue

        # 策略2: 名称匹配（份额基金通过 basename 找到主代码分类）
        basename = normalize_name(name)
        if basename in basename_to_classify:
            t0, t1 = basename_to_classify[basename]
            if t1 != current_t1:
                updates.append((code, t0, t1))
            name_match += 1
            continue

        # 策略3: 模糊匹配——去掉末尾多个字符重试
        found = False
        for trim_len in range(1, 4):
            # 尝试去掉更多后缀字符
            if len(basename) > trim_len + 2:
                trimmed = basename[:-trim_len]
                if trimmed in basename_to_classify:
                    t0, t1 = basename_to_classify[trimmed]
                    if t1 != current_t1:
                        updates.append((code, t0, t1))
                    name_match += 1
                    found = True
                    break
        if found:
            continue

        unmatched += 1

    print(f'  直接代码匹配: {direct_match}')
    print(f'  名称匹配（含份额）: {name_match}')
    print(f'  未匹配: {unmatched}')
    print(f'  需要更新 t1 的记录: {len(updates)}')
    return updates

# ── 5. 批量更新 Supabase ─────────────────────────────────────────────
def batch_update(updates):
    """通过 REST API PATCH 批量更新 fund_scores.t1"""
    print(f'[5/5] 批量更新 {len(updates)} 条记录的 t1...', flush=True)
    updated = 0
    for i in range(0, len(updates), BATCH):
        batch = updates[i:i+BATCH]
        # 构建批量 PATCH（需要代码 + 新值）
        # Supabase REST 不支持按代码列表批量更新，改用逐条 PATCH
        batch_updated = 0
        for code, t0, t1 in batch:
            url = (f'{SUPABASE_URL}/rest/v1/fund_scores'
                   f'?c=eq.{code}.OF'
                   f'&select=c')
            payload = json.dumps({'t0': t0, 't1': t1}, ensure_ascii=False)
            r = subprocess.run(
                ['curl', '-s', '-X', 'PATCH',
                 '-H', f'apikey: {ANON_KEY}',
                 '-H', f'Authorization: Bearer {ANON_KEY}',
                 '-H', 'Content-Type: application/json',
                 '-H', 'Prefer: return=minimal',
                 url,
                 '-d', payload],
                capture_output=True, text=True, timeout=30
            )
            if r.returncode == 0:
                batch_updated += 1
            else:
                # 记录失败的代码
                pass
            updated += batch_updated

        if (i // BATCH) % 10 == 0 or i + BATCH >= len(updates):
            print(f'  进度: {i+len(batch)}/{len(updates)}', flush=True)

    print(f'  ✓ 更新完成，成功 {updated}/{len(updates)} 条')

# ── 主流程 ─────────────────────────────────────────────────────────
def main():
    excel_mapping = load_excel_mapping()
    all_funds = fetch_all_funds()
    basename_to_classify, code_to_info = build_name_index(excel_mapping, all_funds)
    updates = assign_classifications(all_funds, basename_to_classify, code_to_info)
    if updates:
        batch_update(updates)
    else:
        print('[5/5] 无需更新，所有基金已有正确分类')
    print('\n✓ HSPJ 分类映射完成！')

if __name__ == '__main__':
    main()
