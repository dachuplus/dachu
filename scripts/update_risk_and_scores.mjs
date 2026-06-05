/**
 * 更新 fund_scores 风险指标 + 重新计算靠谱分 v5
 *
 * 1. 从 risk_indicators.ndjson 读取风险指标（dd/sr 字段）
 * 2. 从 Supabase 查询所有 fund_scores（含收益率）
 * 3. UPDATE 风险指标到 Supabase
 * 4. 全市场统一排名计算靠谱分 v5（收益60%+回撤30%+夏普10%）
 * 5. UPDATE 靠谱分到 Supabase
 * 6. 更新 fund_scores_meta
 */
import fs from 'fs';

const MGMT_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.argv[2] || 'YOUR_MGMT_TOKEN';
const MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query';

function escNum(v) {
  if (v == null || isNaN(v)) return 'NULL';
  const n = parseFloat(v);
  if (!isFinite(n) || Math.abs(n) > 999999) return 'NULL';
  return n.toFixed(4);
}

async function runSQL(sql) {
  const resp = await fetch(MGMT_API, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${MGMT_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query: sql }),
    signal: AbortSignal.timeout(60000)
  });
  if (!resp.ok) {
    const e = await resp.text();
    throw new Error(`SQL ${resp.status}: ${e.substring(0, 200)}`);
  }
  return resp.json();
}

function calcScoresV5(funds) {
  /**
   * 全市场统一排名计算靠谱分 v5
   * 靠谱指数 = 收益排位×60% + 回撤排位×30% + 夏普排位×10%
   * 参与条件：收益率>0 且至少有回撤或夏普数据之一
   */
  const periods = [
    { k: 'k1', r: 'r1y', dd: 'dd1y', sr: 'sr1y' },
    { k: 'k2', r: 'r2y', dd: 'dd2y', sr: 'sr2y' },
    { k: 'k3', r: 'r3y', dd: 'dd3y', sr: 'sr3y' },
    { k: 'k5', r: 'r5y', dd: 'dd5y', sr: 'sr5y' },
  ];
  const W_RET = 0.60, W_DD = 0.30, W_SR = 0.10;
  let totalScored = 0;

  for (const period of periods) {
    const { k, r, dd, sr } = period;

    // 筛选有效基金：收益>0 且至少有回撤或夏普数据
    const valid = funds.filter(f =>
      (f[r] || 0) > 0 && (f[dd] != null || f[sr] != null)
    );
    if (!valid.length) continue;
    const vn = valid.length;

    // 1. 收益排位（降序，越高越好）
    const retRanked = [...valid].sort((a, b) => (b[r] || 0) - (a[r] || 0));
    const retPct = {};
    retRanked.forEach((f, rank) => {
      retPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
    });

    // 2. 回撤排位（降序，dd 是负数，-5% > -30%）
    const hasDD = valid.filter(f => f[dd] != null);
    const ddPct = {};
    if (hasDD.length > 0) {
      const ddRanked = [...hasDD].sort((a, b) => (b[dd] || -999) - (a[dd] || -999));
      ddRanked.forEach((f, rank) => {
        ddPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
      });
    }

    // 3. 夏普排位（降序，越高越好）
    const hasSR = valid.filter(f => f[sr] != null);
    const srPct = {};
    if (hasSR.length > 0) {
      const srRanked = [...hasSR].sort((a, b) => (b[sr] || -999) - (a[sr] || -999));
      srRanked.forEach((f, rank) => {
        srPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
      });
    }

    // 4. 加权汇总
    for (const f of valid) {
      const rp = retPct[f.c];
      const dp = ddPct[f.c]; // undefined if no dd data
      const sp = srPct[f.c]; // undefined if no sr data

      let totalW = 0, weightedSum = 0;
      if (rp != null) { weightedSum += W_RET * rp; totalW += W_RET; }
      if (dp != null) { weightedSum += W_DD * dp; totalW += W_DD; }
      if (sp != null) { weightedSum += W_SR * sp; totalW += W_SR; }

      if (totalW > 0) {
        f[k] = Math.round((weightedSum / totalW) * 10000) / 10000;
      } else {
        f[k] = null;
      }
      totalScored++;
    }
  }
  return totalScored;
}

function escStr(s) {
  if (s == null) return "''";
  return "'" + String(s).replace(/\\/g, '\\\\').replace(/'/g, "''") + "'";
}

async function main() {
  console.log('='.repeat(60));
  console.log('更新风险指标 + 重算靠谱分 v5');
  console.log('='.repeat(60));

  // 1. 读取风险指标
  const riskFile = fs.readFileSync('/Users/maoshanbo/WorkBuddy/20260405093252/asset-config-miniapp/scripts/risk_indicators.ndjson', 'utf-8');
  const riskMap = {};
  let riskCount = 0;
  for (const line of riskFile.split('\n')) {
    if (!line.trim()) continue;
    const rec = JSON.parse(line);
    if (rec.c) { riskMap[rec.c] = rec; riskCount++; }
  }
  console.log(`\n[1] 风险指标文件: ${riskCount} 条`);

  // 2. 从 Supabase 查询所有 fund_scores
  console.log('\n[2] 从 Supabase 查询 fund_scores...');
  const funds = await runSQL(`
    SELECT c, n, t0, r1y, r2y, r3y, r5y, k1, k2, k3, k5
    FROM fund_scores
    ORDER BY c
  `);
  console.log(`  查询到 ${funds.length} 条记录`);

  // 3. 合并风险指标
  console.log('\n[3] 合并风险指标...');
  let mergedRisk = 0;
  const toUpdateRisk = []; // 只更新缺失风险指标的记录

  for (const f of funds) {
    const risk = riskMap[f.c];
    if (risk) {
      f.dd1y = risk.dd1y; f.dd2y = risk.dd2y; f.dd3y = risk.dd3y; f.dd5y = risk.dd5y;
      f.sr1y = risk.sr1y; f.sr2y = risk.sr2y; f.sr3y = risk.sr3y; f.sr5y = risk.sr5y;
      mergedRisk++;
      // 只添加数据库中缺失风险指标的记录（通过现有 dd1y/sr1y 字段判断）
      // 由于查询时没带 dd/sr 字段，这里标记所有匹配的，后面用 SQL WHERE 条件过滤
      toUpdateRisk.push(f);
    } else {
      f.dd1y = null; f.dd2y = null; f.dd3y = null; f.dd5y = null;
      f.sr1y = null; f.sr2y = null; f.sr3y = null; f.sr5y = null;
    }
  }
  console.log(`  风险指标文件匹配: ${mergedRisk} 条`);
  console.log(`  缺失风险指标: ${funds.length - mergedRisk} 条`);

  // 4. UPDATE 风险指标到 Supabase（只更新 dd1y IS NULL 的记录）
  // 优化：单条 SQL 同时更新 8 个风险字段，减少 SQL 调用次数
  console.log(`\n[4] UPDATE 风险指标到 Supabase...`);
  console.log('  (只更新 dd1y IS NULL 的记录)');
  const BATCH = 1000; // 每批1000条
  let updated = 0;

  for (let i = 0; i < toUpdateRisk.length; i += BATCH) {
    const batch = toUpdateRisk.slice(i, i + BATCH);
    const codes = batch.map(f => escStr(f.c)).join(',');

    // 构建单条 SQL，同时更新 8 个风险字段，WHERE dd1y IS NULL 确保幂等
    const riskFields = ['dd1y', 'dd2y', 'dd3y', 'dd5y', 'sr1y', 'sr2y', 'sr3y', 'sr5y'];
    const setClauses = riskFields.map(field => {
      const cases = batch.map(f =>
        `WHEN ${escStr(f.c)} THEN ${escNum(f[field])}`
      ).join('\n        ');
      return `${field} = CASE c\n        ${cases}\n        END`;
    }).join(',\n      ');

    const sql = `UPDATE fund_scores\n  SET ${setClauses}\n  WHERE c IN (${codes}) AND dd1y IS NULL`;
    try {
      const result = await runSQL(sql);
      updated += batch.length;
    } catch (e) {
      console.error(`  BATCH ${i} err: ${e.message.substring(0, 120)}, 逐条重试...`);
      // 逐条重试
      for (const f of batch) {
        const setParts = riskFields.map(field =>
          `${field} = ${escNum(f[field])}`
        ).join(', ');
        try {
          await runSQL(`UPDATE fund_scores SET ${setParts} WHERE c = ${escStr(f.c)} AND dd1y IS NULL`);
          updated++;
        } catch (e2) {
          console.error(`    SKIP ${f.c}: ${e2.message.substring(0, 60)}`);
        }
      }
    }
    console.log(`  进度: ${Math.min(updated, toUpdateRisk.length)}/${toUpdateRisk.length}`);
    await new Promise(r => setTimeout(r, 150));
  }
  console.log(`  风险指标更新完成: 处理 ${updated} 条`);

  // 5. 重新计算靠谱分 v5
  console.log('\n[5] 重新计算靠谱分 v5（收益60%+回撤30%+夏普10%）...');
  // 重置靠谱分
  for (const f of funds) {
    f.k1 = 0; f.k2 = 0; f.k3 = 0; f.k5 = 0;
  }
  const totalScored = calcScoresV5(funds);
  console.log(`  评分完成: ${totalScored} 次（含多周期）`);

  // 有靠谱分的基金统计
  const scoredFunds = funds.filter(f => f.k3 > 0);
  console.log(`  有 k3(3年靠谱分) 的基金: ${scoredFunds.length} 只`);
  const scoredAll = funds.filter(f => f.k1 > 0 || f.k2 > 0 || f.k3 > 0 || f.k5 > 0);
  console.log(`  有任意靠谱分的基金: ${scoredAll.length} 只`);

  // 6. UPDATE 靠谱分到 Supabase（单条 SQL 更新 4 个靠谱分字段）
  console.log('\n[6] UPDATE 靠谱分到 Supabase...');
  const scoreFields = ['k1', 'k2', 'k3', 'k5'];
  const SCORE_BATCH = 1000;
  let scoreUpdated = 0;

  for (let i = 0; i < funds.length; i += SCORE_BATCH) {
    const batch = funds.slice(i, i + SCORE_BATCH);
    const codes = batch.map(f => escStr(f.c)).join(',');

    const setClauses = scoreFields.map(field => {
      const cases = batch.map(f =>
        `WHEN ${escStr(f.c)} THEN ${escNum(f[field])}`
      ).join('\n        ');
      return `${field} = CASE c\n        ${cases}\n        END`;
    }).join(',\n      ');

    const sql = `UPDATE fund_scores\n  SET ${setClauses}\n  WHERE c IN (${codes})`;
    try {
      await runSQL(sql);
      scoreUpdated += batch.length;
    } catch (e) {
      console.error(`  BATCH ${i} err: ${e.message.substring(0, 120)}, 逐条重试...`);
      for (const f of batch) {
        const setParts = scoreFields.map(field =>
          `${field} = ${escNum(f[field])}`
        ).join(', ');
        try {
          await runSQL(`UPDATE fund_scores SET ${setParts} WHERE c = ${escStr(f.c)}`);
          scoreUpdated++;
        } catch (e2) { /* skip */ }
      }
    }
    console.log(`  进度: ${Math.min(scoreUpdated, funds.length)}/${funds.length}`);
    await new Promise(r => setTimeout(r, 150));
  }
  console.log(`  靠谱分更新完成: ${scoreUpdated} 条`);

  // 7. 更新 fund_scores_meta
  console.log('\n[7] 更新 fund_scores_meta...');
  const navDate = (await runSQL("SELECT date FROM fund_scores WHERE date IS NOT NULL AND date != '' LIMIT 1"))[0]?.date || '';
  try {
    await runSQL('TRUNCATE TABLE fund_scores_meta');
    await runSQL(`INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) VALUES (NOW()::text, ${funds.length}, ${scoredFunds.length}, '${navDate}')`);
    console.log(`  total=${funds.length}, scored=${scoredFunds.length}, date=${navDate}`);
  } catch (e) {
    console.error('  meta 更新失败:', e.message);
  }

  // 8. 验证
  console.log('\n[8] 验证...');

  // 风险指标统计
  const riskStats = await runSQL(`
    SELECT
      count(*) as total,
      count(dd1y) as has_dd1y,
      count(sr1y) as has_sr1y,
      count(k3) as has_k3
    FROM fund_scores
  `);
  console.log(`  总记录: ${riskStats[0].total}`);
  console.log(`  有dd1y: ${riskStats[0].has_dd1y}`);
  console.log(`  有sr1y: ${riskStats[0].has_sr1y}`);
  console.log(`  有k3靠谱分: ${riskStats[0].has_k3}`);

  // 各分类靠谱分统计
  const catStats = await runSQL(`
    SELECT t0, count(*) as cnt, count(k3) as scored,
      round(avg(k3)::numeric, 2) as avg_k3,
      round(max(k3)::numeric, 2) as max_k3
    FROM fund_scores
    GROUP BY t0 ORDER BY cnt DESC
  `);
  console.log('\n  分类统计:');
  for (const s of catStats) {
    console.log(`    ${s.t0}: ${s.cnt}只, 有靠谱分${s.scored}只, 平均${s.avg_k3}, 最高${s.max_k3}`);
  }

  // TOP 10
  const top10 = await runSQL(`
    SELECT c, n, t0, k1, k3, dd1y, sr1y
    FROM fund_scores WHERE k3 > 0
    ORDER BY k3 DESC LIMIT 10
  `);
  console.log('\n  TOP 10 靠谱分(k3):');
  for (const t of top10) {
    console.log(`    ${t.c} ${t.n} [${t.t0}]: k1=${t.k1} k3=${t.k3} dd1y=${t.dd1y} sr1y=${t.sr1y}`);
  }

  console.log('\nDone!');
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
