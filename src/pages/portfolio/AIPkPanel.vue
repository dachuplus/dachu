<template>
  <div class="aipk">

    <!-- 说明卡 -->
    <div class="card aipk-intro">
      <div class="card-title-row">
        <span class="card-title">AI 大 PK</span>
        <span class="aipk-badge">规则版 · 待接入真实大模型</span>
      </div>
      <p class="card-desc">
        让多个大模型各自按规则挑选 5 只基金、每只 20% 等权，每月 1 日调仓，比一比谁的收益更好。
        当前为 <b>规则版（Plan B）</b>：7 个国内模型按各自的量化规则从 ALLFUND.CN 真实基金库中自动选基，
        用于先把框架跑通；接入各家大模型 API Key 后，将改为由真实模型选基（选基逻辑不变）。
      </p>
      <div class="aipk-src">数据来源：ALLFUND.CN 靠谱指数基金库（真实收益，非模拟）</div>
    </div>

    <!-- 模型阵容 -->
    <div class="aipk-section-title">模型阵容（各 5 只 · 等权 20%）</div>
    <div class="aipk-models">
      <div class="aipk-model" v-for="m in orderedModels" :key="m.id" :style="{ borderTopColor: m.color }">
        <div class="aipk-model-hd">
          <span class="aipk-dot" :style="{ background: m.color }"></span>
          <span class="aipk-model-name">{{ m.name }}</span>
          <span class="aipk-model-short" :style="{ color: m.color }">{{ m.name_short }}</span>
        </div>
        <div class="aipk-model-persona">{{ m.persona }}</div>
        <div class="aipk-model-ret" :class="retClass(modelReturns[m.id]?.r1y)">
          近1年组合收益 {{ fmtRet(modelReturns[m.id]?.r1y) }}
        </div>
        <div class="aipk-funds">
          <div class="aipk-fund" v-for="(f, i) in (picksMap[m.id]?.picks || [])" :key="f.code">
            <span class="aipk-fund-idx">{{ i + 1 }}</span>
            <span class="aipk-fund-name">{{ f.name }}</span>
            <span class="aipk-fund-code">{{ f.code }}</span>
            <span class="aipk-fund-w">20%</span>
          </div>
          <div class="aipk-funds-empty" v-if="!(picksMap[m.id]?.picks || []).length">暂无选基数据</div>
        </div>
      </div>
    </div>

    <!-- 收益 PK -->
    <div class="card aipk-pk">
      <div class="aipk-pk-hd">
        <span class="card-title">收益 PK</span>
        <div class="aipk-periods">
          <button
            v-for="p in CHART_PERIODS" :key="p.key"
            class="aipk-period-btn"
            :class="{ active: chartPeriod === p.key }"
            @click="chartPeriod = p.key"
          >{{ p.label }}</button>
        </div>
      </div>

      <!-- 排行榜（冠亚季） -->
      <div class="aipk-rank" v-if="ranking.length">
        <div
          v-for="(item, idx) in ranking.slice(0, 3)" :key="item.id"
          class="aipk-rank-item"
          :class="['rank-' + (idx + 1)]"
        >
          <span class="aipk-rank-medal">{{ ['冠军', '亚军', '季军'][idx] }}</span>
          <span class="aipk-rank-name">{{ modelName(item.id) }}</span>
          <span class="aipk-rank-val" :class="retClass(item.ret)">{{ fmtRet(item.ret) }}</span>
        </div>
      </div>
      <div class="aipk-rank-note" v-if="ranking.length < orderedModels.length">
        注：{{ orderedModels.length - ranking.length }} 个模型因成分基金成立时间不足，该周期暂无数据
      </div>

      <!-- 对比图 -->
      <div class="aipk-chart" ref="chartEl"></div>

      <!-- 完整对比表 -->
      <div class="aipk-table-title">完整区间收益对比</div>
      <div class="aipk-table-wrap">
        <table class="aipk-table">
          <thead>
            <tr>
              <th class="aipk-th-model">模型</th>
              <th v-for="col in RETURN_COLS" :key="col.key">{{ col.label }}</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="m in orderedModels" :key="m.id">
              <td class="aipk-td-model">
                <span class="aipk-dot" :style="{ background: m.color }"></span>{{ m.name }}
              </td>
              <td
                v-for="col in RETURN_COLS" :key="col.key"
                :class="retClass(modelReturns[m.id]?.[col.key])"
              >{{ fmtRet(modelReturns[m.id]?.[col.key]) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 调仓时间线 -->
    <div class="card aipk-timeline-card">
      <div class="card-title">调仓时间线</div>
      <div class="aipk-timeline">
        <div class="aipk-tl-item" v-for="pm in timelinePeriods" :key="pm">
          <span class="aipk-tl-dot"></span>
          <span class="aipk-tl-date">{{ pm }} 月度调仓</span>
          <span class="aipk-tl-desc">各模型按规则重新选基，每月 1 日自动调仓（接入真实模型 API 后生效）</span>
        </div>
        <div class="aipk-tl-item" v-if="!timelinePeriods.length">
          <span class="aipk-tl-desc">暂无调仓记录</span>
        </div>
      </div>
    </div>

    <!-- 加载 / 空态 -->
    <div class="aipk-loading" v-if="loading">加载中...</div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { supabase } from '../../api/supabase'
import echarts from '../../utils/echarts-setup'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent } from 'echarts/components'
import { createGovukChart } from '../../utils/echarts-theme'

// 注册本组件所需的 BarChart（不修改共享的 echarts-setup.js）
echarts.use([BarChart, GridComponent, TooltipComponent, TitleComponent])

const MODEL_ORDER = ['ds', 'doubao', 'qwen', 'wenxin', 'zhipu', 'kimi', 'minimax']

const models = ref([])
const picksMap = ref({})      // { model_id: { period_month, picks:[{code,name,weight}] } }
const fundReturns = ref({})    // { code: { ...returns } }
const loading = ref(true)

const RETURN_COLS = [
  { key: 'daily_change', label: '当日' },
  { key: 'r0w', label: '近1周' },
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r2y', label: '近2年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
  { key: 'r10y', label: '近10年' },
]
const STRICT_COLS = { r3y: true, r5y: true, r10y: true }

const CHART_PERIODS = [
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
]
const chartPeriod = ref('r1y')
const chartEl = ref(null)
let chartInstance = null

const orderedModels = computed(() => {
  const map = {}
  models.value.forEach(m => { map[m.id] = m })
  return MODEL_ORDER.map(id => map[id]).filter(Boolean)
})

// 各模型加权区间收益
const modelReturns = computed(() => {
  const out = {}
  for (const m of models.value) {
    const picks = picksMap.value[m.id]?.picks || []
    const res = {}
    for (const col of RETURN_COLS) {
      const vals = picks
        .map(p => ({ w: p.weight || 0, v: fundReturns.value[p.code]?.[col.key] }))
      // 严格列：任一成分缺失 → 整列 --
      if (STRICT_COLS[col.key] && vals.some(x => x.v == null)) { res[col.key] = null; continue }
      let wsum = 0, vsum = 0, has = false
      for (const x of vals) {
        if (x.v == null) continue
        wsum += x.w; vsum += x.w * x.v; has = true
      }
      res[col.key] = has && wsum > 0 ? +(vsum / wsum).toFixed(2) : null
    }
    out[m.id] = res
  }
  return out
})

// 排行榜（按当前选择周期，排除无数据模型）
const ranking = computed(() => {
  const arr = orderedModels.value
    .map(m => ({ id: m.id, ret: modelReturns.value[m.id]?.[chartPeriod.value] }))
    .filter(x => x.ret != null)
    .sort((a, b) => b.ret - a.ret)
  return arr
})

const timelinePeriods = computed(() => {
  const set = new Set()
  Object.values(picksMap.value).forEach(p => { if (p?.period_month) set.add(p.period_month) })
  return [...set].sort().reverse()
})

function modelName(id) {
  return models.value.find(m => m.id === id)?.name || id
}

function fmtRet(v) {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
function retClass(v) {
  if (v == null) return 'ret-na'
  return v > 0 ? 'ret-pos' : (v < 0 ? 'ret-neg' : 'ret-flat')
}

async function loadAll() {
  loading.value = true
  try {
    const { data: m } = await supabase.from('ai_pk_models').select('*').eq('enabled', true)
    models.value = m || []
    const { data: p } = await supabase.from('ai_pk_picks').select('*').order('period_month', { ascending: false })
    const byModel = {}
    for (const row of (p || [])) {
      if (!byModel[row.model_id]) byModel[row.model_id] = row
    }
    picksMap.value = byModel

    const codes = new Set()
    for (const mid in byModel) (byModel[mid].picks || []).forEach(x => codes.add(x.code))
    if (codes.size) {
      const { data: fr } = await supabase.from('fund_scores')
        .select('c,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,r10y,daily_change')
        .in('c', [...codes])
      const map = {}
      ;(fr || []).forEach(f => { map[f.c] = f })
      fundReturns.value = map
    }
  } catch (e) {
    console.error('[AIPkPanel]', e)
  } finally {
    loading.value = false
    await nextTick()
    renderChart()
  }
}

function renderChart() {
  if (!chartEl.value) return
  if (!chartInstance) chartInstance = echarts.getInstanceByDom(chartEl.value) || echarts.init(chartEl.value)
  // 升序排列：ECharts category 轴首项在底部，最大值的放最后 → 顶部为冠军
  const data = ranking.value.slice().sort((a, b) => a.ret - b.ret)
  if (data.length === 0) {
    chartInstance.clear()
    return
  }
  const names = data.map(d => modelName(d.id))
  const values = data.map(d => ({
    value: +d.ret.toFixed(2),
    itemStyle: { color: (models.value.find(m => m.id === d.id) || {}).color || '#1d70b8' },
  }))
  const option = createGovukChart({
    grid: { left: 10, right: 50, top: 10, bottom: 20, containLabel: true },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        const p = params[0]
        return `${p.name}<br/>${chartPeriodLabel()}：<b>${(p.value > 0 ? '+' : '') + p.value.toFixed(2)}%</b>`
      },
    },
    xAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
    yAxis: { type: 'category', data: names },
    series: [{
      type: 'bar',
      data: values,
      barWidth: '55%',
      label: {
        show: true,
        position: 'right',
        formatter: (p) => (p.value > 0 ? '+' : '') + p.value.toFixed(2) + '%',
        color: '#0b0c0c',
        fontSize: 13,
      },
    }],
  })
  chartInstance.setOption(option, true)
}

function chartPeriodLabel() {
  return CHART_PERIODS.find(p => p.key === chartPeriod.value)?.label || ''
}

function onResize() { if (chartInstance) chartInstance.resize() }

watch(chartPeriod, async () => { await nextTick(); renderChart() })
watch(ranking, async () => { await nextTick(); renderChart() })

onMounted(() => {
  if (supabase) loadAll()
  else { loading.value = false }
  window.addEventListener('resize', onResize)
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  if (chartInstance) chartInstance.dispose()
})
</script>

<style scoped>
.aipk { padding-bottom: var(--space-2xl); }

.card { background: #fff; border: 1px solid var(--border); padding: var(--space-lg); margin-bottom: var(--space-xl); }
.card-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.card-desc { font-size: 16px; color: var(--text-secondary); line-height: 1.7; margin-bottom: var(--space-md); }
.card-desc b { color: var(--text-primary); }

/* 说明卡 */
.aipk-intro { border-left: 5px solid #1d70b8; }
.card-title-row { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-md); }
.card-title-row .card-title { margin-bottom: 0; }
.aipk-badge { font-size: 13px; color: #943c0c; background: #fff4e0; padding: 2px 10px; font-weight: 700; }
.aipk-src { font-size: 14px; color: var(--text-secondary); }

.aipk-section-title { font-size: 19px; font-weight: 700; margin: var(--space-lg) 0 var(--space-md); }

/* 模型阵容 */
.aipk-models { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: var(--space-md); margin-bottom: var(--space-xl); }
.aipk-model { background: #fff; border: 1px solid var(--border); border-top: 4px solid #1d70b8; padding: var(--space-md); }
.aipk-model-hd { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); }
.aipk-dot { width: 12px; height: 12px; border-radius: 50%; display: inline-block; flex: none; }
.aipk-model-name { font-size: 17px; font-weight: 700; }
.aipk-model-short { font-size: 13px; font-weight: 700; }
.aipk-model-persona { font-size: 13px; color: var(--text-secondary); line-height: 1.5; margin-bottom: var(--space-sm); min-height: 38px; }
.aipk-model-ret { font-size: 15px; font-weight: 700; margin-bottom: var(--space-sm); font-variant-numeric: tabular-nums; }
.aipk-funds { display: flex; flex-direction: column; gap: 4px; border-top: 1px solid var(--border); padding-top: var(--space-sm); }
.aipk-fund { display: flex; align-items: center; gap: var(--space-sm); font-size: 13px; }
.aipk-fund-idx { width: 18px; height: 18px; line-height: 18px; text-align: center; background: #f3f2f1; color: var(--text-secondary); font-size: 11px; flex: none; }
.aipk-fund-name { font-weight: 600; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.aipk-fund-code { color: var(--text-secondary); font-size: 12px; }
.aipk-fund-w { color: #1d70b8; font-weight: 700; font-size: 12px; }
.aipk-funds-empty { font-size: 13px; color: var(--text-secondary); }

/* 收益 PK */
.aipk-pk-hd { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: var(--space-md); margin-bottom: var(--space-md); }
.aipk-pk-hd .card-title { margin-bottom: 0; }
.aipk-periods { display: flex; gap: var(--space-xs); flex-wrap: wrap; }
.aipk-period-btn { padding: 4px var(--space-md); border: 1px solid var(--border); background: #fff; cursor: pointer; font-size: 14px; color: var(--text-secondary); }
.aipk-period-btn:hover { border-color: #1d70b8; }
.aipk-period-btn.active { background: #1d70b8; color: #fff; border-color: #1d70b8; }

.aipk-rank { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-md); }
.aipk-rank-item { display: flex; flex-direction: column; align-items: center; padding: var(--space-md); border: 1px solid var(--border); }
.aipk-rank-item.rank-1 { border-color: #b8860b; border-width: 2px; background: #fffdf5; }
.aipk-rank-item.rank-2 { border-color: #8c8c8c; border-width: 2px; background: #fafafa; }
.aipk-rank-item.rank-3 { border-color: #b5651d; border-width: 2px; background: #fdf8f4; }
.aipk-rank-medal { font-size: 14px; font-weight: 700; margin-bottom: 4px; }
.rank-1 .aipk-rank-medal { color: #b8860b; }
.rank-2 .aipk-rank-medal { color: #8c8c8c; }
.rank-3 .aipk-rank-medal { color: #b5651d; }
.aipk-rank-name { font-size: 16px; font-weight: 700; margin-bottom: 4px; }
.aipk-rank-val { font-size: 19px; font-weight: 700; font-variant-numeric: tabular-nums; }
.aipk-rank-note { font-size: 13px; color: var(--text-secondary); margin-bottom: var(--space-md); }

.aipk-chart { width: 100%; height: 360px; margin-bottom: var(--space-xl); }

.aipk-table-title { font-size: 16px; font-weight: 700; margin-bottom: var(--space-sm); }
.aipk-table-wrap { overflow-x: auto; }
.aipk-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 720px; }
.aipk-table th, .aipk-table td { padding: 8px 6px; text-align: center; border: 1px solid var(--border); font-variant-numeric: tabular-nums; white-space: nowrap; }
.aipk-table thead th { background: #f3f2f1; font-weight: 700; }
.aipk-th-model { text-align: left !important; }
.aipk-td-model { text-align: left !important; font-weight: 700; white-space: nowrap; }
.aipk-td-model .aipk-dot { margin-right: 6px; vertical-align: middle; }

/* 涨跌配色 */
.ret-pos { color: #d4351c; }
.ret-neg { color: #00703c; }
.ret-flat { color: #505a66; }
.ret-na { color: #b1b4b6; }

/* 时间线 */
.aipk-timeline { position: relative; padding-left: var(--space-lg); }
.aipk-timeline::before { content: ''; position: absolute; left: 5px; top: 4px; bottom: 4px; width: 2px; background: var(--border); }
.aipk-tl-item { position: relative; display: flex; align-items: baseline; gap: var(--space-md); padding: var(--space-sm) 0; flex-wrap: wrap; }
.aipk-tl-dot { position: absolute; left: calc(-1 * var(--space-lg) + 1px); top: 12px; width: 10px; height: 10px; background: #1d70b8; border-radius: 50%; }
.aipk-tl-date { font-size: 15px; font-weight: 700; color: #1d70b8; }
.aipk-tl-desc { font-size: 14px; color: var(--text-secondary); }

.aipk-loading { text-align: center; padding: var(--space-xl); color: var(--text-secondary); }

@media (max-width: 768px) {
  .aipk-rank { grid-template-columns: 1fr; }
  .aipk-chart { height: 320px; }
}
</style>
