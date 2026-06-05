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

async function main() {
  console.log('=== Creating tables via Management API ===');
  const schemaPath = path.join(__dirname, '..', 'supabase-schema.sql');
  const raw = fs.readFileSync(schemaPath, 'utf-8');

  // Split by -- ==== separators to get logical blocks
  const blocks = raw.split(/-- ={10,}/);

  let ok = 0, fail = 0;
  for (let bi = 0; bi < blocks.length; bi++) {
    const block = blocks[bi].trim();
    if (!block) continue;

    // Remove SQL comments (lines starting with --)
    const cleaned = block
      .split('\n')
      .filter(line => !line.trim().startsWith('--') && line.trim().length > 0)
      .join('\n')
      .trim();

    if (!cleaned) continue;

    // Split by ; and execute each statement
    const statements = cleaned
      .split(';')
      .map(s => s.trim())
      .filter(s => s.length > 0);

    for (const stmt of statements) {
      try {
        await runSQL(stmt);
        console.log(`  OK: ${stmt.substring(0, 50).replace(/\n/g, ' ')}...`);
        ok++;
      } catch (err) {
        const msg = err.message;
        if (msg.includes('already exists') || msg.includes('duplicate')) {
          console.log(`  SKIP: ${stmt.substring(0, 50).replace(/\n/g, ' ')}...`);
          ok++;
        } else {
          fail++;
          console.error(`  FAIL: ${msg.substring(0, 150)}`);
        }
      }
    }
  }

  console.log(`\nResults: ${ok} OK, ${fail} failed`);

  // Verify
  const tables = await runSQL(
    "SELECT table_name FROM information_schema.tables WHERE table_schema='public' ORDER BY table_name"
  );
  console.log('Tables:', tables.map(t => t.table_name).join(', '));

  const policies = await runSQL(
    "SELECT tablename, policyname FROM pg_policies WHERE schemaname='public'"
  );
  console.log(`RLS policies: ${policies.length}`);
  policies.forEach(p => console.log(`  ${p.tablename}: ${p.policyname}`));
}

main().catch(e => { console.error(e); process.exit(1); });
