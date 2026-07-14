<template>
  <div class="jqr-card">
    <div class="jqr-card-head">
      <div class="jqr-card-name">{{ card.name }}</div>
      <div class="jqr-signal" :class="card.signalClass">{{ card.signalLabel }}</div>
    </div>
    <div class="jqr-gauge" ref="gaugeEl"></div>
    <div class="jqr-spark" ref="sparkEl"></div>
    <div class="jqr-notes">
      <div class="jqr-meta">
        <span>取值范围：{{ card.range }}</span>
        <span>数据日期：{{ card.date }}</span>
      </div>
      <div class="jqr-sub" v-if="card.subLines.length">
        <div class="jqr-sub-row" v-for="s in card.subLines" :key="s.k">
          <span>{{ s.k }}</span><span>{{ s.v }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, nextTick } from 'vue'
import echarts from '../utils/echarts-setup'

const props = defineProps({
  card: { type: Object, required: true },
  series: { type: Array, default: () => [] }, // [{ date, value }]
  zones: { type: Array, default: () => [[0.5, '#b1b4b6'], [1, '#505a5f']] }, // [[fraction,color],...]
})

const gaugeEl = ref(null)
const sparkEl = ref(null)
let gaugeChart = null
let sparkChart = null

function numericValue() {
  const v = props.card && props.card.value
  return (typeof v === 'number' && !Number.isNaN(v)) ? v : null
}
function zoneColor(v) {
  if (v == null) return '#505a5f'
  for (const [frac, color] of props.zones) {
    if (v <= frac * 100) return color
  }
  return props.zones[props.zones.length - 1][1]
}

function drawGauge() {
  if (!gaugeEl.value) return
  if (!gaugeChart) gaugeChart = echarts.init(gaugeEl.value)
  const v = numericValue()
  const color = zoneColor(v)
  gaugeChart.setOption({
    series: [{
      type: 'gauge', min: 0, max: 100,
      startAngle: 210, endAngle: -30,
      center: ['50%', '56%'], radius: '94%',
      axisLine: { lineStyle: { width: 10, color: props.zones } },
      pointer: { length: '58%', width: 4, itemStyle: { color } },
      anchor: { show: true, size: 8, itemStyle: { color } },
      axisTick: { show: false }, splitLine: { show: false }, axisLabel: { show: false },
      detail: {
        valueAnimation: true, fontSize: 20, fontWeight: 700, color,
        offsetCenter: [0, '40%'],
        formatter: () => props.card.valueLabel
      },
      data: [{ value: v == null ? 0 : v }]
    }]
  }, true)
  gaugeChart.resize()
}

function drawSpark() {
  if (!sparkEl.value) return
  if (!sparkChart) sparkChart = echarts.init(sparkEl.value)
  const hist = (props.series || []).slice(-120)
  const dates = hist.map(d => d.date)
  const values = hist.map(d => d.value)
  sparkChart.setOption({
    grid: { left: 2, right: 2, top: 4, bottom: 2 },
    xAxis: { type: 'category', show: false, data: dates, boundaryGap: false },
    yAxis: { type: 'value', show: false, min: 0, max: 100 },
    series: [{
      type: 'line', data: values,
      lineStyle: { width: 1.5, color: props.card.color },
      symbol: 'none', areaStyle: { color: props.card.color + '14' }, smooth: false
    }],
    tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${props.card.name}: ${p[0].value}` }
  }, true)
  sparkChart.resize()
}

function onResize() {
  if (gaugeChart) gaugeChart.resize()
  if (sparkChart) sparkChart.resize()
}

onMounted(async () => { await nextTick(); drawGauge(); drawSpark() })
watch(() => props.card, () => { drawGauge(); drawSpark() }, { deep: true })
watch(() => props.series, () => { drawSpark() }, { deep: true })
onUnmounted(() => {
  if (gaugeChart) gaugeChart.dispose()
  if (sparkChart) sparkChart.dispose()
  window.removeEventListener('resize', onResize)
})
window.addEventListener('resize', onResize)
</script>

<style scoped>
.jqr-card {
  border: 1px solid var(--border);
  padding: var(--space-md);
  background: #fff;
  display: flex;
  flex-direction: column;
}
.jqr-card-head {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin-bottom: 2px;
}
.jqr-card-name { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.jqr-signal {
  display: inline-block;
  font-size: 12px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 3px;
  white-space: nowrap;
}
.jqr-signal.hot { color: #fff; background: var(--color-up); }
.jqr-signal.cold { color: #fff; background: var(--color-down); }
.jqr-signal.neutral { color: #fff; background: #505a5f; }
.jqr-gauge { width: 100%; height: 112px; }
.jqr-spark { width: 100%; height: 40px; margin-top: 2px; }
/* 说明文字组（取值范围/数据日期/明细）统一推到卡片底部、靠左，保证各卡底部对齐 */
.jqr-notes {
  margin-top: auto;
  text-align: left;
  border-top: 1px solid var(--border);
  padding-top: 6px;
}
.jqr-meta {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 6px;
}
.jqr-sub {
  margin-top: 8px;
  text-align: left;
}
.jqr-sub-row {
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  padding: 2px 0;
}
.jqr-sub-row span:first-child { color: var(--text-secondary); }
.jqr-sub-row span:last-child { font-weight: 700; color: var(--text-primary); }
</style>
