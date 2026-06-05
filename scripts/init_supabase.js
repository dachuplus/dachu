import pg from 'pg';
const { Client } = pg;
import { createClient } from '@supabase/supabase-js';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_REF = 'tqhtegazxykkqfcpejky';
const ANON_KEY = process.env.SUPABASE_ANON_KEY || 'YOUR_ANON_KEY';
const ACCESS_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.argv[2] || 'YOUR_MGMT_TOKEN';

const MGMT_API = `https://api.supabase.com/v1/projects/${PROJECT_REF}/database/query`;

// --- Step 1: Create tables via Management API ---
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

async function createTables() {
  console.log('=== Step 1: Creating tables ===');
  const schemaPath = path.join(__dirname, '..', 'supabase-schema.sql');
  const schema = fs.readFileSync(schemaPath, 'utf-8');

  // Split by statement boundaries and filter out comments/empty
  const statements = schema
    .split(';')
    .map(s => s.trim())
    .filter(s => s.length > 0 && !s.startsWith('--'));

  for (const stmt of statements) {
    try {
      await runSQL(stmt);
      console.log('  OK:', stmt.substring(0, 60).replace(/\n/g, ' ') + '...');
    } catch (err) {
      // Ignore "already exists" errors
      if (err.message.includes('already exists') || err.message.includes('duplicate')) {
        console.log('  SKIP (exists):', stmt.substring(0, 60).replace(/\n/g, ' ') + '...');
      } else {
        console.error('  FAIL:', err.message.substring(0, 100));
      }
    }
  }

  // Verify tables exist
  const tables = await runSQL(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
  );
  console.log('\nTables created:', tables.map(t => t.table_name).join(', '));
}

// --- Step 2: Import data via REST API (anon key, batch INSERT) ---
async function importData() {
  console.log('\n=== Step 2: Importing data ===');
  const supabase = createClient(
    `https://${PROJECT_REF}.supabase.co`,
    ANON_KEY
  );

  // Import fund_scores from NDJSON
  const fundScoresPath = path.join(__dirname, '..', 'supabase-data', 'fund_scores.ndjson');
  if (fs.existsSync(fundScoresPath)) {
    console.log('Importing fund_scores...');
    const lines = fs.readFileSync(fundScoresPath, 'utf-8').split('\n').filter(Boolean);
    console.log(`  Total records: ${lines.length}`);
    const BATCH = 500;
    let imported = 0;
    for (let i = 0; i < lines.length; i += BATCH) {
      const batch = lines.slice(i, i + BATCH).map(l => JSON.parse(l));
      // Remove id and tsq if present (let DB auto-generate)
      for (const row of batch) {
        delete row.id;
        delete row.tsq;
      }
      const { error } = await supabase.from('fund_scores').insert(batch);
      if (error) {
        // If already exists, try upsert
        console.log(`  Batch ${i}-${i+BATCH}: ${error.message.substring(0,80)}`);
      } else {
        imported += batch.length;
      }
    }
    console.log(`  fund_scores imported: ${imported}/${lines.length}`);
  } else {
    console.log(`  fund_scores.ndjson not found at ${fundScoresPath}`);
  }

  // Import tougu_products
  const touguPath = path.join(__dirname, '..', 'supabase-data', 'tougu_products.ndjson');
  if (fs.existsSync(touguPath)) {
    console.log('Importing tougu_products...');
    const lines = fs.readFileSync(touguPath, 'utf-8').split('\n').filter(Boolean);
    console.log(`  Total records: ${lines.length}`);
    const batch = lines.map(l => {
      const row = JSON.parse(l);
      delete row.id;
      delete row.tsq;
      return row;
    });
    const { error } = await supabase.from('tougu_products').insert(batch);
    if (error) {
      console.log(`  tougu_products error: ${error.message}`);
    } else {
      console.log(`  tougu_products imported: ${batch.length}`);
    }
  } else {
    console.log(`  tougu_products.ndjson not found at ${touguPath}`);
  }

  // Import config
  const configPath = path.join(__dirname, '..', 'supabase-data', 'config.ndjson');
  if (fs.existsSync(configPath)) {
    console.log('Importing config...');
    const lines = fs.readFileSync(configPath, 'utf-8').split('\n').filter(Boolean);
    const batch = lines.map(l => {
      const row = JSON.parse(l);
      delete row.id;
      delete row.tsq;
      return row;
    });
    const { error } = await supabase.from('config').insert(batch);
    if (error) {
      console.log(`  config error: ${error.message}`);
    } else {
      console.log(`  config imported: ${batch.length}`);
    }
  } else {
    console.log(`  config.ndjson not found at ${configPath}`);
  }
}

// --- Step 3: Verify ---
async function verify() {
  console.log('\n=== Step 3: Verification ===');
  const supabase = createClient(
    `https://${PROJECT_REF}.supabase.co`,
    ANON_KEY
  );

  const { count: fsCount } = await supabase.from('fund_scores').select('*', { count: 'exact', head: true });
  const { count: tgCount } = await supabase.from('tougu_products').select('*', { count: 'exact', head: true });
  const { count: cfgCount } = await supabase.from('config').select('*', { count: 'exact', head: true });

  console.log(`fund_scores: ${fsCount} rows`);
  console.log(`tougu_products: ${tgCount} rows`);
  console.log(`config: ${cfgCount} rows`);

  // Check RLS
  const tables = await runSQL(
    "SELECT schemaname, tablename, policyname FROM pg_policies WHERE schemaname='public'"
  );
  console.log(`\nRLS policies: ${tables.length} total`);
  tables.forEach(p => console.log(`  ${p.tablename}: ${p.policyname}`));
}

// --- Main ---
(async () => {
  try {
    await createTables();
    await importData();
    await verify();
    console.log('\nDone!');
  } catch (err) {
    console.error('Fatal:', err);
    process.exit(1);
  }
})();
