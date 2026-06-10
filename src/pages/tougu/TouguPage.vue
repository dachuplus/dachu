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
/* ========== gov.uk 风格投顾产品 ========== */
.page-tougu { min-height: 100vh; }

/* 头部 */
.tougu-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: #ffffff;
}
.header-left { display: flex; flex-direction: column; }
.header-title-row { display: flex; align-items: center; gap: 6px; }
.header-title { font-size: 24px; font-weight: 700; color: var(--text-primary); }
@media (min-width: 641px) { .header-title { font-size: 36px; } }
.help-icon-btn {
  width: 24px; height: 24px; line-height: 24px; text-align: center;
  font-size: 14px; color: var(--text-secondary);
  border: 2px solid var(--text-secondary); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
}
.header-desc { font-size: 14px; color: var(--text-secondary); }
.header-refresh { cursor: pointer; }
.refresh-text { font-size: 16px; color: var(--link); text-decoration: underline; }

/* 类型筛选 */
.type-tabs {
  display: flex; border-bottom: 2px solid var(--border);
  position: sticky; top: var(--header-height); z-index: 20;
  background: #ffffff;
}
.type-tab {
  flex: 1; text-align: center; padding: var(--space-sm) 0;
  font-size: 16px; color: var(--link); cursor: pointer;
  border-bottom: 4px solid transparent;
}
.type-tab.active {
  color: #1d70b8; font-weight: 700; border-bottom-color: #1d70b8;
}

/* 列表 */
.tougu-list { padding: 0; }
.tougu-card {
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: #ffffff; cursor: pointer; transition: background 0.1s;
}
.tougu-card:hover { background: #f8f8f8; }
.card-top { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: var(--space-sm); }
.card-top-left { flex: 1; }
.card-name-row { display: flex; align-items: center; gap: 4px; }
.card-name { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.card-help-icon {
  width: 18px; height: 18px; line-height: 18px; text-align: center;
  font-size: 11px; color: var(--text-secondary);
  border: 2px solid var(--text-secondary); cursor: pointer;
  display: inline-flex; align-items: center; justify-content: center;
}
.card-company { font-size: 14px; color: var(--text-secondary); }
.card-type-tag {
  flex-shrink: 0; padding: 2px 8px; font-size: 14px;
  color: #0b0c0c; font-weight: 700; background: #f3f2f1;
}

.card-returns {
  display: flex; justify-content: space-between;
  padding-top: var(--space-sm); border-top: 1px solid var(--border);
}
.return-item { display: flex; flex-direction: column; align-items: center; flex: 1; }
.return-label { font-size: 14px; color: var(--text-secondary); }
.return-value { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.return-value.up   { color: var(--color-up); }
.return-value.down { color: var(--color-down); }

.loading-wrap { display: flex; justify-content: center; padding: var(--space-2xl) 0; }
.loading-text { font-size: 16px; color: var(--text-secondary); }
.empty-state { text-align: center; padding: var(--space-2xl); }
.empty-text { font-size: 19px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); }
.empty-hint { font-size: 16px; color: var(--text-secondary); }
.footer-note {
  text-align: left; padding: var(--space-xl); font-size: 14px; color: var(--text-secondary);
  border-top: 1px solid var(--border);
}

/* 弹窗 */
.help-mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }
.help-panel {
  position: fixed; bottom: 0; left: 50%; transform: translateX(-50%);
  width: 100%; max-width: 600px; max-height: 70vh;
  background: #ffffff; border: 1px solid var(--border);
  overflow: hidden; display: flex; flex-direction: column; z-index: 101;
}
.item-help-panel { max-height: 60vh; }
.help-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: var(--space-md) var(--space-lg); border-bottom: 1px solid var(--border);
  background: #f3f2f1; flex-shrink: 0;
}
.help-title { font-size: 19px; font-weight: 700; color: var(--text-primary); }
.help-close { font-size: 24px; color: var(--text-primary); cursor: pointer; line-height: 1; }
.help-body { flex: 1; overflow-y: auto; padding: var(--space-lg); }
.help-section { margin-bottom: var(--space-lg); }
.help-section-label { display: block; font-size: 19px; font-weight: 700; margin-bottom: var(--space-sm); border-bottom: 2px solid var(--border); padding-bottom: 4px; }
.help-desc { display: block; font-size: 16px; color: var(--text-primary); line-height: 1.7; }
.help-tags { display: flex; flex-wrap: wrap; gap: var(--space-sm); margin-top: var(--space-sm); }
.help-tag {
  font-size: 14px; color: var(--text-secondary);
  border: 1px solid var(--border); padding: 2px 8px;
}
</style>
