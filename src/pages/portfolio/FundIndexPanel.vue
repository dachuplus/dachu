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
          @click="sub = t.key"
        >{{ t.label }}</button>
      </div>
    </div>

    <div class="fi-note" v-if="sub !== 'basic' && !hasRealData">
      数据说明：指数数据来源于东方财富（akshare），包含宽基、策略及行业主题等14只核心市场指数的行情表现与历史收益。
    </div>

    <div class="fi-loading" v-if="loading">加载中…</div>

    <div class="fi-table-wrap" v-else>
      <!-- 基本信息 -->
      <table class="fi-table" v-if="sub === 'basic'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>年初至今</th><th>发布日期</th>
            <th>成分数量</th><th>加权方式</th><th>收益方式</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td :class="trendCls(r.basic_info && r.basic_info.ytd)">{{ pct(r.basic_info && r.basic_info.ytd) }}</td>
            <td>{{ fmtDate(r.basic_info && r.basic_info.issuing_date) }}</td>
            <td>{{ num(r.basic_info && r.basic_info.ingredient_num) }}</td>
            <td>{{ r.basic_info && r.basic_info.weighting_mode || '—' }}</td>
            <td>{{ r.basic_info && r.basic_info.return_mode || '—' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 市场表现 -->
      <table class="fi-table" v-else-if="sub === 'market'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>YTD</th><th>近1周</th><th>近1月</th>
            <th>近3月</th><th>近1年</th><th>近3年</th><th>近5年</th><th>成立以来</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td :class="trendCls(mp(r,'ytd'))">{{ pct(mp(r,'ytd')) }}</td>
            <td :class="trendCls(mp(r,'r1w'))">{{ pct(mp(r,'r1w')) }}</td>
            <td :class="trendCls(mp(r,'r1m'))">{{ pct(mp(r,'r1m')) }}</td>
            <td :class="trendCls(mp(r,'r3m'))">{{ pct(mp(r,'r3m')) }}</td>
            <td :class="trendCls(mp(r,'r1y'))">{{ pct(mp(r,'r1y')) }}</td>
            <td :class="trendCls(mp(r,'r3y'))">{{ pct(mp(r,'r3y')) }}</td>
            <td :class="trendCls(mp(r,'r5y'))">{{ pct(mp(r,'r5y')) }}</td>
            <td :class="trendCls(mp(r,'since_inception'))">{{ pct(mp(r,'since_inception')) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 历年表现 -->
      <table class="fi-table" v-else-if="sub === 'annual'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th>
            <th v-for="y in annualYears" :key="y">{{ y }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td
              v-for="y in annualYears"
              :key="y"
              :class="trendCls(ap(r, y))"
            >{{ pct(ap(r, y)) }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 估值分析 -->
      <table class="fi-table" v-else-if="sub === 'valuation'">
        <thead>
          <tr>
            <th>代码</th><th>名称</th><th>YTD</th><th>总市值</th><th>流通市值</th>
            <th>市盈率</th><th>净利率</th><th>股息率</th><th>Beta</th><th>波动率</th><th>换手率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="r in rows" :key="r.wind_code">
            <td class="mono">{{ r.wind_code }}</td>
            <td>{{ r.name_cn }}</td>
            <td :class="trendCls(vp(r,'ytd'))">{{ pct(vp(r,'ytd')) }}</td>
            <td>{{ bigNum(vp(r,'total_mv')) }}</td>
            <td>{{ bigNum(vp(r,'float_mv')) }}</td>
            <td>{{ num(vp(r,'pe')) }}</td>
            <td>{{ pct(vp(r,'net_margin')) }}</td>
            <td>{{ pct(vp(r,'dividend_yield')) }}</td>
            <td>{{ num(vp(r,'beta')) }}</td>
            <td>{{ pct(vp(r,'volatility')) }}</td>
            <td>{{ pct(vp(r,'turnover')) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { supabase } from '../../api/supabase'

const subTabs = [
  { key: 'basic', label: '基本信息' },
  { key: 'market', label: '市场表现' },
  { key: 'annual', label: '历年表现' },
  { key: 'valuation', label: '估值分析' },
]
const sub = ref('basic')
const rows = ref([])
const loading = ref(true)
const hasRealData = ref(false)

// 历年表现展示绝对年份（与 Wind 截图一致：2026→2017）
const annualYears = [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017]
// Wind 相对年字段 -> 绝对年映射：ytd=2026, year1=2025, ..., year9=2017
const yearKeyMap = { 2026: 'ytd', 2025: 'year1', 2024: 'year2', 2023: 'year3', 2022: 'year4', 2021: 'year5', 2020: 'year6', 2019: 'year7', 2018: 'year8', 2017: 'year9' }

function mp(r, k) { return r.market_perf ? r.market_perf[k] : null }
function vp(r, k) { return r.valuation ? r.valuation[k] : null }
function ap(r, y) {
  if (!r.annual_perf) return null
  return r.annual_perf[yearKeyMap[y]] ?? null
}

function pct(v) {
  if (v == null || v === '' || isNaN(Number(v))) return '—'
  return (Number(v) >= 0 ? '+' : '') + Number(v).toFixed(2) + '%'
}
function num(v) {
  if (v == null || v === '' || isNaN(Number(v))) return '—'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function bigNum(v) {
  if (v == null || isNaN(Number(v))) return '—'
  const n = Number(v)
  if (n >= 1e12) return (n / 1e12).toFixed(2) + '万亿'
  if (n >= 1e8) return (n / 1e8).toFixed(2) + '亿'
  return num(v)
}
function fmtDate(v) {
  if (!v) return '—'
  return String(v).replace(/^(\d{4})(\d{2})(\d{2})$/, '$1-$2-$3')
}
function trendCls(v) {
  if (v == null || isNaN(Number(v))) return ''
  return Number(v) >= 0 ? 'up' : 'down'
}

onMounted(async () => {
  loading.value = true
  try {
    if (supabase) {
      const { data, error } = await supabase
        .from('fund_indices')
        .select('*')
        .order('category')
        .order('name_cn')
      if (!error && data) {
        rows.value = data
        // 有真实行情数据时隐藏提示
        hasRealData.value = data.some(r => r.market_perf && Object.keys(r.market_perf).length > 0)
      }
    }
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
.fi-subtab.active { background: #1d70b8; color: #fff; }
.fi-note {
  background: #fff4e6; border-left: 3px solid #f47738; padding: 8px 12px;
  font-size: 12px; color: #6b3e00; margin-bottom: var(--space-md); line-height: 1.6;
}
.fi-loading { padding: 40px; text-align: center; color: #505a66; }
.fi-table-wrap { overflow-x: auto; border: 1px solid var(--border); }
.fi-table { width: 100%; border-collapse: collapse; font-size: 13px; min-width: 720px; }
.fi-table th, .fi-table td { padding: 9px 12px; text-align: right; white-space: nowrap; border-bottom: 1px solid #f3f2f1; }
.fi-table th { background: #f3f2f1; color: #505a66; font-weight: 700; position: sticky; top: 0; }
.fi-table td:first-child, .fi-table th:first-child,
.fi-table td:nth-child(2), .fi-table th:nth-child(2) { text-align: left; }
.fi-table tbody tr:hover { background: #f8fafc; }
.fi-table .mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; color: #1d70b8; }
.fi-table .up { color: #cf1322; font-weight: 600; }
.fi-table .down { color: #009a44; font-weight: 600; }
</style>
