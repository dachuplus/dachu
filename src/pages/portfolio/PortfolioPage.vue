<template>
  <div class="page-portfolio">

    <!-- 页面头部 -->
    <div class="section-header">
      <span class="section-title">基金组合构建</span>
      <span class="section-subtitle">权重与"大类资产配置"页面一致，ETF按靠谱指数精选</span>
    </div>

    <!-- 数据状态 -->
    <div class="data-status" v-if="loading">
      <span>正在计算权重...</span>
    </div>
    <div class="data-status" v-else-if="dataDate">
      <span>数据截止：{{ dataDate }}</span>
      <span class="weight-source">{{ weightSource }}</span>
    </div>

    <!-- 组合总览 -->
    <div class="card" v-if="!loading && portfolioItems.length > 0">
      <div class="card-title">当前推荐组合</div>
      <div class="portfolio-overview">
        <div class="po-item" v-for="item in portfolioItems" :key="item.assetKey">
          <div class="po-left">
            <span class="po-icon">{{ ASSET_ICONS[item.assetKey] || '' }}</span>
            <span class="po-name">{{ item.category }}</span>
          </div>
          <div class="po-right">
            <div class="po-bar">
              <div class="po-fill" :style="{ width: item.weight + '%' }"></div>
            </div>
            <span class="po-weight">{{ item.weight }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 各资产ETF明细 -->
    <div class="card" v-for="group in portfolioItems" :key="group.assetKey">
      <div class="card-title">{{ group.category }}（{{ group.weight }}%）</div>
      <div class="etf-list">
        <!-- 加载中 -->
        <div class="etf-loading" v-if="group.loading">
          <span>正在筛选靠谱ETF...</span>
        </div>
        <!-- 现金类提示 -->
        <div class="etf-empty" v-else-if="group.noEtf">
          <span>建议配置货币基金或活期存款，如余额宝、零钱通等</span>
        </div>
        <!-- 无结果 -->
        <div class="etf-empty" v-else-if="group.etfs.length === 0">
          <span>该分类暂无ETF数据</span>
        </div>
        <!-- ETF列表 -->
        <template v-else>
          <div class="etf-item" v-for="etf in group.etfs" :key="etf.code">
            <div class="etf-header">
              <div class="etf-name-wrap">
                <span class="etf-name">{{ etf.name }}</span>
                <span class="etf-code">{{ etf.code }}</span>
              </div>
              <div class="etf-weight-wrap">
                <span class="etf-weight">{{ etf.weight }}%</span>
                <span class="etf-score">靠谱 {{ fmtScore(etf.k3) }}</span>
              </div>
            </div>
            <div class="etf-reason">
              <span>{{ etf.reason }}</span>
              <span v-if="etf.r3y" class="etf-return" :class="etf.r3y > 0 ? 'text-up' : 'text-down'">
                近3年 {{ etf.r3y > 0 ? '+' : '' }}{{ etf.r3y.toFixed(2) }}%
              </span>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 随机抽取分割线 -->
    <div class="divider">
      <div class="divider-line"></div>
      <span class="divider-text">随机抽取ETF</span>
      <div class="divider-line"></div>
    </div>

    <!-- ETF随机抽取 -->
    <div class="card roll-card">
      <div class="roll-btn" :class="{ rolling: isRolling }" @click="rollEtfs">
        <span>{{ isRolling ? '抽取中...' : '随机抽 3 只' }}</span>
      </div>

      <div class="roll-result" v-if="randomEtfs.length > 0">
        <div
          class="roll-etf"
          v-for="(item, index) in randomEtfs"
          :key="item.code + index"
          :style="{ animation: 'fadeInUp 0.3s ease ' + (index * 0.15) + 's both' }"
        >
          <div class="roll-etf-top">
            <span class="roll-rank">#{{ index + 1 }}</span>
            <span class="roll-etf-name">{{ item.name }}</span>
          </div>
          <div class="roll-etf-info">
            <div class="roll-info-item">
              <span class="ri-label">代码</span>
              <span class="ri-value">{{ item.code }}</span>
            </div>
            <div class="roll-info-item">
              <span class="ri-label">类型</span>
              <span class="ri-value">{{ item.category }}</span>
            </div>
            <div class="roll-info-item">
              <span class="ri-label">靠谱分</span>
              <span class="ri-value" :class="scoreColorCls(item.k3)">{{ item.k3 ? item.k3.toFixed(1) : '--' }}</span>
            </div>
            <div class="roll-info-item">
              <span class="ri-label">近3年</span>
              <span class="ri-value" :class="item.r3y > 0 ? 'text-up' : 'text-down'">
                {{ item.r3y != null ? (item.r3y > 0 ? '+' : '') + item.r3y.toFixed(2) + '%' : '--' }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="roll-empty" v-else>
        <span>点击上方按钮开始抽取</span>
      </div>
    </div>

    <!-- 底部声明 -->
    <div class="footer-note">
      <span>权重由 Kan & Zhou 增强型风险平价模型实时计算，与大类资产配置页面一致</span>
      <span>ETF按靠谱指数（3年）从天天基金筛选 | 仅供学习，不构成投资建议</span>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { supabase } from '../../api/supabase'
import { fetchValue500All } from '../../utils/api'
import { getIndexQuotes, buildMarketData } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights } from '../../utils/calc'

// ===== 配置 =====

const ASSET_ICONS = {
  stock: '📈', bond: '🏦', commodity: '📦', gold: '🥇', reit: '🏗️', cash: '💵'
}

const ASSET_ETF_CONFIG = {
  stock:     { category: '股票', t0: 'gp', period: 'k3', count: 3, keyword: 'ETF' },
  bond:      { category: '债券', t0: 'zq', period: 'k3', count: 2, keyword: 'ETF' },
  commodity: { category: '商品', t0: null, period: 'k3', count: 1, keyword: '商品ETF' },
  gold:      { category: '黄金', t0: null, period: 'k3', count: 1, keyword: '黄金' },
  reit:      { category: 'REITs', t0: null, period: 'k3', count: 1, keyword: 'REIT' },
  cash:      { category: '现金', t0: 'hb', period: 'k3', count: 0, noEtf: true }
}

const ETF_POOL = [
  { code: '510300', name: '沪深300ETF', category: '宽基' },
  { code: '159915', name: '创业板ETF', category: '宽基' },
  { code: '510500', name: '中证500ETF', category: '宽基' },
  { code: '159949', name: '创新药ETF', category: '行业' },
  { code: '512100', name: '中证1000ETF', category: '宽基' },
  { code: '159905', name: '深证ETF', category: '宽基' },
  { code: '512880', name: '证券ETF', category: '行业' },
  { code: '512010', name: '医药ETF', category: '行业' },
  { code: '159928', name: '消费ETF', category: '行业' },
  { code: '512170', name: '医疗ETF', category: '行业' },
  { code: '512480', name: '半导体ETF', category: '行业' },
  { code: '159806', name: '新能源车ETF', category: '行业' },
  { code: '512660', name: '军工ETF', category: '行业' },
  { code: '512800', name: '银行ETF', category: '行业' },
  { code: '159919', name: '沪深300ETF(嘉实)', category: '宽基' },
  { code: '510050', name: '上证50ETF', category: '宽基' },
  { code: '159901', name: '深证100ETF', category: '宽基' },
  { code: '512690', name: '酒ETF', category: '行业' },
  { code: '515030', name: '新能源ETF', category: '行业' },
  { code: '512980', name: '传媒ETF', category: '行业' },
  { code: '159922', name: '房地产ETF', category: '行业' },
  { code: '518880', name: '黄金ETF', category: '商品' },
  { code: '159985', name: '豆粕ETF', category: '商品' },
  { code: '511260', name: '10年期国债ETF', category: '债券' },
  { code: '511220', name: '城投债ETF', category: '债券' },
  { code: '508056', name: '中金普洛斯REIT', category: 'REITs' },
  { code: '508000', name: '首钢绿能REIT', category: 'REITs' },
  { code: '180501', name: 'AI智能ETF', category: '行业' },
  { code: '515710', name: '光伏ETF', category: '行业' }
]

// ===== 状态 =====
const loading = ref(true)
const dataDate = ref('')
const weightSource = ref('')
const portfolioItems = ref([])
const randomEtfs = ref([])
const isRolling = ref(false)

// ===== 方法 =====

function fmtScore(val) {
  if (val == null) return '--'
  return val.toFixed(1)
}

function scoreColorCls(val) {
  if (val == null) return ''
  if (val >= 85) return 'score-hot'
  if (val >= 70) return 'score-warm'
  if (val >= 65) return 'score-cyan'
  return 'score-gray'
}

/**
 * 构建基金组合：实时计算权重 + 查询靠谱ETF
 */
async function buildPortfolio() {
  loading.value = true

  try {
    const [quotes, v500] = await Promise.all([
      getIndexQuotes(),
      fetchValue500All()
    ])

    // 解析 value500 数据（与首页完全一致）
    const bondData = v500.bond?.code === 0 ? v500.bond.data : {}
    const shiborData = v500.shibor?.code === 0 ? v500.shibor.data : {}
    const cpiData = v500.cpi?.code === 0 ? v500.cpi.data : {}
    const pe300Data = v500.pe300?.code === 0 ? v500.pe300.data : {}

    const rf = (bondData.yield10y && bondData.yield10y > 0) ? bondData.yield10y : null
    const date = bondData.date || pe300Data.date || ''

    // 构建市场数据
    const marketData = buildMarketData(quotes, { pePercentile: pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null }, {
      yield10y: rf || 0,
      shibor: { on: shiborData.on || 0, date: '' }
    })

    // 计算预期收益率 + 风险平价权重
    const expectedReturns = calcAllExpectedReturns({
      stock: { pe: marketData.stock?.pe || null, pePercentile: marketData.stock?.pePercentile || null },
      bond: { yield10y: rf },
      cash: { shiborOn: marketData.cash?.shiborOn || 0 },
      gold: { yield10y: rf, cpi: cpiData.cpi }
    })
    const rpResult = calcEnhancedRiskParityWeights(expectedReturns, rf, 0.5)
    const weights = rpResult.weights

    // 构建组合骨架
    const assetKeys = ['stock', 'bond', 'commodity', 'gold', 'reit', 'cash']
    const items = []
    for (const key of assetKeys) {
      const cfg = ASSET_ETF_CONFIG[key]
      const w = weights[key] || 0
      if (w > 0) {
        items.push({
          assetKey: key,
          category: cfg.category,
          weight: w,
          etfs: [],
          loading: !cfg.noEtf,
          noEtf: !!cfg.noEtf
        })
      }
    }

    dataDate.value = date
    weightSource.value = 'Kan & Zhou 增强型风险平价（' + date + '）'
    portfolioItems.value = items
    loading.value = false

    // 并行查询各类资产的靠谱ETF
    fetchAllETFs(items, weights)
  } catch (err) {
    console.error('[portfolio] buildPortfolio error:', err)
    loading.value = false
  }
}

/**
 * 从 Supabase 查询各类资产的靠谱ETF
 */
async function fetchAllETFs(items, weights) {
  if (!supabase) {
    // 无 Supabase 连接，直接标记为空
    portfolioItems.value = items.map(item => ({
      ...item,
      loading: false,
      etfs: item.noEtf ? [] : []
    }))
    return
  }

  const promises = items.map(async (item) => {
    if (item.noEtf) return { ...item, loading: false }

    const cfg = ASSET_ETF_CONFIG[item.assetKey]
    const scoreKey = cfg.period // 'k3'

    try {
      // 构建查询
      let query = supabase
        .from('fund_scores')
        .select('c, n, t0, t2, k3, r3y')
        .not(scoreKey, 'is', null)
        .gte(scoreKey, 0)

      if (cfg.t0) {
        // 有 t0 一级分类：按分类 + ETF 关键词
        query = query.eq('t0', cfg.t0).ilike('n', `%${cfg.keyword}%`)
      } else {
        // 无 t0（商品/黄金/REITs）：按关键词搜索
        query = query.ilike('n', `%${cfg.keyword}%`)
      }

      const { data, error } = await query
        .order(scoreKey, { ascending: false, nullsFirst: false })
        .limit(cfg.count)

      if (error) throw error

      const funds = data || []
      const etfs = []
      if (funds.length > 0) {
        const perWeight = Math.round(item.weight / funds.length)
        const used = perWeight * (funds.length - 1)
        const lastWeight = item.weight - used

        funds.forEach((fund, idx) => {
          etfs.push({
            code: fund.c,
            name: fund.n,
            weight: idx === funds.length - 1 ? lastWeight : perWeight,
            k3: fund.k3,
            r3y: fund.r3y,
            t2: fund.t2,
            reason: '靠谱指数(3年) ' + (fund.k3 || 0).toFixed(1)
          })
        })
      }

      return { ...item, etfs, loading: false }
    } catch (err) {
      console.warn('[portfolio] ETF查询失败', item.assetKey, err.message)
      return { ...item, etfs: [], loading: false }
    }
  })

  const results = await Promise.all(promises)
  portfolioItems.value = results
}

/**
 * ETF随机抽取
 */
function rollEtfs() {
  if (isRolling.value) return
  isRolling.value = true

  let count = 0
  const maxRolls = 12

  const interval = setInterval(() => {
    count++
    const shuffled = ETF_POOL.slice().sort(() => Math.random() - 0.5)
    randomEtfs.value = shuffled.slice(0, 3).map(etf => ({
      ...etf,
      k3: null,
      r3y: null
    }))

    if (count >= maxRolls) {
      clearInterval(interval)
      isRolling.value = false
    }
  }, count < maxRolls - 3 ? 100 : 300)
}

onMounted(() => {
  buildPortfolio()
})
</script>

<style scoped>
/* ========== gov.uk 风格基金组合 ========== */
.page-portfolio { padding-bottom: var(--space-2xl); }

.section-header { padding-bottom: var(--space-md); border-bottom: 1px solid var(--border); margin-bottom: var(--space-xl); }
.section-title { font-size: 24px; font-weight: 700; color: var(--text-primary); display: block; }
@media (min-width: 641px) { .section-title { font-size: 36px; } }
.section-subtitle { font-size: 16px; color: var(--text-secondary); display: block; margin-top: var(--space-xs); }

.data-status { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) 0; font-size: 14px; color: var(--text-secondary); }
.weight-source { font-weight: 700; }

.card { background: #ffffff; border: 1px solid var(--border); padding: var(--space-lg); margin-bottom: var(--space-xl); }
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md); }

.portfolio-overview { display: flex; flex-direction: column; gap: var(--space-sm); }
.po-item { display: flex; align-items: center; gap: var(--space-sm); }
.po-left { display: flex; align-items: center; gap: 6px; min-width: 90px; }
.po-icon { font-size: 16px; }
.po-name { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.po-right { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.po-bar { flex: 1; height: 24px; background: #f3f2f1; overflow: hidden; }
.po-fill { height: 100%; background: #1d70b8; transition: width 0.6s ease; }
.po-weight { font-size: 16px; font-weight: 700; min-width: 48px; text-align: right; }

.etf-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.etf-loading, .etf-empty { padding: var(--space-md); text-align: center; font-size: 16px; color: var(--text-secondary); }

.etf-item {
  padding: var(--space-md); border: 1px solid var(--border);
  border-left: 5px solid #1d70b8;
}
.etf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-sm); }
.etf-name-wrap { display: flex; flex-direction: column; }
.etf-name { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.etf-code { font-size: 14px; color: var(--text-secondary); }
.etf-weight-wrap { text-align: right; }
.etf-weight { font-size: 19px; font-weight: 700; display: block; }
.etf-score { font-size: 14px; color: var(--text-secondary); }
.etf-reason {
  font-size: 14px; color: var(--text-secondary); padding-top: var(--space-sm);
  border-top: 1px solid var(--border); display: flex; justify-content: space-between; align-items: center;
}
.etf-return { font-weight: 700; white-space: nowrap; margin-left: var(--space-md); }

.divider { display: flex; align-items: center; gap: var(--space-md); padding: var(--space-xl) 0; }
.divider-line { flex: 1; height: 1px; background: var(--border); }
.divider-text { font-size: 14px; color: var(--text-secondary); white-space: nowrap; }

.roll-card { text-align: center; }
.roll-btn {
  display: inline-flex; align-items: center; justify-content: center;
  padding: var(--space-sm) var(--space-xl);
  background: #00703c; color: #ffffff; font-size: 19px; font-weight: 400;
  margin-bottom: var(--space-lg); cursor: pointer;
  box-shadow: 0 2px 0 #002d18; transition: all 0.15s; user-select: none;
}
.roll-btn:hover { background: #005a30; }
.roll-btn:active { top: 2px; box-shadow: none; }
.roll-btn.rolling { opacity: 0.7; }

.roll-result { display: flex; flex-direction: column; gap: var(--space-sm); }
.roll-etf { padding: var(--space-md); border: 1px solid var(--border); text-align: left; }
.roll-etf-top { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); }
.roll-rank {
  width: 28px; height: 28px; line-height: 28px; text-align: center;
  background: #1d70b8; color: #ffffff; font-size: 14px; font-weight: 700; flex-shrink: 0;
}
.roll-etf-name { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.roll-etf-info { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-sm); }
.roll-info-item { text-align: center; padding: var(--space-sm); border: 1px solid var(--border); }
.ri-label { font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 2px; }
.ri-value { font-size: 14px; font-weight: 700; color: var(--text-primary); }

.text-up { color: var(--color-up); }
.text-down { color: var(--color-down); }
.score-hot  { color: #d4351c; }
.score-warm { color: #f47738; }
.score-cyan { color: #505a5f; }
.score-gray { color: #b1b4b6; }
.roll-empty { padding: var(--space-xl) 0; color: var(--text-secondary); font-size: 16px; }

.footer-note {
  text-align: left; padding: var(--space-xl) 0; font-size: 14px;
  color: var(--text-secondary); border-top: 1px solid var(--border);
}
</style>
