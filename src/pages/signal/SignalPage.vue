<template>
  <div class="page-signal">
    <!-- Header -->
    <div class="header-bar">
      <span class="data-time">数据截止：{{ dataDate }}</span>
      <span class="refresh-btn" @click="loadAll">{{ refreshing ? '加载中...' : '刷新' }}</span>
    </div>

    <!-- Tab 导航 -->
    <div class="signal-tabs">
      <div
        v-for="tab in tabs" :key="tab.key"
        class="signal-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</div>
    </div>

    <!-- 错误提示 -->
    <div class="error-card" v-if="dataError">
      <p>{{ dataError }}</p>
    </div>

    <!-- ==================== 1. 宏观策略 ==================== -->
    <div v-if="activeTab === 'macro'">
      <!-- 隐含夏普仪表盘 -->
      <div class="card" v-if="dashData">
        <div class="card-title">全市场加权平均隐含夏普</div>
        <p class="card-desc">基于风险平价权重加权平均，正值 = 整体有超额收益吸引力</p>
        <div class="gauge-wrap" ref="gaugeRef"></div>
      </div>

      <!-- 宏观指标 6 个 + 10年历史 -->
      <div class="card">
        <div class="card-title">宏观指标（近10年）</div>
        <div class="macro-indicators">
          <div class="macro-item" v-for="m in macroList" :key="m.key">
            <div class="macro-label">{{ m.label }}</div>
            <div class="macro-value">{{ m.value }}</div>
            <div class="macro-date">{{ m.date }}</div>
            <div class="macro-chart-wrap" :class="{ 'macro-chart-expanded': macroExpand[m.key] }">
              <div class="macro-chart" :ref="el => setChartRef(m.key, el)"></div>
            </div>
            <div class="macro-more" v-if="macroHistory[m.key] && macroHistory[m.key].length > MACRO_DEFAULT_WINDOW && !macroExpand[m.key]">
              <span class="more-btn" @click="expandMacroChart(m.key)">更多</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 2. 股债对比 ==================== -->
    <div v-if="activeTab === 'fed'">
      <div class="card">
        <div class="card-title">
          股债性价比
          <span class="card-subtitle">FED Model — 风险溢价指标</span>
        </div>
        <p class="card-desc">股债利差 = 1/PE − 10年期国债收益率，利差越大股票越便宜</p>
        <div class="fed-grid">
          <div class="fed-card" v-for="idx in fedIndices" :key="idx.key">
            <div class="fed-name">{{ idx.name }}</div>
            <div class="fed-spread" :style="{ color: idx.spread > 3 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ idx.spread }}%
            </div>
            <div class="fed-label">股债利差</div>
            <div class="fed-details">
              <div class="fed-row"><span>PE</span><span>{{ idx.pe }}倍</span></div>
              <div class="fed-row"><span>PE百分位</span><span>{{ idx.pePercentile }}%</span></div>
            </div>
          </div>
        </div>
        <p class="data-source">数据参考：funddb.cn | 中国10年期国债收益率 {{ bondY10y }}%</p>
        <!-- FED 历史走势图 -->
        <div class="card-title" style="margin-top:20px">
          股债性价比历史走势（2002—今）
          <span class="card-subtitle">上证指数叠加 10Y 国债收益率 ± 标准差带</span>
        </div>
        <div ref="fedChartRef" style="height:420px"></div>
        <p class="chart-hint" style="margin-top:8px;font-size:12px;color:var(--text-muted)">
          蓝线 = 10Y国债收益率 | 浅蓝带 = ±1σ / ±2σ 标准差 | 灰底 = 上证指数 | 红线 = 当前股债利差参考线
        </p>
      </div>
    </div>

    <!-- ==================== 3. 资产对比 ==================== -->
    <div v-if="activeTab === 'compare'">
      <div class="card">
        <div class="card-title">资产对比 — 隐含夏普 / 预期收益 / 风险溢价</div>
        <p class="card-desc">现金用Shibor，债券用YTM，股票用Gordon模型，黄金用实际利率模型</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>资产</th>
                <th>指标</th>
                <th>隐含夏普</th>
                <th>预期收益</th>
                <th>风险溢价</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in assets" :key="item.key" :class="{ 'row-disabled': !item.hasData }">
                <td class="td-name">{{ item.name }}</td>
                <td>
                  <template v-if="item.isStock">
                    <span>{{ item.metricLabel }}</span>
                    <span class="metric-sub">百分位{{ item.metricSub }}</span>
                  </template>
                  <template v-else>
                    <span :class="metricClass(item.metricLabel)">{{ item.metricLabel }}</span>
                  </template>
                </td>
                <td :style="{ color: item.sharpeColor }">{{ item.sharpeStr }}</td>
                <td :class="item.hasData ? 'text-up' : ''">{{ item.expectedReturn }}</td>
                <td :class="rpClass(item.riskPremium)">{{ item.riskPremium }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- 上证指数历史走势 -->
        <div class="card-title" style="margin-top:20px">上证指数历史走势</div>
        <div ref="compareIdxRef" style="height:200px"></div>
      </div>
    </div>

    <!-- ==================== 4. 资产配比 ==================== -->
    <div v-if="activeTab === 'allocate'">
      <div class="card">
        <div class="card-title">资产配比 — Kan & Zhou 增强型风险平价</div>
        <p class="card-desc">基础权重 × 夏普信号调整，限幅 [0%, 50%]</p>
        <div class="allocate-layout">
          <!-- 饼图 -->
          <div class="pie-section">
            <div class="pie-chart" ref="pieRef"></div>
          </div>
          <!-- 配置明细表 -->
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>资产</th>
                  <th>基础权重</th>
                  <th>调整权重</th>
                  <th>变化</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in weightList" :key="w.key">
                  <td class="td-name">{{ w.name }}</td>
                  <td>{{ w.baseWeight }}%</td>
                  <td class="text-brand">{{ w.weight }}%</td>
                  <td :class="w.weight > w.baseWeight ? 'text-up' : 'text-down'">
                    {{ w.weight > w.baseWeight ? '+' : '' }}{{ (w.weight - w.baseWeight).toFixed(0) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 5. 风格因子 ==================== -->
    <div v-if="activeTab === 'factor'">
      <!-- 子Tab -->
      <div class="sub-tabs">
        <div
          v-for="st in factorSubTabs" :key="st.key"
          class="sub-tab" :class="{ active: factorSub === st.key }"
          @click="switchFactorSub(st.key)"
        >{{ st.label }}</div>
      </div>
      <div v-if="factorSub === 'stock'">
        <div class="card">
          <div class="card-title">Barra 六因子雷达图</div>
          <div class="radar-wrap" ref="radarRef" v-show="factorFactors.length > 0"></div>
          <div class="empty-hint" v-if="factorFactors.length === 0">数据加载中...</div>
        </div>
        <div class="card">
          <div class="card-title">因子百分位详情</div>
          <div class="factor-grid">
            <div class="factor-item" v-for="f in factorFactors" :key="f.name">
              <div class="factor-name">{{ f.name }}</div>
              <div class="factor-bar-wrap">
                <div class="factor-bar">
                  <div class="factor-fill" :style="{ width: f.percentile + '%', background: f.color }"></div>
                </div>
                <span class="factor-val">{{ f.percentile }}%</span>
              </div>
              <div class="factor-signal" :class="f.signal">{{ f.signalLabel }}</div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="factorSub === 'bond'" class="card">
        <div class="card-title">国债收益率曲线</div>
        <div class="chart-wrap" ref="bondCurveRef"></div>
        <div class="card-title" style="margin-top:20px">10Y国债历史走势</div>
        <div class="macro-chart" ref="bondHistRef" style="height:200px"></div>
        <div class="card-title" style="margin-top:20px">期限利差</div>
        <div class="spread-item" v-for="s in bondSpreads" :key="s.label">
          <span>{{ s.label }}</span>
          <span :class="s.bp > 0 ? 'text-up' : 'text-down'">{{ s.bp }}bp</span>
        </div>
      </div>
      <div v-if="factorSub === 'commodity'" class="card">
        <div class="card-title">核心商品价格</div>
        <div class="comm-grid">
          <div class="comm-item" v-for="c in commodityItems" :key="c.label">
            <div class="comm-label">{{ c.label }}</div>
            <div class="comm-value">{{ c.value }}</div>
            <div :class="c.change > 0 ? 'text-up' : 'text-down'">{{ c.change > 0 ? '+' : '' }}{{ c.change }}%</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 6. 行业估值 ==================== -->
    <div v-if="activeTab === 'industry'">
      <div class="card">
        <div class="card-title">指数估值排行</div>
        <div class="filter-row">
          <span
            v-for="f in industryFilters" :key="f.key"
            class="filter-chip" :class="{ active: industryFilter === f.key }"
            @click="industryFilter = f.key"
          >{{ f.label }}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" @click="sortIndustry('name')">名称 {{ sortIcon('name') }}</th>
                <th class="sortable" @click="sortIndustry('pe')">PE {{ sortIcon('pe') }}</th>
                <th class="sortable" @click="sortIndustry('pe_pct')">PE百分位 {{ sortIcon('pe_pct') }}</th>
                <th class="sortable" @click="sortIndustry('pb')">PB {{ sortIcon('pb') }}</th>
                <th class="sortable" @click="sortIndustry('pb_pct')">PB百分位 {{ sortIcon('pb_pct') }}</th>
                <th class="sortable" @click="sortIndustry('div_yield')">股息率 {{ sortIcon('div_yield') }}</th>
                <th class="sortable" @click="sortIndustry('roe')">ROE {{ sortIcon('roe') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in industryList" :key="row.code" @click="toggleIndustryExpand(row)">
                <td>{{ row.name }}</td>
                <td>{{ row.pe }}</td>
                <td :class="row.pe_pct_color">{{ row.pe_pct }}%</td>
                <td>{{ row.pb }}</td>
                <td :class="row.pb_pct_color">{{ row.pb_pct }}%</td>
                <td>{{ row.div_yield }}%</td>
                <td>{{ row.roe }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="data-source">数据来源：蛋卷基金估值中心</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import echarts from '../../utils/echarts-setup'
import { getIndexQuotes, buildMarketData, parseValue500Data } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights, calcMarketSharpe, calcRiskPremium } from '../../utils/calc'
import { fetchValue500All, fetchDanjuanEva } from '../../utils/api'
import { COLORS } from '../../utils/echarts-theme'
import { supabase } from '../../api/supabase'

// ===== Tab 结构 =====
const tabs = [
  { key: 'macro',    label: '宏观策略' },
  { key: 'fed',      label: '股债对比' },
  { key: 'compare',  label: '资产对比' },
  { key: 'allocate', label: '资产配比' },
  { key: 'factor',   label: '风格因子' },
  { key: 'industry', label: '行业估值' },
]
const activeTab = ref('macro')

// ===== 通用状态 =====
const dataDate = ref('--')
const dataError = ref('')
const refreshing = ref(false)

// ===== 宏觀數據 =====
const bondY10y = ref(null)
const dashData = ref(null)

// ===== 资产配置 =====
const ASSET_META = {
  cash:      { name: '现金', color: '#505a5f' },
  bond:      { name: '债券', color: '#1d70b8' },
  stock:     { name: '股票', color: '#d4351c' },
  commodity: { name: '商品', color: '#f47738' },
  gold:      { name: '黄金', color: '#5694ca' },
  reit:      { name: 'REITs', color: '#4c2c92' }
}
const assets = ref([])
const weightList = ref([])

// ===== Macro indicators =====
const macroList = ref([
  { key: 'cn10y',  label: '中国10Y国债', value: '--', date: '', series: [] },
  { key: 'us10y',  label: '美国10Y国债', value: '--', date: '', series: [] },
  { key: 'shibor', label: 'Shibor隔夜', value: '--', date: '', series: [] },
  { key: 'cpi',    label: 'CPI同比', value: '--', date: '', series: [] },
  { key: 'm2',     label: 'M2同比', value: '--', date: '', series: [] },
  { key: 'ppi',    label: 'PPI同比', value: '--', date: '', series: [] }
])
// "更多"展开状态
const macroExpand = reactive({})
const macroHistory = reactive({}) // 完整历史数据缓存
const MACRO_DEFAULT_WINDOW = 250 // dataZoom 默认窗口：250个数据点（约1年日线）

const chartRefs = {}
function setChartRef(key, el) {
  if (el) chartRefs[key] = el
}

// ===== FED 模型 =====
const fedIndices = ref([
  { key: 'hs300', name: '沪深300', spread: '--', pe: '--', pePercentile: '--' },
  { key: 'zz500', name: '中证500', spread: '--', pe: '--', pePercentile: '--' },
  { key: 'zz1000', name: '中证1000', spread: '--', pe: '--', pePercentile: '--' }
])

// ===== 风格因子 =====
const factorSubTabs = [
  { key: 'stock', label: '股票风格' },
  { key: 'bond', label: '债券' },
  { key: 'commodity', label: '商品宏观' }
]
const factorSub = ref('stock')
const factorFactors = ref([])
const bondSpreads = ref([])
const commodityItems = ref([])

// ===== ECharts instances =====
let gaugeChart = null
let pieChart = null
let radarChart = null
let bondCurveChart = null
let fedChart = null
let compareIdxChart = null

// ===== 行业估值 =====
const industryFilters = [
  { key: 'all', label: '全部' },
  { key: 'a_stock', label: 'A股' },
  { key: 'hk_us', label: '港股/海外' }
]
const industryFilter = ref('all')
const industryRaw = ref([])
const industrySort = reactive({ field: 'pe_pct', asc: true })

const filteredIndustry = computed(() => {
  let list = [...industryRaw.value]
  if (industryFilter.value === 'a_stock') {
    list = list.filter(r => r.ttype === 'a_stock')
  } else if (industryFilter.value === 'hk_us') {
    list = list.filter(r => r.ttype === 'hk_us' || r.ttype === 'us')
  }
  const f = industrySort.field
  list.sort((a, b) => {
    const va = a[f]; const vb = b[f]
    if (va == null && vb == null) return 0
    if (va == null) return 1; if (vb == null) return -1
    return industrySort.asc ? va - vb : vb - va
  })
  return list.map(r => ({
    ...r,
    pe_pct_color: r.pe_pct > 70 ? 'text-up' : r.pe_pct < 30 ? 'text-down' : '',
    pb_pct_color: r.pb_pct > 70 ? 'text-up' : r.pb_pct < 30 ? 'text-down' : '',
  }))
})

const industryList = computed(() => filteredIndustry.value.slice(0, 100))

// ===== 工具函数 =====
function metricClass(label) {
  if (!label || label === '--') return ''
  return label[0] === '+' ? 'text-up' : (label[0] === '-' ? 'text-down' : '')
}

function rpClass(val) {
  if (!val || val === '--') return ''
  return val[0] === '+' ? 'text-up' : 'text-down'
}

function sortIndustry(field) {
  if (industrySort.field === field) {
    industrySort.asc = !industrySort.asc
  } else {
    industrySort.field = field
    industrySort.asc = field === 'pe_pct' || field === 'pb_pct'
  }
}

function sortIcon(field) {
  if (industrySort.field !== field) return ''
  return industrySort.asc ? '▲' : '▼'
}

function toggleIndustryExpand(row) {
  // placeholder for expand
}

function switchFactorSub(key) {
  factorSub.value = key
  if (key === 'bond') {
    nextTick(() => drawBondCurve())
  }
}

// ===== 数据加载 =====
async function loadAll() {
  refreshing.value = true
  dataError.value = ''

  try {
    const [quotes, v500] = await Promise.all([
      getIndexQuotes(),
      fetchValue500All()
    ])

    const { bond: bondData, shibor: shiborData, m2: m2Data, cpi: cpiData, ep: epData, pe300: pe300Data, rf, get: v500Get } = parseValue500Data(v500)
    const goldData = v500Get('gold')
    const usdxData = v500Get('usdx')
    const bdiData = v500Get('bdi')
    const ppiData = v500Get('ppi')
    const pmiData = v500Get('pmi')

    // 宏观数据
    bondY10y.value = bondData.yield10y ?? null

    // 更新时间
    const firstQuote = quotes['sh000001'] || quotes['sh000300'] || {}
    const updateTime = firstQuote.updateTime || ''
    dataDate.value = updateTime.length === 14
      ? `${updateTime.slice(0,4)}-${updateTime.slice(4,6)}-${updateTime.slice(6,8)} ${updateTime.slice(8,10)}:${updateTime.slice(10,12)}`
      : new Date().toLocaleString('zh-CN')

    // ===== 从 Supabase macro_history 表获取历史数据 =====
    // 先用 v500 数据构建 macroList，再异步填充 series（不阻塞主流程）
    const v500Values = {
      cn10y:  { value: bondData.yield10y != null ? (bondData.yield10y * 100).toFixed(2) + '%' : '--', date: bondData.date || '' },
      shibor: { value: shiborData.on != null ? (shiborData.on * 100).toFixed(3) + '%' : '--', date: shiborData.date || '' },
      cpi:    { value: cpiData.cpi != null ? (cpiData.cpi * 100).toFixed(1) + '%' : '--', date: cpiData.date || '' },
      m2:     { value: m2Data.m2yoy != null ? m2Data.m2yoy + '%' : '--', date: m2Data.date || '' },
      us10y:  { value: '--', date: '' },
      ppi:    { value: '--', date: '' }
    }
    macroList.value = ['cn10y', 'us10y', 'shibor', 'cpi', 'm2', 'ppi'].map(k => {
      const labels = { cn10y: '中国10Y国债', us10y: '美国10Y国债', shibor: 'Shibor隔夜', cpi: 'CPI同比', m2: 'M2同比', ppi: 'PPI同比' }
      return { key: k, label: labels[k], value: v500Values[k]?.value || '--', date: v500Values[k]?.date || '', series: [] }
    })

    // 异步加载历史数据（不阻塞主流程）
    loadMacroHistoryAsync()

    // 市场数据

    // 市场数据
    const v300Pct = pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null
    const marketData = buildMarketData(quotes, { pePercentile: v300Pct }, {
      yield10y: rf || 0,
      shibor: { on: shiborData.on || 0, date: shiborData.date }
    })

    // 预期收益率
    const erParams = {
      stock: { pe: marketData.stock.pe, pePercentile: marketData.stock.pePercentile },
      bond: { yield10y: rf },
      gold: { yield10y: rf, cpi: cpiData.cpi },
      cash: { shiborOn: marketData.cash.shiborOn || 0 }
    }
    const expectedReturns = calcAllExpectedReturns(erParams)
    const rpResult = calcEnhancedRiskParityWeights(expectedReturns, rf, 0.5)

    // 全市场夏普
    const ms = calcMarketSharpe(rpResult.sharpeMap)
    dashData.value = {
      value: ms != null ? ms : 0,
      label: ms != null ? (ms > 0 ? '市场性价比偏正面' : '市场性价比偏负面') : '无数据'
    }

    // 资产卡片
    const assetKeys = ['cash', 'bond', 'stock', 'commodity', 'gold', 'reit']
    const stockPE = pe300Data.pe || marketData.stock.pe || 0
    const tmpAssets = []
    for (const key of assetKeys) {
      const meta = ASSET_META[key]
      const er = expectedReturns[key]
      const sharpe = rpResult.sharpeMap[key]
      const hasData = er.expectedReturn != null
      let metricLabel = '--', metricSub = ''
      if (key === 'stock') {
        metricLabel = stockPE > 0 ? stockPE.toFixed(2) : '--'
        metricSub = marketData.stock.pePercentile != null ? marketData.stock.pePercentile + '%' : '--'
      } else if (marketData[key]?.changePct) {
        const cp = marketData[key].changePct
        metricLabel = (cp > 0 ? '+' : '') + cp.toFixed(2) + '%'
      }
      tmpAssets.push({
        key, name: meta.name, isStock: key === 'stock',
        metricLabel, metricSub,
        impliedSharpe: sharpe,
        sharpeStr: sharpe != null ? (sharpe > 0 ? '+' : '') + sharpe.toFixed(3) : '--',
        sharpeColor: sharpe != null ? (sharpe > 0 ? 'var(--color-up)' : 'var(--color-down)') : 'var(--text-secondary)',
        expectedReturn: hasData ? (er.expectedReturn * 100).toFixed(2) + '%' : '--',
        riskPremium: hasData && rf != null
          ? (() => { const rp = calcRiskPremium(er.expectedReturn, rf); return rp != null ? (rp > 0 ? '+' : '') + (rp * 100).toFixed(2) + '%' : '--' })()
          : '--',
        hasData
      })
    }
    assets.value = tmpAssets

    // 权重
    const baseWeights = rpResult.baseWeights
    weightList.value = assetKeys.map(key => ({
      key,
      name: ASSET_META[key].name,
      weight: rpResult.weights[key] ? Math.round(rpResult.weights[key] * 100) : 0,
      baseWeight: baseWeights[key] ? Math.round(baseWeights[key] * 100) : 0,
      color: ASSET_META[key].color
    }))

    // 风格因子
    calcStyleFactors(quotes, v300Pct, pe300Data)

    // 债券利差
    bondSpreads.value = bondData.spread != null
      ? [{ label: '10Y-1Y期限利差', bp: bondData.spread }]
      : []

    // 商品数据
    commodityItems.value = [
      { label: '黄金(美元/盎司)', value: goldData.price != null ? '$' + goldData.price : '--', change: goldData.changePct ?? 0 },
      { label: '美元指数', value: usdxData.price != null ? usdxData.price.toFixed(2) : '--', change: usdxData.changePct ?? 0 },
      { label: 'BDI 波罗的海', value: bdiData.price != null ? bdiData.price : '--', change: bdiData.changePct ?? 0 },
      { label: 'PPI 同比', value: ppiData.ppi != null ? ppiData.ppi + '%' : '--', change: 0 },
      { label: 'PMI', value: pmiData.pmi != null ? pmiData.pmi : '--', change: 0 }
    ]

    // FED
    calcFED(quotes, rf)

    // Charts
    await nextTick()
    drawGauge()
    drawMacroCharts()

  } catch (err) {
    let msg = '数据加载失败'
    if (err?.message) msg = err.message.includes('timeout') ? '请求超时' : err.message
    dataError.value = msg
  } finally {
    refreshing.value = false
  }
}

// ===== 风格因子计算 =====
function calcStyleFactors(quotes, v300Pct, pe300Data) {
  const hs300 = quotes['沪深300'] || quotes['sh000300'] || {}
  const sz50 = quotes['上证50'] || quotes['sh000016'] || {}
  const zz500 = quotes['中证500'] || quotes['sh000905'] || {}
  const cyb = quotes['创业板指'] || quotes['sz399006'] || {}
  const zzhl = quotes['中证红利'] || quotes['sh000922'] || {}

  const hs300PE = hs300.pe || 0
  const hs300Pct = v300Pct != null ? v300Pct : 50

  // Helper: estimate percentile from index PE relative to 沪深300 PE, anchored on hs300Pct
  function peToPercentile(idxPE, normalRatio = 1.0) {
    if (!idxPE || idxPE <= 0 || !hs300PE || hs300PE <= 0) return hs300Pct
    // Ratio vs normal: >1 means more expensive relative to normal, so higher percentile
    const currentRatio = idxPE / hs300PE
    const deviation = currentRatio / normalRatio
    // Sigmoid-like mapping: deviation 1.0 → hs300Pct, deviation >1 shifts upward
    let pct = hs300Pct + (deviation - 1) * 80
    return Math.max(5, Math.min(95, Math.round(pct)))
  }

  // Typical PE ratios relative to 沪深300
  const TYPICAL_RATIOS = {
    value:     0.75,  // 中证红利 usually trades at lower PE
    size:      1.30,  // 中证500 usually higher PE
    growth:    1.80,  // 创业板 usually much higher PE
    quality:   0.85,  // 上证50 similar or slightly lower
  }

  const valuePE = zzhl.pe || sz50.pe || 0
  const sizePE = zz500.pe || 0
  const growthPE = cyb.pe || 0
  const qualityPE = sz50.pe || 0

  // Momentum: map changePct to 0-100 scale (typical daily range -3% to +3%)
  const momentumPct = hs300.changePct || 0
  const momentumPercentile = Math.max(5, Math.min(95, Math.round(50 + momentumPct * 15)))

  // Low vol: proxy using 中证500 changePct inverse (less volatile → lower change)
  const zz500Change = zz500.changePct || 0
  const volPercentile = Math.max(5, Math.min(95, Math.round(50 - zz500Change * 10)))

  const factors = [
    { key: 'value',    name: '价值',   percentile: peToPercentile(valuePE, TYPICAL_RATIOS.value) },
    { key: 'size',     name: '规模',   percentile: peToPercentile(sizePE, TYPICAL_RATIOS.size) },
    { key: 'growth',   name: '成长',   percentile: peToPercentile(growthPE, TYPICAL_RATIOS.growth) },
    { key: 'momentum', name: '动量',   percentile: momentumPercentile },
    { key: 'quality',  name: '质量',   percentile: peToPercentile(qualityPE, TYPICAL_RATIOS.quality) },
    { key: 'vol',      name: '低波',   percentile: volPercentile },
  ]

  const results = factors.map(f => {
    const p = f.percentile
    let signal = 'neutral', signalLabel = '中性'
    if (p > 70) { signal = 'hot'; signalLabel = '偏高' }
    else if (p < 30) { signal = 'cold'; signalLabel = '偏低' }
    return {
      name: f.name,
      percentile: p,
      signal, signalLabel,
      color: p > 70 ? 'var(--color-up)' : p < 30 ? 'var(--color-down)' : '#505a5f'
    }
  })
  factorFactors.value = results
  nextTick(() => { drawRadar() })
}

function drawRadar() {
  const el = radarRef()
  if (!el) return
  if (radarChart) radarChart.dispose()
  const indicator = factorFactors.value.map(f => ({ name: f.name, max: 100 }))
  const values = factorFactors.value.map(f => f.percentile)
  radarChart = echarts.init(el)
  radarChart.setOption({
    color: [COLORS[0]],
    radar: {
      indicator, shape: 'polygon', splitNumber: 4,
      axisName: { color: '#505a5f', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f8f8f8'] } },
      axisLine: { lineStyle: { color: '#b1b4b6' } }
    },
    series: [{
      type: 'radar',
      data: [{ value: values, name: '因子百分位',
        areaStyle: { color: 'rgba(29,112,184,0.15)' },
        lineStyle: { color: COLORS[0], width: 2 },
        itemStyle: { color: COLORS[0] }, symbol: 'circle', symbolSize: 6
      }]
    }]
  })
}

function drawBondCurve() {
  const el = bondCurveRef()
  if (!el) return
  if (bondCurveChart) bondCurveChart.dispose()
  bondCurveChart = echarts.init(el)
  bondCurveChart.setOption({
    xAxis: { type: 'category', data: ['1Y','2Y','3Y','5Y','7Y','10Y','30Y'], axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false } },
    yAxis: { type: 'value', name: '%', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false } },
    series: [{ type: 'line', data: [1.5, 1.6, 1.7, 1.9, 2.1, bondY10y.value ? (bondY10y.value * 100).toFixed(1) : 2.3, 2.7], lineStyle: { width: 2, color: COLORS[0] }, symbol: 'circle', symbolSize: 6, itemStyle: { color: COLORS[0] } }]
  })

  // 10Y 国债历史走势（复用 macroHistory 中的 cn10y 数据）
  const histEl = document.querySelector('[ref=bindHistRef]') || document.querySelector('#bond-hist')
  if (histEl && macroHistory['cn10y']) {
    const hdom = histEl.querySelector ? (histEl.querySelector('.macro-chart') || histEl) : histEl
    const hchart = echarts.getInstanceByDom(hdom) || echarts.init(hdom)
    const hist = [...macroHistory['cn10y']].reverse() // ASC
    const dates = hist.map(d => d.date)
    const values = hist.map(d => d.value)
    const total = dates.length
    const defWin = MACRO_DEFAULT_WINDOW
    const useDataZoom = total > defWin
    const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
    const labelStep = Math.max(1, Math.floor(total / 8))
    hchart.setOption({
      grid: { left: 45, right: 10, top: 10, bottom: useDataZoom ? 30 : 15 },
      xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: v => v + '%' } },
      dataZoom: useDataZoom ? [{ type: 'slider', show: true, xAxisIndex: 0, start: startPct, end: 100, height: 18, bottom: 0, borderColor: '#b1b4b6', fillerColor: 'rgba(29,112,184,0.12)', handleStyle: { color: '#1d70b8' }, textStyle: { fontSize: 9, color: '#b1b4b6' } }] : [],
      series: [{ type: 'line', data: values, lineStyle: { width: 1.5, color: COLORS[0] }, symbol: 'none', areaStyle: { color: 'rgba(29,112,184,0.08)' }, smooth: false }],
      tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${p[0].value}%` }
    }, true)
    hchart.resize()
  }
}

// ===== FED 历史图（股债性价比 + 上证指数叠加） =====
async function drawFedChart() {
  const el = document.querySelector('[ref=fedChartRef]')
  if (!el) return
  if (fedChart) { fedChart.dispose(); fedChart = null }

  // 已有缓存则直接绘制
  if (fedSeriesData.value) {
    _renderFedChart(el, fedSeriesData.value)
    return
  }

  // 从 macro_history 拉取数据
  if (!supabase) return
  try {
    const [cn10yRes, idxRes] = await Promise.all([
      supabase.from('macro_history').select('date, value').eq('metric', 'cn10y').order('date', { ascending: true }).limit(10000),
      supabase.from('macro_history').select('date, value').eq('metric', 'sh000001').order('date', { ascending: true }).limit(10000)
    ])
    if (cn10yRes.error || !cn10yRes.data?.length) return

    const cn10yData = cn10yRes.data
    const idxMap = {}
    if (!idxRes.error && idxRes.data) {
      idxRes.data.forEach(d => { idxMap[d.date] = d.value })
    }

    const dates = cn10yData.map(d => d.date)
    const yields = cn10yData.map(d => d.value)
    const indices = cn10yData.map(d => idxMap[d.date] ?? null)

    // 计算均值和标准差（用于绘制带）
    const validYields = yields.filter(v => v != null)
    const n = validYields.length
    const mean = validYields.reduce((a, b) => a + b, 0) / n
    const variance = validYields.reduce((s, v) => s + (v - mean) ** 2, 0) / n
    const std = Math.sqrt(variance)

    // 获取当前股债利差参考线
    const currentSpread = fedIndices.value[0]?.spread !== '--' ? parseFloat(fedIndices.value[0].spread) : null

    const data = { dates, yields, indices, mean, std, currentSpread, validCount: n }
    fedSeriesData.value = data
    _renderFedChart(el, data)
  } catch (err) {
    console.error('[SignalPage] drawFedChart error:', err)
  }
}

// 缓存 FED 数据避免重复拉取
const fedSeriesData = ref(null)

function _renderFedChart(el, data) {
  const { dates, yields, indices, mean, std, currentSpread, validCount } = data
  fedChart = echarts.init(el)

  // 生成标准差带
  const plus1 = yields.map(v => v != null ? mean + std : null)
  const minus1 = yields.map(v => v != null ? mean - std : null)
  const plus2 = yields.map(v => v != null ? mean + 2 * std : null)
  const minus2 = yields.map(v => v != null ? mean - 2 * std : null)

  // 上证指数归一化（对左轴映射到合理范围，取 min/max 归一化到 cn10y 范围附近）
  const validIdx = indices.filter(v => v != null)
  let idxMin = Infinity, idxMax = -Infinity
  if (validIdx.length > 0) {
    idxMin = Math.min(...validIdx)
    idxMax = Math.max(...validIdx)
  }
  // 将指数映射到国债收益率轴范围：scale idx to [mean - 3*std, mean + 3*std]
  const yMin = mean - 3 * std
  const yMax = mean + 3 * std
  const plotRange = yMax - yMin
  const idxNorm = indices.map(v => {
    if (v == null || idxMax === idxMin) return null
    return yMin + ((v - idxMin) / (idxMax - idxMin)) * plotRange
  })

  const useDataZoom = dates.length > 250
  const startPct = useDataZoom ? Math.max(0, Math.round((1 - 500 / dates.length) * 100)) : 0
  const labelStep = Math.max(1, Math.floor(dates.length / 10))

  const option = {
    grid: { left: 60, right: 50, top: 20, bottom: useDataZoom ? 50 : 20 },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: '#b1b4b6' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 10, color: '#505a5f', interval: labelStep - 1 }
    },
    yAxis: {
      type: 'value', name: '收益率 %', nameTextStyle: { fontSize: 10, color: '#505a5f' },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
      axisLine: { show: false },
      axisLabel: { fontSize: 10, color: '#505a5f', formatter: v => v.toFixed(1) + '%' }
    },
    dataZoom: useDataZoom ? [{
      type: 'slider', show: true, xAxisIndex: 0,
      start: startPct, end: 100,
      height: 24, bottom: 6,
      borderColor: '#b1b4b6',
      fillerColor: 'rgba(29,112,184,0.1)',
      handleStyle: { color: '#1d70b8' },
      textStyle: { fontSize: 9, color: '#505a5f' }
    }] : [],
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const p = Array.isArray(params) ? params : [params]
        let html = '<b>' + p[0].axisValue + '</b>'
        for (const item of p) {
          if (item.seriesName === '上证指数(归一化)') {
            // 反归一化显示真实指数值
            const origIdx = indices[item.dataIndex]
            if (origIdx != null) html += `<br/>上证指数: ${origIdx.toFixed(0)}`
          } else if (item.value != null) {
            html += `<br/>${item.seriesName}: ${item.value.toFixed(2)}%`
          }
        }
        return html
      }
    },
    series: [
      // 上证指数背景（灰色填充区域，归一化后）
      {
        name: '上证指数(归一化)', type: 'line', data: idxNorm,
        lineStyle: { width: 0 },
        symbol: 'none',
        areaStyle: { color: 'rgba(180,180,180,0.18)' },
        silent: true, z: 1
      },
      // ±2σ 带
      {
        name: '+2σ', type: 'line', data: plus2,
        lineStyle: { width: 0.5, color: '#e0e0e0', type: 'dashed' },
        symbol: 'none', silent: true, z: 2
      },
      {
        name: '−2σ', type: 'line', data: minus2,
        lineStyle: { width: 0.5, color: '#e0e0e0', type: 'dashed' },
        areaStyle: { color: 'rgba(29,112,184,0.04)' },
        symbol: 'none', silent: true, z: 2
      },
      // ±1σ 带
      {
        name: '+1σ', type: 'line', data: plus1,
        lineStyle: { width: 0.5, color: '#c0c0c0', type: 'dashed' },
        symbol: 'none', silent: true, z: 3
      },
      {
        name: '−1σ', type: 'line', data: minus1,
        lineStyle: { width: 0.5, color: '#c0c0c0', type: 'dashed' },
        areaStyle: { color: 'rgba(29,112,184,0.06)' },
        symbol: 'none', silent: true, z: 3
      },
      // 均值线
      {
        name: '均值', type: 'line',
        data: new Array(dates.length).fill(mean),
        lineStyle: { width: 1, color: '#888', type: 'dotted' },
        symbol: 'none', silent: true, z: 4
      },
      // 10Y国债收益率主曲线
      {
        name: '10Y国债收益率', type: 'line', data: yields,
        lineStyle: { width: 2, color: '#1d70b8' },
        areaStyle: { color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(29,112,184,0.15)' }, { offset: 1, color: 'rgba(29,112,184,0.02)' }]
        }},
        symbol: 'none', smooth: false, z: 5
      },
      // 当前股债利差参考线
      ...(currentSpread != null ? [{
        name: `当前股债利差 ${currentSpread.toFixed(2)}%`,
        type: 'line',
        data: new Array(dates.length).fill(null),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#d4351c', width: 2, type: 'dashed' },
          label: { fontSize: 10, color: '#d4351c', formatter: `股债利差 ${currentSpread.toFixed(2)}%` },
          data: [{ yAxis: mean, name: '参考' }]
        },
        z: 6
      }] : [])
    ]
  }

  fedChart.setOption(option)
  fedChart.resize()
}

// ===== 资产对比 上证指数历史图 =====
function drawCompareIdxChart() {
  const el = document.querySelector('[ref=compareIdxRef]')
  if (!el) return
  // 从 macroHistory 中查 上证指数
  supabase.from('macro_history')
    .select('date, value')
    .eq('metric', 'sh000001')
    .order('date', { ascending: false })
    .limit(7000)
    .then(({ data }) => {
      if (!data || data.length === 0) return
      drawMiniHistoryChart(el, data.map(d => ({ date: d.date, value: d.value })), '上证指数', false)
    })
}

// ===== 通用迷你历史图表 =====
function drawMiniHistoryChart(el, rawData, label, isPercent = true) {
  const dom = el.querySelector ? (el.querySelector('.macro-chart') || el) : el
  const chart = echarts.getInstanceByDom(dom) || echarts.init(dom)
  const hist = [...rawData].reverse() // ASC
  const dates = hist.map(d => d.date)
  const values = hist.map(d => d.value)
  const total = dates.length
  const defWin = MACRO_DEFAULT_WINDOW
  const useDataZoom = total > defWin
  const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
  const labelStep = Math.max(1, Math.floor(total / 8))
  const yFormatter = isPercent ? (v => v + '%') : (v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0))

  chart.setOption({
    grid: { left: 55, right: 10, top: 10, bottom: useDataZoom ? 30 : 15 },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: yFormatter } },
    dataZoom: useDataZoom ? [{ type: 'slider', show: true, xAxisIndex: 0, start: startPct, end: 100, height: 18, bottom: 0, borderColor: '#b1b4b6', fillerColor: 'rgba(29,112,184,0.12)', handleStyle: { color: '#1d70b8' }, textStyle: { fontSize: 9, color: '#b1b4b6' } }] : [],
    series: [{ type: 'line', data: values, lineStyle: { width: 1.5, color: COLORS[0] }, symbol: 'none', areaStyle: { color: 'rgba(29,112,184,0.08)' }, smooth: false }],
    tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${label}: ${isPercent ? p[0].value + '%' : p[0].value}` }
  }, true)
  chart.resize()
}

// ===== 仪表盘 =====
function drawGauge() {
  const el = gaugeRef()
  if (!el) return
  if (gaugeChart) gaugeChart.dispose()
  if (!dashData.value) return
  gaugeChart = echarts.init(el)
  const val = Math.max(-1, Math.min(1, dashData.value.value))
  gaugeChart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 210, endAngle: -30,
      min: -1, max: 1,
      center: ['50%', '55%'],
      radius: '85%',
      axisLine: {
        show: true,
        lineStyle: {
          width: 18,
          color: [[0.25, '#d4351c'], [0.5, '#f47738'], [0.75, '#b1b4b6'], [1, '#00703c']]
        }
      },
      pointer: { length: '65%', width: 5, itemStyle: { color: '#0b0c0c' } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        formatter: '{value}',
        fontSize: 36, fontWeight: 700,
        offsetCenter: [0, '65%'],
        color: val > 0 ? '#d4351c' : '#00703c'
      },
      data: [{ value: +val.toFixed(3), name: '隐含夏普' }]
    }]
  })
}

function gaugeRef() { return document.querySelector('[ref=gaugeRef]') }
function pieRef() { return document.querySelector('[ref=pieRef]') }
function radarRef() { return document.querySelector('[ref=radarRef]') }
function bondCurveRef() { return document.querySelector('[ref=bondCurveRef]') }

// ===== 宏观历史数据加载 =====
const macroMetricMap = {
  cn10y: 'cn10y', us10y: 'us10y', shibor: 'shibor_on',
  cpi: 'cpi', m2: 'm2_growth', ppi: 'ppi'
}

async function loadMacroHistoryAsync() {
  if (!supabase) return
  try {
    // 1. 拉取上证指数历史（用于所有图表叠加）
    const indexPromise = supabase
      .from('macro_history')
      .select('date, value')
      .eq('metric', 'sh000001')
      .order('date', { ascending: false })
      .limit(10000)

    // 2. 拉取六个宏观指标历史
    const macroPromises = macroList.value.map(async (m) => {
      const metric = macroMetricMap[m.key]
      if (!metric) return { key: m.key, data: null }
      const { data, error } = await supabase
        .from('macro_history')
        .select('date, value')
        .eq('metric', metric)
        .order('date', { ascending: false })
        .limit(10000)
      if (error) { console.warn('macro_history query error:', m.key, error); return { key: m.key, data: null } }
      return { key: m.key, data }
    })

    // 3. 同时等待所有请求
    const [indexResult, ...macroResults] = await Promise.all([
      indexPromise,
      ...macroPromises
    ])

    // 4. 构建上证指数日期索引（date → value）
    const indexMap = {}
    if (!indexResult.error && indexResult.data) {
      indexResult.data.forEach(d => { indexMap[d.date] = d.value })
    }

    // 5. 处理每个宏观指标
    macroResults.forEach(r => {
      const { key, data } = r
      if (!data || data.length === 0) return
      // 更新最新值（us10y / ppi 没有 v500 数据源）
      if ((key === 'us10y' || key === 'ppi') && data[0]) {
        const item = macroList.value.find(x => x.key === key)
        if (item && item.value === '--') {
          item.value = data[0].value.toFixed(2) + '%'
          item.date = data[0].date
        }
      }
      // 存储完整历史（保持 DESC 顺序）
      macroHistory[key] = data.map(d => ({
        date: d.date, value: d.value,
        index: indexMap[d.date] ?? null  // 对齐上证指数
      }))
      // 初始显示：所有数据 ASC 排序，默认窗口展示最近 MACRO_DEFAULT_WINDOW 条
      const asc = [...data].reverse()
      const item = macroList.value.find(x => x.key === key)
      if (item) {
        item.series = {
          dates: asc.map(d => d.date),
          values: asc.map(d => d.value),
          indices: asc.map(d => indexMap[d.date] ?? null),
          total: data.length,
          expanded: false,
          defaultWindow: MACRO_DEFAULT_WINDOW
        }
      }
    })

    await nextTick()
    drawMacroCharts()
  } catch (e) {
    console.warn('loadMacroHistoryAsync error:', e)
  }
}

function expandMacroChart(key) {
  macroExpand[key] = true
  const history = macroHistory[key]
  const item = macroList.value.find(m => m.key === key)
  if (!item || !history) return
  // 展开全部历史数据：history 是 DESC，图表需 ASC（旧→新）
  const asc = [...history].reverse()
  item.series = {
    dates: asc.map(d => d.date),
    values: asc.map(d => d.value),
    indices: asc.map(d => d.index),
    total: asc.length,
    expanded: true,
    defaultWindow: MACRO_DEFAULT_WINDOW
  }
  nextTick(() => drawMacroCharts())
}

// ===== 宏观图表 =====
function drawMacroCharts() {
  macroList.value.forEach(m => {
    const el = chartRefs[m.key]
    if (!el) return
    const dom = el.querySelector ? el.querySelector('.macro-chart') || el : el
    if (!dom) return
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom)
    const sd = m.series || {}
    const dates = sd.dates || []
    const values = sd.values || []
    const indices = sd.indices || []
    const total = sd.total || dates.length
    const defWin = sd.defaultWindow || MACRO_DEFAULT_WINDOW

    // dataZoom：始终显示，默认窗口展示最近 defWin 个数据点
    const useDataZoom = total > defWin
    const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
    const dataZoomConfig = useDataZoom ? [{
      type: 'slider',
      show: true,
      xAxisIndex: 0,
      start: startPct,
      end: 100,
      height: 18,
      bottom: 0,
      handleSize: '80%',
      borderColor: '#b1b4b6',
      fillerColor: 'rgba(29,112,184,0.12)',
      handleStyle: { color: '#1d70b8' },
      textStyle: { fontSize: 9, color: '#b1b4b6' }
    }] : []

    // 上证指数叠加：仅当有有效 index 数据时
    const hasIndex = indices && indices.some(v => v != null)
    const indexValid = hasIndex ? indices.map(v => (v != null) ? v : '-') : []

    const bottomPad = useDataZoom ? 30 : 15
    const labelStep = Math.max(1, Math.floor(dates.length / 8))

    const tooltipFormatter = hasIndex
      ? (params) => `${params[0].axisValue}<br/>${m.label}: ${params[0].value}%<br/>上证指数: ${params[1]?.value ?? '--'}`
      : (params) => `${params[0].axisValue}<br/>${params[0].value}%`

    chart.setOption({
      grid: { left: 45, right: hasIndex ? 50 : 10, top: 10, bottom: bottomPad },
      xAxis: {
        type: 'category', data: dates, show: true,
        axisLine: { lineStyle: { color: '#b1b4b6' } },
        axisTick: { show: false },
        axisLabel: { show: true, fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 }
      },
      yAxis: [
        {
          type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } },
          axisLine: { show: false },
          axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: v => v + '%' }
        },
        ...(hasIndex ? [{
          type: 'value',
          axisLine: { show: false },
          axisLabel: { fontSize: 9, color: '#d4351c' },
          splitLine: { show: false }
        }] : [])
      ],
      dataZoom: dataZoomConfig,
      series: [
        {
          name: m.label,
          type: 'line', data: values,
          lineStyle: { width: 1.5, color: COLORS[0] },
          symbol: 'none',
          areaStyle: { color: 'rgba(29,112,184,0.08)' },
          smooth: false
        },
        ...(hasIndex ? [{
          name: '上证指数',
          type: 'line', data: indexValid,
          yAxisIndex: 1,
          lineStyle: { width: 1, color: '#d4351c', type: 'dashed' },
          symbol: 'none',
          smooth: false
        }] : [])
      ],
      tooltip: { trigger: 'axis', formatter: tooltipFormatter },
      legend: hasIndex ? { show: true, bottom: 0, data: [m.label, '上证指数'], textStyle: { fontSize: 10 } } : undefined
    }, true)
    chart.resize()
  })
}

// ===== FED 计算 =====
function calcFED(quotes, rf) {
  const indices = [
    { key: 'hs300', code: 'sh000300', name: '沪深300' },
    { key: 'zz500', code: 'sh000905', name: '中证500' },
    { key: 'zz1000', code: 'sh000852', name: '中证1000' },
  ]
  const results = indices.map(idx => {
    const q = quotes[idx.code]
    const pe = q?.pe || 0
    const pePct = q?.pePercentile || 0
    const spread = rf ? ((1 / pe) - rf) * 100 : 0
    return {
      key: idx.key, name: idx.name,
      spread: spread > 0 ? spread.toFixed(2) : '--',
      pe: pe > 0 ? pe.toFixed(2) : '--',
      pePercentile: pePct > 0 ? pePct.toFixed(0) : '--'
    }
  })
  fedIndices.value = results
}

// ===== 加载行业估值 =====
async function loadIndustry() {
  try {
    const result = await fetchDanjuanEva()
    if (result?.code === 0 && Array.isArray(result.data)) {
      industryRaw.value = result.data.map(r => ({
        ...r,
        pe_pct: r.pe_percentile != null ? parseFloat(r.pe_percentile) : null,
        pb_pct: r.pb_percentile != null ? parseFloat(r.pb_percentile) : null,
      }))
    }
  } catch (e) {
    console.error('行业估值加载失败', e)
  }
}

// ===== 资产配比饼图 =====
function drawPie() {
  const el = pieRef()
  if (!el || weightList.value.length === 0) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(el)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}%', fontSize: 12 },
      data: weightList.value.map(w => ({ name: w.name, value: w.weight, itemStyle: { color: w.color } }))
    }]
  })
}

// ===== 切换 tab 时初始化图表 =====
watch(activeTab, (tab) => {
  nextTick(() => {
    if (tab === 'macro') { drawGauge(); drawMacroCharts() }
    else if (tab === 'fed') drawFedChart()
    else if (tab === 'compare') drawCompareIdxChart()
    else if (tab === 'allocate') drawPie()
    else if (tab === 'factor') {
      if (factorSub.value === 'stock') drawRadar()
      else if (factorSub.value === 'bond') drawBondCurve()
    }
    else if (tab === 'industry') {
      if (industryRaw.value.length === 0) loadIndustry()
    }
  })
})

onMounted(() => {
  const route = useRoute()
  const tabFromQuery = route.query.tab
  if (tabFromQuery && tabs.some(t => t.key === tabFromQuery)) {
    activeTab.value = tabFromQuery
  }
  loadAll()

  // 窗口 resize 时自动调整图表大小
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  const charts = [gaugeChart, pieChart, radarChart, bondCurveChart, fedHistChart, compareIdxChart]
  charts.forEach(c => c?.resize())
  Object.values(chartRefs).forEach(el => {
    const instance = echarts.getInstanceByDom(el)
    if (instance) instance.resize()
  })
}
</script>

<style scoped>
/* ========== gov.uk 蓝白灰 指标信号页 ========== */
.page-signal { padding-bottom: var(--space-2xl); }

.header-bar {
  display: flex; justify-content: space-between; padding: var(--space-sm) 0;
  font-size: 14px; color: var(--text-secondary); border-bottom: 1px solid var(--border);
}
.refresh-btn { color: var(--link); cursor: pointer; text-decoration: underline; }

/* Tab 导航 */
.signal-tabs {
  display: flex; gap: 0; border-bottom: 2px solid var(--border);
  margin: var(--space-md) 0 var(--space-lg); overflow-x: auto;
}
.signal-tab {
  padding: var(--space-sm) var(--space-md); font-size: 16px; font-weight: 700;
  color: var(--text-secondary); cursor: pointer; white-space: nowrap;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}
.signal-tab.active {
  color: #1d70b8; border-bottom-color: #1d70b8;
}
.signal-tab:hover { color: var(--text-primary); }

/* 子 Tab */
.sub-tabs { display: flex; gap: var(--space-md); border-bottom: 2px solid var(--border); margin-bottom: var(--space-lg); }
.sub-tab { padding: var(--space-xs) var(--space-sm); font-size: 14px; font-weight: 700; color: var(--text-secondary); cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; }
.sub-tab.active { color: #1d70b8; border-bottom-color: #1d70b8; }

/* 卡片 */
.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); }
.card-subtitle { font-size: 14px; color: var(--text-secondary); margin-left: 6px; font-weight: 400; }
.card-desc { font-size: 14px; color: var(--text-secondary); margin-bottom: var(--space-md); }
.error-card { border-left: 5px solid #d4351c; padding: var(--space-md); margin-bottom: var(--space-xl); background: #fff; }
.error-card p { margin: 0; font-size: 16px; color: #d4351c; }

/* 仪表盘 */
.gauge-wrap { width: 100%; height: 280px; }

/* 宏观指标 */
.macro-indicators { display: flex; flex-direction: column; gap: var(--space-lg); }
.macro-item { border: 1px solid var(--border); padding: var(--space-md); }
.macro-label { font-size: 14px; color: var(--text-secondary); }
.macro-value { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: var(--space-xs) 0; }
.macro-date { font-size: 12px; color: var(--text-secondary); margin-bottom: var(--space-sm); }
.macro-chart-wrap { width: 100%; height: 200px; overflow: hidden; }
.macro-chart-wrap.macro-chart-expanded { height: 200px; overflow: visible; }
.macro-chart { width: 100%; height: 200px; }
.macro-more { text-align: center; margin-top: var(--space-sm); }
.more-btn {
  display: inline-block; padding: var(--space-xs) var(--space-lg); font-size: 13px;
  color: var(--brand); border: 1px solid var(--brand); background: var(--bg-card);
  cursor: pointer; text-decoration: none; user-select: none;
}
.more-btn:hover { background: var(--brand); color: #fff; }

/* FED */
.fed-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-md); }
.fed-card { border: 1px solid var(--border); padding: var(--space-md); text-align: center; }
.fed-name { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-xs); }
.fed-spread { font-size: 28px; font-weight: 700; }
.fed-label { font-size: 12px; color: var(--text-secondary); margin: var(--space-xs) 0; }
.fed-details { margin-top: var(--space-sm); }
.fed-row { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.fed-row span:first-child { color: var(--text-secondary); }

/* 表格 */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th { text-align: left; padding: var(--space-sm); color: var(--text-secondary); border-bottom: 2px solid var(--border); font-weight: 700; white-space: nowrap; }
.data-table td { padding: var(--space-sm); color: var(--text-primary); border-bottom: 1px solid var(--border); white-space: nowrap; }
.td-name { font-weight: 700; }
.metric-sub { display: block; font-size: 12px; color: var(--text-secondary); }
.row-disabled { opacity: 0.4; }
.text-brand { color: #1d70b8 !important; font-weight: 700; }

/* 分配布局 */
.allocate-layout { display: flex; flex-direction: column; gap: var(--space-lg); }
@media (min-width: 769px) {
  .allocate-layout { flex-direction: row; }
  .allocate-layout .pie-section { flex: 0 0 320px; }
  .allocate-layout .table-wrap { flex: 1; }
}
.pie-section { display: flex; align-items: center; justify-content: center; }
.pie-chart { width: 100%; height: 280px; }

/* 雷达 */
.radar-wrap { width: 100%; height: 320px; }
.empty-hint { text-align: center; color: var(--text-secondary); padding: var(--space-xl); }

/* 因子 */
.factor-grid { display: flex; flex-direction: column; gap: var(--space-sm); }
.factor-item { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
.factor-name { width: 50px; font-size: 14px; font-weight: 700; color: var(--text-primary); }
.factor-bar-wrap { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.factor-bar { flex: 1; height: 16px; background: #f3f2f1; }
.factor-fill { height: 100%; transition: width 0.5s ease; }
.factor-val { width: 40px; font-size: 13px; text-align: right; font-weight: 700; }
.factor-signal { width: 40px; font-size: 12px; text-align: center; padding: 1px 4px; }
.factor-signal.hot { color: var(--color-up); }
.factor-signal.cold { color: var(--color-down); }

/* 利差 */
.spread-item { display: flex; justify-content: space-between; padding: var(--space-sm) 0; border-bottom: 1px solid var(--border); font-size: 16px; }
.chart-wrap { width: 100%; height: 250px; }

/* 商品 */
.comm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }
.comm-item { border: 1px solid var(--border); padding: var(--space-md); text-align: center; }
.comm-label { font-size: 14px; color: var(--text-secondary); }
.comm-value { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: var(--space-xs) 0; }

/* 筛选 */
.filter-row { display: flex; gap: var(--space-md); margin-bottom: var(--space-md); padding-bottom: var(--space-sm); border-bottom: 1px solid var(--border); }
.filter-chip { font-size: 14px; color: var(--text-secondary); cursor: pointer; padding: 2px 0; border-bottom: 2px solid transparent; }
.filter-chip.active { color: #1d70b8; border-bottom-color: #1d70b8; font-weight: 700; }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: #1d70b8; }

.data-source { font-size: 12px; color: var(--text-secondary); margin-top: var(--space-sm); }
.text-up { color: var(--color-up) !important; }
.text-down { color: var(--color-down) !important; }

/* ===== 移动端适配 ===== */
@media (max-width: 768px) {
  .fed-grid { grid-template-columns: repeat(1, 1fr); }
  .comm-grid { grid-template-columns: repeat(1, 1fr); }
  .macro-indicators { grid-template-columns: repeat(1, 1fr); }
  .macro-chart-wrap { height: 160px; }
  .macro-chart { height: 160px; }
  .gauge-wrap { height: 240px; }
  .pie-chart { height: 240px; }
  .radar-wrap { height: 280px; }
  .chart-wrap { height: 200px; }
  .allocate-layout { flex-direction: column; }
}
</style>
