/**
 * 单独创建 user_ai_models 表（AI 大 PK 模型管理功能的数据层）
 * 通过 Supabase Management API 执行 DDL，仅创建本表，不影响其它表。
 *
 * 用法：
 *   node scripts/create_user_ai_models.js
 *   # 或指定 token： SUPABASE_MGMT_TOKEN=xxx node scripts/create_user_ai_models.js
 */
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROJECT_REF = 'tqhtegazxykkqfcpejky';
const ACCESS_TOKEN = process.env.SUPABASE_MGMT_TOKEN || process.env.SUPABASE_PAT || 'YOUR_MGMT_TOKEN';
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

const SQL = `
CREATE TABLE IF NOT EXISTS public.user_ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,
    model_name TEXT NOT NULL,
    model_provider TEXT NOT NULL,
    api_endpoint TEXT,
    api_key_encrypted TEXT,
    system_prompt TEXT DEFAULT '',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_ai_models_user_id ON public.user_ai_models(user_id);

GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_ai_models TO anon;
`;

async function main() {
  console.log('=== Creating user_ai_models via Management API ===');
  const statements = SQL.split(';').map(s => s.trim()).filter(s => s.length > 0);
  let ok = 0, fail = 0;
  for (const stmt of statements) {
    try {
      await runSQL(stmt);
      console.log(`  OK: ${stmt.substring(0, 60).replace(/\n/g, ' ')}...`);
      ok++;
    } catch (err) {
      const msg = err.message;
      if (msg.includes('already exists') || msg.includes('duplicate')) {
        console.log(`  SKIP: ${stmt.substring(0, 60).replace(/\n/g, ' ')}... (已存在)`);
        ok++;
      } else {
        fail++;
        console.error(`  FAIL: ${msg.substring(0, 200)}`);
      }
    }
  }
  console.log(`\nResults: ${ok} OK, ${fail} failed`);

  try {
    const r = await runSQL("SELECT column_name, data_type FROM information_schema.columns WHERE table_name='user_ai_models' ORDER BY ordinal_position");
    console.log('user_ai_models columns:', r.map(c => `${c.column_name}:${c.data_type}`).join(', '));
  } catch (e) {
    console.error('verify failed:', e.message);
  }
}

main().catch(e => { console.error(e); process.exit(1); });
