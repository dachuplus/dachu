<template>
  <div class="fi-wrap">
    <div class="fi-head">
      <div class="fi-title">基金指数</div>
      <div class="fi-subtabs">
        <button
          v-for="t in subTabs"
          :key="t.key"
          class="fi-subtab"
          :class="{ active: sub === t.key }"
          @click="switchSub(t.key)"
        >{{ t.label }}</button>
      </div>
    </div>

    <div class="fi-note">
      数据说明：基金指数按分类从 <b>fund_scores</b> 全量基金等权构建，
      每一类为该分类下所有基金各周期收益率的<b>等权平均值</b>，口径统一、可直接横向比较。数据每日更新。
    </div>

    <div class="fi-loading" v-if="loading">加载中…</div>

    <div class="fi-table-wrap" v-else>
      <table class="fi-table">
        <thead>
          <tr>
            <th
              v-for="c in headCols"
              :key="c.key"
              class="fi-th"
              :class="{ 'fi-th--active': sortState.key === c.key }"
              @click="requestSort(c.key)"
            >
              <span>{{ c.label }}</span>
              <span class="fi-sort" v-if="sortState.key === c.key">{{ sortState.order === 'asc' ? '▲' : '▼' }}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in displayRows" :key="r.name">
            <td :class="sub === 'primary' ? 'fi-pri-name' : 'fi-sec-name'">{{ r.name }}</td>
            <td>{{ num(r.count) }}</td>
            <td v-for="c in ALL_COLS" :key="c.key" :class="trendCls(r[c.key])">{{ pct(r[c.key]) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="fi-note fi-note--sec" v-if="sub === 'secondary'">
      二级分类指数按 <b>fund_scores</b> 全量基金的 <b>t1_tt（天天基金二级分类）</b> 分组，
      每类为该分类下所有基金各周期收益率的<b>等权平均值</b>。
      成分数量 = 该二级分类下的基金只数。
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { supabase } from '../../api/supabase'

const subTabs = [
  { key: 'primary', label: '一级分类' },
  { key: 'secondary', label: '二级分类' },
]
const sub = ref('primary')
const loading = ref(true)

// 全部周期列（与自建组合 RETURN_COLS 对齐）
const ALL_COLS = [
  { key: 'daily_change', label: '当日收益' },
  { key: 'r0w', label: '近1周' },
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r2y', label: '近2年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
]

// 汇总的字段列表
const AGG_KEYS = ALL_COLS.map(c => c.key)

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

const priRows = ref([])
const secRows = ref([])

function switchSub(key) {
  sub.value = key
  // 切换 tab 时重置排序，回到该分类的自然默认顺序
  sortState.value = { key: null, order: 'desc' }
  // 延迟加载：切换到尚未加载的 tab 时触发
  if (key === 'secondary' && secRows.value.length === 0 && !loading.value) loadSecondary()
}

// ===== 表头排序 =====
// sortState.key=null 时按各分类默认顺序展示；点击表头按列升/降序切换
const sortState = ref({ key: null, order: 'desc' })
function requestSort(key) {
  if (sortState.value.key === key) {
    sortState.value = { key, order: sortState.value.order === 'asc' ? 'desc' : 'asc' }
  } else {
    // 名称列默认升序，数量/收益列默认降序
    sortState.value = { key, order: key === 'name' ? 'asc' : 'desc' }
  }
}
// 表头列定义：一级/二级分类共用（首列名称随 tab 变化）
const headCols = computed(() => [
  { key: 'name', label: sub.value === 'primary' ? '一级分类' : '二级分类' },
  { key: 'count', label: '基金数量' },
  ...ALL_COLS,
])
// 当前展示行（已排序）：未指定排序列时返回原始默认顺序
const displayRows = computed(() => {
  const rows = sub.value === 'primary' ? priRows.value : secRows.value
  const { key, order } = sortState.value
  if (!key) return rows
  const mul = order === 'asc' ? 1 : -1
  return [...rows].sort((a, b) => {
    if (key === 'name') return mul * String(a.name).localeCompare(String(b.name), 'zh-CN')
    const va = a[key], vb = b[key]
    if (va == null && vb == null) return 0
    if (va == null) return 1   // 空值恒排末尾
    if (vb == null) return -1
    return mul * (Number(va) - Number(vb))
  })
})

// ===== 一级分类指数：按 t0 分组等权聚合 =====
async function loadPrimary() {
  if (!supabase) return
  try {
    const cols = ['t0', ...AGG_KEYS].join(',')
    const SIZE = 1000
    const agg = {}
    let from = 0
    while (true) {
      const { data, error } = await supabase
        .from('fund_scores')
        .select(cols)
        .range(from, from + SIZE - 1)
      if (error) { console.warn('[FundIndexPanel] primary query error', error); break }
      if (!data || data.length === 0) break
      data.forEach(r => {
        const key = (r.t0 && String(r.t0).trim()) ? String(r.t0).trim() : '其他'
        if (!agg[key]) {
          agg[key] = { n: 0, sum: {}, cnt: {} }
          AGG_KEYS.forEach(k => { agg[key].sum[k] = 0; agg[key].cnt[k] = 0 })
        }
        const a = agg[key]
        a.n++
        AGG_KEYS.forEach(k => {
          const v = Number(r[k])
          if (v != null && !isNaN(v)) { a.sum[k] += v; a.cnt[k]++ }
        })
      })
      if (data.length < SIZE) break
      from += SIZE
    }
    // 排序：按基金数量降序
    const order = ['股票型','债券型','混合型','指数型','FOF','QDII','货币型']
    const out = Object.keys(agg).map(k => {
      const a = agg[k]
      const row = { name: k, count: a.n }
      AGG_KEYS.forEach(k2 => { row[k2] = a.cnt[k2] ? a.sum[k2] / a.cnt[k2] : null })
      return row
    }).sort((x, y) => {
      const ix = order.indexOf(x.name), iy = order.indexOf(y.name)
      if (ix >= 0 && iy >= 0) return ix - iy
      if (ix >= 0) return -1
      if (iy >= 0) return 1
      return y.count - x.count
    })
    priRows.value = out
  } catch (e) {
    console.error('[FundIndexPanel] primary', e)
  }
}

// ===== 二级分类指数：按 t1_tt 分组等权聚合 =====
async function loadSecondary() {
  if (!supabase) return
  try {
    const cols = ['t1_tt', ...AGG_KEYS].join(',')
    const SIZE = 1000
    const agg = {}
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
          agg[key] = { n: 0, sum: {}, cnt: {} }
          AGG_KEYS.forEach(k => { agg[key].sum[k] = 0; agg[key].cnt[k] = 0 })
        }
        const a = agg[key]
        a.n++
        AGG_KEYS.forEach(k => {
          const v = Number(r[k])
          if (v != null && !isNaN(v)) { a.sum[k] += v; a.cnt[k]++ }
        })
      })
      if (data.length < SIZE) break
      from += SIZE
    }
    const out = Object.keys(agg).map(k => {
      const a = agg[k]
      const row = { name: k, count: a.n }
      AGG_KEYS.forEach(k2 => { row[k2] = a.cnt[k2] ? a.sum[k2] / a.cnt[k2] : null })
      return row
    }).sort((x, y) => y.count - x.count)
    secRows.value = out
  } catch (e) {
    console.error('[FundIndexPanel] secondary', e)
  }
}

onMounted(async () => {
  loading.value = true
  try {
    await Promise.all([loadPrimary(), loadSecondary()])
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
.fi-subtab:hover { background: #eaeaea; }
.fi-subtab.active { background: #1d70b8; color: #fff; }
.fi-subtab.active:hover { background: #1d70b8; }
.fi-note {
  background: #fff4e6; border-left: 3px solid #f47738; padding: 8px 12px;
  font-size: 12px; color: #6b3e00; margin-bottom: var(--space-md); line-height: 1.6;
}
.fi-loading { padding: 40px; text-align: center; color: #505a66; }
.fi-table-wrap { overflow-x: auto; border: 1px solid var(--border); }
.fi-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 900px; }
.fi-table th, .fi-table td { padding: 8px 10px; text-align: right; white-space: nowrap; border-bottom: 1px solid #eaeaea; }
.fi-table th { background: #f3f2f1; color: #505a66; font-weight: 700; position: sticky; top: 0; font-size: 12px; }
.fi-th { cursor: pointer; user-select: none; transition: background 0.12s; }
.fi-th:hover { background: #e7e6e4; }
.fi-th--active { color: #1d70b8; }
.fi-th--active:hover { background: #e1edf7; }
.fi-sort { margin-left: 4px; font-size: 10px; color: #1d70b8; }
.fi-table td:first-child, .fi-table th:first-child,
.fi-table td:nth-child(2), .fi-table th:nth-child(2) { text-align: left; }
.fi-table tbody tr:hover { background: #f8fafc; }
.fi-table .up { color: #cf1322; font-weight: 600; }
.fi-table .down { color: #009a44; font-weight: 600; }
.fi-pri-name { font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.fi-sec-name { font-weight: 700; color: var(--text-primary); white-space: nowrap; }
.fi-empty { text-align: center; color: var(--text-secondary); padding: 24px 0; }
.fi-note--sec { background: #e6f3ec; border-left: 3px solid #00703c; color: #1d4829; }

/* 移动端适配 */
@media (max-width: 768px) {
  .fi-table { min-width: 720px; font-size: 12px; }
  .fi-table th, .fi-table td { padding: 6px 8px; }
}
</style>
