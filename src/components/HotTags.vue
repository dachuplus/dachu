<template>
  <div class="hot-tags-section">
    <!-- Tab 切换：热门基金（行业）/ 热门基金（概念） -->
    <div class="tags-header">
      <span class="tags-title">热门基金</span>
      <div class="tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'concept' }"
          @click="activeTab = 'concept'"
        >概念</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'industry' }"
          @click="activeTab = 'industry'"
        >行业</button>
      </div>
    </div>

    <!-- 标签网格 -->
    <div class="tags-grid" v-if="displayTags.length > 0">
      <div
        v-for="tag in displayTags"
        :key="tag.name"
        class="tag-cell"
        :style="{ background: tagColor(tag.return_pct) }"
        @click="openTagDetail(tag)"
      >
        <span class="tag-name">{{ tag.name }}</span>
        <span class="tag-return" v-if="tag.return_pct != null">{{ fmtPct(tag.return_pct) }}</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div class="tags-loading" v-if="loading && displayTags.length === 0">标签加载中...</div>

    <!-- 标签详情弹窗：关联基金列表 -->
    <Teleport to="body">
      <template v-if="selectedTag">
        <div class="mask" @click="selectedTag = null"></div>
        <div class="tag-detail-panel">
          <div class="detail-header">
            <span class="detail-title">
              {{ selectedTag.name }}
              <span class="detail-type-badge" :class="selectedTag.tag_type">{{ selectedTag.tag_type === 'concept' ? '概念' : '行业' }}</span>
              <span class="detail-return" v-if="selectedTag.return_pct != null">{{ fmtPct(selectedTag.return_pct) }}</span>
            </span>
            <span class="detail-close" @click="selectedTag = null">&#x2715;</span>
          </div>
          <div class="detail-body">
            <!-- 关联基金列表 -->
            <div class="funds-loading" v-if="tagFundsLoading">加载中...</div>
            <template v-else-if="tagFunds.length > 0">
              <div class="funds-count">共 {{ tagFunds.length }} 只关联基金</div>
              <div class="fund-tag-list">
                <div
                  v-for="f in tagFunds"
                  :key="f.c"
                  class="fund-tag-item"
                >
                  <a class="ft-code" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.c }}</a>
                  <a class="ft-name" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.n || ('基金' + f.c) }}</a>
                  <span class="ft-type" :title="f.t1_tt || f.t1">{{ f.t1_tt || f.t1 || '--' }}</span>
                  <span class="ft-ret" :style="{ color: retColor(f.r1y) }" v-if="f.r1y != null">{{ fmtRetPlain(f.r1y) }}%</span>
                  <span class="ft-score" :style="scoreColor(f.k1)" v-if="f.k1 != null">{{ Math.round(f.k1) }}</span>
                </div>
              </div>
            </template>
            <div class="funds-empty" v-else>
              <p>暂无关联基金数据</p>
              <p class="funds-empty-hint">可前往<a :href="eastmoneyTopicUrl(selectedTag.name)" target="_blank">天天基金</a>查看完整列表</p>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { fetchFundTags } from '../api/data.js'
import { fmtRetPlain, scoreColor } from '../utils/format.js'

const props = defineProps({
  /** 最大展示行数，默认显示全部 */
  maxRows: { type: Number, default: 0 },
})

// ========== 状态 ==========
const activeTab = ref('concept') // 'concept' | 'industry'
const allTags = ref([]) // [{ name, tag_type, return_pct, sort_order }]
const loading = ref(false)
const selectedTag = ref(null) // 当前选中的标签
const tagFunds = ref([]) // 标签关联的基金列表
const tagFundsLoading = ref(false)

// ========== 计算属性 ==========
const displayTags = computed(() => {
  const filtered = allTags.value.filter(t => t.tag_type === activeTab.value)
  if (props.maxRows > 0) {
    return filtered.slice(0, props.maxRows * 8) // 每行8个
  }
  return filtered
})

// ========== 方法 ==========
async function loadTags() {
  loading.value = true
  try {
    const data = await fetchFundTags()
    if (Array.isArray(data)) {
      allTags.value = data
    }
  } catch (e) {
    console.error('[HotTags] load error', e)
  } finally {
    loading.value = false
  }
}

function openTagDetail(tag) {
  selectedTag.value = tag
  tagFunds.value = []
  loadTagFunds(tag)
}

/** 从 fund_scores 表模糊匹配关联基金 */
async function loadTagFunds(tag) {
  tagFundsLoading.value = true
  try {
    // 通过 Supabase 查询：在 fund_combined 或 fund_scores 中搜索名称包含标签关键词的基金
    const { supabase } = await import('../api/supabase.js')
    if (!supabase) {
      tagFundsLoading.value = false
      return
    }

    // 策略：用标签名作为关键词搜索基金名称，限制返回20只
    const keyword = tag.name.replace(/[+&｜()（）]/g, '')
    const { data, error } = await supabase
      .from('fund_scores')
      .select('c,n,t0,t1,t1_tt,k1,r1y')
      .or(`n.ilike.%${keyword}%`)
      .order('k1', { ascending: false, nullsFirst: false })
      .limit(50)

    if (!error && data) {
      tagFunds.value = data
    }
  } catch (e) {
    console.error('[HotTags] loadTagFunds error', e)
  } finally {
    tagFundsLoading.value = false
  }
}

/** 颜色映射：根据收益率返回红粉渐变色 */
function tagColor(ret) {
  if (ret == null) return '#e8e8e8'
  const r = parseFloat(ret)
  if (isNaN(r)) return '#e8e8e8'
  // 截断到合理范围 [0, 600]
  const v = Math.min(Math.max(r, 0), 600)
  // 映射到颜色：
  //   0% → 浅粉 #ffe0e0
  //   100% → 珊瑚红 #ff8080
  //   300% → 红 #e04040
  //   600% → 深红 #c01010
  let ratio = v / 600
  const r_val = Math.round(255 - ratio * 60)       // 255 -> 195
  const g_val = Math.round(224 - ratio * 200)      // 224 -> 24
  const b_val = Math.round(224 - ratio * 210)      // 224 -> 14
  return `rgb(${r_val},${g_val},${b_val})`
}

function fmtPct(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (isNaN(n)) return ''
  return n.toFixed(2) + '%'
}

function retColor(v) {
  if (v == null) return 'var(--text-secondary)'
  const n = parseFloat(v)
  if (isNaN(n) || n === 0) return 'var(--text-secondary)'
  return n > 0 ? '#d4351c' : '#00703c'
}

function eastMoneyUrl(code) {
  if (!code) return '#'
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `https://fund.eastmoney.com/${pureCode}.html`
}

function eastmoneyTopicUrl(topicName) {
  return `https://fund.eastmoney.com/ztjj/#!syl/Y/curr/zf-${encodeURIComponent(topicName)}/fst/DESC`
}

// ========== 生命周期 ==========
onMounted(() => {
  loadTags()
})

// 暴露方法供父组件调用
defineExpose({ refresh: loadTags })
</script>

<style scoped>
.hot-tags-section {
  background: #ffffff;
  border-bottom: 1px solid var(--border);
}

/* 头部 */
.tags-header {
  display: flex;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  gap: var(--space-md);
}
.tags-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  flex-shrink: 0;
}
.tabs {
  display: flex;
  gap: 0;
}
.tab-btn {
  padding: 4px 14px;
  font-size: 14px;
  color: var(--link);
  cursor: pointer;
  border: 1px solid var(--border);
  background: #fff;
  text-decoration: none;
  transition: all 0.15s;
}
.tab-btn:hover { border-color: #1d70b8; }
.tab-btn.active {
  color: #fff;
  background: #1d70b8;
  border-color: #1d70b8;
  font-weight: 700;
}

/* 标签网格：8列布局，参考截图 */
.tags-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: var(--space-sm) var(--space-md) var(--space-md);
}
@media (max-width: 767px) {
  .tags-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 3px;
  }
}

.tag-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  min-height: 52px;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  border-radius: 2px;
  text-align: center;
}
.tag-cell:hover {
  opacity: 0.85;
  transform: scale(1.03);
}
.tag-cell:active {
  transform: scale(0.97);
}
.tag-name {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
  word-break: keep-all;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.tag-return {
  font-size: 11px;
  color: rgba(255,255,255,0.9);
  margin-top: 2px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.tags-loading {
  text-align: center;
  padding: var(--space-md);
  font-size: 14px;
  color: var(--text-secondary);
}

/* ===== 标签详情弹窗 ===== */
.tag-detail-panel {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 640px;
  max-height: 82vh;
  background: #ffffff;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 2px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  flex-shrink: 0;
}
.detail-type-badge.concept { background: #d4351c; }
.detail-type-badge.industry { background: #1d70b8; }
.detail-return {
  font-size: 16px;
  font-weight: 700;
  color: #d4351c;
  flex-shrink: 0;
}
.detail-close {
  font-size: 24px;
  color: var(--text-primary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  flex-shrink: 0;
}
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md) var(--space-lg);
}
.funds-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}
.fund-tag-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.fund-tag-item {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.fund-tag-item:last-child { border-bottom: none; }
.ft-code {
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
  color: var(--text-primary);
  min-width: 68px;
  text-decoration: none;
  flex-shrink: 0;
}
.ft-code:hover { color: var(--link); text-decoration: underline; }
.ft-name {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
  min-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
  flex: 1;
}
.ft-name:hover { color: var(--link); text-decoration: underline; }
.ft-type {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  max-width: 90px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ft-ret {
  font-size: 13px;
  font-weight: 700;
  width: 65px;
  text-align: right;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.ft-score {
  font-size: 14px;
  font-weight: 700;
  width: 32px;
  text-align: right;
  flex-shrink: 0;
}
.funds-loading, .funds-empty {
  text-align: center;
  padding: var(--space-xl) 0;
  color: var(--text-secondary);
  font-size: 15px;
}
.funds-empty p { margin: var(--space-xs) 0; }
.funds-empty-hint { font-size: 13px; }
.funds-empty a { color: var(--link); text-decoration: underline; }

.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }
</style>
