<template>
  <div class="me">
    <div class="me-head">
      <h2 class="me-title">{{ title }}</h2>
      <p v-if="intro" class="me-intro">{{ intro }}</p>
      <p class="me-count">
        共 {{ items.length }} 条上榜记录 · 覆盖 {{ coveredYears.length }} 个年份<template v-if="coveredYears.length">（{{ yearRange }}）</template> · {{ shops.length }} 家餐厅
      </p>
    </div>

    <!-- 视图切换 -->
    <div class="me-modes">
      <button class="me-mode" :class="{ active: mode === 'year' }" @click="mode = 'year'">按年份浏览</button>
      <button class="me-mode" :class="{ active: mode === 'shop' }" @click="mode = 'shop'">按餐厅聚合</button>
    </div>

    <!-- 检索：独占一行 -->
    <div class="me-search-row">
      <input
        v-model.trim="q"
        class="me-search"
        type="search"
        aria-label="搜索餐厅 / 区域 / 品类"
        placeholder="搜索餐厅 / 区域 / 品类"
      />
    </div>

    <!-- 筛选：年份 -->
    <div class="me-chips me-chips--year">
      <span class="me-chip" :class="{ active: activeYear === 'all' }" @click="activeYear = 'all'">全部年份</span>
      <span
        v-for="y in coveredYears"
        :key="y"
        class="me-chip"
        :class="{ active: activeYear === y }"
        @click="activeYear = y"
      >{{ y }}</span>
    </div>
    <div v-if="districts.length" class="me-chips me-chips--dist">
      <span class="me-chip" :class="{ active: activeDistrict === 'all' }" @click="activeDistrict = 'all'">全部区域</span>
      <span
        v-for="d in districts"
        :key="d"
        class="me-chip"
        :class="{ active: activeDistrict === d }"
        @click="activeDistrict = d"
      >{{ d }}</span>
    </div>
    <p v-if="districts.length && noDistrictCount" class="me-dist-hint">
      注：分区信息来自官方分区名单，目前仅 {{ distYears.join('、') }} 年有权威分区来源；
      其余年份多为整榜名单、未标注行政区，共 {{ noDistrictCount }} 条记录无分区，按区域筛选时不会出现。
    </p>

    <!-- 按年份浏览 -->
    <template v-if="mode === 'year'">
      <div v-for="g in yearGroups" :key="g.year" class="me-group">
        <h3 class="me-group-title">
          {{ g.year }} 年
          <span class="me-group-count">{{ g.list.length }} 家</span>
        </h3>
        <ol class="me-list">
          <li v-for="it in yearRows(g)" :key="g.year + '-' + it.name" class="me-row">
            <div class="me-row-main">
              <span class="me-year">{{ g.year }}</span>
              <div class="me-info">
                <div class="me-name">
                  {{ it.name }}
                  <span v-if="countOf(it.name) >= 2" class="me-repeat">上榜 {{ countOf(it.name) }} 次</span>
                </div>
                <div v-if="metaOf(it)" class="me-meta">{{ metaOf(it) }}</div>
              </div>
            </div>
          </li>
        </ol>
        <div v-if="g.list.length > YEAR_PREVIEW" class="me-more">
          <button class="me-more-btn" @click="toggleYear(g.year)">
            {{ yearAll[g.year]
              ? '收起本年名单'
              : `展开本年全部 ${g.list.length} 家（其余 ${g.list.length - YEAR_PREVIEW} 家）` }}
          </button>
        </div>
      </div>
      <p v-if="yearGroups.length === 0" class="me-empty">没有匹配的餐厅。</p>
    </template>

    <!-- 按餐厅聚合 -->
    <template v-else>
      <ol class="me-list">
        <li v-for="s in shopShown" :key="s.name" class="me-row">
          <div class="me-row-main">
            <span class="me-year">{{ s.years.length }}次</span>
            <div class="me-info">
              <div class="me-name">
                {{ s.name }}
                <span class="me-repeat">累计上榜 {{ s.years.length }} 次</span>
              </div>
              <div class="me-meta">
                <template v-if="metaOf(s)">{{ metaOf(s) }} · </template>{{ s.years.join(' · ') }}
              </div>
            </div>
          </div>
        </li>
      </ol>
      <div v-if="shopShown.length < shopList.length" class="me-more">
        <button class="me-more-btn" @click="shopLimit += 30">加载更多（还有 {{ shopList.length - shopShown.length }} 家）</button>
      </div>
      <p v-if="shopList.length === 0" class="me-empty">没有匹配的餐厅。</p>
    </template>

    <!-- 数据说明（来源与覆盖度） -->
    <details v-if="coverageNote || sources.length" class="me-fw">
      <summary>数据来源与覆盖说明</summary>
      <p v-if="coverageNote" class="me-fw-text">{{ coverageNote }}</p>
      <ul v-if="sources.length" class="me-fw-dims">
        <li v-for="s in sources" :key="s.year" class="me-fw-year">
          <div>
            <b>{{ s.year }} 年</b>
            <span class="me-fw-count">收录 {{ s.count }} 家</span>
            <span v-if="s.fact" class="me-fw-fact">{{ s.fact }}</span>
          </div>
          <div v-if="s.note" class="me-fw-note">{{ s.note }}</div>
          <div v-if="s.urls && s.urls.length" class="me-fw-links">
            <a
              v-for="(u, i) in s.urls"
              :key="u"
              :href="u"
              target="_blank"
              rel="noopener noreferrer"
              class="me-src"
            >来源{{ i + 1 }}</a>
          </div>
        </li>
      </ul>
      <p class="me-fw-text">本站仅做公开信息整理，属非官方汇编，榜单归属与解释权均属大众点评；收录条目以官方实际发布为准，本页不代表官方立场，也不构成消费建议。</p>
    </details>
  </div>
</template>

<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  intro: { type: String, default: '' },
  /** [{ name, year, district, category }] —— 一条 = 该店该年上榜一次 */
  items: { type: Array, required: true },
  coverageNote: { type: String, default: '' },
  /** [{ year, urls: ['https://...'] }] */
  sources: { type: Array, default: () => [] },
})

const mode = ref('year')
const activeYear = ref('all')
const activeDistrict = ref('all')
const q = ref('')

const coveredYears = computed(() => {
  const set = new Set(props.items.map((x) => x.year).filter(Boolean))
  return [...set].sort((a, b) => b - a)
})
const yearRange = computed(() => {
  const ys = coveredYears.value
  if (!ys.length) return ''
  return ys.length === 1 ? String(ys[0]) : `${ys[ys.length - 1]}–${ys[0]}`
})
const districts = computed(() => {
  const set = []
  for (const it of props.items) if (it.district && !set.includes(it.district)) set.push(it.district)
  return set.sort()
})

/** 无分区字段的记录数（用于「区域筛选覆盖不全」的说明） */
const noDistrictCount = computed(() => props.items.filter((x) => !x.district).length)

/** 哪些年份带分区来源（升序）——说明文案里动态展示，避免写死 */
const distYears = computed(() => {
  const ys = new Set()
  for (const it of props.items) if (it.district) ys.add(it.year)
  return [...ys].sort((a, b) => a - b)
})

/** 餐厅名 → 累计上榜次数（跨年份） */
const repeatMap = computed(() => {
  const m = new Map()
  for (const it of props.items) m.set(it.name, (m.get(it.name) || 0) + 1)
  return m
})
function countOf(name) {
  return repeatMap.value.get(name) || 0
}

/** 匹配当前筛选条件的基础记录 */
const base = computed(() =>
  props.items.filter((it) => {
    if (activeYear.value !== 'all' && it.year !== activeYear.value) return false
    if (activeDistrict.value !== 'all' && it.district !== activeDistrict.value) return false
    if (q.value) {
      const hay = `${it.name} ${it.district || ''} ${it.category || ''}`
      if (!hay.includes(q.value)) return false
    }
    return true
  })
)

/** 单条记录的副标题：区 · 品类 */
function metaOf(it) {
  const parts = []
  if (it.district) parts.push(it.district)
  if (it.category) parts.push(it.category)
  return parts.join(' · ')
}

/** 视图一：按年份分组（年份倒序，组内保持原始顺序） */
const yearGroups = computed(() => {
  const map = new Map()
  for (const it of base.value) {
    if (!map.has(it.year)) map.set(it.year, [])
    map.get(it.year).push(it)
  }
  return [...map.entries()]
    .sort((a, b) => b[0] - a[0])
    .map(([year, list]) => ({ year, list }))
})

/** 视图二：按餐厅聚合，按上榜次数降序 */
const shopList = computed(() => {
  const map = new Map()
  for (const it of base.value) {
    if (!map.has(it.name)) map.set(it.name, { name: it.name, years: [], district: it.district, category: it.category })
    map.get(it.name).years.push(it.year)
  }
  const list = [...map.values()].map((s) => {
    s.years.sort((a, b) => a - b)
    return s
  })
  return list.sort((a, b) => b.years.length - a.years.length || b.years[b.years.length - 1] - a.years[a.years.length - 1])
})

/** 去重后的全部餐厅（模板用 .length 取家数） */
const shops = computed(() => [...new Set(props.items.map((x) => x.name))])

/**
 * 渐进展示：必吃榜共 800+ 条记录，一次性铺开会把页面拉得极长。
 * 按年份视图：每年先渲染 20 条，其余点「展开本年全部」再出；
 * 按餐厅聚合视图：先渲染 30 家，其余点「加载更多」。
 */
const YEAR_PREVIEW = 20
const yearAll = ref({})
function yearRows(g) {
  return yearAll.value[g.year] ? g.list : g.list.slice(0, YEAR_PREVIEW)
}
function toggleYear(y) {
  yearAll.value = { ...yearAll.value, [y]: !yearAll.value[y] }
}

const shopLimit = ref(30)
const shopShown = computed(() => shopList.value.slice(0, shopLimit.value))

// 改筛选条件后回到收拢态，避免「展开状态」与筛选结果错位
watch([activeYear, activeDistrict, q, mode], () => {
  yearAll.value = {}
  shopLimit.value = 30
})
</script>

<style scoped>
.me { padding: 0; }
.me-title { font-size: 22px; font-weight: 700; color: var(--text-primary); margin: 0 0 6px; }
.me-intro { font-size: 14px; color: var(--text-secondary); line-height: 1.6; margin: 0 0 6px; }
.me-count { font-size: 13px; color: var(--text-muted); margin: 0 0 14px; }

.me-modes { display: flex; gap: 0; margin-bottom: 14px; }
.me-mode {
  font-size: 14px; padding: 8px 16px; cursor: pointer;
  border: 1px solid var(--border); background: var(--bg-card); color: var(--text-secondary);
}
.me-mode + .me-mode { border-left: none; }
.me-mode.active { background: #1d70b8; border-color: #1d70b8; color: #fff; font-weight: 700; }

.me-search-row { margin-bottom: 10px; }
.me-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.me-chips--year { margin-bottom: 8px; }
.me-chips--dist { margin-bottom: 14px; }
.me-dist-hint {
  font-size: 12px; line-height: 1.6; color: var(--text-muted);
  margin: 0 0 12px; padding-left: 10px; border-left: 3px solid var(--border);
}
.me-chip {
  font-size: 13px; padding: 4px 12px; cursor: pointer;
  border: 1px solid var(--border); color: var(--text-secondary); background: var(--bg-card);
  white-space: nowrap;
}
.me-chip.active { background: #1d70b8; border-color: #1d70b8; color: #fff; font-weight: 700; }
.me-search {
  display: block; width: 100%; font-size: 14px; padding: 8px 10px;
  border: 1px solid var(--border); background: var(--bg-card); color: var(--text-primary);
}

.me-group { margin-bottom: 18px; }
.me-group-title {
  font-size: 16px; font-weight: 700; color: var(--text-primary);
  margin: 0 0 8px; padding-bottom: 6px; border-bottom: 2px solid #1d70b8;
}
.me-group-count { font-size: 13px; font-weight: 400; color: var(--text-muted); margin-left: 6px; }

.me-list { list-style: none; margin: 0; padding: 0; }
.me-row { border: 1px solid var(--border); border-left: 6px solid #1d70b8; margin-bottom: 6px; background: var(--bg-card); }
.me-row-main { display: flex; align-items: center; gap: 12px; padding: 10px 14px; }
.me-year {
  flex: none; min-width: 46px; text-align: center; font-size: 13px; font-weight: 700;
  color: #fff; background: #1d70b8; padding: 3px 6px;
}
.me-info { flex: 1; min-width: 0; }
.me-name { font-size: 15px; font-weight: 700; color: var(--text-primary); }
.me-repeat { font-size: 12px; font-weight: 700; color: #0b0c0c; background: #f3f2f1; padding: 1px 8px; margin-left: 8px; }
.me-meta { font-size: 13px; color: var(--text-secondary); margin-top: 3px; }

.me-empty { text-align: center; color: var(--text-secondary); padding: 30px 0; }

.me-more { text-align: center; margin: 12px 0 4px; }
.me-more-btn {
  background: var(--bg-card); border: 1px solid #1d70b8; color: #1d70b8;
  font-size: 13px; font-weight: 700; padding: 8px 16px; cursor: pointer;
}
.me-more-btn:hover { background: #1d70b8; color: #fff; }

.me-fw { margin-top: 22px; border-top: 1px solid var(--border); padding-top: 14px; }
.me-fw summary { font-size: 14px; font-weight: 700; color: #1d70b8; cursor: pointer; }
.me-fw-text { font-size: 13px; color: var(--text-secondary); line-height: 1.7; margin: 10px 0; }
.me-fw-dims { margin: 8px 0; padding-left: 18px; }
.me-fw-dims li { font-size: 13px; color: var(--text-secondary); line-height: 1.7; }
.me-fw-dims b { color: var(--text-primary); }
.me-fw-year { margin-bottom: 10px; }
.me-fw-count { font-size: 12px; font-weight: 700; color: #fff; background: #1d70b8; padding: 1px 7px; margin-left: 8px; }
.me-fw-fact { color: var(--text-muted); margin-left: 8px; }
.me-fw-note { margin-top: 4px; color: var(--text-secondary); }
.me-fw-links { margin-top: 4px; }
.me-src { color: #1d70b8; margin-right: 10px; }
</style>
