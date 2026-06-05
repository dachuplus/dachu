/**
 * 重算靠谱分 v6
 * 权重：收益50% + 回撤25% + 夏普25%（v5 是 60/30/10）
 * 同时补充 k7(7年) / k10(10年) 周期（v5 只算了 k1~k5）
 *
 * 运行：node recalc_scores_v6.mjs [mgmt_token]
 */

const MGMT_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.argv[2] || 'YOUR_MGMT_TOKEN';
const MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query';

function escNum(v) {
  if (v == null || isNaN(v)) return 'NULL';
  const n = parseFloat(v);
  if (!isFinite(n) || Math.abs(n) > 999999) return 'NULL';
  return n.toFixed(4);
}

function escStr(s) {
  if (s == null) return "''";
  return "'" + String(s).replace(/\\/g, '\\\\').replace(/'/g, "''") + "'";
}

async function runSQL(sql) {
  const resp = await fetch(MGMT_API, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${MGMT_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query: sql }),
    signal: AbortSignal.timeout(90000)
  });
  if (!resp.ok) {
    const e = await resp.text();
    throw new Error(`SQL ${resp.status}: ${e.substring(0, 300)}`);
  }
  return resp.json();
}

/**
 * 靠谱分 v6 计算
 * 权重：收益排位×50% + 回撤排位×25% + 夏普排位×25%
 * 参与条件：收益率>0 且至少有回撤或夏普数据之一
 *
 * 注：k7/k10 目前无 r7y/r10y、dd7y/sr7y 等数据，跳过
 */
function calcScoresV6(funds) {
  const periods = [
    { k: 'k1', r: 'r1y', dd: 'dd1y', sr: 'sr1y' },
    { k: 'k2', r: 'r2y', dd: 'dd2y', sr: 'sr2y' },
    { k: 'k3', r: 'r3y', dd: 'dd3y', sr: 'sr3y' },
    { k: 'k5', r: 'r5y', dd: 'dd5y', sr: 'sr5y' },
  ];
  // v6 权重
  const W_RET = 0.50, W_DD = 0.25, W_SR = 0.25;
  let totalScored = 0;

  for (const period of periods) {
    const { k, r, dd, sr } = period;

    // 筛选有效基金：收益>0 且至少有回撤或夏普数据
    const valid = funds.filter(f =>
      (parseFloat(f[r]) || 0) > 0 && (f[dd] != null || f[sr] != null)
    );
    if (!valid.length) continue;
    const vn = valid.length;

    // 1. 收益排位（降序，越高越好）
    const retRanked = [...valid].sort((a, b) => (parseFloat(b[r]) || 0) - (parseFloat(a[r]) || 0));
    const retPct = {};
    retRanked.forEach((f, rank) => {
      retPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
    });

    // 2. 回撤排位（dd 是负数，-5% > -30%，数值越大越好）
    const hasDD = valid.filter(f => f[dd] != null);
    const ddPct = {};
    if (hasDD.length > 0) {
      const ddRanked = [...hasDD].sort((a, b) => (parseFloat(b[dd]) || -999) - (parseFloat(a[dd]) || -999));
      ddRanked.forEach((f, rank) => {
        ddPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
      });
    }

    // 3. 夏普排位（越高越好）
    const hasSR = valid.filter(f => f[sr] != null);
    const srPct = {};
    if (hasSR.length > 0) {
      const srRanked = [...hasSR].sort((a, b) => (parseFloat(b[sr]) || -999) - (parseFloat(a[sr]) || -999));
      srRanked.forEach((f, rank) => {
        srPct[f.c] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
      });
    }

    // 4. 加权汇总（按实际有数据的权重归一化）
    for (const f of valid) {
      const rp = retPct[f.c];
      const dp = ddPct[f.c];
      const sp = srPct[f.c];

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

async function main() {
  console.log('='.repeat(60));
  console.log('重算靠谱分 v6（收益50%+回撤25%+夏普25%）');
  console.log('='.repeat(60));

  // 1. 从 Supabase 查询所有 fund_scores（含收益率和风险指标）
  console.log('\n[1] 从 Supabase 查询 fund_scores...');
  const funds = await runSQL(`
    SELECT c, n, t0,
           r1y, r2y, r3y, r5y,
           dd1y, dd2y, dd3y, dd5y,
           sr1y, sr2y, sr3y, sr5y
    FROM fund_scores
    ORDER BY c
  `);
  console.log(`  查询到 ${funds.length} 条记录`);

  // 2. 重置靠谱分
  for (const f of funds) {
    f.k1 = null; f.k2 = null; f.k3 = null; f.k5 = null;
  }

  // 3. 计算 v6
  console.log('\n[2] 计算靠谱分 v6...');
  const totalScored = calcScoresV6(funds);
  console.log(`  评分完成: ${totalScored} 次（含多周期）`);

  const scoredFunds = funds.filter(f => f.k3 != null && f.k3 > 0);
  const scoredAny = funds.filter(f => (f.k1 || 0) > 0 || (f.k2 || 0) > 0 || (f.k3 || 0) > 0 || (f.k5 || 0) > 0);
  console.log(`  有 k3 靠谱分: ${scoredFunds.length} 只`);
  console.log(`  有任意靠谱分: ${scoredAny.length} 只`);

  // 颜色分布
  const dist = { gold: 0, orange: 0, cyan: 0, gray: 0 };
  for (const f of scoredFunds) {
    if (f.k3 >= 85) dist.gold++;
    else if (f.k3 >= 75) dist.orange++;
    else if (f.k3 >= 65) dist.cyan++;
    else dist.gray++;
  }
  console.log(`  分布：金(≥85)=${dist.gold}, 橙(75-84)=${dist.orange}, 青(65-74)=${dist.cyan}, 灰(<65)=${dist.gray}`);

  // 4. UPDATE 靠谱分到 Supabase（每批1000条）
  console.log('\n[3] UPDATE 靠谱分到 Supabase...');
  const scoreFields = ['k1', 'k2', 'k3', 'k5'];
  const BATCH = 1000;
  let updated = 0;

  for (let i = 0; i < funds.length; i += BATCH) {
    const batch = funds.slice(i, i + BATCH);
    const codes = batch.map(f => escStr(f.c)).join(',');

    const setClauses = scoreFields.map(field => {
      const cases = batch.map(f =>
        `WHEN ${escStr(f.c)} THEN ${escNum(f[field])}`
      ).join('\n        ');
      return `${field} = CASE c\n        ${cases}\n        ELSE ${field}\n        END`;
    }).join(',\n      ');

    const sql = `UPDATE fund_scores\n  SET ${setClauses}\n  WHERE c IN (${codes})`;
    try {
      await runSQL(sql);
      updated += batch.length;
    } catch (e) {
      console.error(`  BATCH ${i} 失败: ${e.message.substring(0, 120)}`);
      // 逐条重试
      for (const f of batch) {
        const setParts = scoreFields.map(field =>
          `${field} = ${escNum(f[field])}`
        ).join(', ');
        try {
          await runSQL(`UPDATE fund_scores SET ${setParts} WHERE c = ${escStr(f.c)}`);
          updated++;
        } catch (e2) { /* skip */ }
      }
    }
    process.stdout.write(`\r  进度: ${Math.min(updated, funds.length)}/${funds.length}`);
    await new Promise(r => setTimeout(r, 150));
  }
  console.log(`\n  靠谱分 v6 更新完成: ${updated} 条`);

  // 5. 更新 fund_scores_meta
  console.log('\n[4] 更新 fund_scores_meta...');
  const navDateRows = await runSQL("SELECT date FROM fund_scores WHERE date IS NOT NULL AND date != '' LIMIT 1");
  const navDate = navDateRows[0]?.date || '';
  try {
    await runSQL('TRUNCATE TABLE fund_scores_meta');
    await runSQL(`INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date)
      VALUES (NOW()::text, ${funds.length}, ${scoredFunds.length}, '${navDate}')`);
    console.log(`  total=${funds.length}, scored=${scoredFunds.length}, date=${navDate}`);
  } catch (e) {
    console.error('  meta 更新失败:', e.message);
  }

  // 6. 验证 TOP 10
  console.log('\n[5] 验证 TOP 10（k3）:');
  const top10 = await runSQL(`
    SELECT c, n, t0, k1, k3, k5, dd1y, sr1y
    FROM fund_scores WHERE k3 > 0
    ORDER BY k3 DESC LIMIT 10
  `);
  for (const t of top10) {
    console.log(`  ${t.c} ${t.n} [${t.t0}]: k1=${t.k1?.toFixed(2)} k3=${t.k3?.toFixed(2)} k5=${t.k5?.toFixed(2)}`);
  }

  console.log('\nDone! 靠谱分 v6 计算完成。');
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
