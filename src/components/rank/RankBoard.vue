<template>
  <div class="rb">
    <div class="rb-head">
      <h2 class="rb-title">{{ title }}</h2>
      <p v-if="intro" class="rb-intro">{{ intro }}</p>
      <p class="rb-count">共 {{ items.length }} 个条目 · 按总分排序 · 评分标准见文末</p>
    </div>

    <!-- 检索：独占一行 -->
    <div class="rb-search-row">
      <input
        v-model.trim="q"
        class="rb-search"
        type="search"
        :aria-label="`搜索${catLabel}或名称`"
        :placeholder="`搜索${catLabel}或名称`"
      />
    </div>

    <!-- 筛选 -->
    <div class="rb-chips">
      <span
        class="rb-chip"
        :class="{ active: activeCat === 'all' }"
        @click="activeCat = 'all'"
      >全部</span>
      <span
        v-for="c in cats"
        :key="c"
        class="rb-chip"
        :class="{ active: activeCat === c }"
        @click="activeCat = c"
      >{{ c }}</span>
    </div>

    <!-- 列表 -->
    <ol class="rb-list">
      <li v-for="it in shown" :key="it.name" class="rb-row">
        <div class="rb-row-main" @click="toggle(it.name)">
          <div class="rb-rank" :class="{ top3: it.rank <= 3 }">{{ it.rank }}</div>
          <div class="rb-info">
            <div class="rb-name">{{ it.name }}</div>
            <div class="rb-meta">{{ it.meta }}</div>
          </div>
          <div class="rb-total">{{ it.total }}</div>
          <div class="rb-caret" :class="{ open: openName === it.name }"></div>
        </div>

        <div v-if="openName === it.name" class="rb-detail">
          <p v-if="it.comment" class="rb-comment">{{ it.comment }}</p>
          <div class="rb-dims">
            <div v-for="(d, i) in dims" :key="d" class="rb-dim">
              <span class="rb-dim-label">{{ d }}</span>
              <span class="rb-dim-bar"><i :style="{ width: (scoreOf(it, i) * 10) + '%' }"></i></span>
              <span class="rb-dim-val">{{ scoreOf(it, i) }}</span>
            </div>
          </div>
          <div class="rb-detail-foot">
            <span>基础分 {{ it.base }}/90</span>
            <span class="rb-dot">·</span>
            <span>好创新 +{{ it.bonus }}</span>
            <span class="rb-dot">·</span>
            <span>总分 <b>{{ it.total }}</b>/100</span>
            <span class="rb-grade">{{ grade(it) }}</span>
          </div>
        </div>
      </li>
    </ol>

    <div v-if="shown.length < filtered.length" class="rb-more">
      <button class="rb-more-btn" @click="limit += 30">加载更多（还有 {{ filtered.length - shown.length }} 个）</button>
    </div>
    <p v-if="filtered.length === 0" class="rb-empty">没有匹配的条目。</p>

    <!-- 框架说明 -->
    <details class="rb-fw">
      <summary>评分框架说明（{{ frameworkName }}）</summary>
      <p class="rb-fw-text">{{ frameworkNote }}</p>
      <ul class="rb-fw-dims">
        <li v-for="(d, i) in dims" :key="d">
          <b>{{ d }}</b>{{ i < 9 ? '（基础项，0-10 分，缺失计 0）' : '（加分项，0-10 分，不创新不扣分）' }}
        </li>
      </ul>
      <p class="rb-fw-text">基础九项合计满分 90 分（54 分合格 / 72 分优秀 / 81 分顶尖）；加创新分后满分 100 分，超 90 分属罕见的「全能型佳作」。评分均为本站编辑评分，仅供参考。</p>
    </details>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  intro: { type: String, default: '' },
  items: { type: Array, required: true },   // [{ name, meta, cat, scores:[9], bonus, comment }]
  dims: { type: Array, required: true },     // 10 labels（第 10 个为「好创新」）
  catLabel: { type: String, default: '分类' },
  frameworkName: { type: String, default: '9+1 框架' },
  frameworkNote: { type: String, default: '' },
})

const activeCat = ref('all')
const q = ref('')
const limit = ref(30)
const openName = ref('')

const cats = computed(() => {
  const set = []
  for (const it of props.items) if (it.cat && !set.includes(it.cat)) set.push(it.cat)
  return set
})

/** 预处理：算基础分/总分并排序（总分降序，同分按基础分降序） */
const ranked = computed(() =>
  props.items
    .map((it) => {
      const base = it.scores.reduce((a, b) => a + b, 0)
      return { ...it, base, total: base + (it.bonus || 0) }
    })
    .sort((a, b) => b.total - a.total || b.base - a.base)
    .map((it, i) => ({ ...it, rank: i + 1 }))
)

const filtered = computed(() => {
  const kw = q.value
  return ranked.value.filter(
    (it) =>
      (activeCat.value === 'all' || it.cat === activeCat.value) &&
      (!kw || it.name.includes(kw) || (it.meta || '').includes(kw))
  )
})

const shown = computed(() => filtered.value.slice(0, limit.value))

function scoreOf(it, i) {
  return i < 9 ? (it.scores[i] || 0) : (it.bonus || 0)
}
function grade(it) {
  if (it.total > 90) return '全能型佳作'
  if (it.base >= 81) return '顶尖'
  if (it.base >= 72) return '优秀'
  if (it.base >= 54) return '合格'
  return '待提升'
}
function toggle(name) {
  openName.value = openName.value === name ? '' : name
}
</script>

<style scoped>
.rb { padding: 0; }
.rb-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
.rb-intro { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin: 0 0 6px; }
.rb-count { font-size: 13px; color: var(--text-muted); margin: 0 0 14px; }

.rb-search-row { margin-bottom: 10px; }
.rb-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 14px; }
.rb-chip {
  font-size: 13px; padding: 4px 12px; cursor: pointer;
  border: 1px solid var(--border); color: var(--text-secondary); background: var(--bg-card);
  white-space: nowrap;
}
.rb-chip.active { background: #1d70b8; border-color: #1d70b8; color: #fff; font-weight: 700; }
.rb-search {
  display: block; width: 100%; font-size: 14px; padding: 8px 10px;
  border: 1px solid var(--border); background: var(--bg-card); color: var(--text-primary);
}

.rb-list { list-style: none; margin: 0; padding: 0; }
.rb-row { border: 1px solid var(--border); border-left: 6px solid #1d70b8; margin-bottom: 8px; background: var(--bg-card); }
.rb-row-main { display: flex; align-items: center; gap: 12px; padding: 12px 14px; cursor: pointer; }
.rb-rank { flex: none; width: 30px; text-align: center; font-size: 17px; font-weight: 700; color: var(--text-muted); }
.rb-rank.top3 { color: #1d70b8; font-size: 20px; }
.rb-info { flex: 1; min-width: 0; }
.rb-name { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.rb-meta { font-size: 13px; color: var(--text-secondary); margin-top: 3px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rb-total { flex: none; background: #1d70b8; color: #fff; font-size: 16px; font-weight: 700; padding: 5px 10px; min-width: 48px; text-align: center; }
.rb-caret { flex: none; width: 0; height: 0; border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #1d70b8; transition: transform 0.15s; }
.rb-caret.open { transform: rotate(180deg); }

.rb-detail { padding: 0 14px 14px 56px; border-top: 1px solid var(--border); }
.rb-comment { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin: 12px 0; }
.rb-dims { display: flex; flex-direction: column; gap: 6px; }
.rb-dim { display: flex; align-items: center; gap: 10px; font-size: 13px; }
.rb-dim-label { flex: none; width: 62px; color: var(--text-secondary); }
.rb-dim-bar { flex: 1; height: 8px; background: #e5e5e5; }
.rb-dim-bar i { display: block; height: 100%; background: #1d70b8; }
.rb-dim-val { flex: none; width: 22px; text-align: right; font-weight: 700; color: var(--text-primary); }
.rb-detail-foot { margin-top: 12px; font-size: 13px; color: var(--text-secondary); display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.rb-detail-foot b { color: #1d70b8; }
.rb-dot { color: var(--text-muted); }
.rb-grade { background: #f3f2f1; color: #0b0c0c; font-size: 12px; font-weight: 700; padding: 1px 8px; }

.rb-more { text-align: center; margin: 16px 0; }
.rb-more-btn { background: var(--bg-card); border: 1px solid #1d70b8; color: #1d70b8; font-size: 14px; font-weight: 700; padding: 9px 18px; cursor: pointer; }
.rb-more-btn:hover { background: #1d70b8; color: #fff; }
.rb-empty { text-align: center; color: var(--text-secondary); padding: 30px 0; }

.rb-fw { margin-top: 22px; border-top: 1px solid var(--border); padding-top: 14px; }
.rb-fw summary { font-size: 14px; font-weight: 700; color: #1d70b8; cursor: pointer; }
.rb-fw-text { font-size: 13px; color: var(--text-secondary); line-height: 1.7; margin: 10px 0; }
.rb-fw-dims { margin: 8px 0; padding-left: 18px; }
.rb-fw-dims li { font-size: 13px; color: var(--text-secondary); line-height: 1.8; }
.rb-fw-dims b { color: var(--text-primary); }

@media (max-width: 640px) {
  .rb-detail { padding-left: 14px; }
}
</style>
