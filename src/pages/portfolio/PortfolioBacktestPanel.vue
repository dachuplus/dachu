<template>
  <div class="pbp-wrap">
    <!-- 头部 -->
    <div class="pbp-head">
      <div class="pbp-title">组合收益跟踪 · 回测</div>
      <div class="pbp-select">
        <label for="pbp-sel">选择组合</label>
        <select id="pbp-sel" v-model="selectedId" :disabled="!portfolios.length">
          <option v-for="p in portfolios" :key="p.id" :value="p.id">{{ p.name }}</option>
        </select>
      </div>
    </div>

    <!-- 说明 -->
    <p class="pbp-note">
      说明：曲线为<strong>近似</strong>回测。fund_scores 仅提供各周期收益率（r1m/r3m/r6m/r1y/r3y/r5y），
      无法获得真实净值序列；此处用相邻周期收益率链式相乘还原累计收益走势，仅供横向参考。
    </p>

    <!-- 空态 -->
    <div class="pbp-empty" v-if="!portfolios.length">
      还没有组合，先去「自建组合」创建一个吧
    </div>

    <!-- 加载 -->
    <div class="pbp-loading" v-else-if="loading">加载中…</div>

    <!-- 内容 -->
    <template v-else>
      <!-- 摘要卡 -->
      <div class="pbp-cards">
        <div class="pbp-card">
          <div class="pbp-card-label">组合期末累计收益</div>
          <div class="pbp-card-value" :class="trendCls(portFinal)">{{ pct(portFinal) }}</div>
          <div class="pbp-card-sub">约 {{ usedWeightPct }}% 仓位参与回测</div>
        </div>
        <div class="pbp-card">
          <div class="pbp-card-label">等权基准累计收益</div>
          <div class="pbp-card-value" :class="trendCls(benchFinal)">{{ pct(benchFinal) }}</div>
          <div class="pbp-card-sub">同等权重平均（不含个股比重）</div>
        </div>
        <div class="pbp-card">
          <div class="pbp-card-label">近似最大回撤</div>
          <div class="pbp-card-value pbp-down">{{ pct(-maxDD) }}</div>
          <div class="pbp-card-sub">自曲线谷底估算</div>
        </div>
      </div>

      <!-- 图表 -->
      <div class="pbp-chart" ref="chartEl"></div>

      <!-- 持仓明细 -->
      <div class="pbp-hold-wrap" v-if="holdRows.length">
        <div class="pbp-hold-title">回测成分（已匹配 {{ holdRows.length }} 只）</div>
        <table class="pbp-hold-table">
          <thead>
            <tr><th>基金</th><th>代码</th><th class="pbp-num">权重</th><th class="pbp-num">5年</th><th class="pbp-num">1年</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in holdRows" :key="r.code">
              <td>{{ r.name }}</td>
              <td>{{ r.code }}</td>
              <td class="pbp-num">{{ r.weightPct }}%</td>
              <td class="pbp-num" :class="trendCls(r.r5y)">{{ pct(r.r5y) }}</td>
              <td class="pbp-num" :class="trendCls(r.r1y)">{{ pct(r.r1y) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pbp-nomatch" v-if="holdRows.length === 0 && selectedPortfolio">
        该组合持仓未匹配到 fund_scores 数据，无法回测
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onBeforeUnmount, nextTick } from 'vue'
import { supabase } from '../../api/supabase'
import { useAuth } from '../../composables/useAuth'
import echarts from '../../utils/echarts-setup'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { createGovukChart } from '../../utils/echarts-theme'

// 注册本组件所需的图表类型（不改动共享的 echarts-setup.js）
echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent])

const { portfolios } = useAuth()

// ---- 状态 ----
const selectedId = ref(null)
const loading = ref(false)
const portCurve = ref([])      // 组合累计收益序列（%，近似）
const benchCurve = ref([])     // 等权基准累计收益序列（%）
const holdRows = ref([])       // 参与回测的持仓明细
const usedWeightPct = ref(0)   // 实际参与回测的权重合计（%）

// 曲线采样点：5年前 → 今（近似月份轴）
const POINTS = [
  { label: '5年前', months: 60 },
  { label: '3年前', months: 36 },
  { label: '1年前', months: 12 },
  { label: '6月前', months: 6 },
  { label: '3月前', months: 3 },
  { label: '1月前', months: 1 },
  { label: '今', months: 0 },
]
// 相邻周期之间的分段（用于链式相乘还原累计收益）
// 第 6 段为最近 1 个月，收益 = r1m
const SEGMENTS = [
  { from: 'r5y', to: 'r3y' },
  { from: 'r3y', to: 'r1y' },
  { from: 'r1y', to: 'r6m' },
  { from: 'r6m', to: 'r3m' },
  { from: 'r3m', to: 'r1m' },
  { from: 'r1m', to: null },
]

const selectedPortfolio = computed(
  () => portfolios.find(p => p.id === selectedId.value) || portfolios[0] || null
)

// ---- 工具函数 ----
function trendCls(v) {
  if (v > 0) return 'pbp-up'
  if (v < 0) return 'pbp-down'
  return ''
}
function pct(v) {
  if (v == null || isNaN(v)) return '—'
  const s = v > 0 ? '+' : ''
  return `${s}${v.toFixed(2)}%`
}
function parseWeight(w) {
  if (typeof w === 'string') {
    const n = parseFloat(w.replace('%', ''))
    return isNaN(n) ? 0 : n / 100
  }
  if (typeof w === 'number') {
    return w > 1 ? w / 100 : w   // 0-1 视作小数；大于 1 视作百分比
  }
  return 0
}

// 由某基金的各周期收益率，导出分段收益率（小数）
function segReturns(p) {
  const f = k => (typeof p[k] === 'number' ? p[k] : 0) / 100
  const r5 = f('r5y'), r3 = f('r3y'), r1 = f('r1y'),
        r6 = f('r6m'), r3m = f('r3m'), r1m = f('r1m')
  // 相邻周期收益率链式相除，得到各分段收益；乘积恒等于 (1+r5y)
  return [
    (1 + r5) / (1 + r3) - 1,
    (1 + r3) / (1 + r1) - 1,
    (1 + r1) / (1 + r6) - 1,
    (1 + r6) / (1 + r3m) - 1,
    (1 + r3m) / (1 + r1m) - 1,
    r1m, // 最后 1 个月
  ]
}

// 由分段收益率序列链式相乘，生成累计收益序列（%），起点 0
function chainCumulative(segs) {
  const out = [0]
  let acc = 1
  for (const s of segs) {
    acc *= (1 + s)
    out.push((acc - 1) * 100)
  }
  return out // 长度 = 分段数 + 1 = 7
}

// 由分段收益率序列加权平均（按权重）
function weightedAvgSegs(segList, weights) {
  const n = SEGMENTS.length
  const res = new Array(n).fill(0)
  for (let i = 0; i < segList.length; i++) {
    const w = weights[i]
    for (let k = 0; k < n; k++) res[k] += w * segList[i][k]
  }
  return res
}

// 估算最大回撤（从累计收益序列，%）
function estimateMaxDrawdown(curve) {
  let peak = -Infinity
  let maxDD = 0
  for (const v of curve) {
    if (v > peak) peak = v
    const dd = peak - v
    if (dd > maxDD) maxDD = dd
  }
  return maxDD
}

// ---- 数据加载与曲线构造 ----
async function load() {
  const pf = selectedPortfolio.value
  if (!pf) return
  // 先确认持仓字段结构
  console.log('[PortfolioBacktestPanel] 组合字段：', pf)
  console.log('[PortfolioBacktestPanel] 首个持仓：', (pf.portfolio_data || [])[0])

  loading.value = true
  try {
    const holdings = (pf.portfolio_data || []).filter(h => h && h.code)
    if (!holdings.length) {
      holdRows.value = []
      portCurve.value = []
      benchCurve.value = []
      usedWeightPct.value = 0
      return
    }

    const codes = holdings.map(h => h.code)
    let scoreMap = {}
    if (supabase) {
      const { data } = await supabase
        .from('fund_scores')
        .select('c,name,r1m,r3m,r6m,r1y,r3y,r5y')
        .in('c', codes)
      ;(data || []).forEach(f => { scoreMap[f.c] = f })
    }

    // 仅保留成功匹配且字段完整的持仓，并归一化权重
    const matched = []
    let wsum = 0
    for (const h of holdings) {
      const sc = scoreMap[h.code]
      if (!sc) continue
      const w = parseWeight(h.weight)
      if (!(w > 0)) continue
      matched.push({ code: h.code, name: sc.name || h.name || h.code, weight: w, scores: sc })
      wsum += w
    }
    if (wsum <= 0 || matched.length === 0) {
      holdRows.value = []
      portCurve.value = []
      benchCurve.value = []
      usedWeightPct.value = 0
      return
    }
    // 权重归一化（仅对参与回测的持仓）
    const normWeights = matched.map(m => m.weight / wsum)
    usedWeightPct.value = +(normWeights.reduce((a, b) => a + b, 0) * 100).toFixed(1)

    // 各基金分段收益率
    const segs = matched.map(m => segReturns(m.scores))

    // 组合：按权重加权分段收益 → 链式相乘
    const portSegs = weightedAvgSegs(segs, normWeights)
    portCurve.value = chainCumulative(portSegs)

    // 等权基准：对基金等权平均分段收益 → 链式相乘
    const equalW = matched.map(() => 1 / matched.length)
    const benchSegs = weightedAvgSegs(segs, equalW)
    benchCurve.value = chainCumulative(benchSegs)

    // 明细表
    holdRows.value = matched.map((m, i) => ({
      code: m.code,
      name: m.name,
      weightPct: +(normWeights[i] * 100).toFixed(1),
      r5y: typeof m.scores.r5y === 'number' ? m.scores.r5y : null,
      r1y: typeof m.scores.r1y === 'number' ? m.scores.r1y : null,
    }))
  } catch (e) {
    console.error('[PortfolioBacktestPanel]', e)
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

// ---- 摘要 ----
const portFinal = computed(() => portCurve.value.length ? portCurve.value[portCurve.value.length - 1] : null)
const benchFinal = computed(() => benchCurve.value.length ? benchCurve.value[benchCurve.value.length - 1] : null)
const maxDD = computed(() => portCurve.value.length ? estimateMaxDrawdown(portCurve.value) : 0)

// ---- ECharts ----
const chartEl = ref(null)
let chartInstance = null

function renderChart() {
  if (!chartEl.value) return
  if (!chartInstance) chartInstance = echarts.getInstanceByDom(chartEl.value) || echarts.init(chartEl.value)

  if (!portCurve.value.length) {
    chartInstance.clear()
    return
  }

  const option = createGovukChart({
    legend: {
      bottom: 0, left: 0, right: 0,
      textStyle: { fontSize: 12, color: '#505a66' },
      itemWidth: 18, itemHeight: 3, itemGap: 16,
    },
    grid: { left: 8, right: 18, top: 12, bottom: 44, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        if (!Array.isArray(params)) params = [params]
        const t = params[0]?.axisValue || ''
        let html = `<b>${t}</b><br/>`
        for (const p of params) {
          const v = p.value
          if (v == null) continue
          const sign = v > 0 ? '+' : ''
          html += `${p.marker} ${p.seriesName}：<b>${sign}${v.toFixed(2)}%</b><br/>`
        }
        return html
      },
    },
    xAxis: {
      type: 'category',
      data: POINTS.map(p => p.label),
      boundaryGap: false,
      axisLabel: { fontSize: 12 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { formatter: '{value}%', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
    },
    series: [
      {
        name: '组合',
        type: 'line',
        data: portCurve.value,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#1d70b8' },
        itemStyle: { color: '#1d70b8' },
        emphasis: { focus: 'series' },
        connectNulls: true,
      },
      {
        name: '等权基准',
        type: 'line',
        data: benchCurve.value,
        symbol: 'circle', symbolSize: 6,
        lineStyle: { width: 2, color: '#505a66', type: 'dashed' },
        itemStyle: { color: '#505a66' },
        emphasis: { focus: 'series' },
        connectNulls: true,
      },
    ],
  })
  chartInstance.setOption(option, true)
}

function onResize() { if (chartInstance) chartInstance.resize() }

// ---- 生命周期 ----
onMounted(() => {
  // 默认选中第一个组合
  if (portfolios.length && !selectedId.value) {
    selectedId.value = portfolios[0].id
  }
  if (selectedPortfolio.value) load()
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chartInstance) chartInstance.dispose()
})

// 组合列表就绪或切换时重载
watch(() => portfolios.length, (n) => {
  if (n && !selectedId.value) selectedId.value = portfolios[0].id
})
watch(selectedId, () => { if (selectedId.value) load() })
</script>

<style scoped>
.pbp-wrap {
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
  color: var(--text-primary, #0b0c0c);
}
.pbp-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-lg, 16px);
  flex-wrap: wrap;
}
.pbp-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary, #0b0c0c);
}
.pbp-select {
  display: flex;
  align-items: center;
  gap: var(--space-md, 8px);
}
.pbp-select label {
  font-size: 13px;
  color: var(--text-secondary, #505a5f);
}
.pbp-select select {
  border: 1px solid var(--border, #b1b4b6);
  border-radius: 2px;
  padding: 6px 8px;
  font-size: 14px;
  background: #fff;
  color: var(--text-primary, #0b0c0c);
  max-width: 220px;
}
.pbp-note {
  margin: var(--space-md, 8px) 0 var(--space-lg, 16px);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-secondary, #505a5f);
  border-left: 3px solid var(--color-up, #d4351c);
  padding-left: 10px;
}
.pbp-empty,
.pbp-loading {
  padding: 32px 0;
  text-align: center;
  color: var(--text-secondary, #505a5f);
  border: 1px dashed var(--border, #b1b4b6);
  border-radius: 2px;
}
.pbp-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-md, 8px);
  margin-bottom: var(--space-lg, 16px);
}
@media (max-width: 640px) {
  .pbp-cards { grid-template-columns: 1fr; }
}
.pbp-card {
  border: 1px solid var(--border, #b1b4b6);
  border-radius: 2px;
  padding: 12px;
}
.pbp-card-label {
  font-size: 12px;
  color: var(--text-secondary, #505a5f);
}
.pbp-card-value {
  font-size: 22px;
  font-weight: 700;
  margin: 6px 0 2px;
}
.pbp-card-sub {
  font-size: 11px;
  color: var(--text-secondary, #505a5f);
}
.pbp-up { color: var(--color-up, #d4351c); }   /* 涨=红 */
.pbp-down { color: var(--color-down, #00703c); } /* 跌=绿 */
.pbp-chart {
  width: 100%;
  height: 320px;
  border: 1px solid var(--border, #b1b4b6);
  border-radius: 2px;
  margin-bottom: var(--space-lg, 16px);
}
.pbp-hold-wrap { margin-top: 4px; }
.pbp-hold-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary, #0b0c0c);
  margin-bottom: 6px;
}
.pbp-hold-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}
.pbp-hold-table th,
.pbp-hold-table td {
  border-bottom: 1px solid var(--border, #b1b4b6);
  padding: 7px 8px;
  text-align: left;
}
.pbp-hold-table th {
  color: var(--text-secondary, #505a5f);
  font-weight: 600;
}
.pbp-num { text-align: right; }
.pbp-nomatch {
  font-size: 13px;
  color: var(--text-secondary, #505a5f);
  padding: 12px 0;
}
</style>
