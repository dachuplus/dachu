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

-- ============================================================
-- 6. user_profiles - 用户注册/登录信息
-- ============================================================
CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL UNIQUE REFERENCES auth.users(id) ON DELETE CASCADE,
  email VARCHAR(255),
  display_name VARCHAR(100),
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  last_login_at TIMESTAMP WITH TIME ZONE,
  login_count INTEGER DEFAULT 0,
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_user_id ON user_profiles(user_id);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;
-- 用户只能读写自己的 profile
CREATE POLICY "Users read own profile" ON user_profiles FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users insert own profile" ON user_profiles FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own profile" ON user_profiles FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);

-- ============================================================
-- 7. user_portfolios - 用户自建组合
-- ============================================================
CREATE TABLE IF NOT EXISTS user_portfolios (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  name VARCHAR(200) NOT NULL DEFAULT '我的组合',
  portfolio_data JSONB NOT NULL DEFAULT '[]'::jsonb,  -- [{code, name, weight, addedAt}]
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  tsq TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_portfolios_user_id ON user_portfolios(user_id);

ALTER TABLE user_portfolios ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Users read own portfolios" ON user_portfolios FOR SELECT TO authenticated USING (auth.uid() = user_id);
CREATE POLICY "Users insert own portfolios" ON user_portfolios FOR INSERT TO authenticated WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users update own portfolios" ON user_portfolios FOR UPDATE TO authenticated USING (auth.uid() = user_id) WITH CHECK (auth.uid() = user_id);
CREATE POLICY "Users delete own portfolios" ON user_portfolios FOR DELETE TO authenticated USING (auth.uid() = user_id);

-- ============================================================
-- 8. user_ai_models - 用户自建 AI 选基模型（AI 大 PK 模型管理）
-- ============================================================
CREATE TABLE IF NOT EXISTS public.user_ai_models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT,                    -- 手机号或匿名ID（后续接登录）
    model_name TEXT NOT NULL,        -- 模型名称（如 '我的GPT-4'）
    model_provider TEXT NOT NULL,    -- 提供商（openai/deepseek/anthropic/custom）
    api_endpoint TEXT,               -- API 端点URL
    api_key_encrypted TEXT,          -- 加密存储的API Key
    system_prompt TEXT DEFAULT '',   -- 系统提示词（如何选基金的指令）
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_user_ai_models_user_id ON public.user_ai_models(user_id);

-- 当前未启用 RLS：匿名(anon)用户可直接对自己创建的模型做增删改查（前端用 user_id 隔离）
GRANT SELECT, INSERT, UPDATE, DELETE ON public.user_ai_models TO anon;

-- ============================================================
-- 9. stock_scores - 股票靠谱分（A股：沪深300+中证500+中证1000 成分股，约1800只）
--    与基金 AI 大 PK 的 fund_scores / ai_pk_* 完全隔离，独立建表。
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stock_scores (
  code text PRIMARY KEY,            -- 如 '600519.SH'
  name text NOT NULL,
  industry text,                    -- 二级行业（东财行业分类名称）
  industry_code text,
  exchange text,                    -- SH/SZ/BJ
  secid text,                       -- 东财 secid 如 '1.600519'
  close numeric,
  pe_ttm numeric,
  pb numeric,
  mktcap numeric,                   -- 总市值(亿元)
  circ_mktcap numeric,              -- 流通市值(亿元)
  turnover_rate numeric,            -- 换手率(%)
  return_1m numeric,                -- 区间收益(%) 近1月
  return_3m numeric,                -- 近3月
  return_6m numeric,                -- 近6月
  return_1y numeric,                -- 近1年
  return_3y numeric,                -- 近3年
  daily_change numeric,             -- 当日涨跌幅(%)
  max_drawdown numeric,             -- 近1年最大回撤(%)，负值
  sharpe numeric,                   -- 近1年夏普
  k_ret numeric,                    -- 收益分位(0-100)
  k_drawdown numeric,               -- 回撤分位(0-100, 越大回撤越小)
  k_sharpe numeric,                 -- 夏普分位(0-100)
  k_all numeric,                    -- 0.5*k_ret+0.25*k_drawdown+0.25*k_sharpe
  is_st boolean DEFAULT false,
  is_delisted boolean DEFAULT false,
  is_suspended boolean DEFAULT false,
  list_date date,
  updated_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_scores_code ON public.stock_scores(code);
CREATE INDEX IF NOT EXISTS idx_stock_scores_industry ON public.stock_scores(industry);
CREATE INDEX IF NOT EXISTS idx_stock_scores_k_all ON public.stock_scores(k_all DESC);

ALTER TABLE public.stock_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on stock_scores" ON public.stock_scores FOR SELECT TO anon USING (true);

-- ============================================================
-- 10. stock_scores_staging - 抓取流水线第1级临时表（绝不直写生产表）
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stock_scores_staging (
  LIKE public.stock_scores INCLUDING ALL
);

CREATE INDEX IF NOT EXISTS idx_stock_scores_staging_code ON public.stock_scores_staging(code);
CREATE INDEX IF NOT EXISTS idx_stock_scores_staging_industry ON public.stock_scores_staging(industry);
CREATE INDEX IF NOT EXISTS idx_stock_scores_staging_k_all ON public.stock_scores_staging(k_all DESC);

ALTER TABLE public.stock_scores_staging ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on stock_scores_staging" ON public.stock_scores_staging FOR SELECT TO anon USING (true);

-- ============================================================
-- 11. stock_scores_test - 测试用镜像表
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stock_scores_test (
  LIKE public.stock_scores INCLUDING ALL
);

CREATE INDEX IF NOT EXISTS idx_stock_scores_test_code ON public.stock_scores_test(code);
CREATE INDEX IF NOT EXISTS idx_stock_scores_test_industry ON public.stock_scores_test(industry);
CREATE INDEX IF NOT EXISTS idx_stock_scores_test_k_all ON public.stock_scores_test(k_all DESC);

ALTER TABLE public.stock_scores_test ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read on stock_scores_test" ON public.stock_scores_test FOR SELECT TO anon USING (true);

-- ============================================================
-- 12. stock_pk_models - 股票组合 PK 模型元信息（镜像 ai_pk_models，新增 sort_order）
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stock_pk_models (
  id text PRIMARY KEY,
  name text NOT NULL,
  name_short text,
  region text NOT NULL DEFAULT 'A股',
  color text NOT NULL,
  persona text,
  category_logic text,
  mode text NOT NULL DEFAULT 'rule',
  api_provider text,
  api_model text,
  api_key_env text,
  enabled boolean NOT NULL DEFAULT true,
  sort_order int,
  created_at timestamptz DEFAULT now()
);

ALTER TABLE public.stock_pk_models ENABLE ROW LEVEL SECURITY;
CREATE POLICY "stock_pk_models_public_read" ON public.stock_pk_models FOR SELECT TO anon USING (true);

-- ============================================================
-- 13. stock_pk_picks - 股票组合 PK 每期选股结果
-- ============================================================
CREATE TABLE IF NOT EXISTS public.stock_pk_picks (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  model_id text NOT NULL REFERENCES public.stock_pk_models(id),
  period_month text NOT NULL,
  picks jsonb NOT NULL,
  mode text NOT NULL DEFAULT 'rule',
  created_at timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_stock_pk_picks_model_period
  ON public.stock_pk_picks(model_id, period_month);

ALTER TABLE public.stock_pk_picks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "stock_pk_picks_public_read" ON public.stock_pk_picks FOR SELECT TO anon USING (true);
