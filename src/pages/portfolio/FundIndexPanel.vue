<template>
  <div class="fi-wrap">
    <div class="fi-head">
      <div class="fi-title">基金指数（按一级分类）</div>
      <div class="fi-subtabs">
        <button
          v-for="t in subTabs"
          :key="t.key"
          class="fi-subtab"
          :class="{ active: sub === t.key }"
          @click="sub = t.key"
        >{{ t.label }}</button>
      </div>
    </div>

    <div class="fi-note">
      数据说明：基金指数按一级分类（股票型 / 债券型 / 混合型 / 指数型 / FOF / QDII / 货币型）从 fund_scores 全量基金等权构建，
      每一类为该分类下所有基金各周期收益率的<b>等权平均值</b>，口径统一、可直接横向比较。数据每日更新。
    </div>

    <div class="fi-loading" v-if="loading">加载中…</div>

    <div class="fi-table-wrap" v-else>
      <!-- 基本信息 -->
      <table class="fi-table" v-if="sub === 'basic'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>成分数量</th><th>加权方式</th><th>口径</th><th>更新日期</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td>{{ num(r.basic_info && r.basic_info.ingredient_num) }}</td>
            <td>{{ r.basic_info && r.basic_info.weighting_mode || '—' }}</td>
            <td class="fi-caliber">{{ r.basic_info && r.basic_info.caliber || '—' }}</td>
            <td>{{ r.basic_info && r.basic_info.last_date || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 各周期收益 -->
      <table class="fi-table" v-else-if="sub === 'market'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th>
            <th v-for="c in periodCols" :key="c.key">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td
              v-for="c in periodCols"
              :key="c.key"
              :class="trendCls(mp(r, c.key))"
            >{{ pct(mp(r, c.key)) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 二级分类指数：按 t1_tt 等权聚合 -->
      <table class="fi-table" v-else-if="sub === 'secondary'">
        <thead>
          <tr>
            <th>二级分类</th><th>成分数量</th>
            <th>近1年</th><th>近2年</th><th>近3年</th><th>近5年</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in secRows" :key="r.name">
            <td class="fi-sec-name">{{ r.name }}</td>
            <td>{{ num(r.count) }}</td>
            <td :class="trendCls(r.r1y)">{{ pct(r.r1y) }}</td>
            <td :class="trendCls(r.r2y)">{{ pct(r.r2y) }}</td>
            <td :class="trendCls(r.r3y)">{{ pct(r.r3y) }}</td>
            <td :class="trendCls(r.r5y)">{{ pct(r.r5y) }}</td>
          </tr>
          <tr v-if="secRows.length === 0"><td colspan="6" class="fi-empty">暂无二级分类数据</td></tr>
        </tbody>
      </table>
    </div>

    <div class="fi-note fi-note--sec" v-if="sub === 'secondary'">
      二级分类指数按 <b>fund_scores</b> 全量基金的 <b>t1_tt（天天基金二级分类）</b> 分组，
      每类为该分类下所有基金各周期收益率的<b>等权平均值</b>，与一级分类口径一致、可直接横向比较。
      成分数量 = 该二级分类下的基金只数。
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { supabase } from '../../api/supabase'

const subTabs = [
  { key: 'basic', label: '基本信息' },
  { key: 'market', label: '各周期收益' },
  { key: 'secondary', label: '二级分类' },
]
const sub = ref('basic')
const rows = ref([])
const secRows = ref([])
const loading = ref(true)

// 各周期列（仅在任一分类存在该周期时展示）
const ALL_PERIODS = [
  { key: 'ytd', label: 'YTD' },
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
]
const periodCols = ref([])

function mp(r, k) { return r.market_perf ? r.market_perf[k] : null }

function pct(v) {
  if (v == null || v === '' || isNaN(Number(v))) return '—'
  return (Number(v) >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'
}
function num(v) {
  if (v == null || v === '' || isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('zh-CN')
}
function trendCls(v) {
  if (v == null || isNaN(Number(v))) return ''
  return Number(v) >= 0 ? 'up' : 'down'
}

// ===== 二级分类指数：按 t1_tt 分组等权聚合 =====
const SEC_PERIODS = ['r1y', 'r2y', 'r3y', 'r5y']
async function loadSecondary() {
  if (!supabase) return
  try {
    const cols = ['t1_tt', ...SEC_PERIODS].join(',')
    const SIZE = 1000
    const agg = {} // t1_tt -> { n, sum, cnt }
    let from = 0
    while (true) {
      const { data, error } = await supabase
        .from('fund_scores')
        .select(cols)
        .range(from, from + SIZE - 1)
      if (error) { console.warn('[FundIndexPanel] secondary query error', error); break }
      if (!data || data.length === 0) break
      data.forEach(r => {
        const key = (r.t1_tt && String(r.t1_tt).trim()) ? String(r.t1_tt).trim() : '其他'
        if (!agg[key]) {
          agg[key] = { n: 0, sum: { r1y: 0, r2y: 0, r3y: 0, r5y: 0 }, cnt: { r1y: 0, r2y: 0, r3y: 0, r5y: 0 } }
        }
        const a = agg[key]
        a.n++
        SEC_PERIODS.forEach(k => {
          const v = Number(r[k])
          if (v != null && !isNaN(v)) { a.sum[k] += v; a.cnt[k]++ }
        })
      })
      if (data.length < SIZE) break
      from += SIZE
    }
    const out = Object.keys(agg).map(k => {
      const a = agg[k]
      const avg = k2 => a.cnt[k2] ? a.sum[k2] / a.cnt[k2] : null
      return { name: k, count: a.n, r1y: avg('r1y'), r2y: avg('r2y'), r3y: avg('r3y'), r5y: avg('r5y') }
    }).sort((x, y) => y.count - x.count)
    secRows.value = out
  } catch (e) {
    console.error('[FundIndexPanel] secondary', e)
  }
}

onMounted(async () => {
  loading.value = true
  try {
    if (supabase) {
      const { data, error } = await supabase
        .from('fund_category_indices')
        .select('*')
        .order('name_cn')
      if (!error && data) {
        rows.value = data
        // 计算需要展示的周期列（至少某一分类有值）
        const present = new Set()
        data.forEach(r => {
          const mp_ = r.market_perf || {}
          ALL_PERIODS.forEach(p => { if (mp_[p.key] != null) present.add(p.key) })
        })
        periodCols.value = ALL_PERIODS.filter(p => present.has(p.key))
      }
      // 二级分类指数（不阻塞主流程）
      loadSecondary()
    }
  } catch (e) {
    console.error('[FundIndexPanel]', e)
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.fi-wrap { padding: var(--space-md) 0; }
.fi-head { display: flex; align-items: center; gap: var(--space-lg); flex-wrap: wrap; margin-bottom: var(--space-md); }
.fi-title { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.fi-subtabs { display: inline-flex; gap: 4px; background: #f3f2f1; padding: 4px; border-radius: 2px; }
.fi-subtab {
  border: none; background: transparent; padding: 6px 16px; font-size: 14px;
  color: #505a66; cursor: pointer; border-radius: 2px; font-weight: 600;
}
.fi-subtab.active { background: #1d70b8; color: #fff; }
.fi-note {
  background: #fff4e6; border-left: 3px solid #f47738; padding: 8px 12px;
  font-size: 12px; color: #6b3e00; margin-bottom: var(--space-md); line-height: 1.6;
}
.fi-loading { padding: 40px; text-align: center; color: #505a66; }
.fi-table-wrap { overflow-x: auto; border: 1px solid var(--border); }
.fi-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 640px; }
.fi-table th, .fi-table td { padding: 9px 12px; text-align: right; white-space: nowrap; border-bottom: 1px solid #f3f2f1; }
.fi-table th { background: #f3f2f1; color: #505a66; font-weight: 700; position: sticky; top: 0; }
.fi-table td:first-child, .fi-table th:first-child,
.fi-table td:nth-child(2), .fi-table th:nth-child(2) { text-align: left; }
.fi-table tbody tr:hover { background: #f8fafc; }
.fi-table .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #1d70b8; }
.fi-table .up { color: #cf1322; font-weight: 600; }
.fi-table .down { color: #009a44; font-weight: 600; }
.fi-caliber { white-space: normal; min-width: 200px; color: var(--text-secondary); font-weight: 400; }
.fi-sec-name { font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.fi-empty { text-align: center; color: var(--text-secondary); padding: 24px 0; }
.fi-note--sec { background: #e6f3ec; border-left: 3px solid #00703c; color: #1d4829; }
</style>
