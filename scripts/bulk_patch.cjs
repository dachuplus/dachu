/**
 * bulk_patch.cjs — 并发 PATCH 靠谱评分到 Supabase REST API
 *
 * 读取 funds_full.ndjson，并发 PATCH 更新评分字段到 fund_scores 表。
 * 使用 Node.js https + IPv6 (family: 6)，并发度10。
 *
 * 更新字段: k0w/k1m/k3m/k6m/k1/k2/k3/k5/k_all/score_grade
 * 以及 fund_scores_meta 元信息表
 */

const https = require('https');
const fs = require('fs');
const path = require('path');

// ===== 配置 =====
const SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co';
const SUPABASE_ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3';
const CONCURRENCY = 10;
const NDJSON_PATH = path.resolve(
  __dirname,
  '../../asset-config-miniapp/scripts/funds_full.ndjson'
);

// 要 PATCH 到 Supabase 的字段列表
const SCORE_FIELDS = [
  'k0w', 'k1m', 'k3m', 'k6m',
  'k1', 'k2', 'k3', 'k5',
  'k_all', 'score_grade'
];

// ===== 工具函数 =====
const t0 = Date.now();

function log(msg) {
  const elapsed = ((Date.now() - t0) / 1000).toFixed(1);
  console.log(`[${elapsed}s] ${msg}`);
}

/**
 * 使用 Node.js https 发送 PATCH 请求（IPv6 family:6）
 */
function patchRecord(tableName, filterKey, filterValue, data) {
  return new Promise((resolve, reject) => {
    const url = new URL(`${SUPABASE_URL}/rest/v1/${tableName}`);
    url.searchParams.set(filterKey, `eq.${filterValue}`);

    const bodyStr = JSON.stringify(data);
    const options = {
      hostname: url.hostname,
      port: 443,
      path: url.pathname + url.search,
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
        'Prefer': 'return=minimal',
        'Content-Length': Buffer.byteLength(bodyStr),
      },
      family: 6,  // IPv6
      timeout: 30000,
    };

    const req = https.request(options, (res) => {
      let chunks = [];
      res.on('data', (chunk) => chunks.push(chunk));
      res.on('end', () => {
        if (res.statusCode >= 200 && res.statusCode < 300) {
          resolve({ status: res.statusCode });
        } else {
          const body = Buffer.concat(chunks).toString().substring(0, 200);
          reject(new Error(`HTTP ${res.statusCode}: ${body}`));
        }
      });
    });

    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
    req.write(bodyStr);
    req.end();
  });
}

/**
 * POST 到 fund_scores_meta
 */
function postMeta(meta) {
  return new Promise((resolve, reject) => {
    // 先 DELETE ALL，再 INSERT
    const url = new URL(`${SUPABASE_URL}/rest/v1/fund_scores_meta`);

    // Step 1: DELETE all
    const delUrl = new URL(`${SUPABASE_URL}/rest/v1/fund_scores_meta`);
    delUrl.searchParams.set('id', 'gte.0');

    const delOptions = {
      hostname: delUrl.hostname,
      port: 443,
      path: delUrl.pathname + delUrl.search,
      method: 'DELETE',
      headers: {
        'apikey': SUPABASE_ANON_KEY,
        'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
        'Prefer': 'return=minimal',
      },
      family: 6,
      timeout: 15000,
    };

    const delReq = https.request(delOptions, (res) => {
      let ch = [];
      res.on('data', (c) => ch.push(c));
      res.on('end', () => {
        // Step 2: INSERT new meta
        const bodyStr = JSON.stringify(meta);
        const insOptions = {
          hostname: url.hostname,
          port: 443,
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'apikey': SUPABASE_ANON_KEY,
            'Authorization': `Bearer ${SUPABASE_ANON_KEY}`,
            'Prefer': 'return=minimal',
            'Content-Length': Buffer.byteLength(bodyStr),
          },
          family: 6,
          timeout: 15000,
        };
        const insReq = https.request(insOptions, (res2) => {
          let ch2 = [];
          res2.on('data', (c) => ch2.push(c));
          res2.on('end', () => {
            if (res2.statusCode >= 200 && res2.statusCode < 300) {
              resolve();
            } else {
              reject(new Error(`Meta insert HTTP ${res2.statusCode}`));
            }
          });
        });
        insReq.on('error', reject);
        insReq.write(bodyStr);
        insReq.end();
      });
    });
    delReq.on('error', reject);
    delReq.end();
  });
}

/**
 * 并发控制器
 */
async function runWithConcurrency(tasks, concurrency) {
  const results = [];
  let idx = 0;
  let success = 0;
  let fail = 0;

  async function worker() {
    while (idx < tasks.length) {
      const i = idx++;
      const task = tasks[i];
      try {
        await task();
        success++;
      } catch (e) {
        fail++;
        if (fail <= 5) {
          log(`  ❌ #${i} 失败: ${e.message.substring(0, 100)}`);
        }
      }
      // 进度报告
      const done = success + fail;
      if (done % 500 === 0 || done === tasks.length) {
        log(`  进度: ${done}/${tasks.length} (✓${success} ✗${fail})`);
      }
    }
  }

  const workers = [];
  for (let w = 0; w < concurrency; w++) {
    workers.push(worker());
  }
  await Promise.all(workers);
  return { success, fail, total: tasks.length };
}

// ===== 主流程 =====
async function main() {
  console.log('============================================================');
  console.log('靠谱评分 Supabase REST API 批量 PATCH');
  console.log('============================================================');

  // 1. 读取 NDJSON
  log('读取 funds_full.ndjson...');
  const content = fs.readFileSync(NDJSON_PATH, 'utf-8');
  const funds = content.trim().split('\n').filter(Boolean).map(JSON.parse);
  log(`共 ${funds.length} 条记录`);

  // 2. 构建 PATCH 任务
  log(`构建 PATCH 任务（字段: ${SCORE_FIELDS.join(', ')}）...`);
  const tasks = funds.map((fund) => async () => {
    const data = {};
    for (const field of SCORE_FIELDS) {
      if (fund[field] !== undefined) {
        data[field] = fund[field];
      }
    }
    await patchRecord('fund_scores', 'c', fund.c, data);
  });
  log(`任务数: ${tasks.length}`);

  // 3. 并发 PATCH
  log(`开始并发 PATCH（并发度=${CONCURRENCY}）...`);
  const result = await runWithConcurrency(tasks, CONCURRENCY);
  log(`PATCH 完成: ✓${result.success} ✗${result.fail} / 共${result.total}`);

  // 4. 更新 fund_scores_meta
  log('更新 fund_scores_meta...');
  const scoredCount = funds.filter(f => f.k_all != null).length;
  const navDate = funds.find(f => f.date)?.date || '';
  const gradeDist = { gold: 0, orange: 0, cyan: 0, gray: 0 };
  for (const f of funds) {
    const g = f.score_grade;
    if (g === 'gold') gradeDist.gold++;
    else if (g === 'orange') gradeDist.orange++;
    else if (g === 'cyan') gradeDist.cyan++;
    else gradeDist.gray++;
  }

  try {
    await postMeta({
      update_time: new Date().toISOString().replace('T', ' ').substring(0, 19),
      total_count: funds.length,
      scored_count: scoredCount,
      nav_date: navDate,
    });
    log(`meta 更新成功: total=${funds.length}, scored=${scoredCount}, date=${navDate}`);
  } catch (e) {
    log(`meta 更新失败: ${e.message}`);
  }

  // 5. 汇总报告
  const totalSec = ((Date.now() - t0) / 1000).toFixed(1);
  console.log('\n============================================================');
  console.log('完成汇总');
  console.log('============================================================');
  console.log(`  总耗时: ${totalSec}s`);
  console.log(`  PATCH: ✓${result.success} ✗${result.fail} / ${result.total}`);
  console.log(`  有靠谱分(k_all): ${scoredCount}`);
  console.log(`  分级分布: 金=${gradeDist.gold} 橙=${gradeDist.orange} 青=${gradeDist.cyan} 灰=${gradeDist.gray}`);
  console.log(`  净值日期: ${navDate}`);
  console.log(`  QPS: ${(result.success / parseFloat(totalSec)).toFixed(1)}`);
}

main().catch(e => { console.error('Fatal:', e); process.exit(1); });
