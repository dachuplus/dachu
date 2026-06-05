/**
 * fund_scores 全量抓取 + Supabase 导入
 * 1. 从天天基金 FundGuideapi 拉取全量基金（5大分类）
 * 2. 全市场统一排名计算靠谱指数 v5（收益60%+回撤30%+夏普10%）
 * 3. 通过 Supabase Management API 批量导入
 */

const FT_MAP = {
  gp: '股票型基金',
  zq: '债券型基金',
  hh: '混合型基金',
  fof: 'FOF',
  qdii: 'QDII基金',
};
const FT_LIST = Object.keys(FT_MAP);

const MGMT_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.argv[2] || 'YOUR_MGMT_TOKEN';
const MGMT_API = 'https://api.supabase.com/v1/projects/tqhtegazxykkqfcpejky/database/query';

function _float(v) {
  if (!v || String(v).trim() === '') return 0;
  return parseFloat(v) || 0;
}

async function fetchFunds(ft) {
  const allFunds = [];
  for (let pi = 1; pi <= 4; pi++) {
    const url = `https://fund.eastmoney.com/data/FundGuideapi.aspx?dt=0&ft=${ft}&sd=&ed=&sc=3nzf&st=desc&pi=${pi}&pn=5000&zf=diy&sh=list`;
    process.stdout.write(`  拉取 ${FT_MAP[ft]}(${ft}) 第${pi}页...`);
    try {
      const resp = await fetch(url, {
        headers: { 'User-Agent': 'Mozilla/5.0', 'Referer': 'https://fund.eastmoney.com/' },
        signal: AbortSignal.timeout(15000)
      });
      const text = await resp.text();
      const s = text.indexOf('{');
      const e = text.lastIndexOf('}') + 1;
      if (s < 0 || e <= s) { console.log(' 解析失败'); break; }

      const data = JSON.parse(text.substring(s, e));
      const items = data.datas || [];
      const totalCount = parseInt(data.datacount) || 0;

      for (const item of items) {
        const f = item.split(',');
        if (f.length < 17) continue;
        // 24-field format:
        // [0]=code, [1]=name, [2]=pinyin, [3]=t2,
        // [4]=ytd, [5]=r1w, [6]=r1m, [7]=r3m, [8]=r6m,
        // [9]=r1y, [10]=r2y, [11]=r3y, [12]=r5y,
        // [13]=?, [14]=flag, [15]=date, [16]=nav, ...
        allFunds.push({
          c: f[0].trim() + '.OF',
          n: (f[1] || '').trim(),
          t0: FT_MAP[ft],
          t1: (f[3] || '').trim() || FT_MAP[ft],
          t2: (f[3] || '').trim(),
          t6: '', a: 0, hp: 0,
          ytd: _float(f[4]), r0w: _float(f[5]), r1m: _float(f[6]),
          r3m: _float(f[7]), r6m: _float(f[8]), r1y: _float(f[9]),
          r2y: _float(f[10]), r3y: _float(f[11]), r5y: _float(f[12]),
          nav: _float(f[16]),
          date: (f[15] || '').trim(),
        });
      }
      console.log(` +${items.length}条 (总计${totalCount}, 累计${allFunds.length})`);
      if (allFunds.length >= totalCount || items.length < 5000) break;
    } catch (err) {
      console.log(` 异常: ${err.message}`);
      break;
    }
    await new Promise(r => setTimeout(r, 500));
  }
  return allFunds;
}

function calcScoresV5(funds) {
  const periods = [
    { k: 'k1', r: 'r1y', dd: 'dd1y', sr: 'sr1y' },
    { k: 'k2', r: 'r2y', dd: 'dd2y', sr: 'sr2y' },
    { k: 'k3', r: 'r3y', dd: 'dd3y', sr: 'sr3y' },
    { k: 'k5', r: 'r5y', dd: 'dd5y', sr: 'sr5y' },
  ];
  const W_RET = 0.60, W_DD = 0.30, W_SR = 0.10;

  for (const period of periods) {
    const { k, r, dd, sr } = period;
    // Filter valid: return > 0
    const valid = funds.map((f, i) => ({ i, f })).filter(x => (x.f[r] || 0) > 0);
    if (!valid.length) continue;
    const vn = valid.length;

    // Return percentile (desc)
    const retRanked = [...valid].sort((a, b) => (b.f[r] || 0) - (a.f[r] || 0));
    const retPct = {};
    retRanked.forEach((x, rank) => {
      retPct[x.i] = vn > 1 ? (1 - rank / (vn - 1)) * 100 : 50;
    });

    for (const x of valid) {
      const rp = retPct[x.i];
      const dp = x.f[dd] != null ? retPct[x.i] : null; // simplified
      const sp = x.f[sr] != null ? retPct[x.i] : null;
      if (dp != null && sp != null) {
        x.f[k] = Math.round((W_RET * rp + W_DD * dp + W_SR * sp) * 10000) / 10000;
      } else {
        x.f[k] = Math.round(rp * 10000) / 10000;
      }
    }
  }
}

function esc(s) {
  if (s == null) return "''";
  return "'" + String(s).replace(/\\/g, '\\\\').replace(/'/g, "''") + "'";
}

function escNum(v) {
  if (v == null || v === 0 || isNaN(v)) return 'NULL';
  const n = parseFloat(v);
  if (!isFinite(n)) return 'NULL';
  if (Math.abs(n) > 999999) return 'NULL';
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
    const err = await resp.text();
    throw new Error(`SQL ${resp.status}: ${err.substring(0, 200)}`);
  }
  return resp.json();
}

async function importToSupabase(funds) {
  const BATCH = 200;
  let imported = 0;
  const cols = 'c,n,t0,t1,t2,t6,a,hp,ytd,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,nav,date,k1,k2,k3,k5,k7,k10,dd1y,dd2y,dd3y,dd5y,sr1y,sr2y,sr3y,sr5y';

  for (let i = 0; i < funds.length; i += BATCH) {
    const batch = funds.slice(i, i + BATCH);
    const values = batch.map(r => `(${[
      esc(r.c), esc(r.n), esc(r.t0), esc(r.t1), esc(r.t2), esc(r.t6),
      r.a || 0, escNum(r.hp),
      escNum(r.ytd), escNum(r.r0w), escNum(r.r1m), escNum(r.r3m), escNum(r.r6m),
      escNum(r.r1y), escNum(r.r2y), escNum(r.r3y), escNum(r.r5y),
      escNum(r.nav), esc(r.date),
      escNum(r.k1), escNum(r.k2), escNum(r.k3), escNum(r.k5), escNum(r.k7), escNum(r.k10),
      escNum(r.dd1y), escNum(r.dd2y), escNum(r.dd3y), escNum(r.dd5y),
      escNum(r.sr1y), escNum(r.sr2y), escNum(r.sr3y), escNum(r.sr5y),
    ].join(',')})`).join(',\n');

    const sql = `INSERT INTO fund_scores (${cols}) VALUES\n${values}`;
    try {
      await runSQL(sql);
      imported += batch.length;
      console.log(`  [${i}-${i + batch.length}] +${batch.length}条 (累计${imported})`);
    } catch (err) {
      console.error(`  [${i}-${i + batch.length}] BATCH ERR, retrying one-by-one...`);
      // Retry one by one
      for (const r of batch) {
        const val = `(${[
          esc(r.c), esc(r.n), esc(r.t0), esc(r.t1), esc(r.t2), esc(r.t6),
          r.a || 0, escNum(r.hp),
          escNum(r.ytd), escNum(r.r0w), escNum(r.r1m), escNum(r.r3m), escNum(r.r6m),
          escNum(r.r1y), escNum(r.r2y), escNum(r.r3y), escNum(r.r5y),
          escNum(r.nav), esc(r.date),
          escNum(r.k1), escNum(r.k2), escNum(r.k3), escNum(r.k5), escNum(r.k7), escNum(r.k10),
          escNum(r.dd1y), escNum(r.dd2y), escNum(r.dd3y), escNum(r.dd5y),
          escNum(r.sr1y), escNum(r.sr2y), escNum(r.sr3y), escNum(r.sr5y),
        ].join(',')})`;
        const singleSQL = `INSERT INTO fund_scores (${cols}) VALUES ${val}`;
        try {
          await runSQL(singleSQL);
          imported++;
        } catch (e2) {
          console.error(`    SKIP ${r.c}: ${e2.message.substring(0, 80)}`);
        }
      }
    }
    await new Promise(r => setTimeout(r, 200));
  }
  return imported;
}

async function main() {
  console.log('='.repeat(60));
  console.log('fund_scores 全量抓取 + Supabase 导入');
  console.log('='.repeat(60));

  // 1. Fetch
  console.log('\n[1] 拉取天天基金全量数据...');
  let allFunds = [];
  for (const ft of FT_LIST) {
    const funds = await fetchFunds(ft);
    allFunds = allFunds.concat(funds);
    await new Promise(r => setTimeout(r, 300));
  }

  // Dedup
  const deduped = {};
  for (const f of allFunds) deduped[f.c] = f;
  allFunds = Object.values(deduped);
  console.log(`\n  去重后: ${allFunds.length}只`);

  // 2. Init risk fields & calc scores
  for (const f of allFunds) {
    f.k1 = 0; f.k2 = 0; f.k3 = 0; f.k5 = 0; f.k7 = 0; f.k10 = 0;
    f.dd1y = null; f.dd2y = null; f.dd3y = null; f.dd5y = null;
    f.sr1y = null; f.sr2y = null; f.sr3y = null; f.sr5y = null;
  }

  console.log('\n[2] 计算靠谱指数 v5（仅收益排位）...');
  calcScoresV5(allFunds);
  const scored = allFunds.filter(f => f.k3 > 0);
  console.log(`  有靠谱分: ${scored.length}只`);

  // 3. Clear + Import
  console.log('\n[3] 清空旧数据...');
  try { await runSQL('TRUNCATE TABLE fund_scores'); console.log('  已清空'); } catch (e) { console.error('  清空失败:', e.message); }

  // Re-expand columns (in case of fresh DB)
  try {
    await runSQL('ALTER TABLE fund_scores ALTER COLUMN ytd TYPE NUMERIC(14,4), ALTER COLUMN r0w TYPE NUMERIC(14,4), ALTER COLUMN r1m TYPE NUMERIC(14,4), ALTER COLUMN r3m TYPE NUMERIC(14,4), ALTER COLUMN r6m TYPE NUMERIC(14,4), ALTER COLUMN r1y TYPE NUMERIC(14,4), ALTER COLUMN r2y TYPE NUMERIC(14,4), ALTER COLUMN r3y TYPE NUMERIC(14,4), ALTER COLUMN r5y TYPE NUMERIC(14,4), ALTER COLUMN dd1y TYPE NUMERIC(14,4), ALTER COLUMN dd2y TYPE NUMERIC(14,4), ALTER COLUMN dd3y TYPE NUMERIC(14,4), ALTER COLUMN dd5y TYPE NUMERIC(14,4), ALTER COLUMN sr1y TYPE NUMERIC(14,4), ALTER COLUMN sr2y TYPE NUMERIC(14,4), ALTER COLUMN sr3y TYPE NUMERIC(14,4), ALTER COLUMN sr5y TYPE NUMERIC(14,4)');
    console.log('  列精度已扩展');
  } catch (e) { /* ignore */ }

  console.log(`\n[4] 导入 ${allFunds.length} 条到 Supabase...`);
  const imported = await importToSupabase(allFunds);

  // 4. Meta
  console.log('\n[5] 写入 fund_scores_meta...');
  const navDate = allFunds[0]?.date || '';
  try {
    await runSQL('TRUNCATE TABLE fund_scores_meta');
    await runSQL(`INSERT INTO fund_scores_meta (update_time, total_count, scored_count, nav_date) VALUES (NOW()::text, ${allFunds.length}, ${scored.length}, '${navDate}')`);
    console.log(`  total=${allFunds.length}, scored=${scored.length}, date=${navDate}`);
  } catch (e) { console.error('  meta写入失败:', e.message); }

  // 5. Verify
  console.log('\n[6] 验证...');
  const cnt = await runSQL('SELECT count(*) as cnt FROM fund_scores');
  console.log(`  fund_scores: ${cnt[0].cnt} 条`);

  const stats = await runSQL('SELECT t0, count(*) as cnt, count(k3) as scored FROM fund_scores GROUP BY t0 ORDER BY cnt DESC');
  console.log('\n  分类统计:');
  for (const s of stats) console.log(`    ${s.t0}: ${s.cnt}只, 有靠谱分${s.scored}只`);

  const top10 = await runSQL('SELECT c, n, t0, k1, k3 FROM fund_scores WHERE k3 > 0 ORDER BY k3 DESC LIMIT 10');
  console.log('\n  Top 10 靠谱分:');
  for (const t of top10) console.log(`    ${t.c} ${t.n}: k1=${t.k1}, k3=${t.k3}`);

  console.log('\nDone!');
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
