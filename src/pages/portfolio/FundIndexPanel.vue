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
      <!-- 一级分类指数 -->
      <table class="fi-table" v-if="sub === 'primary'">
        <thead>
          <tr>
            <th>一级分类</th><th>基金数量</th>
            <th v-for="c in ALL_COLS" :key="c.key">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in priRows" :key="r.name">
            <td class="fi-pri-name">{{ r.name }}</td>
            <td>{{ num(r.count) }}</td>
            <td v-for="c in ALL_COLS" :key="c.key" :class="trendCls(r[c.key])">{{ pct(r[c.key]) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 二级分类指数 -->
      <table class="fi-table" v-else-if="sub === 'secondary'">
        <thead>
          <tr>
            <th>二级分类</th><th>基金数量</th>
            <th v-for="c in ALL_COLS" :key="c.key">{{ c.label }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in secRows" :key="r.name">
            <td class="fi-sec-name">{{ r.name }}</td>
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
  // 延迟加载：切换到尚未加载的 tab 时触发
  if (key === 'secondary' && secRows.value.length === 0 && !loading.value) loadSecondary()
}

// ===== 一级分类指数：按 t0 分组等权聚合 =====
async function loadPrimary() {
  if (!supabase) return
  try {
    const cols = ['t0', ...AGG_KEYS].join(',')
    const SIZE = 2000
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
    const SIZE = 2000
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
