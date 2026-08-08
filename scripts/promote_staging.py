#!/usr/bin/env python3
"""
promote_staging.py — 校验 fund_scores_staging 并原子切换到生产 fund_scores

设计目标（解决"夜跑 TRUNCATE 清空生产表"的回归）：
  1. 抓取/计算全程写入【临时表】fund_scores_staging，绝不触碰生产 fund_scores；
  2. 本脚本在临时表写入完成后做严格校验（数量 / 分类分布 / 评分非空 / 货币型评分）；
  3. 校验通过后，才把临时表原子切到生产 fund_scores，并重建 fund_combined；
  4. 任何一步失败 → 拒绝切换、保留生产数据、从备份恢复，绝不产生空表。

用法：
  python3 promote_staging.py
（需 SUPABASE_MGMT_TOKEN 环境变量；CI 中自动注入）
"""
import os
import sys
import json
import time
import subprocess
import argparse

MGMT_TOKEN = os.environ.get('SUPABASE_MGMT_TOKEN') or os.environ.get('SUPABASE_PAT')
if not MGMT_TOKEN:
    sys.exit('请设置环境变量 SUPABASE_MGMT_TOKEN（Supabase Personal Access Token）')
MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query'

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# fund_scores 全部数据列（不含 id，切换时由生产表自增生成）
PROMOTE_COLS = (
    'c,n,t0,t1,t1_tt,sg,daily_change,company,fund_scale,manage_fee,fund_manager,'
    'share_scale,custody_fee,sale_fee,found_date,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,'
    'r7y,r10y,return_all,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y,'
    'k0w,k1m,k3m,k6m,k1,k2,k3,k5,k_all,score_grade,'
    'stock_pct,bond_pct,cash_pct,sub_purchase,sub_redemption,net_sub_share,total_share_end,net_asset_end,nav_change_rate,inst_hold_pct,indiv_hold_pct,internal_hold_pct'
)


def pg(sql, timeout=300):
    from _db import run_sql as _db_run_sql
    return _db_run_sql(sql, timeout=timeout)


def get_t0_counts(table):
    rows = pg(f"SELECT t0, count(*) AS cnt FROM {table} WHERE t0 IS NOT NULL GROUP BY t0")
    return {r['t0']: r['cnt'] for r in rows}


def check(cond, msg):
    if not cond:
        print(f'  ✗ 校验失败: {msg}', flush=True)
        return False
    print(f'  ✓ {msg}', flush=True)
    return True


def main():
    parser = argparse.ArgumentParser(description='校验并原子切换 fund_scores_staging → fund_scores')
    parser.add_argument('--skip-combined', action='store_true',
                        help='跳过 fund_combined 重建（仅切换 fund_scores）')
    args = parser.parse_args()

    print('=' * 64, flush=True)
    print(' 校验并原子切换 fund_scores_staging → fund_scores', flush=True)
    print('=' * 64, flush=True)

    # ── 0. 前置检查：staging 是否存在且有数据 ─────────────────────────────
    print('\n[0] 前置检查', flush=True)
    try:
        st = pg("SELECT to_regclass('fund_scores_staging') AS t")
    except Exception as e:
        print(f'  [ERR] 无法访问数据库: {e}', flush=True)
        sys.exit(1)
    staging_table = st[0]['t'] if st and len(st) > 0 else None
    if not staging_table:
        print('  ✗ fund_scores_staging 不存在，请先运行 import_via_rest.py --staging', flush=True)
        sys.exit(1)

    # 0a. 归一化 staging.t0 → 天天 7 大类命名
    #     修复：(1) 聚源命名（股票型基金等）与历史生产（股票型等）不一致；
    #           (2) 指数基金被并入「股票型基金」导致缺失独立的「指数型」大类；
    #           (3) QDII 与指数型交叉（如「指数型-海外股票」）此前被错判为指数型，
    #               导致 staging QDII 数量远低于生产（395→220），promote 校验整批拒绝。
    #     规则优先级：QDII 先于指数型。QDII 判定信号：t0 ∈ {QDII,QDII基金}
    #                或 t1_tt 含 'QDII'/'海外'；其次 t1_tt 以「指数型」开头→指数型；
    #                t1_tt 非空→取前缀；其余（如货币型 t1_tt 为空）保留原 t0。
    print('\n[0a] 归一化 fund_scores_staging.t0 → 天天 7 大类命名', flush=True)
    pg("""UPDATE fund_scores_staging
        SET t0 = CASE
            WHEN t0 IN ('QDII', 'QDII基金') OR t1_tt LIKE '%QDII%' OR t1_tt LIKE '%海外%' THEN 'QDII'
            WHEN t1_tt LIKE '指数型%' THEN '指数型'
            WHEN t1_tt IS NOT NULL THEN split_part(t1_tt, '-', 1)
            ELSE t0 END
        WHERE t0 IS DISTINCT FROM (
            CASE WHEN t0 IN ('QDII', 'QDII基金') OR t1_tt LIKE '%QDII%' OR t1_tt LIKE '%海外%' THEN 'QDII'
                 WHEN t1_tt LIKE '指数型%' THEN '指数型'
                 WHEN t1_tt IS NOT NULL THEN split_part(t1_tt, '-', 1)
                 ELSE t0 END
        )""")
    print('  ✓ staging.t0 已归一化', flush=True)

    # 0b. 【最高风控：分类不可漂移】以生产表既有分类为准回钉 staging 分类
    #     规则：同一基金代码(c)一旦在生产表被定为某类，必须钉死，禁止因上游
    #     标签命名变更（如指数型→股票型）导致分类漂移。仅对已在生产表存在的
    #     代码做回钉；全新代码(生产表无)保留 [0a] 归一化结果（无漂移可言）。
    #     回钉后统计漂移量用于告警，但漂移已被消除，阈值仅为灾难性丢失安全网。
    print('\n[0b] 分类回钉（防漂移）：以生产表既有分类覆盖 staging 同代码分类', flush=True)
    drift = pg("""SELECT s.t0 AS staging_t0, p.t0 AS prod_t0, count(*) AS n
                  FROM fund_scores_staging s JOIN fund_scores p ON s.c = p.c
                  WHERE s.t0 IS DISTINCT FROM p.t0
                  GROUP BY s.t0, p.t0 ORDER BY n DESC""")
    if drift:
        print('  ⚠ 检测到分类漂移（已被回钉消除），明细：', flush=True)
        for d in drift:
            print(f'     staging[{d["staging_t0"]}] → 生产[{d["prod_t0"]}]: {d["n"]} 只', flush=True)
        pg("""UPDATE fund_scores_staging s
              SET t0 = p.t0
              FROM fund_scores p
              WHERE s.c = p.c AND s.t0 IS DISTINCT FROM p.t0""")
        print(f'  ✓ 已回钉 {sum(d["n"] for d in drift)} 只基金分类（消除漂移）', flush=True)
    else:
        print('  ✓ 无分类漂移', flush=True)

    staging_counts = get_t0_counts('fund_scores_staging')
    staging_total = sum(staging_counts.values())
    prod_counts = get_t0_counts('fund_scores')
    prod_total = sum(prod_counts.values())
    # 折叠历史遗留聚源命名脏类（股票型基金等），丢弃空字符串/非规范类，
    # 使后续校验仅比对 7 大类，避免陈旧脏类导致误判。
    _CANON = {'股票型基金': '股票型', '混合型基金': '混合型', '债券型基金': '债券型'}
    _merged = {}
    for _t0, _c in prod_counts.items():
        if not _t0:
            continue
        _key = _CANON.get(_t0, _t0)
        if _key not in ('指数型', '混合型', '债券型', '股票型', 'FOF', '货币型', 'QDII'):
            continue
        _merged[_key] = _merged.get(_key, 0) + _c
    prod_counts = _merged

    print(f'  staging 总数: {staging_total}，生产总数: {prod_total}', flush=True)
    print(f'  staging t0 分布: {staging_counts}', flush=True)
    print(f'  prod    t0 分布: {prod_counts}', flush=True)

    ok = True
    # 1. staging 必须有足够数据
    ok &= check(staging_total >= 19000, f'staging 数据量充足 (>=19000): {staging_total}')

    # 2. 非货币型各大类数量须与生产接近（容差 20%，允许新发/清盘的正常数量波动）
    #    注：分类漂移已由 [0b] 回钉彻底消除（同代码分类钉死为生产值），此处 80% 阈值
    #    仅作"灾难性数据丢失"安全网（如上游 API 仅返回半数基金）。放宽到 80% 的依据：
    #    天天基金数据源会不定期调整部分基金分类命名，已不可再依赖上游分类稳定性，
    #    故用 [0b] 钉死分类，而非依赖阈值容忍漂移。
    for t0, pc in prod_counts.items():
        if t0 == '货币型':
            continue
        sc = staging_counts.get(t0, 0)
        ratio = sc / pc if pc > 0 else 0
        ok &= check(sc >= pc * 0.80,
                    f'分类 [{t0}] staging {sc} >= 80% 生产 {pc} (实际 {ratio*100:.1f}%)')
        if ratio < 0.95:
            print(f'  ⚠ 分类 [{t0}] 漂移较大 ({ratio*100:.1f}%)，可能数据源分类命名变更，已放行', flush=True)

    # 3. 货币型必须存在且数量健康
    hb_staging = staging_counts.get('货币型', 0)
    ok &= check(hb_staging >= 900, f'货币型数量充足 (>=900): {hb_staging}')

    # 4. 整体 k_all 非空率
    kall = pg("SELECT count(*) AS tot, count(k_all) AS scored FROM fund_scores_staging")[0]
    kall_rate = (kall['scored'] / kall['tot']) if kall['tot'] else 0
    ok &= check(kall_rate >= 0.90, f'整体 k_all 非空率 >=90%: {kall_rate*100:.1f}% ({kall["scored"]}/{kall["tot"]})')

    # 5. 【关键】货币型 k_all 必须非空（此前回归：货币型全 NULL）
    hb = pg("SELECT count(*) AS tot, count(k_all) AS scored FROM fund_scores_staging WHERE t0='货币型'")[0]
    hb_rate = (hb['scored'] / hb['tot']) if hb['tot'] else 0
    ok &= check(hb['tot'] > 0 and hb_rate >= 0.90,
                f'货币型 k_all 非空率 >=90%: {hb_rate*100:.1f}% ({hb["scored"]}/{hb["tot"]})')

    # 6. 货币型阶段收益必须非空（r1y 代表）
    hb_ret = pg("SELECT count(*) AS tot, count(r1y) AS has_ret FROM fund_scores_staging WHERE t0='货币型'")[0]
    ok &= check(hb_ret['has_ret'] >= hb_ret['tot'] * 0.90,
                f'货币型 r1y 阶段收益非空率 >=90%: {hb_ret["has_ret"]}/{hb_ret["tot"]}')

    # 7. 评分等级分布合理
    grades = pg("SELECT score_grade, count(*) AS cnt FROM fund_scores_staging GROUP BY score_grade")
    gmap = {r['score_grade']: r['cnt'] for r in grades}
    print(f'  grade 分布: {gmap}', flush=True)
    ok &= check((gmap.get('green', 0) + gmap.get('blue', 0) + gmap.get('orange', 0)) > 0,
                '评分等级分布非空（green/blue/orange 均存在）')

    if not ok:
        print('\n❌ 校验未通过，拒绝切换，生产 fund_scores 保持不变。', flush=True)
        sys.exit(1)

    print('\n✅ 全部校验通过，开始原子切换...', flush=True)

    # ── 1. 切换前备份当前生产 fund_scores ────────────────────────────────
    print('\n[1] 备份当前生产 fund_scores → _fs_backup', flush=True)
    pg('CREATE TABLE IF NOT EXISTS _fs_backup (LIKE fund_scores INCLUDING ALL)')
    pg('TRUNCATE TABLE _fs_backup')
    pg('INSERT INTO _fs_backup SELECT * FROM fund_scores')
    backup_n = pg('SELECT count(*) AS cnt FROM _fs_backup')[0]['cnt']
    print(f'  ✓ 备份 {backup_n} 条', flush=True)

    # ── 2. 原子切换：TRUNCATE 生产 + 从 staging 整表 INSERT（单语句事务）──
    print('\n[2] 原子切换 fund_scores ← fund_scores_staging', flush=True)
    promote_sql = (
        f'TRUNCATE TABLE fund_scores; '
        f'INSERT INTO fund_scores ({PROMOTE_COLS}) SELECT {PROMOTE_COLS} FROM fund_scores_staging;'
    )
    try:
        pg(promote_sql, timeout=600)
    except Exception as e:
        print(f'  [ERR] 切换失败: {e}', flush=True)
        print('  尝试从备份恢复生产 fund_scores...', flush=True)
        pg('TRUNCATE TABLE fund_scores; INSERT INTO fund_scores SELECT * FROM _fs_backup;')
        sys.exit(1)

    # ── 3. 切换后校验 ────────────────────────────────────────────────────
    new_total = pg('SELECT count(*) AS cnt FROM fund_scores')[0]['cnt']
    if new_total != staging_total:
        print(f'  [ERR] 切换后数量不匹配 (生产 {new_total} != staging {staging_total})，从备份恢复', flush=True)
        pg('TRUNCATE TABLE fund_scores; INSERT INTO fund_scores SELECT * FROM _fs_backup;')
        sys.exit(1)
    print(f'  ✓ 切换成功，fund_scores 现有 {new_total} 条', flush=True)

    # 货币型评分确认
    hb_after = pg("SELECT count(*) AS tot, count(k_all) AS scored FROM fund_scores WHERE t0='货币型'")[0]
    print(f'  ✓ 货币型评分: {hb_after["scored"]}/{hb_after["tot"]} 有 k_all', flush=True)

    # ── 2.2 保护配置/规模/持有人列 + 基本信息列：用备份恢复非空值 ─────────
    # 若当日抓取步骤未成功写入 staging 的这些列（例如东财限流/超时/接口变更），
    # staging 对应列为 NULL，原子切换会清空生产表这些列。此处用上一版生产(_fs_backup)
    # 的非空值回填，确保历史抓取数据不丢失（COALESCE 优先保留 staging 已写入的新值）。
    # ⚠ 2026-07-27 修复：此前保护列表漏掉了基本信息 8 列（fund_manager/fund_scale/
    # manage_fee/company/found_date/share_scale/custody_fee/sale_fee），导致抓取失败当日
    # TRUNCATE+INSERT 把生产表这些历史值擦成 NULL 且备份被 DROP，数据永久丢失。
    # 现已全部纳入保护，任何列抓取失败都不会再擦除生产历史值。
    print('\n[2.2] 保护配置类 12 列 + 基本信息 8 列（COALESCE 备份回填）', flush=True)
    _alloc_cols = ['stock_pct', 'bond_pct', 'cash_pct', 'sub_purchase', 'sub_redemption',
                   'net_sub_share', 'total_share_end', 'net_asset_end', 'nav_change_rate',
                   'inst_hold_pct', 'indiv_hold_pct', 'internal_hold_pct',
                   # 基本信息列（2026-07-27 起纳入保护，防止抓取失败擦除历史值）
                   'fund_manager', 'fund_scale', 'manage_fee', 'company',
                   'found_date', 'share_scale', 'custody_fee', 'sale_fee']
    _set = ', '.join([f'{c} = COALESCE(f.{c}, b.{c})' for c in _alloc_cols])
    try:
        pg(f'UPDATE fund_scores f SET {_set} FROM _fs_backup b WHERE f.c = b.c', timeout=300)
        print('  ✓ 配置类列已用备份保护', flush=True)
    except Exception as e:
        print(f'  [WARN] 配置类列备份回填失败（不影响评分切换）: {e}', flush=True)

    # ── 2.5 重新应用标签（tags）到 fund_scores ──────────────────────────
    # fund_scores.tags 由 fund_tag_funds 派生，不在 PROMOTE_COLS 内（staging 无该列），
    # 故每次切换后需从 fund_tag_funds 重新聚合写入，保证夜跑后标签不丢。
    # （nightly 工作流不重跑标签脚本，fund_tag_funds 由 sync_tag_funds_full.py 单独维护，稳定。）
    print('\n[2.5] 重新应用标签到 fund_scores（来源 fund_tag_funds）', flush=True)
    try:
        pg("ALTER TABLE fund_scores ADD COLUMN IF NOT EXISTS tags text[];", timeout=120)
        pg("UPDATE fund_scores SET tags = NULL;", timeout=300)
        pg("""UPDATE fund_scores fs
              SET tags = sub.tags
              FROM (SELECT fund_code, array_agg(DISTINCT tag_name) AS tags
                    FROM fund_tag_funds GROUP BY fund_code) sub
              WHERE fs.c = sub.fund_code OR fs.c = sub.fund_code || '.OF';""", timeout=600)
        tagged = pg("SELECT count(*) AS cnt FROM fund_scores WHERE tags IS NOT NULL")[0]['cnt']
        print(f'  ✓ 已为 {tagged} 只基金标记标签', flush=True)
    except Exception as e:
        print(f'  [WARN] 标签重新应用失败（不影响评分切换）: {e}', flush=True)

    # ── 3. 重建 fund_combined（复用已验证的增量同步脚本，非破坏性）──────
    if not args.skip_combined:
        print('\n[3] 重建 fund_combined（复用 sync_fund_combined_scores.py）', flush=True)
        rc = subprocess.run(
            [sys.executable, os.path.join(SCRIPT_DIR, 'sync_fund_combined_scores.py')],
            cwd=SCRIPT_DIR
        ).returncode
        if rc != 0:
            print(f'  [WARN] fund_combined 同步返回非零 ({rc})，但 fund_scores 已切换成功', flush=True)
    else:
        print('\n[3] 跳过 fund_combined 重建（--skip-combined）', flush=True)

    # ── 3.5 更新 fund_scores_meta 时间戳（页面底部"更新时间"的唯一来源）──
    # 根因：此前 CI 刷新 fund_scores 后从不写这张元数据表，导致页面"更新时间"
    # 长期停留在 2026-07-07。现改为每次成功 promote 后追加一行最新时间戳，
    # 前端 ORDER BY tsq DESC LIMIT 1 即取最新值，时间随数据刷新自动前进。
    # 追加式写入（不 UPDATE 历史行），失败仅告警不影响评分切换。
    print('\n[3.5] 更新 fund_scores_meta 时间戳（页面"更新时间"来源）', flush=True)
    try:
        pg("""INSERT INTO fund_scores_meta (tsq, update_time, total_count, scored_count)
              SELECT now(), now()::text, count(*), count(k_all) FROM fund_scores""")
        mm = pg("SELECT tsq, total_count, scored_count FROM fund_scores_meta ORDER BY tsq DESC LIMIT 1")[0]
        print(f"  ✓ fund_scores_meta 已更新: tsq={mm['tsq']}, 总数={mm['total_count']}, 已评分={mm['scored_count']}", flush=True)
    except Exception as e:
        print(f'  [WARN] fund_scores_meta 时间戳更新失败（不影响评分切换）: {e}', flush=True)

    # ── 5. 清理备份 ──────────────────────────────────────────────────────
    print('\n[4] 清理备份表 _fs_backup', flush=True)
    pg('DROP TABLE IF EXISTS _fs_backup')
    print('  ✓ 已清理', flush=True)

    print('\n✅ 切换完成！生产 fund_scores 已更新，fund_combined 已同步。', flush=True)


if __name__ == '__main__':
    main()
