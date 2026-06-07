<template>
  <div class="page-tougu">
    <!-- 头部 -->
    <div class="tougu-header">
      <div class="header-left">
        <div class="header-title-row">
          <span class="header-title">投顾产品精选</span>
          <span class="help-icon-btn" @click="showHelp = true">?</span>
        </div>
        <span class="header-desc" v-if="updateTime">
          截至 {{ updateTime }} · {{ totalCount }} 只产品
        </span>
        <span class="header-desc" v-else-if="loading">加载中...</span>
      </div>
      <div class="header-refresh" @click="loadData">
        <span class="refresh-text">{{ loading ? '刷新中' : '刷新' }}</span>
      </div>
    </div>

    <!-- 类型筛选 -->
    <div class="type-tabs">
      <div
        v-for="(t, idx) in types"
        :key="t.key"
        class="type-tab"
        :class="{ active: currentType === idx }"
        @click="switchType(idx)"
      >
        {{ t.name }}
      </div>
    </div>

    <!-- 列表 -->
    <div class="tougu-list" v-if="!loading">
      <!-- 有数据 -->
      <template v-if="list.length > 0">
        <div
          v-for="item in list"
          :key="item.id"
          class="tougu-card"
          @click="goDetail(item)"
        >
          <!-- 顶部：名称 + 管理人 + 类型标签 -->
          <div class="card-top">
            <div class="card-top-left">
              <div class="card-name-row">
                <span class="card-name">{{ item.name }}</span>
                <span
                  v-if="item.desc"
                  class="card-help-icon"
                  @click.stop="openItemHelp(item)"
                >?</span>
              </div>
              <span class="card-company">{{ item.company }}</span>
            </div>
            <div class="card-type-tag">{{ item.typeName || '--' }}</div>
          </div>

          <!-- 收益数据 -->
          <div class="card-returns">
            <div class="return-item">
              <span class="return-label">近3月</span>
              <span class="return-value" :class="pctClass(item.return3m)">
                {{ fmtPct(item.return3m) }}
              </span>
            </div>
            <div class="return-item">
              <span class="return-label">近1年</span>
              <span class="return-value" :class="pctClass(item.return1y)">
                {{ fmtPct(item.return1y) }}
              </span>
            </div>
            <div class="return-item">
              <span class="return-label">最大回撤</span>
              <span class="return-value" :class="item.maxDrawdown != null ? 'down' : ''">
                {{ fmtDrawdown(item.maxDrawdown) }}
              </span>
            </div>
          </div>
        </div>
      </template>

      <!-- 空状态 -->
      <div class="empty-state" v-else>
        <p class="empty-text">暂无投顾产品数据</p>
        <p class="empty-hint">数据正在积累中，敬请期待</p>
      </div>
    </div>

    <!-- 加载中 -->
    <div class="loading-wrap" v-if="loading">
      <span class="loading-text">正在加载投顾产品...</span>
    </div>

    <!-- 底部说明 -->
    <div class="footer-note" v-if="list.length > 0">仅供参考，不构成投资建议</div>

    <!-- 产品策略简介弹窗 -->
    <Teleport to="body">
      <template v-if="itemHelp">
        <div class="help-mask" @click="itemHelp = null"></div>
        <div class="help-panel item-help-panel">
          <div class="help-header">
            <span class="help-title">{{ itemHelp.name }}</span>
            <span class="help-close" @click="itemHelp = null">✕</span>
          </div>
          <div class="help-body">
            <div class="help-section" v-if="itemHelp.company">
              <span class="help-section-label">管理人</span>
              <span class="help-desc">{{ itemHelp.company }}</span>
            </div>
            <div class="help-section" v-if="itemHelp.typeName">
              <span class="help-section-label">分类</span>
              <span class="help-desc">{{ itemHelp.typeName }}</span>
            </div>
            <div class="help-section" v-if="itemHelp.desc">
              <span class="help-section-label">策略理念</span>
              <span class="help-desc">{{ itemHelp.desc }}</span>
            </div>
            <div class="help-section" v-if="itemHelp.tags && itemHelp.tags.length">
              <span class="help-section-label">策略标签</span>
              <div class="help-tags">
                <span class="help-tag" v-for="tag in itemHelp.tags" :key="tag">{{ tag }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 帮助说明弹窗 -->
    <Teleport to="body">
      <template v-if="showHelp">
        <div class="help-mask" @click="showHelp = false"></div>
        <div class="help-panel">
          <div class="help-header">
            <span class="help-title">投顾产品说明</span>
            <span class="help-close" @click="showHelp = false">✕</span>
          </div>
          <div class="help-body">
            <div class="help-section">
              <span class="help-section-label">数据来源</span>
              <span class="help-desc">天天基金投顾页面（fund.eastmoney.com/tg/），涵盖全市场投顾组合产品。</span>
            </div>
            <div class="help-section">
              <span class="help-section-label">分类规则</span>
              <span class="help-desc">追求高收益：默认分类</span>
              <span class="help-desc">稳健理财：含"固收/债券/低波"等关键词</span>
              <span class="help-desc">养老储蓄：含"养老/90后/80后"等关键词</span>
            </div>
            <div class="help-section">
              <span class="help-section-label">收益指标</span>
              <span class="help-desc">展示近3月、近1年收益率（阶段真实收益）及最大回撤。</span>
            </div>
            <div class="help-section">
              <span class="help-section-label">更新频率</span>
              <span class="help-desc">手动更新，当前数据截止时间请查看页面顶部。一般每周更新一次。</span>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchTouguProducts } from '../../api/data.js'

const types = [
  { name: '全部',     key: 'all'     },
  { name: '追求高收益', key: 'high'    },
  { name: '稳健理财', key: 'stable'  },
  { name: '养老储蓄', key: 'pension' },
]

const currentType = ref(0)
const list        = ref([])
const loading     = ref(false)
const updateTime  = ref('')
const totalCount  = ref(0)
const showHelp    = ref(false)
const itemHelp    = ref(null)

function fmtPct(val) {
  if (val == null) return '--'
  const pct = (val * 100).toFixed(2)
  return (val > 0 ? '+' : '') + pct + '%'
}

function fmtDrawdown(val) {
  if (val == null) return '--'
  return (val * 100).toFixed(2) + '%'
}

function pctClass(val) {
  if (val == null) return ''
  return val > 0 ? 'up' : val < 0 ? 'down' : ''
}

async function loadData() {
  if (loading.value) return
  loading.value = true
  try {
    const type = types[currentType.value].key
    const data = await fetchTouguProducts(type === 'all' ? {} : { type })
    list.value = data || []
    totalCount.value = list.value.length
    updateTime.value = list.value[0]?.updateDate || ''
  } catch (e) {
    console.error('[tougu] 加载失败', e)
    list.value = []
  } finally {
    loading.value = false
  }
}

function switchType(idx) {
  currentType.value = idx
  loadData()
}

function openItemHelp(item) {
  itemHelp.value = item
}

function goDetail(item) {
  if (item.url && item.url !== '#') {
    window.open(item.url, '_blank')
  }
}

onMounted(loadData)
</script>

<style scoped>
.page-tougu {
  min-height: 100vh;
}

/* 头部 */
.tougu-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  margin-bottom: 0;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.header-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.header-title {
  font-size: 17px;
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

.header-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.header-refresh {
  padding: 6px 14px;
  background: rgba(255, 82, 82, 0.12);
  border-radius: 14px;
  cursor: pointer;
  flex-shrink: 0;
}

.refresh-text {
  font-size: 12px;
  color: var(--color-up);
  font-weight: 500;
}

/* 类型筛选 */
.type-tabs {
  display: flex;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: var(--header-height);
  z-index: 20;
}

.type-tab {
  flex: 1;
  text-align: center;
  padding: 10px 0;
  font-size: 13px;
  color: var(--text-secondary);
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.type-tab.active {
  color: var(--color-up);
  font-weight: 600;
}

.type-tab.active::after {
  content: '';
  position: absolute;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 24px;
  height: 2px;
  background: var(--color-up);
  border-radius: 1px;
}

/* 列表 */
.tougu-list {
  padding: 8px;
}

/* 卡片 */
.tougu-card {
  padding: 14px;
  margin-bottom: 8px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
}

.tougu-card:hover {
  background: var(--bg-hover);
}

.card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 10px;
}

.card-top-left {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.card-name-row {
  display: flex;
  align-items: center;
  gap: 4px;
}

.card-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
}

.card-help-icon {
  width: 14px;
  height: 14px;
  line-height: 14px;
  text-align: center;
  font-size: 9px;
  color: var(--text-muted);
  border: 1px solid #484F58;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.card-company {
  font-size: 12px;
  color: var(--text-secondary);
}

.card-type-tag {
  flex-shrink: 0;
  padding: 3px 8px;
  background: rgba(255, 82, 82, 0.12);
  border-radius: 6px;
  font-size: 11px;
  color: var(--color-up);
  font-weight: 500;
}

/* 收益数据行 */
.card-returns {
  display: flex;
  justify-content: space-between;
  padding-top: 8px;
  border-top: 1px solid var(--border);
}

.return-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  flex: 1;
}

.return-label {
  font-size: 11px;
  color: var(--text-muted);
}

.return-value {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
}

.return-value.up   { color: var(--color-up);   }
.return-value.down { color: var(--color-down); }

/* 加载/空状态 */
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
  color: var(--text-muted);
}

/* 底部说明 */
.footer-note {
  text-align: center;
  padding: 16px;
  font-size: 11px;
  color: var(--text-muted);
}

/* ===== 弹窗 ===== */
.help-mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
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

.item-help-panel {
  max-height: 60vh;
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
  font-size: 18px;
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
  margin-bottom: 4px;
}

.help-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.help-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 4px;
}

.help-tag {
  font-size: 11px;
  color: var(--text-secondary);
  background: var(--bg-hover);
  border: 1px solid var(--border);
  padding: 3px 8px;
  border-radius: 6px;
}
</style>
