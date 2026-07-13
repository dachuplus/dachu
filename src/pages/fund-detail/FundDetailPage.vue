<template>
  <div class="fund-detail">
    <button class="back-btn" type="button" @click="goBack">返回</button>

    <template v-if="loaded && fund">
      <!-- 头部卡片 -->
      <section class="card header-card">
        <h1 class="fund-name">{{ fund.name }}</h1>
        <div class="fund-code">{{ fund.c }}</div>
        <div class="fund-tag" v-if="fund.t0 || fund.t1">
          <span class="tag" v-if="fund.t0">{{ fund.t0 }}</span>
          <span class="tag" v-if="fund.t1">{{ fund.t1 }}</span>
        </div>
        <div class="fund-company" v-if="company">{{ company }}</div>
      </section>

      <!-- 评分卡 -->
      <section class="card score-card">
        <div class="score-label">综合评分</div>
        <div class="score-value">{{ fund.k_all ?? '--' }}</div>
        <span class="grade-badge" :class="'grade-' + fund.score_grade">
          {{ gradeText(fund.score_grade) }}
        </span>
      </section>

      <!-- 收益表 -->
      <section class="card return-card">
        <h2 class="card-title">阶段收益(%)</h2>
        <table class="return-table">
          <tbody>
            <tr v-for="row in returnRows" :key="row.label">
              <td class="row-label">{{ row.label }}</td>
              <td class="row-value" :class="valueClass(row.value)">
                {{ formatValue(row.value) }}
              </td>
            </tr>
          </tbody>
        </table>
      </section>
    </template>

    <!-- 空态 -->
    <div class="empty-state card" v-else-if="loaded && !fund">
      <p>未找到该基金数据</p>
    </div>

    <!-- 加载态 -->
    <div class="loading card" v-else>
      <p>加载中…</p>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { supabase } from '../../api/supabase'

const route = useRoute()
const router = useRouter()

const fund = ref(null)
const company = ref(null)
const loaded = ref(false)

const SCORE_FIELDS = 'c,name,t0,t1,t1_tt,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,daily_change,k_all,score_grade'

async function fetchFund(code) {
  // 先精确匹配，再尝试补 .OF 后缀
  let { data } = await supabase
    .from('fund_scores')
    .select(SCORE_FIELDS)
    .eq('c', code)
    .single()

  if (!data) {
    const { data: data2 } = await supabase
      .from('fund_scores')
      .select(SCORE_FIELDS)
      .eq('c', code + '.OF')
      .single()
    data = data2
  }

  if (!data) return null

  // 取公司名（容错；最高风控规则：所有取基金均查 fund_scores）
  const { data: cb } = await supabase
    .from('fund_scores')
    .select('c,company')
    .eq('c', data.c)
    .single()
  company.value = cb?.company ?? null

  return data
}

function gradeText(g) {
  return { green: '优秀', blue: '良好', orange: '中等', gray: '待观察' }[g] || '—'
}

function valueClass(v) {
  if (v === null || v === undefined) return ''
  return v > 0 ? 'up' : v < 0 ? 'down' : ''
}

function formatValue(v) {
  if (v === null || v === undefined) return '--'
  return (v > 0 ? '+' : '') + v
}

const returnRows = computed(() => {
  if (!fund.value) return []
  const f = fund.value
  return [
    { label: '当日', value: f.daily_change },
    { label: '近1周', value: f.r0w },
    { label: '近1月', value: f.r1m },
    { label: '近3月', value: f.r3m },
    { label: '近6月', value: f.r6m },
    { label: '近1年', value: f.r1y },
    { label: '近2年', value: f.r2y },
    { label: '近3年', value: f.r3y },
    { label: '近5年', value: f.r5y }
  ]
})

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/tools/fund-rank')
  }
}

onMounted(async () => {
  const code = route.params.code
  if (code && supabase) {
    fund.value = await fetchFund(code)
  }
  loaded.value = true
})
</script>

<style scoped>
.fund-detail {
  padding: var(--space-lg);
  max-width: 720px;
  margin: 0 auto;
}

.back-btn {
  margin-bottom: var(--space-md);
  padding: var(--space-sm) var(--space-md);
  background: transparent;
  border: 1px solid var(--border);
  border-radius: 2px;
  color: var(--text-secondary);
  font-size: 14px;
  cursor: pointer;
}

.card {
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: var(--space-lg);
  margin-bottom: var(--space-md);
  background: #fff;
}

.header-card .fund-name {
  margin: 0 0 var(--space-sm);
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.fund-code {
  color: var(--text-secondary);
  font-size: 14px;
  margin-bottom: var(--space-sm);
}

.fund-tag {
  display: flex;
  gap: var(--space-sm);
  flex-wrap: wrap;
}

.tag {
  font-size: 12px;
  color: var(--text-secondary);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: 2px var(--space-sm);
}

.fund-company {
  margin-top: var(--space-md);
  font-size: 14px;
  color: var(--text-primary);
}

.score-card {
  display: flex;
  align-items: center;
  gap: var(--space-lg);
}

.score-label {
  font-size: 14px;
  color: var(--text-secondary);
}

.score-value {
  font-size: 48px;
  font-weight: 700;
  line-height: 1;
  color: var(--text-primary);
}

.grade-badge {
  font-size: 13px;
  color: #fff;
  border-radius: 2px;
  padding: var(--space-sm) var(--space-md);
}

.grade-green { background: #00703c; }
.grade-blue { background: #1d70b8; }
.grade-orange { background: #f47738; }
.grade-gray { background: #505a66; }

.card-title {
  margin: 0 0 var(--space-md);
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.return-table {
  width: 100%;
  border-collapse: collapse;
}

.return-table td {
  padding: var(--space-sm) 0;
  border-bottom: 1px solid var(--border);
  font-size: 15px;
}

.return-table tr:last-child td {
  border-bottom: none;
}

.row-label {
  color: var(--text-secondary);
}

.row-value {
  text-align: right;
  color: var(--text-primary);
}

.row-value.up { color: var(--color-up); }
.row-value.down { color: var(--color-down); }

.empty-state,
.loading {
  text-align: center;
  color: var(--text-secondary);
}
</style>
