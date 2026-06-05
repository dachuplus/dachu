<template>
  <div class="page-industry-rank">
    <!-- 顶部：标题 + 帮助 -->
    <div class="top-bar">
      <div class="top-title-row">
        <span class="top-title-text">指数估值</span>
        <span class="help-icon-btn" @click="showHelp = true">?</span>
      </div>
      <div class="data-info-row" v-if="updateTime">
        数据：蛋卷基金估值中心 · {{ totalCount }}个指数 · {{ updateTime }}
        <span class="data-refresh" :class="{ refreshing }" @click="refreshData">↻ 刷新</span>
      </div>
      <div class="data-info-row" v-else-if="loading">加载中...</div>
    </div>

    <!-- 类型筛选 -->
    <div class="filter-bar">
      <div
        v-for="t in ttypeOptions"
        :key="t.key"
        class="filter-chip"
        :class="{ active: ttypeFilter === t.key }"
        @click="setTtype(t.key)"
      >{{ t.label }}</div>
    </div>

    <!-- 加载中 -->
    <div class="loading-wrap" v-if="loading && filteredIndices.length === 0">
      <span class="loading-text">正在加载指数估值数据...</span>
    </div>

    <!-- 错误状态 -->
    <div class="empty-state" v-else-if="errorMsg">
      <p class="empty-text">{{ errorMsg }}</p>
      <p class="empty-hint" @click="loadData">点击重试</p>
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-else-if="!loading && filteredIndices.length === 0">
      <p class="empty-text">没有找到符合条件的指数</p>
    </div>

    <!-- 估值表格 -->
    <div class="eva-table-wrap" v-else>
      <div class="eva-table-scroll">
        <!-- 表头 -->
        <div class="eva-header-row">
          <div
            class="col col-name"
            :class="{ sortable: true, sorted: sortBy === 'name' }"
            @click="setSort('name')"
          >名称</div>
          <div
            class="col col-num"
            :class="{ sortable: true, sorted: sortBy === 'pe' }"
            @click="setSort('pe')"
          >PE</div>
          <div
            class="col col-pct"
            :class="{ sortable: true, sorted: sortBy === 'pePercentile' }"
            @click="setSort('pePercentile')"
          >PE百分位</div>
          <div
            class="col col-num"
            :class="{ sortable: true, sorted: sortBy === 'pb' }"
            @click="setSort('pb')"
          >PB</div>
          <div
            class="col col-pct"
            :class="{ sortable: true, sorted: sortBy === 'pbPercentile' }"
            @click="setSort('pbPercentile')"
          >PB百分位</div>
          <div
            class="col col-num"
            :class="{ sortable: true, sorted: sortBy === 'dividendYield' }"
            @click="setSort('dividendYield')"
          >股息率</div>
          <div
            class="col col-num"
            :class="{ sortable: true, sorted: sortBy === 'roe' }"
            @click="setSort('roe')"
          >ROE</div>
          <div
            class="col col-num"
            :class="{ sortable: true, sorted: sortBy === 'peg' }"
            @click="setSort('peg')"
          >PEG</div>
          <div
            class="col col-status"
            :class="{ sortable: true, sorted: sortBy === 'evaType' }"
            @click="setSort('evaType')"
          >估值状态</div>
        </div>

        <!-- 数据行 -->
        <div
          v-for="(item, idx) in filteredIndices"
          :key="item.code"
          class="eva-row"
          :class="{ 'row-even': idx % 2 === 0 }"
        >
          <div class="col col-name" :title="item.name">{{ item.name }}</div>
          <div class="col col-num">{{ fmtPe(item.pe) }}</div>
          <div class="col col-pct" :class="pctClass(item.pePercentile)">{{ fmtPct(item.pePercentile) }}</div>
          <div class="col col-num">{{ fmtPb(item.pb) }}</div>
          <div class="col col-pct" :class="pctClass(item.pbPercentile)">{{ fmtPct(item.pbPercentile) }}</div>
          <div class="col col-num">{{ fmtYield(item.dividendYield) }}</div>
          <div class="col col-num">{{ fmtRoe(item.roe) }}</div>
          <div class="col col-num">{{ fmtPeg(item.peg) }}</div>
          <div class="col col-status">
            <span
              class="eva-tag"
              :style="{ background: item.evaColor + '20', color: item.evaColor }"
            >{{ item.evaText }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 底部说明 -->
    <div class="bottom-info" v-if="!loading || filteredIndices.length > 0">
      <span>数据来源：蛋卷基金估值中心（danjuanfunds.com）</span>
      <span>PE/PB百分位 = 当前值在历史数据中的排名位置，越低越便宜</span>
      <span>仅供学习参考，不构成投资建议</span>
    </div>

    <!-- 帮助弹窗 -->
    <Teleport to="body">
      <template v-if="showHelp">
        <div class="mask" @click="showHelp = false"></div>
        <div class="help-panel">
          <div class="help-header">
            <span class="help-title">指数估值说明</span>
            <span class="help-close" @click="showHelp = false">✕</span>
          </div>
          <div class="help-body">
            <div class="help-section">
              <span class="help-section-label">估值方法</span>
              <span class="help-desc">
                PE百分位 = 当前PE在过去N年历史数据中的排名位置。百分位越低，代表当前估值相对历史越便宜。
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">百分位含义</span>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FF5252;"></span>
                <span class="help-color-text" style="color:#FF5252;">&lt; 30%</span>
                <span class="help-color-desc">低估（红色），历史中性价比偏低区间</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FFA502;"></span>
                <span class="help-color-text" style="color:#FFA502;">30% ~ 70%</span>
                <span class="help-color-desc">适中（橙色），估值中性</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#2ED573;"></span>
                <span class="help-color-text" style="color:#2ED573;">&gt; 70%</span>
                <span class="help-color-desc">高估（绿色），历史中性价比偏高区间</span>
              </div>
            </div>
            <div class="help-section">
              <span class="help-section-label">数据类型</span>
              <span class="help-desc">
                PE = 市盈率（股价/每股收益）；PB = 市净率（股价/每股净资产）<br>
                股息率 = 年度分红/股价；ROE = 净资产收益率；PEG = PE/盈利增长率
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">覆盖范围</span>
              <span class="help-desc">
                共63个主流指数，含A股宽基/行业、港股、美股及海外指数。
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">数据更新</span>
              <span class="help-desc">
                蛋卷基金每日更新指数估值数据，通常在交易日17:00后更新。
              </span>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchDanjuanEva } from '../../utils/api.js'

// ========== 常量 ==========
const ttypeOptions = [
  { key: 'all', label: '全部' },
  { key: '3',   label: 'A股' },
  { key: '1',   label: '港股/海外' },
  { key: '2',   label: '美股/其他' },
]

// ========== 状态 ==========
const allIndices      = ref([])
const filteredIndices = ref([])
const ttypeFilter     = ref('all')
const sortBy          = ref('pePercentile')
const sortOrder       = ref('asc')
const loading         = ref(false)
const refreshing      = ref(false)
const errorMsg        = ref('')
const updateTime      = ref('')
const totalCount      = ref(0)
const showHelp        = ref(false)

// ========== 生命周期 ==========
onMounted(() => {
  loadData()
})

// ========== 数据加载 ==========
async function loadData() {
  if (loading.value) return
  loading.value = true
  errorMsg.value = ''

  try {
    const result = await fetchDanjuanEva()
    if (result.code !== 0 || !result.data || result.data.length === 0) {
      errorMsg.value = result.msg || '数据加载失败，请刷新重试'
      return
    }

    const mapped = result.data.map(item => ({
      name:          item.name        || '',
      code:          item.code        || '',
      ttype:         item.ttype       || '',
      pe:            item.pe,
      pePercentile:   item.pePercentile,
      pb:            item.pb,
      pbPercentile:   item.pbPercentile,
      dividendYield: item.dividendYield,
      roe:           item.roe,
      peg:           item.peg,
      evaType:       item.evaType    || '',
      evaText:       item.evaText    || '--',
      evaColor:      item.evaColor   || '#6E7681',
      date:          item.date        || '',
    }))

    allIndices.value = mapped
    totalCount.value = mapped.length

    const dated = mapped.find(d => d.date)
    if (dated) updateTime.value = dated.date

    applyFilter()
  } catch (e) {
    console.error('[industry-rank] load error', e)
    errorMsg.value = '数据加载失败：' + (e.message || '未知错误')
  } finally {
    loading.value = false
  }
}

// ========== 筛选 ==========
function applyFilter() {
  let data = allIndices.value

  if (ttypeFilter.value !== 'all') {
    data = data.filter(d => String(d.ttype) === String(ttypeFilter.value))
  }

  data = [...data].sort((a, b) => {
    let va = a[sortBy.value]
    let vb = b[sortBy.value]

    if (va == null && vb == null) return 0
    if (va == null) return 1
    if (vb == null) return -1

    if (sortBy.value === 'name') {
      return sortOrder.value === 'asc'
        ? String(va).localeCompare(String(vb))
        : String(vb).localeCompare(String(va))
    }

    if (sortBy.value === 'evaType') {
      const order = { low: 0, normal: 1, high: 2 }
      va = order[va] ?? 9
      vb = order[vb] ?? 9
    }

    const diff = Number(va) - Number(vb)
    return sortOrder.value === 'asc' ? diff : -diff
  })

  filteredIndices.value = data
}

function setTtype(key) {
  ttypeFilter.value = key
  applyFilter()
}

// ========== 排序 ==========
function setSort(key) {
  if (sortBy.value === key) {
    sortOrder.value = sortOrder.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortBy.value = key
    if (key === 'pePercentile' || key === 'pbPercentile') {
      sortOrder.value = 'asc'
    } else if (key === 'name' || key === 'evaType') {
      sortOrder.value = 'asc'
    } else {
      sortOrder.value = 'desc'
    }
  }
  applyFilter()
}

// ========== 刷新 ==========
function refreshData() {
  if (refreshing.value) return
  refreshing.value = true
  loadData()
  setTimeout(() => { refreshing.value = false }, 2000)
}

// ========== 格式化 ==========
function fmtPe(v) {
  if (v == null || v === 0) return '--'
  return Number(v).toFixed(2)
}

function fmtPb(v) {
  if (v == null || v === 0) return '--'
  return Number(v).toFixed(2)
}

function fmtPct(v) {
  if (v == null) return '--'
  return Number(v).toFixed(2) + '%'
}

function fmtYield(v) {
  if (v == null) return '--'
  return Number(v).toFixed(2) + '%'
}

function fmtRoe(v) {
  if (v == null || v === 0) return '--'
  return Number(v).toFixed(2) + '%'
}

function fmtPeg(v) {
  if (v == null || v === 0) return '--'
  return Number(v).toFixed(2)
}

function pctClass(v) {
  if (v == null) return ''
  if (v < 30) return 'pct-low'
  if (v > 70) return 'pct-high'
  return 'pct-mid'
}
</script>

<style scoped>
.page-industry-rank {
  min-height: 100vh;
  padding-bottom: 60px;
}

/* 顶部栏 */
.top-bar {
  position: sticky;
  top: 0;
  z-index: 10;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 12px 16px 8px;
}

.top-title-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  margin-bottom: 6px;
}

.top-title-text {
  font-size: 19px;
  font-weight: 700;
  color: var(--text-primary);
}

.help-icon-btn {
  width: 17px;
  height: 17px;
  line-height: 17px;
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  border: 1px solid #484F58;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.data-info-row {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.data-refresh {
  margin-left: auto;
  padding: 2px 10px;
  font-size: 11px;
  color: var(--accent-red);
  background: rgba(255, 71, 87, 0.1);
  border-radius: 12px;
  cursor: pointer;
}

.data-refresh.refreshing { opacity: 0.5; }

/* 筛选栏 */
.filter-bar {
  display: flex;
  gap: 6px;
  padding: 10px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  white-space: nowrap;
}

.filter-chip {
  flex-shrink: 0;
  padding: 5px 14px;
  background: var(--bg-card-hover);
  border-radius: 14px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
}

.filter-chip.active {
  background: var(--accent-red);
  color: #fff;
}

/* 表格容器 */
.eva-table-wrap {
  padding: 0 0 8px;
}

.eva-table-scroll {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

/* 表头 */
.eva-header-row {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 5;
  min-width: 900px;
}

/* 表格列 */
.col {
  flex-shrink: 0;
  font-size: 11px;
  text-align: center;
}

.col-name {
  width: 120px;
  text-align: left;
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.col-num {
  width: 70px;
}

.col-pct {
  width: 90px;
}

.col-status {
  width: 80px;
}

/* 可排序列 */
.sortable {
  cursor: pointer;
  user-select: none;
}

.sortable:hover {
  color: var(--accent-red);
}

.sorted {
  color: var(--accent-red);
}

/* 数据行 */
.eva-row {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  border-bottom: 1px solid rgba(48, 54, 61, 0.3);
  min-width: 900px;
  transition: background 0.1s;
}

.eva-row:hover {
  background: var(--bg-card-hover);
}

.row-even {
  background: rgba(22, 27, 34, 0.3);
}

.col-name {
  color: var(--text-primary);
  font-size: 12px;
}

.col-num {
  color: var(--text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.col-pct {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

/* 百分位颜色 */
.pct-low {
  color: var(--accent-red);
  font-weight: 600;
}

.pct-mid {
  color: #FFA502;
}

.pct-high {
  color: var(--accent-green);
  font-weight: 600;
}

/* 估值标签 */
.eva-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

/* 加载/空/错误状态 */
.loading-wrap {
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.loading-text {
  font-size: 13px;
  color: var(--text-muted);
}

.empty-state {
  text-align: center;
  padding: 60px 24px;
}

.empty-text {
  font-size: 15px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}

.empty-hint {
  font-size: 12px;
  color: var(--accent-red);
  cursor: pointer;
}

/* 底部说明 */
.bottom-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 24px 16px 48px;
}

.bottom-info span {
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.6;
}

/* ===== 弹窗通用 ===== */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 100;
}

.help-panel {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  max-height: 70vh;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}

.help-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.help-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.help-close {
  font-size: 16px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
}

.help-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 32px;
}

.help-section {
  margin-bottom: 14px;
}

.help-section-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.help-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.help-color-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}

.help-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.help-color-text {
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
  min-width: 90px;
}

.help-color-desc {
  font-size: 12px;
  color: var(--text-muted);
}
</style>
