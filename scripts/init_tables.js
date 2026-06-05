import pg from 'pg';
const { Client } = pg;

const SQL = `
-- 1. fund_scores
CREATE TABLE IF NOT EXISTS fund_scores (
  id BIGSERIAL PRIMARY KEY,
  c VARCHAR(20) NOT NULL,
  n VARCHAR(100) NOT NULL,
  t0 VARCHAR(50),
  t1 VARCHAR(50),
  t2 VARCHAR(50),
  t6 VARCHAR(50),
  a INTEGER DEFAULT 0,
  hp INTEGER,
  ytd NUMERIC(10,4),
  r0w NUMERIC(10,4),
  r1m NUMERIC(10,4),
  r3m NUMERIC(10,4),
  r6m NUMERIC(10,4),
  r1y NUMERIC(10,4),
  r2y NUMERIC(10,4),
  r3y NUMERIC(10,4),
  r5y NUMERIC(10,4),
  nav NUMERIC(10,4),
  date VARCHAR(20),
  k1 NUMERIC(6,4),
  k2 NUMERIC(6,4),
  k3 NUMERIC(6,4),
  k5 NUMERIC(6,4),
  k7 NUMERIC(6,4),
  k10 NUMERIC(6,4),
  dd1y NUMERIC(10,4),
  dd2y NUMERIC(10,4),
  dd3y NUMERIC(10,4),
  dd5y NUMERIC(10,4),
  sr1y NUMERIC(10,4),
  sr2y NUMERIC(10,4),
  sr3y NUMERIC(10,4),
  sr5y NUMERIC(10,4),
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_fund_scores_c ON fund_scores(c);
CREATE INDEX IF NOT EXISTS idx_fund_scores_k3 ON fund_scores(k3 DESC);
CREATE INDEX IF NOT EXISTS idx_fund_scores_t0 ON fund_scores(t0);
CREATE INDEX IF NOT EXISTS idx_fund_scores_k1 ON fund_scores(k1 DESC);
ALTER TABLE fund_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on fund_scores" ON fund_scores FOR SELECT TO anon USING (true);

-- 2. tougu_products
CREATE TABLE IF NOT EXISTS tougu_products (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  company VARCHAR(200),
  type VARCHAR(20),
  typeName VARCHAR(50),
  "desc" TEXT,
  tags TEXT[],
  return3m NUMERIC(10,4),
  return1y NUMERIC(10,4),
  maxDrawdown NUMERIC(10,4),
  url VARCHAR(500),
  updateDate VARCHAR(20),
  dataSource VARCHAR(50),
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_tougu_type ON tougu_products(type);
CREATE INDEX IF NOT EXISTS idx_tougu_return1y ON tougu_products(return1y DESC);
ALTER TABLE tougu_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on tougu_products" ON tougu_products FOR SELECT TO anon USING (true);

-- 3. config
CREATE TABLE IF NOT EXISTS config (
  id BIGSERIAL PRIMARY KEY,
  type VARCHAR(50) NOT NULL UNIQUE,
  v TEXT,
  meta JSONB DEFAULT '{}',
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on config" ON config FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert on config" ON config FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update on config" ON config FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- 4. index_pe_history
CREATE TABLE IF NOT EXISTS index_pe_history (
  id BIGSERIAL PRIMARY KEY,
  index_code VARCHAR(20) NOT NULL,
  trade_date VARCHAR(20) NOT NULL,
  pe NUMERIC(12,4),
  pb NUMERIC(12,4),
  data_source VARCHAR(50),
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(index_code, trade_date)
);
CREATE INDEX IF NOT EXISTS idx_peh_date ON index_pe_history(trade_date DESC);
ALTER TABLE index_pe_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on index_pe_history" ON index_pe_history FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert on index_pe_history" ON index_pe_history FOR INSERT TO anon WITH CHECK (true);

-- 5. fund_scores_meta
CREATE TABLE IF NOT EXISTS fund_scores_meta (
  id BIGSERIAL PRIMARY KEY,
  update_time VARCHAR(50),
  total_count INTEGER DEFAULT 0,
  scored_count INTEGER DEFAULT 0,
  nav_date VARCHAR(20),
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
ALTER TABLE fund_scores_meta ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on fund_scores_meta" ON fund_scores_meta FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert on fund_scores_meta" ON fund_scores_meta FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update on fund_scores_meta" ON fund_scores_meta FOR UPDATE TO anon USING (true) WITH CHECK (true);
`;

// 尝试多种连接方式
const attempts = [
  { host: 'db.tqhtegazxykkqfcpejky.supabase.co', port: 5432, user: 'postgres', label: 'direct' },
  { host: 'aws-0-ap-southeast-1.pooler.supabase.com', port: 5432, user: 'postgres.tqhtegazxykkqfcpejky', label: 'session-pooler' },
  { host: 'aws-0-ap-southeast-1.pooler.supabase.com', port: 6543, user: 'postgres.tqhtegazxykkqfcpejky', label: 'tx-pooler' },
];

const PASS = 'Mao15901622389!';
let connected = false;

for (const att of attempts) {
  const client = new Client({
    host: att.host,
    port: att.port,
    database: 'postgres',
    user: att.user,
    password: PASS,
    ssl: { rejectUnauthorized: false }
  });
  try {
    await client.connect();
    console.log(`Connected via ${att.label}`);
    console.log('Creating tables...');
    await client.query(SQL);
    console.log('All tables created successfully!');
    await client.end();
    connected = true;
    break;
  } catch (err) {
    console.log(`${att.label}: ${err.code || ''} ${err.message.split('\n')[0]}`);
  }
}

if (!connected) {
  console.log('\nAll connection attempts failed.');
  console.log('Please execute the SQL manually in Supabase Dashboard SQL Editor:');
  console.log('https://supabase.com/dashboard/project/tqhtegazxykkqfcpejky/sql');
  console.log('\nCopy the content of: invest-h5/supabase-schema.sql');
  process.exit(1);
}
