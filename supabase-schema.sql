-- Supabase 建表脚本
-- 执行方式：在 Supabase Dashboard → SQL Editor 中执行
-- URL: https://supabase.com/dashboard/project/tqhtegazxykkqfcpejky/sql

-- ============================================================
-- 1. fund_scores - 靠谱基金指数（~20000条）
-- ============================================================
CREATE TABLE IF NOT EXISTS fund_scores (
  id BIGSERIAL PRIMARY KEY,
  c VARCHAR(20) NOT NULL,           -- 基金代码，如 000001.OF
  n VARCHAR(100) NOT NULL,          -- 基金名称
  t0 VARCHAR(50),                   -- 一级分类（股票型基金/债券型基金/混合型基金/FOF/QDII基金）
  t1 VARCHAR(50),                   -- 二级分类
  t2 VARCHAR(50),                   -- 三级分类（天天基金API分类）
  t6 VARCHAR(50),                   -- 六级标签
  a INTEGER DEFAULT 0,              -- 属性位标志：ETF=1, LOF=2, 定开=4, 近2年=8
  hp INTEGER,                       -- 持有期月数

  -- 收益字段
  ytd NUMERIC(10,4),                -- 今年来收益率(%)
  r0w NUMERIC(10,4),                -- 近1周收益率(%)
  r1m NUMERIC(10,4),                -- 近1月收益率(%)
  r3m NUMERIC(10,4),                -- 近3月收益率(%)
  r6m NUMERIC(10,4),                -- 近6月收益率(%)
  r1y NUMERIC(10,4),                -- 近1年收益率(%)
  r2y NUMERIC(10,4),                -- 近2年收益率(%)
  r3y NUMERIC(10,4),                -- 近3年收益率(%)
  r5y NUMERIC(10,4),                -- 近5年收益率(%)
  nav NUMERIC(10,4),                -- 最新净值
  date VARCHAR(20),                 -- 净值日期

  -- 靠谱指数
  k1 NUMERIC(6,4),                  -- 1年靠谱指数（0-100）
  k2 NUMERIC(6,4),                  -- 2年靠谱指数
  k3 NUMERIC(6,4),                  -- 3年靠谱指数
  k5 NUMERIC(6,4),                  -- 5年靠谱指数
  k7 NUMERIC(6,4),                  -- 7年靠谱指数
  k10 NUMERIC(6,4),                 -- 10年靠谱指数

  -- 风险指标
  dd1y NUMERIC(10,4),               -- 1年最大回撤(%)，负数
  dd2y NUMERIC(10,4),               -- 2年最大回撤(%)
  dd3y NUMERIC(10,4),               -- 3年最大回撤(%)
  dd5y NUMERIC(10,4),               -- 5年最大回撤(%)
  sr1y NUMERIC(10,4),               -- 1年夏普比率
  sr2y NUMERIC(10,4),               -- 2年夏普比率
  sr3y NUMERIC(10,4),               -- 3年夏普比率
  sr5y NUMERIC(10,4),               -- 5年夏普比率
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_fund_scores_c ON fund_scores(c);
CREATE INDEX IF NOT EXISTS idx_fund_scores_k3 ON fund_scores(k3 DESC);
CREATE INDEX IF NOT EXISTS idx_fund_scores_t0 ON fund_scores(t0);
CREATE INDEX IF NOT EXISTS idx_fund_scores_k1 ON fund_scores(k1 DESC);

-- 允许 anon 读取
ALTER TABLE fund_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on fund_scores" ON fund_scores FOR SELECT TO anon USING (true);

-- ============================================================
-- 2. tougu_products - 投顾产品（~103条）
-- ============================================================
CREATE TABLE IF NOT EXISTS tougu_products (
  id BIGSERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,       -- 产品名称
  company VARCHAR(200),             -- 管理机构
  type VARCHAR(20),                 -- 分类标识（high/stable/pension）
  typeName VARCHAR(50),             -- 分类名称（追求高收益/稳健理财/养老储蓄）
  "desc" TEXT,                     -- 策略理念简介
  tags TEXT[],                      -- 策略标签数组
  return3m NUMERIC(10,4),           -- 近3月收益率（小数形式）
  return1y NUMERIC(10,4),           -- 近1年收益率
  maxDrawdown NUMERIC(10,4),        -- 最大回撤
  url VARCHAR(500),                 -- 天天基金详情页URL
  updateDate VARCHAR(20),           -- 数据更新日期
  dataSource VARCHAR(50),           -- 数据来源
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tougu_type ON tougu_products(type);
CREATE INDEX IF NOT EXISTS idx_tougu_return1y ON tougu_products(return1y DESC);

ALTER TABLE tougu_products ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on tougu_products" ON tougu_products FOR SELECT TO anon USING (true);

-- ============================================================
-- 3. config - 配置项
-- ============================================================
CREATE TABLE IF NOT EXISTS config (
  id BIGSERIAL PRIMARY KEY,
  type VARCHAR(50) NOT NULL UNIQUE, -- 配置类型标识
  v TEXT,                           -- 通用值字段
  meta JSONB DEFAULT '{}',          -- 扩展字段（JSON格式）
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE config ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on config" ON config FOR SELECT TO anon USING (true);
-- config 需要写入权限给 anon（前端直读、脚本直写）
CREATE POLICY "Allow anon insert on config" ON config FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update on config" ON config FOR UPDATE TO anon USING (true) WITH CHECK (true);

-- ============================================================
-- 4. index_pe_history - PE历史数据
-- ============================================================
CREATE TABLE IF NOT EXISTS index_pe_history (
  id BIGSERIAL PRIMARY KEY,
  index_code VARCHAR(20) NOT NULL,  -- 指数代码，如 000300
  trade_date VARCHAR(20) NOT NULL,  -- 交易日期 YYYY-MM-DD
  pe NUMERIC(12,4),                 -- 市盈率
  pb NUMERIC(12,4),                 -- 市净率
  data_source VARCHAR(50),          -- 数据来源
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  UNIQUE(index_code, trade_date)
);

CREATE INDEX IF NOT EXISTS idx_peh_date ON index_pe_history(trade_date DESC);

ALTER TABLE index_pe_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on index_pe_history" ON index_pe_history FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon insert on index_pe_history" ON index_pe_history FOR INSERT TO anon WITH CHECK (true);

-- ============================================================
-- 5. fund_scores_meta - 基金数据元信息
-- ============================================================
CREATE TABLE IF NOT EXISTS fund_scores_meta (
  id BIGSERIAL PRIMARY KEY,
  update_time VARCHAR(50),          -- 更新时间
  total_count INTEGER DEFAULT 0,    -- 基金总数
  scored_count INTEGER DEFAULT 0,   -- 有靠谱分的基金数
  nav_date VARCHAR(20),             -- 净值日期
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE fund_scores_meta ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on fund_scores_meta" ON fund_scores_meta FOR SELECT TO anon USING (true);
CREATE POLICY "Allow anon upsert on fund_scores_meta" ON fund_scores_meta FOR INSERT TO anon WITH CHECK (true);
CREATE POLICY "Allow anon update on fund_scores_meta" ON fund_scores_meta FOR UPDATE TO anon USING (true) WITH CHECK (true);
