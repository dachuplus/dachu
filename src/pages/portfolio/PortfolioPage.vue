<template>
  <div class="page-portfolio">

    <!-- 四 Tab 导航 -->
    <div class="pf-tabs">
      <div
        v-for="tab in tabs" :key="tab.key"
        class="pf-tab"
        :class="{ active: activeTab === tab.key }"
        @click="switchTab(tab.key)"
      >{{ tab.label }}</div>
    </div>

    <!-- ==================== 1. 自建组合 ==================== -->
    <div v-if="activeTab === 'custom'">
      <!-- 未登录提示 -->
      <div class="card" v-if="!isLoggedIn">
        <div class="card-title">自建组合</div>
        <p class="card-desc">登录后可创建和管理自己的智能组合</p>
        <button class="btn-primary" @click="showLogin">登录 / 注册</button>
      </div>

      <!-- 已登录：组合列表 -->
      <template v-else>
        <div class="pf-actions">
          <button class="btn-primary" @click="showCreateModal = true">+ 新建组合</button>
        </div>

        <!-- 组合列表 -->
        <div class="card" v-for="pf in customPortfolios" :key="pf.id">
          <div class="pf-card-hd">
            <span class="pf-card-name" @click="editPortfolio(pf)">{{ pf.name }}</span>
            <span class="pf-card-date">{{ pf.updated_at?.slice(0,10) || pf.created_at?.slice(0,10) }}</span>
            <button class="pf-card-del" @click.stop="deletePf(pf.id)">删除</button>
          </div>

          <!-- 组合持仓 -->
          <div class="pf-holdings" v-if="pf.portfolio_data && pf.portfolio_data.length > 0">
            <div class="pf-holding-item" v-for="(h, idx) in pf.portfolio_data" :key="h.code">
              <div class="pf-hold-left">
                <span class="pf-hold-idx">{{ idx + 1 }}</span>
                <span class="pf-hold-name">{{ h.name }}</span>
                <span class="pf-hold-code">{{ h.code }}</span>
                <span class="pf-hold-cat" v-if="holdMetaMap[h.code]">
                  <span class="pf-meta-cat" :title="'基金二级分类'">{{ holdMetaMap[h.code].cat }}</span>
                  <span class="pf-meta-score">1年评分 {{ fmtScore2(holdMetaMap[h.code].score) }}</span>
                  <span class="pf-meta-rank" v-if="holdMetaMap[h.code].rank != null">1年评分排名 {{ holdMetaMap[h.code].rank }}/{{ holdMetaMap[h.code].total }}</span>
                  <span class="pf-meta-rank pf-meta-na" v-else>1年评分排名 --</span>
                </span>
              </div>
              <div class="pf-hold-right">
                <input
                  type="number" class="pf-weight-input"
                  :value="h.weight" min="0" max="100"
                  @change="e => updateWeight(pf.id, h.code, Number(e.target.value))"
                />%
                <span class="pf-hold-nav" v-if="h.nav">净值 {{ h.nav }}</span>
              </div>
            </div>
          </div>
          <div class="pf-empty" v-else>
            <span>暂无持仓 — 在靠谱指数页面将基金添加到组合</span>
          </div>

          <!-- 组合汇总 -->
          <div class="pf-summary" v-if="pf.portfolio_data && pf.portfolio_data.length > 0">
            <span>共 {{ pf.portfolio_data.length }} 只基金</span>
          </div>

          <!-- 组合区间收益 -->
          <div class="pf-returns" v-if="pf.portfolio_data && pf.portfolio_data.length > 0 && pf._returns">
            <div class="pf-returns-title">组合区间收益</div>
            <div class="pf-returns-grid">
              <div
                class="pf-ret-cell"
                v-for="col in RETURN_COLS"
                :key="col.key"
              >
                <div class="pf-ret-label">{{ col.label }}</div>
                <div class="pf-ret-value" :class="retClass(pf._returns[col.key])">
                  {{ fmtRet(pf._returns[col.key]) }}
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 无组合 -->
        <div class="card empty-card" v-if="customPortfolios.length === 0">
          <span>还没有组合，点击"+ 新建组合"开始创建</span>
        </div>
      </template>

      <!-- 新建组合弹窗 -->
      <div class="modal-overlay" v-if="showCreateModal" @click.self="showCreateModal = false">
        <div class="modal-box">
          <div class="modal-title">新建组合</div>
          <input v-model="newPfName" class="modal-input" placeholder="组合名称" />
          <div class="modal-btns">
            <button class="btn-secondary" @click="showCreateModal = false">取消</button>
            <button class="btn-primary" @click="createPortfolio" :disabled="!newPfName.trim()">创建</button>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 2. AI 组合 ==================== -->
    <div v-if="activeTab === 'ai'">
      <div class="card ai-card">
        <div class="card-title">DeepSeek AI 自动建组合</div>
        <p class="card-desc">选择投资策略，AI 分析当前市场并生成定制化智能组合</p>

        <div class="ai-strategies">
          <button
            v-for="st in AI_STRATEGIES"
            :key="st.key"
            class="ai-st-btn"
            :class="{ active: aiStrategy === st.key }"
            :disabled="aiGenerating"
            @click="selectStrategy(st.key)"
          >
            {{ st.label }}
            <span class="ai-st-desc">{{ st.desc }}</span>
          </button>
          <button
            class="ai-st-btn"
            :class="{ active: showCategoryPicker }"
            :disabled="aiGenerating"
            @click="toggleCategoryPicker"
          >
            分类组合
            <span class="ai-st-desc">按品类智能选基</span>
          </button>
          <button class="ai-st-btn ai-custom-st-btn" @click="openCustom" :disabled="aiGenerating">
            自定义
            <span class="ai-st-desc">输入你的要求</span>
          </button>
        </div>

        <!-- 分类组合：选择二级分类（含货币型） -->
        <div class="ai-cat-picker" v-if="showCategoryPicker">
          <div class="ai-cat-picker-hd">选择二级分类（含货币型），AI 将自动生成该品类组合</div>
          <div class="ai-cat-grid">
            <button
              v-for="cat in AI_ALL_CATEGORIES"
              :key="cat"
              class="ai-cat-chip"
              :disabled="aiGenerating"
              @click="pickCategory(cat)"
            >{{ cat }}</button>
          </div>
        </div>

        <div class="ai-action">
          <button class="ai-generate-btn" :disabled="aiGenerating" @click="generateAiPortfolio">
            <span v-if="aiGenerating">AI 分析中...</span>
            <span v-else>生成 AI 组合</span>
          </button>
          <span class="ai-status" v-if="aiStatusText">{{ aiStatusText }}</span>
        </div>

        <!-- 自定义弹窗 -->
        <div class="modal-overlay" v-if="showCustomDialog" @click.self="showCustomDialog = false">
          <div class="modal-box">
            <div class="modal-title">自定义 AI 组合要求</div>
            <textarea v-model="customRequirement" class="modal-textarea" placeholder="例如：我想配置一个防守型的养老组合，重点配置债券和红利基金，不要科技类..." rows="4"></textarea>
            <div class="modal-btns">
              <button class="btn-secondary" @click="showCustomDialog = false">取消</button>
              <button class="btn-primary" @click="generateAiPortfolio()" :disabled="aiGenerating">提交生成</button>
            </div>
          </div>
        </div>

        <div class="ai-result" v-if="aiPortfolio && aiPortfolio.funds">
          <div class="ai-result-hd">
            <span class="ai-result-title">AI 推荐组合 — {{ aiPortfolio.strategyName }}</span>
            <span class="ai-result-date">{{ aiPortfolio.createdAt }}</span>
          </div>
          <p class="ai-summary">{{ aiPortfolio.summary }}</p>

          <div class="ai-funds">
            <div class="ai-fund-item" v-for="f in aiPortfolio.funds" :key="f.code">
              <div class="ai-fund-left">
                <span class="ai-fund-name">{{ f.name }}</span>
                <span class="ai-fund-code">{{ f.code }}</span>
                <span class="ai-fund-cat" v-if="holdMetaMap[f.code]">
                  <span class="pf-meta-cat" :title="'基金二级分类'">{{ holdMetaMap[f.code].cat }}</span>
                  <span class="pf-meta-score">1年评分 {{ fmtScore2(holdMetaMap[f.code].score) }}</span>
                  <span class="pf-meta-rank" v-if="holdMetaMap[f.code].rank != null">1年评分排名 {{ holdMetaMap[f.code].rank }}/{{ holdMetaMap[f.code].total }}</span>
                  <span class="pf-meta-rank pf-meta-na" v-else>1年评分排名 --</span>
                </span>
              </div>
              <div class="ai-fund-right">
                <span class="ai-fund-weight">{{ f.weight }}%</span>
                <span class="ai-fund-reason">{{ f.reason }}</span>
              </div>
            </div>
          </div>

          <div class="ai-backtest" v-if="aiPortfolio.backtest">
            <div class="ai-bt-title">历史回测</div>
            <div class="ai-bt-grid">
              <div class="ai-bt-item">
                <span class="ai-bt-label">年化收益</span>
                <span class="ai-bt-val" :class="aiPortfolio.backtest.annualReturn > 0 ? 'text-up' : 'text-down'">
                  {{ aiPortfolio.backtest.annualReturn > 0 ? '+' : '' }}{{ aiPortfolio.backtest.annualReturn }}%
                </span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">最大回撤</span>
                <span class="ai-bt-val text-down">{{ aiPortfolio.backtest.maxDrawdown }}%</span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">夏普比率</span>
                <span class="ai-bt-val">{{ aiPortfolio.backtest.sharpe }}</span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">胜率</span>
                <span class="ai-bt-val">{{ aiPortfolio.backtest.winRate }}%</span>
              </div>
            </div>
          </div>
          <div class="ai-add-row">
            <button class="btn-primary" @click="addAiToCustom">+ 添加到自建组合</button>
          </div>
        </div>

        <div class="ai-history" v-if="aiHistory.length > 0">
          <div class="card-title" style="font-size:19px; margin-top:20px">历史 AI 组合</div>
          <div class="ai-hist-item" v-for="h in aiHistory" :key="h.id" @click="loadAiFromHistory(h)">
            <span class="ai-hist-name">{{ h.strategyName }}</span>
            <span class="ai-hist-date">{{ h.createdAt }}</span>
            <span class="ai-hist-count">{{ h.funds?.length || 0 }}只基金</span>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 3. 专家组合 ==================== -->
    <div v-if="activeTab === 'model'">
      <div class="data-status" v-if="loading">
        <span>正在计算权重...</span>
      </div>
      <div class="data-status" v-else-if="dataDate">
        <span>数据截止：{{ dataDate }}</span>
        <span class="weight-source">{{ weightSource }}</span>
      </div>

      <div class="card" v-if="!loading && portfolioItems.length > 0">
        <div class="card-title">Kan &amp; Zhou 增强型风险平价</div>
        <div ref="pieChartRef" class="risk-pie"></div>
      </div>

      <div class="card" v-for="group in portfolioItems" :key="group.assetKey">
        <div class="card-title">{{ group.category }}（{{ group.weight }}%）</div>
        <div class="etf-list">
          <div class="etf-loading" v-if="group.loading"><span>正在筛选靠谱ETF...</span></div>
          <div class="etf-empty" v-else-if="group.noEtf"><span>建议配置货币基金或活期存款</span></div>
          <div class="etf-empty" v-else-if="group.etfs.length === 0"><span>该分类暂无ETF数据</span></div>
          <template v-else>
            <div class="etf-item" v-for="etf in group.etfs" :key="etf.code">
              <div class="etf-header">
                <div class="etf-name-wrap">
                  <span class="etf-name">{{ etf.name }}</span>
                  <span class="etf-code">{{ etf.code }}</span>
                </div>
                <div class="etf-weight-wrap">
                  <span class="etf-weight">{{ etf.weight }}%</span>
                  <span class="etf-score">靠谱 {{ fmtScore(etf.k1) }}</span>
                </div>
              </div>
              <div class="etf-reason">
                <span>{{ etf.reason }}</span>
                <span v-if="etf.r3y" class="etf-return" :class="etf.r3y > 0 ? 'text-up' : 'text-down'">
                  近3年 {{ etf.r3y > 0 ? '+' : '' }}{{ etf.r3y.toFixed(2) }}%
                </span>
              </div>
            </div>
          </template>
        </div>
      </div>

      <div class="footer-note">
        <span>权重由 Kan & Zhou 增强型风险平价模型实时计算 | ETF按靠谱指数精选 | 仅供学习，不构成投资建议</span>
      </div>
    </div>

    <!-- ==================== 4. 基金指数 ==================== -->
    <div v-if="activeTab === 'index'">
      <FundIndexPanel />
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, onBeforeUnmount, nextTick, watch } from 'vue'
import { supabase } from '../../api/supabase'
import { fetchValue500All } from '../../utils/api'
import { getCategoryRankInfo, getCategoryRankInfoByScore } from '../../api/data.js'
import { getIndexQuotes, buildMarketData, parseValue500Data } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights } from '../../utils/calc'
import { useAuth } from '../../composables/useAuth'
import { toast, confirm } from '../../composables/useToast.js'
import { createPortfolio as savePortfolioToDb, deletePortfolio } from '../../api/user-data'
import FundIndexPanel from './FundIndexPanel.vue'
import echarts from '../../utils/echarts-setup'
import { COLORS } from '../../utils/echarts-theme'

const {
  user, isLoggedIn,
  portfolios: customPortfolios,
  refreshUserData, showLogin
} = useAuth()

// ===== Tab =====
const tabs = [
  { key: 'custom', label: '自建组合' },
  { key: 'ai', label: 'AI 组合' },
  { key: 'model', label: '专家组合' },
  { key: 'index', label: '基金指数' }
]
const activeTab = ref('custom')

function switchTab(key) {
  activeTab.value = key
  if (key === 'model' && portfolioItems.value.length === 0) buildPortfolio()
  if (key === 'custom' && isLoggedIn.value) loadCustomPortfolios()
}

// ===== 组合成份基金的细分品类内排名 =====
const catRankMap = ref({})
function fmtCatRank(info) {
  if (!info || !info.cat) return ''
  if (info.rank == null) return info.cat
  return `${info.cat} ${info.rank}|${info.total}`
}

// 持仓基金的「分类 + 1年评分(k1) + 细分品类排名」映射（按 k1 降序排名）
const holdMetaMap = ref({})
function fmtScore2(v) {
  if (v == null) return '--'
  return Number(v).toFixed(1)
}
async function enrichRanks() {
  const codes = new Set()
  customPortfolios.value.forEach(pf => (pf.portfolio_data || []).forEach(h => h.code && codes.add(h.code)))
  if (aiPortfolio.value?.funds) aiPortfolio.value.funds.forEach(f => f.code && codes.add(f.code))
  if (codes.size === 0) { catRankMap.value = {}; holdMetaMap.value = {}; return }
  try {
    catRankMap.value = await getCategoryRankInfo([...codes])
    holdMetaMap.value = await getCategoryRankInfoByScore([...codes], 'k1')
  } catch (e) {
    catRankMap.value = {}
    holdMetaMap.value = {}
  }
}

// ===== 自建组合 =====
const showCreateModal = ref(false)
const newPfName = ref('')

async function loadCustomPortfolios() {
  await refreshUserData()
  await enrichRanks()
  loadPortfolioReturns()
}

async function createPortfolio() {
  if (!newPfName.value.trim()) return
  const name = newPfName.value.trim()
  showCreateModal.value = false
  newPfName.value = ''

  // 持久化到 Supabase
  const result = await savePortfolioToDb(name, [])
  if (!result.success) {
    toast('创建失败: ' + (result.error || '未知错误'), 'error')
    return
  }

  // 同步到本地状态（使用 DB 返回的真实 ID）
  customPortfolios.value.unshift(result.data || {
    id: Date.now().toString(),
    name,
    portfolio_data: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  })
  toast('组合已创建', 'success')
}

async function deletePf(id) {
  const ok = await confirm('确定删除？', '将删除该组合及其所有持仓信息，该操作不可撤销。')
  if (!ok) return
  await deletePortfolio(id)
  customPortfolios.value = customPortfolios.value.filter(p => p.id !== id)
  toast('组合已删除', 'success')
}

function editPortfolio(pf) {
  // 跳转到靠谱指数页面添加基金
  // 这里简单切换 tab 或不做操作
}

function updateWeight(pfId, code, weight) {
  const pf = customPortfolios.value.find(p => p.id === pfId)
  if (!pf) return
  const item = (pf.portfolio_data || []).find(i => i.code === code)
  if (item) {
    item.weight = Math.max(0, Math.min(100, weight || 0))
    // 权重变更后实时重算组合区间收益（无需重新请求）
    if (pf._fundReturns) pf._returns = buildPortfolioReturns(pf.portfolio_data, pf._fundReturns)
  }
}

// ===== 组合区间收益（基于持仓基金真实区间收益率按权重加权） =====
// 列定义：key 对应 fund_scores 字段；label 为展示名
const RETURN_COLS = [
  { key: 'daily_change', label: '当日' },
  { key: 'r0w', label: '近1周' },
  { key: 'r1m', label: '近1月' },
  { key: 'r3m', label: '近3月' },
  { key: 'r6m', label: '近6月' },
  { key: 'r1y', label: '近1年' },
  { key: 'r2y', label: '近2年' },
  { key: 'r3y', label: '近3年' },
  { key: 'r5y', label: '近5年' },
  { key: 'r10y', label: '近10年' }
]
// 严格列：组合内任一成分基金该周期数据缺失（即基金成立不满该周期），整列显示 --
const STRICT_COLS = { r3y: true, r5y: true }

// 按持仓权重加权计算组合各周期收益率
// 返回 { key: number | null }，null 表示应显示 --
function buildPortfolioReturns(holdings, fundMap) {
  const matched = holdings.filter(h => fundMap[h.code])
  if (matched.length === 0) return null
  const items = matched.map(h => ({ weight: Number(h.weight) || 0, fund: fundMap[h.code] }))
  const result = {}
  for (const col of RETURN_COLS) {
    const vals = items.map(it => ({ w: it.weight, v: it.fund[col.key] }))
    // 严格列：任一成分缺失 → 整列 --
    if (STRICT_COLS[col.key] && vals.some(x => x.v == null)) { result[col.key] = null; continue }
    // 其余列：按有权值的成分加权（缺失成分忽略，权重归一化）
    let wsum = 0, vsum = 0, has = false
    for (const x of vals) {
      if (x.v == null) continue
      wsum += x.w
      vsum += x.w * x.v
      has = true
    }
    result[col.key] = has && wsum > 0 ? +(vsum / wsum).toFixed(2) : null
  }
  return result
}

// 区间收益展示格式：null → '--'，否则带符号百分比
function fmtRet(v) {
  if (v == null) return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}
// 涨跌配色：涨=红，跌=绿，缺失=灰（A股习惯）
function retClass(v) {
  if (v == null) return 'ret-na'
  return v > 0 ? 'ret-pos' : (v < 0 ? 'ret-neg' : 'ret-flat')
}

// 拉取组合内成分基金的区间收益字段，并计算组合加权收益
// 说明：场外基金(.OF)取自 fund_scores；场内基金(ETF/LOF，无 .OF 后缀)取自 etf_returns
//       （fund_scores/fund_combined 均不含场内基金，需单独数据源）
async function loadPortfolioReturns() {
  if (!supabase) return
  for (const pf of customPortfolios.value) {
    const codes = (pf.portfolio_data || []).map(h => h.code).filter(Boolean)
    if (codes.length === 0) { pf._returns = null; pf._fundReturns = {}; continue }
    const ofCodes = codes.filter(c => c.includes('.'))   // 场外 .OF
    const etfCodes = codes.filter(c => !c.includes('.'))  // 场内 ETF/LOF
    try {
      const fundMap = {}
      if (ofCodes.length > 0) {
        const { data } = await supabase.from('fund_scores')
          .select('c,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,r10y,daily_change')
          .in('c', ofCodes)
        ;(data || []).forEach(f => { fundMap[f.c] = f })
      }
      if (etfCodes.length > 0) {
        const { data } = await supabase.from('etf_returns')
          .select('c,r0w,r1m,r3m,r6m,r1y,r2y,r3y,r5y,r10y,daily_change')
          .in('c', etfCodes)
        ;(data || []).forEach(f => { fundMap[f.c] = f })
      }
      pf._fundReturns = fundMap
      pf._returns = buildPortfolioReturns(pf.portfolio_data, fundMap)
    } catch (e) {
      console.error('[portfolioReturns]', pf.id, e)
      pf._returns = null
    }
  }
}

// ===== AI 组合（复用已有逻辑） =====
const AI_STRATEGIES = [
  { key: 'balanced',       label: '均衡配置',    desc: '股债平衡，风险可控' },
  { key: 'aggressive',     label: '积极成长',    desc: '高仓位权益，追求高收益' },
  { key: 'defensive',      label: '稳健防御',    desc: '低波动，保值优先' },
  { key: 'value',          label: '价值投资',    desc: '低估值+高股息' },
  { key: 'growth',         label: '成长精选',    desc: '高景气赛道+创新' },
  { key: 'income',         label: '红利收入',    desc: '高分红+稳定现金流' },
  { key: 'momentum',       label: '趋势追踪',    desc: '跟随市场动量' },
  { key: 'quality',        label: '质量优选',    desc: '高ROE+优质基本面' },
  { key: 'fixed_value',    label: '固收+价值',   desc: '债基打底+价值权益增强' },
  { key: 'fixed_growth',   label: '固收+成长',   desc: '债基打底+成长权益增强' },
  { key: 'fixed_tech',     label: '固收+科技',   desc: '债基打底+科技主题增强' },
  { key: 'fixed_multi',    label: '固收+多资产', desc: '债基打底+多资产分散' },
  { key: 'fixed_index',    label: '固收+指数',   desc: '债基打底+指数ETF增强' },
  { key: 'fixed_div',      label: '固收+红利',   desc: '债基打底+红利策略增强' },
  { key: 'technology',     label: '科技主题',    desc: '聚焦半导体/AI/新能源' },
  { key: 'consumption',    label: '消费主题',    desc: '必选+可选消费龙头' },
]
const aiCategory = ref('')
const aiStrategy = ref('balanced')

// 全部二级分类（含货币型），用于「分类组合」选择器
const AI_ALL_CATEGORIES = [
  '混合型-偏股', '混合型-灵活', '混合型-偏债', '混合型-平衡', '混合型-绝对收益',
  '指数型-股票', '指数型-固收', '指数型-海外股票', '指数型-其他',
  '债券型-长债', '债券型-混合二级', '债券型-混合一级', '债券型-中短债', '债券型-利率债', '债券型-信用债',
  '股票型',
  'FOF-稳健型', 'FOF-均衡型', 'FOF-进取型',
  'QDII-混合偏股', 'QDII-普通股票', 'QDII-纯债', 'QDII-混合灵活', 'QDII-混合债', 'QDII-商品', 'QDII-FOF', 'QDII-REITs', 'QDII-混合平衡',
  '货币型'
]
const showCategoryPicker = ref(false)
const aiCategoryMode = ref(false)
function selectStrategy(key) {
  aiStrategy.value = key
  aiCategory.value = ''
  aiCategoryMode.value = false
}
function toggleCategoryPicker() {
  showCategoryPicker.value = !showCategoryPicker.value
  if (showCategoryPicker.value) aiCategoryMode.value = false
}
function openCustom() {
  aiCategoryMode.value = false
  showCustomDialog.value = true
}
function pickCategory(cat) {
  aiCategory.value = cat
  aiCategoryMode.value = true
  showCategoryPicker.value = false
  generateAiPortfolio()
}

const aiGenerating = ref(false)
const aiStatusText = ref('')
const aiPortfolio = ref(null)
const aiHistory = ref([])
const AI_STORAGE_KEY = 'allfund_ai_portfolios'

function loadAiHistory() {
  try { const r = localStorage.getItem(AI_STORAGE_KEY); aiHistory.value = r ? JSON.parse(r) : [] } catch { aiHistory.value = [] }
}
function saveAiToHistory(pf) {
  const h = [...aiHistory.value]; h.unshift(pf); if (h.length > 10) h.length = 10
  aiHistory.value = h; localStorage.setItem(AI_STORAGE_KEY, JSON.stringify(h))
}
function loadAiFromHistory(pf) { aiPortfolio.value = pf; enrichRanks() }

// ==== 自定义弹窗 ====
const showCustomDialog = ref(false)
const customRequirement = ref('')

async function generateAiPortfolio() {
  if (aiGenerating.value) return
  aiGenerating.value = true
  aiStatusText.value = '正在查询高分靠谱基金...'
  try {
    // 1. 从 Supabase 获取高分靠谱基金（规模>2亿；可按「二级分类」筛选；k_all 降序）
    let fundPool = []
    if (supabase) {
      const buildQ = (withScale) => {
        let q = supabase.from('fund_scores')
          .select('c,n,t0,k_all,score_grade,t1_tt,fund_scale')
        if (withScale) q = q.gt('fund_scale', 2)   // 规模 > 2亿
        if (aiCategory.value) {
          q = (aiCategory.value === '货币型') ? q.eq('t0', '货币型') : q.eq('t1_tt', aiCategory.value)
        } else {
          q = q.not('k_all','is',null).gte('k_all', 70)
        }
        return q
      }
      let { data } = await buildQ(true).order('k_all', { ascending: false }).limit(30)
      // 分类模式下若该品类规模>2亿的基金不足，放宽规模限制兜底
      if ((!data || data.length === 0) && aiCategory.value) {
        const r2 = await buildQ(false).order('k_all', { ascending: false }).limit(30)
        data = r2.data || []
      }
      fundPool = (data || []).map(f => `${f.c} ${f.n || '基金'+f.c} (靠谱${f.k_all?.toFixed(0)} 规模${f.fund_scale != null ? f.fund_scale.toFixed(0)+'亿' : '—'})`)
    }
    if (fundPool.length === 0) {
      fundPool = ['510300 沪深300ETF', '159915 创业板ETF', '511260 10年国债ETF', '518880 黄金ETF', '512100 中证1000ETF', '510500 中证500ETF', '512880 证券ETF', '512010 医药ETF', '159928 消费ETF', '512480 半导体ETF', '512660 军工ETF', '512800 银行ETF', '515030 新能源ETF', '512980 传媒ETF', '159985 豆粕ETF']
    }

    const isCatMode = aiCategoryMode.value && aiCategory.value
    const strategy = AI_STRATEGIES.find(s => s.key === aiStrategy.value)
    const strategyName = isCatMode ? `分类组合·${aiCategory.value}` : (strategy?.label || '均衡配置')
    const customReq = customRequirement.value.trim()
    const reqHint = customReq ? `\n用户额外要求：${customReq}` : ''
    const catHint = aiCategory.value ? `\n基金池已限定在「${aiCategory.value}」细分品类内（规模>2亿），请从该品类的高分基金中挑选。` : ''
    const intro = isCatMode
      ? `从以下「${aiCategory.value}」品类的基金池中，构建一份${aiCategory.value}主题组合。`
      : `从以下高分靠谱基金池中，为"${strategyName}"策略选出10只基金构建组合。`

    const prompt = `你是一位专业基金投顾。${intro}
基金池（代码 名称 靠谱分 规模）：
${fundPool.join('\n')}
${reqHint}${catHint}
请返回纯JSON（不要markdown）：
{ "strategyName": "${strategyName}", "summary": "一句话概述（50字内）",
  "funds": [{"code":"基金代码","name":"基金名称","weight":10,"reason":"推荐理由（15字内）"}],
  "backtest": {"annualReturn":预估年化收益率,"maxDrawdown":预估最大回撤,"sharpe":预估夏普比率,"winRate":预估月度胜率} }
要求：必须从基金池中选择，选出10只，每只权重10%，权重和=100%。`

    aiStatusText.value = 'AI 正在生成组合...'
    const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY || ''}` },
      body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'system', content: '你是专业基金投顾，只从给定基金池选择，只返回JSON。' }, { role: 'user', content: prompt }], temperature: 0.7, max_tokens: 2000 })
    })
    if (!response.ok) throw new Error(`API调用失败: ${response.status}`)
    const result = await response.json()
    const content = result.choices?.[0]?.message?.content || ''
    let parsed
    try { parsed = JSON.parse(content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim()) }
    catch { throw new Error('AI返回格式异常，请重试') }
    const now = new Date()
    aiPortfolio.value = {
      id: Date.now().toString(),
      strategyName: parsed.strategyName || strategyName,
      summary: parsed.summary || '',
      funds: (parsed.funds || []).slice(0, 10).map(f => ({ code: f.code, name: f.name, weight: 10, reason: f.reason||'' })),
      backtest: parsed.backtest ? { annualReturn: Number(parsed.backtest.annualReturn)||0, maxDrawdown: Number(parsed.backtest.maxDrawdown)||0, sharpe: Number(parsed.backtest.sharpe)||0, winRate: Number(parsed.backtest.winRate)||0 } : null,
      createdAt: `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
    }
    saveAiToHistory(aiPortfolio.value)
    aiStatusText.value = 'AI 组合生成完成'
    await enrichRanks()
    customRequirement.value = ''
    showCustomDialog.value = false
  } catch (err) { console.error(err); aiStatusText.value = '生成失败: ' + err.message; aiPortfolio.value = null }
  finally { aiGenerating.value = false }
}

// 添加到自建组合
async function addAiToCustom() {
  if (!aiPortfolio.value?.funds) {
    toast('暂无 AI 组合数据', 'warning')
    return
  }
  if (!isLoggedIn.value) {
    toast('请先登录后再添加到自建组合', 'warning')
    return
  }

  const pfName = aiPortfolio.value.strategyName || 'AI组合'
  const portfolioData = aiPortfolio.value.funds.map(f => ({
    code: f.code,
    name: f.name,
    weight: f.weight || 10,
    reason: f.reason || ''
  }))

  try {
    // 持久化到 Supabase
    const result = await savePortfolioToDb(pfName, portfolioData)
    if (!result.success) {
      toast('保存失败: ' + (result.error || '未知错误'), 'error')
      return
    }

    // 同步到本地状态（使用 DB 返回的真实 ID）
    customPortfolios.value.unshift(result.data || {
      id: Date.now().toString(),
      name: pfName,
      portfolio_data: portfolioData,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })

    toast('已添加到自建组合', 'success')
    // 自动切换到自建组合 tab
    activeTab.value = 'custom'
    await nextTick()
    loadPortfolioReturns()
  } catch (err) {
    console.error('[addAiToCustom]', err)
    toast('添加失败: ' + (err.message || '未知错误'), 'error')
  }
}

// ===== 专家组合（Kan & Zhou 风险平价） =====
// 每个资产大类按「一级分类 t0」筛选；无 t0 的品类（商品/黄金/REIT）用名称关键字识别
// 选基优先级：ETF > 指数型产品 > 主动管理型（同品类内按 k1 降序取 top 10）
const ASSET_ETF_CONFIG = {
  // fallbackT0: 当该一级分类(t0)下 ETF/指数产品不足时，到「指数型」分类补回对应的指数/ETF 高分基金
  stock: { category: '股票', t0: 'gp', nameKeyword: null, fallbackT0: '指数型' },
  bond: { category: '债券', t0: 'zq', nameKeyword: null, fallbackT0: '指数型' },
  // nameKeyword: 以名称关键字识别品类；fallbackKeywords: 该品类命中太少时扩大名称关键字范围补充同类高分基金
  commodity: { category: '商品', t0: null, nameKeyword: '商品ETF', fallbackKeywords: ['商品', '豆粕', '能源'] },
  gold: { category: '黄金', t0: null, nameKeyword: '黄金', fallbackKeywords: ['黄金', '贵金属', '金ETF'] },
  reit: { category: 'REITs', t0: null, nameKeyword: 'REIT', fallbackKeywords: ['REIT', '不动产', '基础设施', 'reits'] },
  cash: { category: '现金', t0: 'hb', nameKeyword: null, noEtf: true }
}
// 每个资产大类精选的基金数量
const ETF_SELECT_TOP = 10
const loading = ref(false)
const dataDate = ref('')
const weightSource = ref('')
const portfolioItems = ref([])
const pieChartRef = ref(null)
let pieChart = null

// 风险平价总览：各大类权重占比饼图（gov.uk 品牌色系）
function renderPieChart() {
  const el = pieChartRef.value
  if (!el || portfolioItems.value.length === 0) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(el)
  const palette = ['#1d70b8', '#5694ca', '#003078', '#f47738', '#4c2c92', '#28a197']
  pieChart.setOption({
    color: COLORS,
    tooltip: { trigger: 'item', formatter: p => `${p.name}: ${p.percent}%` },
    legend: { bottom: 0, textStyle: { fontFamily: 'inherit', fontSize: 13 } },
    series: [{
      type: 'pie',
      radius: ['42%', '70%'],
      center: ['50%', '46%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b} {c}%', fontSize: 12, color: '#0b0c0c' },
      labelLine: { length: 8, length2: 8 },
      data: portfolioItems.value.map((it, i) => ({
        name: it.category,
        value: it.weight,
        itemStyle: { color: palette[i % palette.length] }
      }))
    }]
  })
}

function fmtScore(val) { return val != null ? val.toFixed(1) : '--' }

async function buildPortfolio() {
  loading.value = true
  try {
    const [quotes, v500] = await Promise.all([getIndexQuotes(), fetchValue500All()])
    const { bond: bondData, shibor: shiborData, cpi: cpiData, pe300: pe300Data, rf } = parseValue500Data(v500)
    const date = bondData.date || pe300Data.date || ''
    const marketData = buildMarketData(quotes, { pePercentile: pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null }, { yield10y: rf || 0, shibor: { on: shiborData.on || 0, date: '' } })
    const er = calcAllExpectedReturns({ stock: { pe: marketData.stock?.pe || null, pePercentile: marketData.stock?.pePercentile || null }, bond: { yield10y: rf }, cash: { shiborOn: marketData.cash?.shiborOn || 0 }, gold: { yield10y: rf, cpi: cpiData.cpi } })
    const rpResult = calcEnhancedRiskParityWeights(er, rf, 0.5)
    const weights = rpResult.weights
    const assetKeys = ['stock', 'bond', 'commodity', 'gold', 'reit', 'cash']
    const items = []
    for (const key of assetKeys) {
      const cfg = ASSET_ETF_CONFIG[key]; const w = weights[key] || 0
      if (w > 0) items.push({ assetKey: key, category: cfg.category, weight: w, etfs: [], loading: !cfg.noEtf, noEtf: !!cfg.noEtf })
    }
    dataDate.value = date; weightSource.value = 'Kan & Zhou 增强型风险平价'; portfolioItems.value = items; loading.value = false
    fetchAllETFs(items)
  } catch (err) { console.error(err); loading.value = false }
}

// 按品类精选高分基金：优先级 ETF > 指数型产品 > 主动管理型，同品类内按 k1（1年评分）降序取 top N
// 若某品类备选不足（< limit），自动启用 fallback：跨相关一级分类补充 / 扩大名称关键字范围，
// 确保每类资产都能展示足够多的高分基金
async function fetchCategoryFunds(cfg, limit) {
  if (!supabase) return []
  // 基础查询：按 t0（一级分类）或名称关键字定位品类，按 k1 降序
  const base = () => {
    let q = supabase.from('fund_scores').select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
    if (cfg.t0) q = q.eq('t0', cfg.t0)
    else if (cfg.nameKeyword) q = q.ilike('n', `%${cfg.nameKeyword}%`)
    return q
  }
  const uniq = (list, have = new Set()) => {
    const out = []
    list.forEach(f => { if (!have.has(f.c)) { have.add(f.c); out.push(f) } })
    return out
  }
  let funds = []
  try {
    if (cfg.t0) {
      // 1) ETF 优先（同 t0 内）
      const { data: etf } = await base().ilike('n', '%ETF%').order('k1', { ascending: false }).limit(limit)
      funds = uniq(etf || [])
      // 2) 指数型产品降级补充（同 t0 内）
      if (funds.length < limit) {
        const { data: idx } = await base().ilike('n', '%指数%').order('k1', { ascending: false }).limit(limit)
        funds = funds.concat(uniq(idx || [], new Set(funds.map(f => f.c))))
      }
      // 3) 主动管理型兜底（同 t0 内，无名称限制）
      if (funds.length < limit) {
        const { data: act } = await base().order('k1', { ascending: false }).limit(limit)
        funds = funds.concat(uniq(act || [], new Set(funds.map(f => f.c))))
      }
      // 4) 放宽：跨相关一级分类补充 ETF/指数产品
      //    （如股票/债券的一级分类下无 ETF，则到「指数型」分类补回对应的指数/ETF 高分基金）
      if (funds.length < limit && cfg.fallbackT0) {
        const have = new Set(funds.map(f => f.c))
        const { data: fb } = await supabase.from('fund_scores')
          .select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
          .eq('t0', cfg.fallbackT0).order('k1', { ascending: false }).limit(limit)
        funds = funds.concat(uniq(fb || [], have))
      }
    } else if (cfg.nameKeyword) {
      // 商品/黄金/REIT 等以名称关键字识别的品类，直接按 k1 取 top N
      const { data } = await base().order('k1', { ascending: false }).limit(limit)
      funds = data || []
      // 兜底：若关键字命中太少（< limit），扩大名称关键字范围补充同类高分基金
      if (funds.length < limit && cfg.fallbackKeywords && cfg.fallbackKeywords.length) {
        const have = new Set(funds.map(f => f.c))
        for (const kw of cfg.fallbackKeywords) {
          if (funds.length >= limit) break
          const { data: fb } = await supabase.from('fund_scores')
            .select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
            .ilike('n', `%${kw}%`).order('k1', { ascending: false }).limit(limit)
          funds = funds.concat(uniq(fb || [], have))
        }
      }
    }
  } catch (e) { console.error('[fetchCategoryFunds]', cfg.category, e) }
  return funds.slice(0, limit)
}

async function fetchAllETFs(items) {
  if (!supabase) { portfolioItems.value = items.map(i => ({ ...i, loading: false, etfs: [] })); return }
  const results = await Promise.all(items.map(async item => {
    if (item.noEtf) return { ...item, loading: false }
    const cfg = ASSET_ETF_CONFIG[item.assetKey]
    try {
      const funds = await fetchCategoryFunds(cfg, ETF_SELECT_TOP)
      const etfs = []
      if (funds.length > 0) {
        // 在品类权重内按最大余数法分配整数权重，保证各基金权重之和 = 品类权重
        const N = funds.length
        const baseW = Math.floor(item.weight / N)
        let rem = item.weight - baseW * N
        funds.forEach((f, idx) => etfs.push({
          code: f.c,
          name: f.n || '基金' + f.c,
          weight: baseW + (idx < rem ? 1 : 0),
          k1: f.k1,
          r3y: f.r3y,
          reason: '靠谱指数(1年) ' + (f.k1 || 0).toFixed(1)
        }))
      }
      return { ...item, etfs, loading: false }
    } catch { return { ...item, etfs: [], loading: false } }
  }))
  portfolioItems.value = results
}

onMounted(() => {
  loadAiHistory()
  window.addEventListener('resize', handlePieResize)
})

function handlePieResize() {
  if (pieChart) pieChart.resize()
}

// 切换到专家组合 tab 或权重数据就绪后渲染/重渲染饼图
watch([activeTab, portfolioItems], () => {
  if (activeTab.value === 'model') nextTick(renderPieChart)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handlePieResize)
  if (pieChart) { pieChart.dispose(); pieChart = null }
})
</script>

<style scoped>
.page-portfolio { padding-bottom: var(--space-2xl); }

/* ===== 三Tab导航 ===== */
.pf-tabs { display: flex; border-bottom: 2px solid var(--border); margin-bottom: var(--space-xl); }
.pf-tab { padding: var(--space-sm) var(--space-lg); font-size: 19px; font-weight: 700; color: var(--text-secondary); cursor: pointer; border-bottom: 4px solid transparent; margin-bottom: -2px; transition: all 0.15s; }
.pf-tab:hover { color: var(--text-primary); }
.pf-tab.active { color: var(--brand); border-bottom-color: var(--brand); }

/* ===== Cards ===== */
.card { background: #fff; border: 1px solid var(--border); padding: var(--space-lg); margin-bottom: var(--space-xl); }
.card-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.card-desc { font-size: 16px; color: var(--text-secondary); margin-bottom: var(--space-md); }
.empty-card { text-align: center; padding: var(--space-2xl); color: var(--text-secondary); font-size: 16px; }

/* ===== 登录 ===== */

/* ===== 自建组合 ===== */
.pf-actions { margin-bottom: var(--space-md); display: flex; align-items: center; gap: var(--space-md); }
.btn-primary { padding: var(--space-sm) var(--space-lg); background: #1d70b8; color: #fff; border: none; font-size: 16px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; }
.btn-secondary { padding: var(--space-sm) var(--space-lg); background: #f3f2f1; color: var(--text-primary); border: 1px solid var(--border); font-size: 16px; cursor: pointer; }
.pf-card-hd { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-md); }
.pf-card-name { font-size: 19px; font-weight: 700; cursor: pointer; flex: 1; }
.pf-card-date { font-size: 14px; color: var(--text-secondary); }
.pf-card-del { padding: 2px var(--space-sm); border: 1px solid #d4351c; color: #d4351c; background: #fff; font-size: 13px; cursor: pointer; }
.pf-holdings { display: flex; flex-direction: column; gap: var(--space-sm); }
.pf-holding-item { display: flex; justify-content: space-between; align-items: center; padding: var(--space-sm); border: 1px solid var(--border); border-left: 4px solid #1d70b8; }
.pf-hold-left { display: flex; align-items: center; flex-wrap: wrap; gap: var(--space-sm); }
.pf-hold-idx { width: 22px; height: 22px; line-height: 22px; text-align: center; background: #1d70b8; color: #fff; font-size: 13px; font-weight: 700; }
.pf-hold-name { font-size: 16px; font-weight: 700; }
.pf-hold-code { font-size: 13px; color: var(--text-secondary); }
.pf-hold-right { display: flex; align-items: center; gap: var(--space-sm); }
.pf-weight-input { width: 50px; padding: 2px var(--space-sm); border: 1px solid var(--border); font-size: 14px; text-align: center; }
.pf-hold-nav { font-size: 13px; color: var(--text-secondary); }
.pf-hold-cat { display: inline-flex; flex-wrap: wrap; gap: 4px; align-items: center; }
.pf-meta-cat { font-size: 12px; color: #1d70b8; background: #eaf2fb; padding: 1px 6px; white-space: nowrap; }
.pf-meta-score { font-size: 12px; color: #505a66; background: #f3f2f1; padding: 1px 6px; white-space: nowrap; }
.pf-meta-rank { font-size: 12px; color: #943c0c; background: #fff4e0; padding: 1px 6px; white-space: nowrap; font-variant-numeric: tabular-nums; }
.pf-meta-na { color: #b1b4b6; background: #f3f2f1; }
.pf-empty { padding: var(--space-lg); text-align: center; color: var(--text-secondary); }
.pf-summary { margin-top: var(--space-sm); padding-top: var(--space-sm); border-top: 1px solid var(--border); font-size: 14px; color: var(--text-secondary); }
.pf-returns { margin-top: var(--space-md); padding-top: var(--space-md); border-top: 1px solid var(--border); }
.pf-returns-title { font-size: 15px; font-weight: 700; color: var(--text-secondary); margin-bottom: var(--space-sm); }
.pf-returns-grid { display: grid; grid-template-columns: repeat(5, 1fr); gap: 1px; background: var(--border); border: 1px solid var(--border); }
.pf-ret-cell { background: #fff; padding: 8px 4px; text-align: center; }
.pf-ret-label { font-size: 12px; color: var(--text-secondary); margin-bottom: 4px; }
.pf-ret-value { font-size: 14px; font-weight: 700; font-variant-numeric: tabular-nums; }
.pf-ret-value.ret-pos { color: #d4351c; }   /* 涨=红 */
.pf-ret-value.ret-neg { color: #00703c; }   /* 跌=绿 */
.pf-ret-value.ret-flat { color: #505a66; }
.pf-ret-value.ret-na { color: #b1b4b6; font-weight: 400; }

/* ===== Modal ===== */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; padding: var(--space-xl); border: 1px solid var(--border); min-width: 300px; }
.modal-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.modal-input { width: 100%; padding: var(--space-sm); border: 1px solid var(--border); font-size: 16px; margin-bottom: var(--space-md); }
.modal-btns { display: flex; gap: var(--space-sm); justify-content: flex-end; }

/* ===== 专家组合 ===== */
.data-status { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) 0; font-size: 14px; color: var(--text-secondary); }
.weight-source { font-weight: 700; }
.risk-pie { width: 100%; height: 340px; }
.etf-list { display: flex; flex-direction: column; gap: var(--space-sm); }
.etf-loading, .etf-empty { padding: var(--space-md); text-align: center; color: var(--text-secondary); }
.etf-item { padding: var(--space-md); border: 1px solid var(--border); border-left: 5px solid #1d70b8; }
.etf-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-sm); }
.etf-name-wrap { display: flex; flex-direction: column; }
.etf-name { font-size: 16px; font-weight: 700; }
.etf-code { font-size: 14px; color: var(--text-secondary); }
.etf-weight-wrap { text-align: right; }
.etf-weight { font-size: 19px; font-weight: 700; display: block; }
.etf-score { font-size: 14px; color: var(--text-secondary); }
.etf-reason { font-size: 14px; color: var(--text-secondary); padding-top: var(--space-sm); border-top: 1px solid var(--border); display: flex; justify-content: space-between; }
.etf-return { font-weight: 700; white-space: nowrap; margin-left: var(--space-md); }

/* ===== AI 组合 ===== */
.ai-card { background: #f8f8ff; border-left: 5px solid #6c5ce7; }
.ai-strategies { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: var(--space-sm); margin-bottom: var(--space-lg); }
.ai-st-btn { display: flex; flex-direction: column; align-items: center; padding: var(--space-sm); border: 1px solid var(--border); background: #fff; cursor: pointer; font-size: 14px; transition: all 0.15s; text-align: center; }
.ai-st-btn:hover { border-color: #6c5ce7; background: #f0edff; }
.ai-st-btn.active { border-color: #6c5ce7; background: #6c5ce7; color: #fff; }
.ai-st-btn.active .ai-st-desc { color: rgba(255,255,255,0.7); }
.ai-st-btn:disabled { opacity: 0.5; }
.ai-custom-st-btn { border-style: dashed; border-color: #6c5ce7; color: #6c5ce7; }
.ai-custom-st-btn:hover { background: #f0edff; border-style: solid; }
.ai-st-desc { font-size: 11px; color: var(--text-secondary); margin-top: 2px; }
.ai-action { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-lg); }
.ai-generate-btn { padding: var(--space-sm) var(--space-xl); font-size: 19px; background: #6c5ce7; color: #fff; border: none; cursor: pointer; box-shadow: 0 2px 0 #4a3db5; }
.ai-generate-btn:hover:not(:disabled) { background: #5a4bd1; }
.ai-generate-btn:disabled { opacity: 0.6; }
.ai-status { font-size: 14px; color: var(--text-secondary); }
.ai-custom-btn { padding: var(--space-sm) var(--space-lg); font-size: 16px; background: #fff; color: #6c5ce7; border: 1px solid #6c5ce7; cursor: pointer; }
.ai-custom-btn:hover { background: #f0edff; }
.ai-custom-btn:disabled { opacity: 0.5; }
.ai-add-row { margin-top: var(--space-md); padding-top: var(--space-md); border-top: 1px solid var(--border); }
.modal-textarea { width: 100%; padding: var(--space-sm); border: 1px solid var(--border); font-size: 14px; resize: vertical; box-sizing: border-box; }
.ai-result { margin-top: var(--space-lg); padding: var(--space-lg); border: 1px solid var(--border); background: #fff; }
.ai-result-hd { display: flex; justify-content: space-between; align-items: center; margin-bottom: var(--space-sm); }
.ai-result-title { font-size: 19px; font-weight: 700; }
.ai-result-date { font-size: 14px; color: var(--text-secondary); }
.ai-summary { font-size: 16px; color: var(--text-secondary); margin-bottom: var(--space-md); line-height: 1.6; }
.ai-funds { display: flex; flex-direction: column; gap: var(--space-sm); margin-bottom: var(--space-md); }
.ai-fund-item { display: flex; justify-content: space-between; align-items: center; padding: var(--space-sm) var(--space-md); border: 1px solid var(--border); }
.ai-fund-left { display: flex; flex-direction: column; }
.ai-fund-name { font-size: 16px; font-weight: 700; }
.ai-fund-code { font-size: 13px; color: var(--text-secondary); }
.ai-fund-right { text-align: right; }
.ai-fund-weight { font-size: 19px; font-weight: 700; display: block; }
.ai-fund-reason { font-size: 13px; color: var(--text-secondary); }
.ai-fund-cat { font-size: 12px; color: #1d70b8; background: #eaf2fb; padding: 1px 6px; margin-top: 2px; align-self: flex-start; }
.ai-cat-row { display: flex; align-items: center; gap: var(--space-sm); margin-bottom: var(--space-lg); flex-wrap: wrap; }
.ai-cat-label { font-size: 15px; font-weight: 700; }
.ai-cat-select { padding: var(--space-xs) var(--space-sm); border: 1px solid var(--border); font-size: 15px; background: #fff; min-width: 200px; }
.ai-cat-hint { font-size: 13px; color: var(--text-secondary); }
.ai-backtest { padding: var(--space-md); background: #f3f2f1; }
.ai-bt-title { font-size: 16px; font-weight: 700; margin-bottom: var(--space-sm); }
.ai-bt-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--space-sm); }
.ai-bt-item { text-align: center; padding: var(--space-sm); background: #fff; }
.ai-bt-label { font-size: 12px; color: var(--text-secondary); display: block; margin-bottom: 2px; }
.ai-bt-val { font-size: 19px; font-weight: 700; }
.ai-history { margin-top: var(--space-lg); }
.ai-hist-item { display: flex; align-items: center; gap: var(--space-md); padding: var(--space-sm) var(--space-md); border: 1px solid var(--border); cursor: pointer; margin-bottom: var(--space-sm); }
.ai-hist-item:hover { background: #f0edff; }
.ai-hist-name { font-size: 16px; font-weight: 700; flex: 1; }
.ai-hist-date { font-size: 14px; color: var(--text-secondary); }
.ai-hist-count { font-size: 14px; color: var(--text-secondary); }

/* 分类组合选择器 */
.ai-cat-picker { margin-bottom: var(--space-lg); padding: var(--space-md); border: 1px dashed #6c5ce7; background: #faf9ff; }
.ai-cat-picker-hd { font-size: 15px; font-weight: 700; color: #4a3db5; margin-bottom: var(--space-sm); }
.ai-cat-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: var(--space-sm); }
.ai-cat-chip { padding: var(--space-sm); border: 1px solid var(--border); background: #fff; cursor: pointer; font-size: 14px; transition: all 0.15s; text-align: center; }
.ai-cat-chip:hover { border-color: #6c5ce7; background: #f0edff; }
.ai-cat-chip:disabled { opacity: 0.5; }

/* ===== Utils ===== */
.text-up { color: var(--color-up); }
.text-down { color: var(--color-down); }
.footer-note { text-align: left; padding: var(--space-xl) 0; font-size: 14px; color: var(--text-secondary); border-top: 1px solid var(--border); }

/* ===== 移动端适配 ===== */
@media (max-width: 768px) {
  .ai-bt-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
