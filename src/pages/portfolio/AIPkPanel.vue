<template>
  <div class="aipk">

    <!-- 说明卡 -->
    <div class="card aipk-intro">
      <div class="card-title-row">
        <span class="card-title">AI 大 PK</span>
        <span class="aipk-badge" :class="{ 'aipk-badge-real': realModels.length }">
          {{ realModels.length ? `真实大模型已接入（${realModels.length}）` : '规则版' }}
        </span>
      </div>
      <p class="card-desc">
        让多个大模型各自挑选 5 只基金、每只 20% 等权，每月 1 日调仓，比一比谁的收益更好。
        由 <b>7 个真实大模型</b>基于 ALLFUND.CN 靠谱指数（fund_scores）真实数据，先选二级分类(t1)品类、再在该品类内选单品（含豆包·火山方舟真实模型），
        并给出两层逻辑（第一层品类选择 · 第二层单品选择）；各模型按自身推理逻辑自主决策，目标只有一个——跑赢对手。
        通过「千问百炼」聚合平台调用的模型已在卡片上标注<span class="aipk-ds-badge">百炼</span>徽标。
        所有选品与推理均基于 fund_scores 真实指标（收益/回撤/夏普/规模），模型不引用任何表外或网络信息，无编造、无模拟。
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
          <span class="aipk-model-mode" :class="m.mode === 'real' ? 'is-real' : m.mode === 'pending' ? 'is-pending' : 'is-rule'">
            {{ m.mode === 'real' ? '真实' : m.mode === 'pending' ? '待接入' : '规则' }}
          </span>
          <span v-if="m.api_provider === 'qwen'" class="aipk-ds-badge">百炼</span>
        </div>
        <div class="aipk-model-persona">{{ modelTagline(m) }}</div>
        <div class="aipk-model-ret" v-if="m.mode !== 'pending'" :class="retClass(modelReturns[m.id]?.r1y)">
          近1年组合收益 {{ fmtRet(modelReturns[m.id]?.r1y) }}
        </div>
        <div class="aipk-funds">
          <div class="aipk-pending" v-if="m.mode === 'pending'">待接入</div>
          <template v-else>
            <div class="aipk-fund" v-for="(f, i) in (picksMap[m.id]?.picks || [])" :key="f.code">
              <span class="aipk-fund-idx">{{ i + 1 }}</span>
              <span class="aipk-fund-name">{{ f.name }}</span>
              <span class="aipk-fund-code">{{ f.code }}</span>
              <span class="aipk-fund-w">20%</span>
            </div>
            <div class="aipk-funds-empty" v-if="!(picksMap[m.id]?.picks || []).length">暂无选基数据</div>
          </template>
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
      <div class="aipk-tl-period" v-if="latestPeriod">
        {{ latestPeriod }} 月度调仓 · 各模型选基逻辑（两层）
        <span class="aipk-tl-mode-note" v-if="orderedModels.length">
          （{{ realModels.length ? realModels.length + ' 个真实模型' : '' }}{{ realModels.length && ruleModels.length ? ' + ' : '' }}{{ ruleModels.length ? ruleModels.length + ' 个规则版' : '' }}）
        </span>
      </div>
      <div class="aipk-tl-empty" v-if="!orderedModels.length">暂无选基数据</div>
      <div class="aipk-tl-model" v-for="m in orderedModels" :key="m.id">
        <div class="aipk-tl-model-hd">
          <span class="aipk-dot" :style="{ background: m.color }"></span>
          <span class="aipk-tl-model-name">{{ m.name }}</span>
          <span class="aipk-tl-model-short" :style="{ color: m.color }">{{ m.name_short }}</span>
        </div>
        <div class="aipk-tl-pending" v-if="m.mode === 'pending'">待接入</div>
        <template v-else>
          <div class="aipk-tl-layer">
            <span class="aipk-tl-tag">第一层 · 模型独立研究（宏观/策略/行业/流动性/金融工程/胜率赔率 六维度）</span>
            <p class="aipk-tl-text">{{ m.category_logic || '—' }}</p>
          </div>
          <div class="aipk-tl-layer">
            <span class="aipk-tl-tag">第二层 · 单品逻辑（多维度分析）</span>
            <div class="aipk-tl-funds">
              <div class="aipk-tl-fund" v-for="(f, i) in (picksMap[m.id]?.picks || [])" :key="f.code">
                <span class="aipk-tl-fund-idx">{{ i + 1 }}</span>
                <span class="aipk-tl-fund-name">{{ f.name }}</span>
                <span class="aipk-tl-fund-w">20%</span>
                <p class="aipk-tl-fund-reason">{{ f.reason || '—' }}</p>
              </div>
            </div>
          </div>
        </template>
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

const realModels = computed(() => orderedModels.value.filter(m => m.mode === 'real'))
const ruleModels = computed(() => orderedModels.value.filter(m => m.mode !== 'real'))

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
const latestPeriod = computed(() => timelinePeriods.value[0] || null)

function modelName(id) {
  return models.value.find(m => m.id === id)?.name || id
}

// 各模型的「调用通道 / 聚合平台」中文标签（用于卡片标语，明确展示百炼等聚合平台）
const PROVIDER_LABEL = {
  ds: 'DeepSeek · 千问百炼',
  doubao: '豆包 · 火山方舟',
  qwen: '千问百炼聚合',
  wenxin: '文心 · 百度千帆',
  zhipu: '智谱 · 千问百炼',
  kimi: 'Kimi · 千问百炼',
  minimax: 'MiniMax · 千问百炼',
}
// 取代旧的固定「人设」文案：现在每个模型都按自身推理逻辑自主选基
function modelTagline(m) {
  const label = PROVIDER_LABEL[m.id] || PROVIDER_LABEL[m.api_provider] || m.api_provider || '真实大模型'
  return `${label} · 自主推理选基`
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
.aipk-badge-real { color: #fff; background: #1d70b8; }
.aipk-src { font-size: 14px; color: var(--text-secondary); }

/* 模型卡模式标签（真实/规则） */
.aipk-model-mode { font-size: 12px; font-weight: 700; padding: 1px 8px; margin-left: auto; }
.aipk-model-mode.is-real { color: #fff; background: #1d70b8; }
.aipk-model-mode.is-rule { color: #505a66; background: #f3f2f1; border: 1px solid var(--border); }
.aipk-model-mode.is-pending { color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; }

/* 千问百炼聚合平台徽标 */
.aipk-ds-badge { font-size: 12px; font-weight: 700; padding: 1px 8px; margin-left: 6px; color: #fff; background: #b8860b; }

/* 时间线模式注记 */
.aipk-tl-mode-note { font-size: 13px; font-weight: 400; color: var(--text-secondary); }

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
.aipk-pending { font-size: 14px; font-weight: 700; color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; padding: var(--space-sm); text-align: center; }
.aipk-tl-pending { font-size: 15px; font-weight: 700; color: #943c0c; background: #fff4e0; border: 1px solid #f0c89a; padding: var(--space-md); text-align: center; }

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

/* 时间线（两层选基逻辑） */
.aipk-tl-period { font-size: 15px; font-weight: 700; color: #1d70b8; margin-bottom: var(--space-md); }
.aipk-tl-empty { font-size: 14px; color: var(--text-secondary); }
.aipk-tl-model { border-top: 1px solid var(--border); padding: var(--space-md) 0; }
.aipk-tl-model:first-of-type { border-top: none; }
.aipk-tl-model-hd { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-sm); }
.aipk-tl-model-name { font-size: 17px; font-weight: 700; }
.aipk-tl-model-short { font-size: 13px; font-weight: 700; }
.aipk-tl-layer { margin-bottom: var(--space-sm); }
.aipk-tl-tag { display: inline-block; font-size: 12px; font-weight: 700; color: #fff; background: #1d70b8; padding: 2px 8px; margin-bottom: 6px; }
.aipk-tl-text { font-size: 14px; color: var(--text-secondary); line-height: 1.7; margin: 0; }
.aipk-tl-funds { display: flex; flex-direction: column; gap: 8px; }
.aipk-tl-fund { display: grid; grid-template-columns: 20px 1fr auto; gap: var(--space-sm); align-items: baseline; }
.aipk-tl-fund-idx { width: 20px; height: 20px; line-height: 20px; text-align: center; background: #f3f2f1; color: var(--text-secondary); font-size: 11px; }
.aipk-tl-fund-name { font-weight: 600; font-size: 14px; }
.aipk-tl-fund-w { color: #1d70b8; font-weight: 700; font-size: 12px; }
.aipk-tl-fund-reason { grid-column: 2 / 4; font-size: 13px; color: var(--text-secondary); line-height: 1.6; margin: 2px 0 0; }

.aipk-loading { text-align: center; padding: var(--space-xl); color: var(--text-secondary); }

@media (max-width: 768px) {
  .aipk-rank { grid-template-columns: 1fr; }
  .aipk-chart { height: 320px; }
}
</style>
