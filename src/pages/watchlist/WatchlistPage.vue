<template>
  <div class="watchlist">
    <h1 class="govuk-heading-l">自选基金</h1>

    <!-- 顶部操作栏 -->
    <div v-if="favorites.length" class="toolbar">
      <span class="count text-muted">共 {{ favorites.length }} 只</span>
      <button class="btn-clear" type="button" @click="onClear">清空</button>
    </div>

    <!-- 加载态 -->
    <div v-if="loading" class="state">加载中...</div>

    <!-- 空态 -->
    <div v-else-if="!favorites.length" class="state empty">
      <p>还没有关注基金，去 <router-link to="/tools/fund-rank">选基</router-link> 页点☆关注吧</p>
    </div>

    <!-- 列表 -->
    <div v-else class="card">
      <div
        v-for="item in rows"
        :key="item.c"
        class="row"
      >
        <div class="row-main">
          <div class="name">{{ item.name || '--' }}</div>
          <div class="meta text-muted">
            <span>{{ item.c || '--' }}</span>
            <span v-if="item.t0"> · {{ item.t0 }}</span>
          </div>
        </div>

        <div class="row-score">
          <div class="score-label text-muted">综合分</div>
          <div class="score-value">{{ item.k_all != null ? item.k_all : '--' }}</div>
        </div>

        <div class="row-return">
          <div class="return-label text-muted">近1年</div>
          <div
            class="return-value"
            :class="{
              'text-up': isUp(item.r1y),
              'text-down': isDown(item.r1y)
            }"
          >{{ formatReturn(item.r1y) }}</div>
        </div>

        <button class="btn-remove" type="button" :aria-label="'移除 ' + (item.name || item.c)" @click="onRemove(item.c)">移除</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { supabase } from '../../api/supabase'
import { useFavorites } from '../../composables/useFavorites'

const { favorites, removeFav, clear } = useFavorites()

const loading = ref(false)
// 每行：收藏项 + 来自 fund_scores 的评分（缺失字段为 undefined）
const rows = ref([])

function isUp(v) {
  return typeof v === 'number' && v > 0
}
function isDown(v) {
  return typeof v === 'number' && v < 0
}
function formatReturn(v) {
  if (typeof v !== 'number') return '--'
  const sign = v > 0 ? '+' : ''
  return sign + v.toFixed(2) + '%'
}

async function fetchScores() {
  if (!favorites.value.length) {
    rows.value = []
    loading.value = false
    return
  }
  loading.value = true
  const codes = favorites.value.map(f => f.c)

  // 以收藏项为基础，保证顺序与去重；评分缺失的项字段为空
  const base = favorites.value.map(f => ({ ...f, k_all: undefined, r1y: undefined }))

  if (supabase) {
    try {
      const { data, error } = await supabase
        .from('fund_scores')
        .select('c,name,t0,k_all,score_grade,r1m,r3m,r6m,r1y,r3y,r5y')
        .in('c', codes)

      if (!error && data) {
        const byCode = Object.fromEntries(data.map(d => [d.c, d]))
        rows.value = base.map(f => {
          const s = byCode[f.c]
          return s ? { ...f, name: s.name, t0: s.t0, k_all: s.k_all, r1y: s.r1y } : { ...f, k_all: undefined, r1y: undefined }
        })
      } else {
        rows.value = base
      }
    } catch (e) {
      rows.value = base
    }
  } else {
    rows.value = base
  }

  loading.value = false
}

function onRemove(c) {
  removeFav(c)
}

function onClear() {
  clear()
}

onMounted(fetchScores)
// 收藏变更时（移除/清空）重新构建列表
watch(favorites, fetchScores, { deep: true })
</script>

<style scoped>
.watchlist {
  padding: var(--space-lg);
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}

.count {
  font-size: 14px;
}

.btn-clear {
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 2px;
  color: var(--color-up);
  padding: 6px 14px;
  font-size: 14px;
  cursor: pointer;
}

.btn-clear:hover {
  background: #f3f2f1;
}

.state {
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: var(--space-lg);
  color: var(--text-secondary);
  text-align: center;
}

.state.empty a {
  color: #1d70b8;
  text-decoration: underline;
}

.card {
  border: 1px solid var(--border);
  border-radius: 2px;
}

.row {
  display: flex;
  align-items: center;
  gap: var(--space-md);
  padding: var(--space-md) var(--space-lg);
  border-bottom: 1px solid var(--border);
}

.row:last-child {
  border-bottom: none;
}

.row-main {
  flex: 1 1 auto;
  min-width: 0;
}

.name {
  font-weight: 700;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.meta {
  font-size: 13px;
  margin-top: 2px;
}

.row-score,
.row-return {
  text-align: right;
  flex: 0 0 auto;
  width: 64px;
}

.score-label,
.return-label {
  font-size: 12px;
}

.score-value {
  font-weight: 700;
  color: var(--text-primary);
  font-size: 18px;
}

.return-value {
  font-weight: 700;
  font-size: 16px;
}

.btn-remove {
  flex: 0 0 auto;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 2px;
  color: var(--text-secondary);
  padding: 6px 12px;
  font-size: 13px;
  cursor: pointer;
}

.btn-remove:hover {
  color: var(--color-up);
  border-color: var(--color-up);
}
</style>
