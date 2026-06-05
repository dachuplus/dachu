import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_REF = 'tqhtegazxykkqfcpejky';
const ACCESS_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.argv[2] || 'YOUR_MGMT_TOKEN';
const MGMT_API = `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`;

async function runSQL(sql) {
  const res = await fetch(MGMT_API, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${ACCESS_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ query: sql })
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`SQL error ${res.status}: ${err}`);
  }
  return res.json();
}

function esc(str) {
  if (str === null || str === undefined) return 'NULL';
  return "'" + String(str).replace(/'/g, "''") + "'";
}

function escArray(arr) {
  if (!Array.isArray(arr)) return 'NULL';
  return "ARRAY[" + arr.map(a => esc(a)).join(',') + "]::text[]";
}

async function addRLSPolicies() {
  console.log('=== Adding INSERT/DELETE RLS policies ===');
  const policies = [
    `DROP POLICY IF EXISTS "Allow anon insert on tougu_products" ON tougu_products`,
    `CREATE POLICY "Allow anon insert on tougu_products" ON tougu_products FOR INSERT TO anon WITH CHECK (true)`,
    `DROP POLICY IF EXISTS "Allow anon delete on tougu_products" ON tougu_products`,
    `CREATE POLICY "Allow anon delete on tougu_products" ON tougu_products FOR DELETE TO anon USING (true)`,
    `DROP POLICY IF EXISTS "Allow anon insert on fund_scores" ON fund_scores`,
    `CREATE POLICY "Allow anon insert on fund_scores" ON fund_scores FOR INSERT TO anon WITH CHECK (true)`,
    `DROP POLICY IF EXISTS "Allow anon delete on fund_scores" ON fund_scores`,
    `CREATE POLICY "Allow anon delete on fund_scores" ON fund_scores FOR DELETE TO anon USING (true)`,
  ];
  for (const p of policies) {
    try {
      await runSQL(p);
      console.log('  OK:', p.substring(0, 60));
    } catch (err) {
      console.error('  ERR:', err.message.substring(0, 100));
    }
  }
}

async function importTouguViaSQL() {
  console.log('\n=== Importing tougu_products via Management API SQL ===');
  const srcPath = '/Users/maoshanbo/WorkBuddy/20260405093252/asset-config-miniapp/scripts/tougu_products_v2.ndjson';
  const lines = fs.readFileSync(srcPath, 'utf-8').split('\n').filter(Boolean);
  console.log(`  Total: ${lines.length} records`);

  let imported = 0;
  const BATCH = 20; // Keep batches small for SQL strings

  for (let i = 0; i < lines.length; i += BATCH) {
    const batch = lines.slice(i, i + BATCH);
    const values = batch.map(line => {
      const row = JSON.parse(line);
      const tags = typeof row.tags === 'string' ? row.tags.split(' ') : (Array.isArray(row.tags) ? row.tags : []);
      return `(${esc(row.name)}, ${esc(row.company)}, ${esc(row.type)}, ${esc(row.typeName)}, ${esc(row.desc)}, ${escArray(tags)}, ${esc(row.return3m)}, ${esc(row.return1y)}, ${esc(row.maxDrawdown)}, ${esc(row.url)}, ${esc(row.updateDate)}, ${esc(row.dataSource || '天天基金')})`;
    }).join(',\n');

    const sql = `INSERT INTO tougu_products (name, company, type, typename, "desc", tags, return3m, return1y, maxdrawdown, url, updatedate, datasource) VALUES\n${values}`;

    try {
      await runSQL(sql);
      imported += batch.length;
    } catch (err) {
      console.error(`  Batch ${i}-${i+BATCH} error:`, err.message.substring(0, 120));
    }
    await new Promise(r => setTimeout(r, 200));
  }
  console.log(`  Imported: ${imported}/${lines.length}`);
}

async function verify() {
  console.log('\n=== Verification ===');
  const result = await runSQL(
    "SELECT table_name, (SELECT count(*) FROM information_schema.columns c WHERE c.table_name = t.table_name) as cols FROM information_schema.tables t WHERE table_schema = 'public' ORDER BY table_name"
  );
  console.log('Tables:', JSON.stringify(result, null, 2));

  const counts = await runSQL(`
    SELECT 'fund_scores' as tbl, count(*) as cnt FROM fund_scores
    UNION ALL SELECT 'tougu_products', count(*) FROM tougu_products
    UNION ALL SELECT 'config', count(*) FROM config
    UNION ALL SELECT 'index_pe_history', count(*) FROM index_pe_history
    UNION ALL SELECT 'fund_scores_meta', count(*) FROM fund_scores_meta
  `);
  console.log('\nRow counts:');
  counts.forEach(r => console.log(`  ${r.tbl}: ${r.cnt}`));

  const sample = await runSQL("SELECT name, company, type, return1y FROM tougu_products LIMIT 3");
  console.log('\nSample tougu_products:');
  sample.forEach(r => console.log(`  ${r.name} | ${r.company} | ${r.type} | 1yr: ${r.return1y}`));
}

(async () => {
  try {
    await addRLSPolicies();
    await importTouguViaSQL();
    await verify();
    console.log('\nDone!');
  } catch (err) {
    console.error('Fatal:', err);
    process.exit(1);
  }
})();
