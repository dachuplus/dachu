<template>
  <div class="compare-page">
    <header class="page-head">
      <h1 class="page-title">基金对比工具</h1>
      <p class="page-sub">搜索并加入 2–3 只基金，横向对比各周期收益与综合评分。</p>
    </header>

    <!-- 搜索框 -->
    <div class="search-box">
      <input
        type="text"
        class="search-input"
        v-model="query"
        placeholder="输入基金名称片段或代码（如 沪深300、000001.OF）"
        @input="onInput"
        @focus="onFocus"
      />
      <button class="search-clear" v-if="query" @click="clearQuery" aria-label="清空">×</button>

      <ul class="candidate-list" v-if="showCandidates && candidates.length">
        <li
          v-for="item in candidates"
          :key="item.c"
          class="candidate-item"
          @click="addFund(item)"
        >
          <span class="candidate-name">{{ item.name }}</span>
          <span class="candidate-code">{{ item.c }} · {{ item.t0 }}</span>
        </li>
      </ul>
      <div class="candidate-empty" v-if="showCandidates && query && !candidates.length && !loading">
        无匹配基金
      </div>
    </div>

    <!-- 空态 -->
    <div class="empty-state" v-if="!selected.length">
      <p>尚未选择基金。</p>
      <p class="empty-hint">请在上方搜索框输入名称或代码，加入 2–3 只基金开始对比。</p>
    </div>

    <!-- 对比表 -->
    <div class="compare-table-wrap" v-else>
      <table class="compare-table">
        <thead>
          <tr>
            <th class="row-label">指标</th>
            <th v-for="f in selected" :key="f.c" class="col-head">
              <div class="col-head-inner">
                <span class="col-name">{{ f.name }}</span>
                <span class="col-code">{{ f.c }}</span>
                <button class="col-remove" @click="removeFund(f.c)" aria-label="移除">×</button>
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.key">
            <th class="row-label">{{ row.label }}</th>
            <td
              v-for="f in selected"
              :key="f.c"
              :class="['cell', isBest(row.key, f.c) ? 'cell-best' : '']"
            >
              {{ fmt(f[row.key], row.signed) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'
import { supabase } from '../../api/supabase'

const MAX = 3
const query = ref('')
const candidates = ref([])
const selected = ref([])
const loading = ref(false)
const showCandidates = ref(false)

// 防抖查询
let timer = null
function onInput() {
  showCandidates.value = true
  if (timer) clearTimeout(timer)
  timer = setTimeout(doSearch, 250)
}
function onFocus() {
  if (query.value) showCandidates.value = true
}
function clearQuery() {
  query.value = ''
  candidates.value = []
  showCandidates.value = false
}

// 转义 % 与引号，避免注入并防止模糊匹配误吞特殊字符
function escapeLike(s) {
  return s.replace(/[\\%'"]/g, (m) => '\\' + m)
}

async function doSearch() {
  const q = query.value.trim()
  if (!q) {
    candidates.value = []
    return
  }
  loading.value = true
  try {
    const safe = escapeLike(q)
    const { data, error } = await supabase
      .from('fund_scores')
      .select('c,name,t0')
      .or(`name.ilike.%${safe}%,c.ilike.%${safe}%`)
      .limit(20)
    if (error) throw error
    candidates.value = (data || []).filter(
      (d) => !selected.value.some((s) => s.c === d.c)
    )
  } catch (e) {
    console.error('[CompareTool] search failed:', e)
    candidates.value = []
  } finally {
    loading.value = false
  }
}

// 加入对比
async function addFund(item) {
  if (selected.value.length >= MAX) return
  if (selected.value.some((s) => s.c === item.c)) return
  const { data, error } = await supabase
    .from('fund_scores')
    .select('c,name,t0,k_all,r1m,r3m,r6m,r1y,r3y,r5y,daily_change')
    .eq('c', item.c)
    .single()
  if (!error && data) {
    selected.value.push(data)
  }
  query.value = ''
  candidates.value = []
  showCandidates.value = false
}

function removeFund(code) {
  selected.value = selected.value.filter((f) => f.c !== code)
}

// 行定义：key 对应基金字段，signed=true 表示有涨跌幅需红绿着色
const rows = [
  { key: 'k_all', label: '综合评分', signed: false },
  { key: 't0', label: '大类', signed: false },
  { key: 'r1m', label: '近1月(%)', signed: true },
  { key: 'r3m', label: '近3月(%)', signed: true },
  { key: 'r6m', label: '近6月(%)', signed: true },
  { key: 'r1y', label: '近1年(%)', signed: true },
  { key: 'r3y', label: '近3年(%)', signed: true },
  { key: 'r5y', label: '近5年(%)', signed: true },
  { key: 'daily_change', label: '当日(%)', signed: true }
]

// 格式化：null -> '--'，数值保留两位
function fmt(val, signed) {
  if (val === null || val === undefined || val === '') return '--'
  const n = Number(val)
  if (Number.isNaN(n)) return '--'
  return n.toFixed(2)
}

// 高亮最优值：数值行取最大（收益越高越优），大类行不高亮
function bestValue(key) {
  const nums = selected.value
    .map((f) => f[key])
    .filter((v) => v !== null && v !== undefined && v !== '')
    .map(Number)
  if (!nums.length) return null
  return Math.max(...nums)
}
function isBest(key, code) {
  const row = rows.find((r) => r.key === key)
  if (!row || !row.signed) return false
  const f = selected.value.find((s) => s.c === code)
  if (!f || f[key] === null || f[key] === undefined || f[key] === '') return false
  return Number(f[key]) === bestValue(key)
}
</script>

<style scoped>
.compare-page {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-lg) var(--space-md);
  color: var(--text-primary);
}

.page-head {
  margin-bottom: var(--space-lg);
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 4px;
}
.page-sub {
  margin: 0;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 搜索框 */
.search-box {
  position: relative;
  margin-bottom: var(--space-lg);
}
.search-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 36px 10px 12px;
  border: 1px solid var(--border);
  border-radius: 2px;
  font-size: 14px;
  color: var(--text-primary);
  background: #fff;
  outline: none;
}
.search-input:focus {
  border-color: var(--color-up);
}
.search-clear {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  font-size: 18px;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
}
.candidate-list {
  position: absolute;
  z-index: 10;
  width: 100%;
  margin: 4px 0 0;
  padding: 0;
  list-style: none;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 2px;
  max-height: 280px;
  overflow-y: auto;
}
.candidate-item {
  display: flex;
  justify-content: space-between;
  gap: var(--space-md);
  padding: 8px 12px;
  cursor: pointer;
  border-bottom: 1px solid var(--border);
}
.candidate-item:last-child {
  border-bottom: none;
}
.candidate-item:hover {
  background: #f5f8fc;
}
.candidate-name {
  color: var(--text-primary);
  font-size: 14px;
}
.candidate-code {
  color: var(--text-secondary);
  font-size: 12px;
  white-space: nowrap;
}
.candidate-empty {
  position: absolute;
  z-index: 10;
  width: 100%;
  margin-top: 4px;
  padding: 8px 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 2px;
  color: var(--text-secondary);
  font-size: 13px;
}

/* 空态 */
.empty-state {
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: var(--space-lg);
  text-align: center;
  color: var(--text-secondary);
}
.empty-hint {
  font-size: 13px;
  margin-top: 8px;
}

/* 对比表 */
.compare-table-wrap {
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: 2px;
}
.compare-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.compare-table th,
.compare-table td {
  border: 1px solid var(--border);
  padding: 10px 12px;
  text-align: center;
}
.row-label {
  text-align: left;
  color: var(--text-secondary);
  font-weight: 600;
  white-space: nowrap;
  background: #fafbfc;
}
.col-head {
  background: #f2f6fb;
}
.col-head-inner {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  position: relative;
}
.col-name {
  font-weight: 700;
  color: var(--text-primary);
}
.col-code {
  font-size: 12px;
  color: var(--text-secondary);
}
.col-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 18px;
  height: 18px;
  border: 1px solid var(--border);
  border-radius: 2px;
  background: #fff;
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}
.col-remove:hover {
  color: var(--color-down);
  border-color: var(--color-down);
}
.cell {
  color: var(--text-primary);
  white-space: nowrap;
}
.cell-best {
  font-weight: 700;
  color: var(--color-up);
}
</style>
