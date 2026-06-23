<template>
  <div class="page-style-factor">
    <!-- Tab 切换 -->
    <div class="tab-bar">
      <div class="tab-item" :class="{ active: activeTab === 'stock' }" @click="switchTab('stock')">股票风格</div>
      <div class="tab-item" :class="{ active: activeTab === 'bond' }" @click="switchTab('bond')">债券</div>
      <div class="tab-item" :class="{ active: activeTab === 'commodity' }" @click="switchTab('commodity')">商品/宏观</div>
    </div>

    <div class="tab-content">
      <!-- ===== 股票风格 ===== -->
      <template v-if="activeTab === 'stock'">
        <div class="header-bar">
          <span class="data-time">数据截止：{{ dataDate }}</span>
          <span class="refresh-btn" @click="loadStockData">↻ 刷新</span>
        </div>

        <!-- 雷达图 -->
        <div class="card radar-card">
          <div class="card-title">
            Barra 六因子雷达
            <span class="help-icon" @click="showHelp('factorScore')"><SvgIcon name="help" :size="16" class="help-icon-svg" /></span>
          </div>
          <div ref="radarRef" class="radar-chart"></div>
          <p class="radar-hint">越靠外圈=百分位越高=该因子越被高估(性价比差)</p>
        </div>

        <!-- 因子百分位列表 -->
        <div class="card">
          <div class="card-title">因子百分位详情</div>
          <div class="factor-list">
            <div class="factor-item" v-for="f in factors" :key="f.key">
              <div class="factor-header">
                <span class="factor-name">{{ f.name }}</span>
                <span class="factor-en">{{ f.en }}</span>
                <span class="factor-pct" :style="{ color: f.color }">{{ f.percentile != null ? f.percentile + '%' : '--' }}</span>
              </div>
              <div class="factor-bar-wrap">
                <div class="factor-bar">
                  <div class="factor-fill" :style="{ width: barWidth(f.percentile), background: f.color }"></div>
                  <div class="factor-mark-50"></div>
                  <div class="factor-mark-75"></div>
                </div>
                <span class="factor-signal" :style="{ color: f.color }">{{ f.advice }}</span>
              </div>
              <p class="factor-explain">{{ f.explain }}</p>
            </div>
          </div>
        </div>

        <!-- 风格配置建议 -->
        <div class="card">
          <div class="card-title">
            风格配置建议
            <span class="help-icon" @click="showHelp('styleAdvice')"><SvgIcon name="help" :size="16" class="help-icon-svg" /></span>
          </div>
          <div class="advice-list">
            <div class="advice-item" v-for="a in styleAdvice" :key="a.key">
              <div class="advice-style">{{ a.style }}</div>
              <div class="advice-meta">
                <span class="advice-score" :style="{ color: a.color }">{{ a.score != null ? a.score + '%' : '--' }}</span>
                <span class="advice-signal" :style="{ color: a.color }">{{ a.advice }}</span>
                <span class="advice-weight" v-if="a.weight != null">建议权重 {{ a.weight }}%</span>
              </div>
              <p class="advice-desc">{{ a.desc }}</p>
            </div>
          </div>
        </div>
      </template>

      <!-- ===== 债券 ===== -->
      <template v-if="activeTab === 'bond'">
        <div class="header-bar">
          <span class="data-time">{{ bondDate }}</span>
          <span class="refresh-btn" @click="loadBondData">{{ bondLoading ? '加载中...' : '↻ 刷新' }}</span>
        </div>

        <div class="card">
          <div class="card-title">国债收益率曲线 <span class="help-icon" @click="showHelp('bondScore')"><SvgIcon name="help" :size="16" class="help-icon-svg" /></span></div>
          <div class="bond-yield-list">
            <div class="bond-yield-item" v-for="b in bondYields" :key="b.label">
              <span class="by-label">{{ b.label }}</span>
              <span class="by-value">{{ b.yield }}</span>
            </div>
          </div>
          <div class="bond-spread-section" v-if="bondSpreads.length">
            <div class="bs-title">期限利差</div>
            <div class="bs-item" v-for="s in bondSpreads" :key="s.label">
              <span class="bs-label">{{ s.label }}</span>
              <span class="bs-value" :style="{ color: s.color }">{{ s.value }}</span>
              <span class="bs-desc">{{ s.desc }}</span>
            </div>
          </div>
          <p class="trend-note" v-if="bondTrendNote">{{ bondTrendNote }}</p>
        </div>
      </template>

      <!-- ===== 商品/宏观 ===== -->
      <template v-if="activeTab === 'commodity'">
        <div class="header-bar">
          <span class="data-time">{{ cmdDate }}</span>
          <span class="refresh-btn" @click="loadCommodityData">{{ cmdLoading ? '加载中...' : '↻ 刷新' }}</span>
        </div>

        <div class="card">
          <div class="card-title">核心商品价格 <span class="help-icon" @click="showHelp('commodityScore')"><SvgIcon name="help" :size="16" class="help-icon-svg" /></span></div>
          <div class="cmd-grid">
            <div class="cmd-item" v-for="c in cmdPrices" :key="c.label">
              <div class="cmd-label">{{ c.label }}</div>
              <div class="cmd-value">{{ c.value }}</div>
              <div class="cmd-desc">{{ c.desc }}</div>
            </div>
          </div>
        </div>

        <div class="card" v-if="cmdMacro.length">
          <div class="card-title">宏观指标</div>
          <div class="macro-item" v-for="m in cmdMacro" :key="m.label">
            <span class="macro-label">{{ m.label }}</span>
            <span class="macro-value" :style="{ color: m.color }">{{ m.value }}</span>
            <span class="macro-desc">{{ m.desc }}</span>
          </div>
        </div>

        <p class="trend-note" v-if="cmdTrendNote">{{ cmdTrendNote }}</p>
      </template>
    </div>

    <!-- 帮助弹窗 -->
    <div class="help-overlay" v-if="helpKey" @click.self="helpKey = null">
      <div class="help-popup">
        <div class="help-title">{{ helpMap[helpKey]?.title }}</div>
        <div v-for="(sec, i) in helpMap[helpKey]?.sections" :key="i" class="help-section">
          <div class="help-heading">{{ sec.heading }}</div>
          <p v-if="sec.desc" class="help-desc">{{ sec.desc }}</p>
          <div v-if="sec.items" class="help-items">
            <div v-for="(item, j) in sec.items" :key="j" class="help-item-row">
              <span class="hir-label">{{ item.label }}</span>
              <span class="hir-desc">{{ item.desc }}</span>
            </div>
          </div>
        </div>
        <p class="help-footer" v-if="helpMap[helpKey]?.footer">{{ helpMap[helpKey].footer }}</p>
        <div class="help-close" @click="helpKey = null">关闭</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, nextTick, watch } from 'vue'
import echarts from '../../utils/echarts-setup'
import { getIndexQuotes } from '../../utils/market-data'
import { calcFactorScore, getSignalFromPercentile } from '../../utils/calc'
import { fetchValue500All } from '../../utils/api'
import { COLORS, createGovukChart } from '../../utils/echarts-theme'
import SvgIcon from '../../components/SvgIcon.vue'

const activeTab = ref('stock')
const dataDate = ref('--')
const helpKey = ref(null)
const radarRef = ref(null)
let radarChart = null

// 股票风格
const factors = ref([])
const styleAdvice = ref([])

// 债券
const bondLoading = ref(false)
const bondDate = ref('')
const bondYields = ref([])
const bondSpreads = ref([])
const bondTrendNote = ref('')

// 商品
const cmdLoading = ref(false)
const cmdDate = ref('')
const cmdPrices = ref([])
const cmdMacro = ref([])
const cmdTrendNote = ref('')

// 帮助
const helpMap = {
  factorScore: {
    title: '因子评分公式说明',
    sections: [
      { heading: 'Barra六因子性价比评分', desc: '综合评分 = EP×0.25 + Size×0.15 + Growth×0.15 + Momentum×0.15 + Quality×0.15 + Vol×0.15' },
      { heading: '因子含义', items: [
        { label: 'EP(价值)', desc: '沪深300 PE历史百分位' },
        { label: 'Size(规模)', desc: '中证500/沪深300 PE比值' },
        { label: 'Growth(成长)', desc: '中证1000/沪深300 PE比值' },
        { label: 'Momentum(动量)', desc: '沪深300在52周高低区间的位置' },
        { label: 'Quality(质量)', desc: '中证红利/沪深300 超额收益方向' },
        { label: 'Vol(低波)', desc: '上证50/沪深300 超额收益方向' }
      ]},
      { heading: '说明', desc: '因子百分位为近似值，基于实时指数PE和相对强弱推算。' }
    ],
    footer: '数据来源：腾讯行情API + value500.com | 更新：交易日实时'
  },
  styleAdvice: {
    title: '风格配置建议说明',
    sections: [
      { heading: '配置逻辑', desc: '基于Barra六因子性价比，动态分配各风格权重。百分位越低=越低估=权重越高。' },
      { heading: '权重范围', desc: '建议权重范围0~50%，评分≥75超配，25~50标配，<25回避。' }
    ],
    footer: '数据来源：腾讯行情API | 更新：交易日实时'
  },
  bondScore: {
    title: '国债收益率曲线说明',
    sections: [
      { heading: '数据来源', desc: 'value500.com/10Bond.html，中债国债收益率曲线。' },
      { heading: '期限利差', items: [
        { label: '正常陡峭', desc: '长端>短端，经济预期正常' },
        { label: '倒挂/平坦', desc: '长端≤短端，可能预示经济放缓' }
      ]}
    ],
    footer: '数据来源：value500.com | 更新：跟随 value500.com（日度）'
  },
  commodityScore: {
    title: '商品与宏观指标说明',
    sections: [
      { heading: '核心指标', items: [
        { label: 'COMEX黄金', desc: '全球贵金属定价基准' },
        { label: 'NYMEX原油', desc: '全球原油定价基准' },
        { label: '美元指数', desc: '强美元利空商品' },
        { label: 'BDI干散货', desc: '全球散货海运需求' }
      ]},
      { heading: '金油比', desc: 'COMEX黄金÷NYMEX原油。>25避险情绪升温，<20风险偏好上升。' }
    ],
    footer: '数据来源：value500.com | 更新：跟随 value500.com（日度）'
  }
}

function showHelp(key) { helpKey.value = key }

function barWidth(pct) {
  if (pct == null) return '0%'
  return Math.max(2, Math.min(100, pct)) + '%'
}

// ===== 股票风格 =====
async function loadStockData() {
  const [quotes, v500] = await Promise.all([
    getIndexQuotes(),
    fetchValue500All(['pe300']).catch(() => ({}))
  ])
  const pe300 = v500.pe300?.code === 0 ? v500.pe300.data : {}
  const epPercentile = pe300.pePercentile != null ? pe300.pePercentile : null

  const f = calcStyleFactors(quotes, epPercentile)
  factors.value = f
  styleAdvice.value = calcStyleAdvice(f)

  const hs300 = quotes['沪深300'] || quotes['sh000300'] || {}
  const ut = hs300.updateTime || ''
  dataDate.value = ut.length === 14
    ? `${ut.slice(0,4)}-${ut.slice(4,6)}-${ut.slice(6,8)} ${ut.slice(8,10)}:${ut.slice(10,12)}`
    : new Date().toLocaleString('zh-CN')

  await nextTick()
  drawRadar(f)
}

function calcStyleFactors(quotes, epPercentile) {
  const hs300 = quotes['沪深300'] || quotes['sh000300'] || {}
  const zz500 = quotes['中证500'] || quotes['sh000905'] || {}
  const zz1000 = quotes['中证1000'] || quotes['sh000852'] || {}
  const divIdx = quotes['中证红利'] || quotes['sh000922'] || {}
  const sz50 = quotes['上证50'] || quotes['sh000016'] || {}
  const gzValue = quotes['国证价值'] || quotes['sz399371'] || {}
  const gzGrowth = quotes['国证成长'] || quotes['sz399370'] || {}

  const hs300PE = hs300.pe || 0
  const zz500PE = zz500.pe || 0
  const zz1000PE = zz1000.pe || 0

  // Size: 中证500/沪深300 PE比
  let sizePct = null
  if (zz500PE > 0 && hs300PE > 0) {
    const ratio = zz500PE / hs300PE
    sizePct = Math.round(Math.max(0, Math.min(100, (ratio - 1.0) / 2.0 * 100)))
  }

  // Growth: 中证1000/沪深300 PE比
  let growthPct = null
  if (zz1000PE > 0 && hs300PE > 0) {
    const ratio = zz1000PE / hs300PE
    growthPct = Math.round(Math.max(0, Math.min(100, (ratio - 1.0) / 3.0 * 100)))
  }

  // Momentum: 沪深300在52周高低区间的位置
  let momentumPct = null
  if (hs300.price && hs300.high && hs300.low && hs300.low > 0) {
    const range = hs300.high - hs300.low
    if (range > 0) {
      momentumPct = Math.round(Math.max(0, Math.min(100, (hs300.price - hs300.low) / range * 100)))
    }
  }

  // Quality: 中证红利/沪深300 超额收益方向
  let qualityPct = null
  if (divIdx.changePct != null && hs300.changePct != null) {
    const excess = divIdx.changePct - hs300.changePct
    qualityPct = Math.round(Math.max(0, Math.min(100, 50 + excess * 10)))
  }

  // Vol: 上证50/沪深300 超额收益方向
  let volPct = null
  if (sz50.changePct != null && hs300.changePct != null) {
    const excess = sz50.changePct - hs300.changePct
    volPct = Math.round(Math.max(0, Math.min(100, 50 + excess * 10)))
  }

  const raw = [
    { key: 'ep', name: '价值', en: 'EP', percentile: epPercentile, explain: '沪深300 PE在历史中的百分位，高=估值偏高（贵），低=估值偏低（便宜）' },
    { key: 'size', name: '规模', en: 'Size', percentile: sizePct, explain: '中证500/沪深300 PE比，高=小盘估值偏贵，低=小盘估值偏便宜' },
    { key: 'growth', name: '成长', en: 'Growth', percentile: growthPct, explain: '中证1000/沪深300 PE比，高=成长溢价高，低=成长溢价低' },
    { key: 'momentum', name: '动量', en: 'Momentum', percentile: momentumPct, explain: '沪深300在52周高低区间的位置，高=接近高点(偏贵)，低=接近低点(偏便宜)' },
    { key: 'quality', name: '质量', en: 'Quality', percentile: qualityPct, explain: '中证红利/沪深300 超额收益方向，高=质量受追捧' },
    { key: 'vol', name: '波动', en: 'Vol', percentile: volPct, explain: '上证50/沪深300 超额收益方向，高=低波受追捧' }
  ]

  raw.forEach(f => {
    if (f.percentile != null) {
      const sig = getSignalFromPercentile(f.percentile)
      f.score = f.percentile
      f.signal = sig.signal
      f.advice = sig.level
      f.color = sig.color
    } else {
      f.score = null
      f.signal = 'neutral'
      f.advice = '暂无数据'
      f.color = '#8B949E'
    }
  })
  return raw
}

function calcStyleAdvice(factors) {
  const factorValues = {}
  factors.forEach(f => {
    factorValues[f.key] = f.percentile != null ? (100 - f.percentile) : 50
  })
  const totalScore = calcFactorScore(factorValues)

  return [
    { style: '价值风格', key: 'value', factor: factors[0], desc: 'EP(价值)因子驱动，低估值品种受益' },
    { style: '规模风格', key: 'size', factor: factors[1], desc: 'Size(规模)因子驱动，小盘相对大盘强弱' },
    { style: '成长风格', key: 'growth', factor: factors[2], desc: 'Growth(成长)因子驱动，高成长溢价方向' },
    { style: '动量风格', key: 'momentum', factor: factors[3], desc: 'Momentum(动量)因子驱动，趋势延续方向' },
    { style: '质量风格', key: 'quality', factor: factors[4], desc: 'Quality(质量)因子驱动，高ROE高股息方向' },
    { style: '低波风格', key: 'vol', factor: factors[5], desc: 'Vol(低波)因子驱动，低波动稳健方向' }
  ].map(s => {
    if (s.factor?.score != null) {
      return {
        ...s,
        score: s.factor.score,
        signal: s.factor.signal,
        advice: s.factor.advice,
        color: s.factor.color,
        weight: Math.round(Math.max(0, Math.min(50, (100 - s.factor.score - 30) * 1.2)))
      }
    }
    return { ...s, score: null, weight: null, signal: 'neutral', advice: '暂无数据', color: '#8B949E' }
  })
}

function drawRadar(factors) {
  if (!radarRef.value) return
  if (radarChart) radarChart.dispose()

  const indicator = factors.map(f => ({
    name: f.name,
    max: 100
  }))
  const values = factors.map(f => f.percentile != null ? f.percentile : 0)

  const option = {
    color: [COLORS[0]],
    radar: {
      indicator,
      shape: 'polygon',
      splitNumber: 4,
      axisName: { color: '#505a5f', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f8f8f8'] } },
      axisLine: { lineStyle: { color: '#b1b4b6' } }
    },
    series: [{
      type: 'radar',
      data: [{
        value: values,
        name: '因子百分位',
        areaStyle: { color: 'rgba(29,112,184,0.15)' },
        lineStyle: { color: COLORS[0], width: 2 },
        itemStyle: { color: COLORS[0] },
        symbol: 'circle',
        symbolSize: 6
      }]
    }]
  }

  radarChart = echarts.init(radarRef.value)
  radarChart.setOption(option)
}

// ===== 债券 =====
async function loadBondData() {
  bondLoading.value = true
  try {
    const res = await fetchValue500All(['bond'])
    const bd = res.bond?.code === 0 ? res.bond.data : {}
    bondDate.value = bd.date || '--'
    bondYields.value = [
      { label: '1年期', yield: bd.yield1y != null ? (bd.yield1y * 100).toFixed(2) + '%' : '--' },
      { label: '5年期', yield: bd.yield5y != null ? (bd.yield5y * 100).toFixed(2) + '%' : '--' },
      { label: '10年期', yield: bd.yield10y != null ? (bd.yield10y * 100).toFixed(2) + '%' : '--' }
    ]

    const spreads = []
    if (bd.yield10y != null && bd.yield1y != null) {
      const isNormal = bd.yield10y > bd.yield1y
      spreads.push({
        label: '10Y - 1Y',
        value: ((bd.yield10y - bd.yield1y) * 100).toFixed(2) + '%',
        color: isNormal ? '#FF4757' : '#2ED573',
        desc: isNormal ? '正常陡峭' : '倒挂/平坦'
      })
    }
    if (bd.yield5y != null && bd.yield1y != null) {
      spreads.push({
        label: '5Y - 1Y',
        value: ((bd.yield5y - bd.yield1y) * 100).toFixed(2) + '%',
        color: bd.yield5y > bd.yield1y ? '#FF4757' : '#2ED573',
        desc: bd.yield5y > bd.yield1y ? '正常' : '倒挂'
      })
    }
    bondSpreads.value = spreads

    if (bd.yield10y != null) {
      const y10 = (bd.yield10y * 100).toFixed(2)
      if (bd.yield10y < 0.02) bondTrendNote.value = `10Y国债收益率${y10}%，处于历史极低水平，长期债券价格偏高`
      else if (bd.yield10y < 0.025) bondTrendNote.value = `10Y国债收益率${y10}%，处于历史低位，利率下行空间有限`
      else if (bd.yield10y > 0.04) bondTrendNote.value = `10Y国债收益率${y10}%，处于历史中高水平`
      else bondTrendNote.value = `10Y国债收益率${y10}%`
    }
  } catch (e) {
    bondTrendNote.value = '数据加载失败'
  }
  bondLoading.value = false
}

// ===== 商品/宏观 =====
async function loadCommodityData() {
  cmdLoading.value = true
  try {
    const res = await fetchValue500All(['gold', 'usdx', 'bdi', 'ppi', 'pmi'])
    const gd = res.gold?.code === 0 ? res.gold.data : {}
    const ud = res.usdx?.code === 0 ? res.usdx.data : {}
    const bd = res.bdi?.code === 0 ? res.bdi.data : {}
    const pd = res.ppi?.code === 0 ? res.ppi.data : {}
    const md = res.pmi?.code === 0 ? res.pmi.data : {}
    cmdDate.value = gd.date || ud.date || bd.date || pd.date || md.date || '--'

    cmdPrices.value = [
      { label: 'COMEX黄金', value: gd.gold ? '$' + gd.gold.toFixed(1) + '/oz' : '--', desc: gd.gold ? '贵金属龙头' : '' },
      { label: 'NYMEX原油', value: gd.oil ? '$' + gd.oil.toFixed(2) + '/bbl' : '--', desc: gd.oil ? (gd.oil > 80 ? '价格偏高' : gd.oil > 60 ? '中性区间' : '价格偏低') : '' },
      { label: '美元指数', value: (ud.usdx || gd.usdx) ? (ud.usdx || gd.usdx).toFixed(2) : '--', desc: ud.usdxChange != null ? (ud.usdxChange > 0 ? '涨' + ud.usdxChange.toFixed(2) + '%' : '跌' + Math.abs(ud.usdxChange).toFixed(2) + '%') : '' },
      { label: 'BDI干散货', value: bd.bdi ? bd.bdi.toFixed(0) : '--', desc: bd.bdiChange != null ? (bd.bdiChange > 0 ? '涨' + bd.bdiChange.toFixed(2) + '%' : '跌' + Math.abs(bd.bdiChange).toFixed(2) + '%') : '' }
    ]

    const macro = []
    if (pd.ppi != null) macro.push({ label: 'PPI同比', value: pd.ppi.toFixed(1) + '%', color: pd.ppi > 0 ? '#FF5252' : '#2ED573', desc: pd.ppi > 2 ? '工业品通胀偏高' : pd.ppi > 0 ? '温和通胀' : '通缩压力' })
    if (md.mfgPmi != null) macro.push({ label: '制造业PMI', value: md.mfgPmi.toFixed(1), color: md.mfgPmi > 50 ? '#FF5252' : '#2ED573', desc: md.mfgPmi > 50 ? '荣枯线以上·扩张' : '荣枯线以下·收缩' })
    if (md.nonMfgPmi != null) macro.push({ label: '非制造业PMI', value: md.nonMfgPmi.toFixed(1), color: md.nonMfgPmi > 50 ? '#FF5252' : '#2ED573', desc: md.nonMfgPmi > 50 ? '服务业扩张' : '服务业收缩' })
    cmdMacro.value = macro

    if (gd.gold && gd.oil) {
      cmdTrendNote.value = `金油比 ${(gd.gold / gd.oil).toFixed(1)}。>25避险情绪升温，<20风险偏好上升。`
    }
  } catch (e) {
    cmdTrendNote.value = '数据加载失败'
  }
  cmdLoading.value = false
}

function switchTab(tab) {
  activeTab.value = tab
  if (tab === 'stock') loadStockData()
  else if (tab === 'bond') loadBondData()
  else if (tab === 'commodity') loadCommodityData()
}

onMounted(() => {
  loadStockData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  radarChart?.resize()
}
</script>

<style scoped>
/* ========== gov.uk 风格因子分析 ========== */
.page-style-factor { padding-bottom: var(--space-2xl); }
.header-bar { display: flex; justify-content: space-between; padding: var(--space-sm) 0; font-size: 14px; color: var(--text-secondary); border-bottom: 1px solid var(--border); }
.refresh-btn { color: var(--link); cursor: pointer; text-decoration: underline; }

.tab-bar { display: flex; border-bottom: 2px solid var(--border); background: #ffffff; margin-bottom: var(--space-xl); }
.tab-item { flex: 1; text-align: center; padding: var(--space-sm); font-size: 16px; color: var(--link); cursor: pointer; border-bottom: 4px solid transparent; }
.tab-item.active { color: #1d70b8; font-weight: 700; border-bottom-color: #1d70b8; }

.card { background: #ffffff; border: 1px solid var(--border); padding: var(--space-lg); margin-bottom: var(--space-xl); }
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md); }
.help-icon { cursor: pointer; }
.help-icon-svg { display: inline-block; cursor: help; color: var(--text-secondary); vertical-align: middle; }

.radar-card { padding: var(--space-md); }
.radar-chart { width: 100%; height: 320px; }
.radar-hint { text-align: center; font-size: 14px; color: var(--text-secondary); margin-top: var(--space-sm); }

.factor-list { display: flex; flex-direction: column; gap: var(--space-lg); }
.factor-header { display: flex; align-items: baseline; gap: 6px; }
.factor-name { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.factor-en { font-size: 14px; color: var(--text-secondary); }
.factor-pct { margin-left: auto; font-size: 19px; font-weight: 700; }
.factor-bar-wrap { display: flex; align-items: center; gap: var(--space-sm); margin-top: 6px; }
.factor-bar { flex: 1; height: 20px; background: #f3f2f1; position: relative; }
.factor-fill { position: absolute; top: 0; left: 0; height: 100%; transition: width 0.5s; }
.factor-mark-50 { position: absolute; left: 50%; top: 0; width: 1px; height: 100%; background: var(--border); }
.factor-mark-75 { position: absolute; left: 75%; top: 0; width: 1px; height: 100%; background: var(--border); }
.factor-signal { width: 60px; text-align: right; font-size: 14px; font-weight: 700; }
.factor-explain { font-size: 14px; color: var(--text-secondary); margin-top: 4px; }

.advice-list { display: flex; flex-direction: column; gap: var(--space-md); }
.advice-item { padding: var(--space-md); border: 1px solid var(--border); border-left: 5px solid #1d70b8; }
.advice-style { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.advice-meta { display: flex; gap: var(--space-md); margin-top: 4px; font-size: 14px; }
.advice-score { font-weight: 700; }
.advice-weight { color: var(--text-secondary); }
.advice-desc { font-size: 14px; color: var(--text-secondary); margin-top: 4px; }

.bond-yield-list { display: flex; gap: var(--space-lg); }
.bond-yield-item { flex: 1; text-align: center; padding: var(--space-md); border: 1px solid var(--border); }
.by-label { display: block; font-size: 14px; color: var(--text-secondary); }
.by-value { display: block; font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 4px 0; }
.bond-spread-section { margin-top: var(--space-md); padding-top: var(--space-md); border-top: 1px solid var(--border); }
.bs-title { font-size: 16px; font-weight: 700; margin-bottom: var(--space-sm); }
.bs-item { display: flex; align-items: center; gap: var(--space-sm); font-size: 16px; padding: 4px 0; border-bottom: 1px solid var(--border); }
.bs-label { color: var(--text-secondary); min-width: 60px; }
.bs-value { font-weight: 700; }
.bs-desc { color: var(--text-secondary); font-size: 14px; }
.trend-note { font-size: 14px; color: var(--link); margin-top: var(--space-sm); }

.cmd-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-md); }
.cmd-item { text-align: center; padding: var(--space-md); border: 1px solid var(--border); }
.cmd-label { font-size: 14px; color: var(--text-secondary); }
.cmd-value { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 4px 0; }
.cmd-desc { font-size: 14px; color: var(--text-secondary); }
.macro-item { display: flex; align-items: center; gap: var(--space-sm); font-size: 16px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
.macro-label { color: var(--text-secondary); min-width: 80px; }
.macro-value { font-weight: 700; }
.macro-desc { color: var(--text-secondary); font-size: 14px; }

.help-overlay { position: fixed; inset: 0; background: rgba(29,112,184,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; padding: var(--space-lg); }
.help-popup { background: #ffffff; border: 1px solid var(--border); padding: var(--space-xl); max-width: 400px; width: 100%; max-height: 80vh; overflow-y: auto; }
.help-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.help-section { margin-bottom: var(--space-md); }
.help-heading { font-size: 16px; font-weight: 700; color: var(--text-primary); margin-bottom: 4px; }
.help-desc { font-size: 16px; color: var(--text-primary); line-height: 1.6; margin: 0; }
.help-item-row { display: flex; gap: var(--space-sm); font-size: 14px; padding: 2px 0; }
.hir-label { color: var(--link); white-space: nowrap; }
.hir-desc { color: var(--text-secondary); }
.help-footer { font-size: 14px; color: var(--text-secondary); margin-top: var(--space-sm); border-top: 1px solid var(--border); padding-top: var(--space-sm); }
.help-close { margin-top: var(--space-md); text-align: center; color: var(--link); cursor: pointer; font-size: 16px; text-decoration: underline; }
</style>
