<script setup>
/**
 * 定投收益计算器（纯前端，不依赖 supabase）
 *
 * 计算模型（按月复利）：
 *   monthlyRate = 年化% / 100 / 12
 *   首月：balance = 初始投入 * (1 + monthlyRate) + 月定投额
 *   其余每月：balance = balance * (1 + monthlyRate) + 月定投额
 *   月度序列记录 { 月序号, 累计投入, 资产总值 }
 */
import { ref, reactive, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import echarts from '../../utils/echarts-setup'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  LegendComponent,
} from 'echarts/components'

echarts.use([LineChart, GridComponent, TooltipComponent, LegendComponent])

const form = reactive({
  monthlyAmount: 1000,   // 每月定投金额（元）
  years: 5,              // 定投期限（年）
  annualRate: 8,         // 预期年化收益率（%）
  initialAmount: 0,      // 初始一次性投入（元，可选）
})

const chartRef = ref(null)
let chartInstance = null

// 月度序列计算
const series = computed(() => {
  const months = Math.max(1, Math.round((form.years || 0) * 12))
  const monthlyRate = (form.annualRate || 0) / 100 / 12
  const monthly = Math.max(0, Number(form.monthlyAmount) || 0)
  const initial = Math.max(0, Number(form.initialAmount) || 0)

  const rows = []
  let balance = 0
  let invested = 0

  for (let m = 1; m <= months; m++) {
    if (m === 1) {
      // 首月：先加初始投入，再复利，再加月度定投
      balance = initial * (1 + monthlyRate) + monthly
    } else {
      balance = balance * (1 + monthlyRate) + monthly
    }
    invested += monthly + (m === 1 ? initial : 0)
    rows.push({
      month: m,
      累计投入: Number(invested.toFixed(2)),
      资产总值: Number(balance.toFixed(2)),
    })
  }
  return rows
})

const totalInvested = computed(() => {
  const months = Math.max(1, Math.round((form.years || 0) * 12))
  const monthly = Math.max(0, Number(form.monthlyAmount) || 0)
  const initial = Math.max(0, Number(form.initialAmount) || 0)
  return months * monthly + initial
})

const finalValue = computed(() => {
  const rows = series.value
  return rows.length ? rows[rows.length - 1].资产总值 : 0
})

const totalProfit = computed(() => Number((finalValue.value - totalInvested.value).toFixed(2)))

const profitRate = computed(() => {
  if (totalInvested.value <= 0) return 0
  return Number(((totalProfit.value / totalInvested.value) * 100).toFixed(2))
})

const fmt = (n) => Number(n || 0).toLocaleString('zh-CN', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

function buildOption() {
  const rows = series.value
  return {
    backgroundColor: '#ffffff',
    color: ['#505a66', '#1d70b8'],
    legend: {
      data: ['累计投入', '资产总值'],
      textStyle: { color: '#505a66', fontSize: 12 },
      itemWidth: 20,
      itemHeight: 3,
      itemGap: 20,
      top: 0,
    },
    grid: { left: 8, right: 16, top: 36, bottom: 28, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: '#1d70b8',
      borderWidth: 0,
      textStyle: { color: '#ffffff', fontSize: 13 },
      valueFormatter: (v) => '¥ ' + fmt(v),
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      axisLine: { lineStyle: { color: '#b1b4b6' } },
      axisTick: { show: false },
      axisLabel: { color: '#505a66', fontSize: 11 },
      splitLine: { show: false },
      data: rows.map((r) => r.month + '月'),
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisTick: { show: false },
      axisLabel: {
        color: '#505a66',
        fontSize: 11,
        formatter: (v) => (v >= 10000 ? (v / 10000).toFixed(1) + '万' : v),
      },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
    },
    series: [
      {
        name: '累计投入',
        type: 'line',
        data: rows.map((r) => r.累计投入),
        lineStyle: { width: 2 },
        symbol: 'none',
        smooth: false,
      },
      {
        name: '资产总值',
        type: 'line',
        data: rows.map((r) => r.资产总值),
        lineStyle: { width: 2 },
        symbol: 'none',
        smooth: false,
        areaStyle: { color: 'rgba(29,112,184,0.10)' },
      },
    ],
  }
}

function renderChart() {
  if (!chartInstance) return
  chartInstance.setOption(buildOption())
}

function handleResize() {
  if (chartInstance) chartInstance.resize()
}

onMounted(() => {
  if (chartRef.value) {
    chartInstance = echarts.init(chartRef.value)
    renderChart()
    window.addEventListener('resize', handleResize)
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})

watch([series], async () => {
  await nextTick()
  renderChart()
})
</script>

<template>
  <div class="sip-calc">
    <header class="page-head">
      <h1>定投收益计算器</h1>
      <p class="subtitle">按月复利测算长期定投的投入与资产增长</p>
    </header>

    <section class="card form-card">
      <h2>输入参数</h2>
      <div class="field">
        <label for="monthlyAmount">每月定投金额（元）</label>
        <input id="monthlyAmount" type="number" min="0" step="100" v-model="form.monthlyAmount" />
      </div>
      <div class="field">
        <label for="years">定投期限（年）</label>
        <input id="years" type="number" min="1" step="1" v-model="form.years" />
      </div>
      <div class="field">
        <label for="annualRate">预期年化收益率（%）</label>
        <input id="annualRate" type="number" min="0" step="0.5" v-model="form.annualRate" />
      </div>
      <div class="field">
        <label for="initialAmount">初始一次性投入（元，可选）</label>
        <input id="initialAmount" type="number" min="0" step="100" v-model="form.initialAmount" />
      </div>
    </section>

    <section class="card result-card">
      <h2>计算结果</h2>
      <div class="result-grid">
        <div class="result-item">
          <span class="label">总投入</span>
          <span class="value">¥ {{ fmt(totalInvested) }}</span>
        </div>
        <div class="result-item">
          <span class="label">期末总额</span>
          <span class="value">¥ {{ fmt(finalValue) }}</span>
        </div>
        <div class="result-item">
          <span class="label">总收益</span>
          <span class="value" :class="totalProfit >= 0 ? 'up' : 'down'">¥ {{ fmt(totalProfit) }}</span>
        </div>
        <div class="result-item">
          <span class="label">收益率</span>
          <span class="value" :class="totalProfit >= 0 ? 'up' : 'down'">{{ fmt(profitRate) }}%</span>
        </div>
      </div>
    </section>

    <section class="card chart-card">
      <h2>资产增长曲线</h2>
      <div ref="chartRef" class="chart"></div>
    </section>

    <p class="disclaimer">
      本计算器结果为理论测算（按月复利），未考虑税费、手续费与通胀，不构成任何投资建议。
    </p>
  </div>
</template>

<style scoped>
.sip-calc {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-lg);
  color: var(--text-primary);
}

.page-head {
  margin-bottom: var(--space-lg);
}

.page-head h1 {
  font-size: 24px;
  margin: 0 0 var(--space-md);
  color: var(--text-primary);
}

.subtitle {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

.card {
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: var(--space-lg);
  margin-bottom: var(--space-lg);
  background: #ffffff;
}

.card h2 {
  font-size: 16px;
  margin: 0 0 var(--space-md);
  color: var(--text-primary);
}

.field {
  margin-bottom: var(--space-md);
  display: flex;
  flex-direction: column;
}

.field:last-child {
  margin-bottom: 0;
}

.field label {
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.field input {
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 8px 10px;
  font-size: 15px;
  color: var(--text-primary);
  background: #ffffff;
}

.field input:focus {
  outline: 2px solid #1d70b8;
  outline-offset: -1px;
}

.result-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-md);
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.result-item .label {
  font-size: 13px;
  color: var(--text-secondary);
}

.result-item .value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.value.up {
  color: var(--color-up);
}

.value.down {
  color: var(--color-down);
}

.chart {
  width: 100%;
  height: 320px;
}

.disclaimer {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-top: var(--space-lg);
}
</style>
