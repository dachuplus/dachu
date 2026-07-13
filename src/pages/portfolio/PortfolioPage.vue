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
                <span class="pf-hold-cat" v-if="holdTypeMap[h.code]">
                  <span class="pf-meta-cat" :title="'基金类型'">{{ holdTypeMap[h.code].type || '--' }}</span>
                  <span class="pf-meta-rank" v-if="holdTypeMap[h.code].kAll != null">排名 {{ fmtKAll(holdTypeMap[h.code]) }}</span>
                  <span class="pf-meta-rank pf-meta-na" v-else>排名 --</span>
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
      <!-- AI 组合子标签 -->
      <div class="ai-subtabs">
        <div class="ai-subtab" :class="{ active: aiSubTab === 'strategy' }" @click="aiSubTab = 'strategy'">AI 策略</div>
        <div class="ai-subtab" :class="{ active: aiSubTab === 'riskparity' }" @click="aiSubTab = 'riskparity'">风险平价</div>
      </div>

      <!-- 2a. AI 策略 -->
      <div v-if="aiSubTab === 'strategy'">
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

          <div class="ai-category-logic" v-if="aiPortfolio.category_logic">
            <div class="ai-cl-title">品类逻辑</div>
            <p class="ai-cl-text">{{ aiPortfolio.category_logic }}</p>
          </div>

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

          <!-- AI 策略组合区间收益 -->
          <div class="pf-returns" v-if="aiPortfolio._returns">
            <div class="pf-returns-title">组合区间收益</div>
            <div class="pf-returns-grid">
              <div class="pf-ret-cell" v-for="col in RETURN_COLS" :key="col.key">
                <div class="pf-ret-label">{{ col.label }}</div>
                <div class="pf-ret-value" :class="retClass(aiPortfolio._returns[col.key])">{{ fmtRet(aiPortfolio._returns[col.key]) }}</div>
              </div>
            </div>
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

      <!-- 2b. 风险平价 -->
      <div v-if="aiSubTab === 'riskparity'" class="card ai-card rp-card">
        <div class="card-title">Kan &amp; Zhou 增强型风险平价组合</div>
        <p class="card-desc">基于 Kan &amp; Zhou (2007) 增强型风险平价模型计算各大类资产目标权重，由 DeepSeek 在每类高分靠谱基金中精选并分配权重。</p>

        <div class="rp-weights" v-if="rpAssetWeights && rpAssetWeights.weights">
          <div class="rp-w-title">模型目标资产配置（数据截止 {{ rpAssetWeights.date || '—' }}）</div>
          <div class="rp-w-grid">
            <div class="rp-w-cell" v-for="(w, k) in rpAssetWeights.weights" :key="k" v-show="w > 0">
              <span class="rp-w-asset">{{ assetLabel(k) }}</span>
              <span class="rp-w-val">{{ w }}%</span>
            </div>
          </div>
        </div>

        <div class="ai-action">
          <button class="ai-generate-btn" :disabled="rpGenerating" @click="generateRiskParityPortfolio">
            <span v-if="rpGenerating">AI 分析中...</span>
            <span v-else>生成风险平价组合</span>
          </button>
          <span class="ai-status" v-if="rpStatusText">{{ rpStatusText }}</span>
        </div>

        <div class="ai-result" v-if="rpPortfolio && rpPortfolio.funds">
          <div class="ai-result-hd">
            <span class="ai-result-title">AI 推荐组合 — {{ rpPortfolio.strategyName }}</span>
            <span class="ai-result-date">{{ rpPortfolio.createdAt }}</span>
          </div>
          <p class="ai-summary">{{ rpPortfolio.summary }}</p>

          <div class="ai-funds">
            <div class="ai-fund-item" v-for="f in rpPortfolio.funds" :key="f.code">
              <div class="ai-fund-left">
                <span class="ai-fund-name">{{ f.name }}</span>
                <span class="ai-fund-code">{{ f.code }}</span>
                <span class="ai-fund-asset" v-if="f.asset">{{ f.asset }}</span>
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

          <div class="ai-backtest" v-if="rpPortfolio.backtest">
            <div class="ai-bt-title">历史回测</div>
            <div class="ai-bt-grid">
              <div class="ai-bt-item">
                <span class="ai-bt-label">年化收益</span>
                <span class="ai-bt-val" :class="rpPortfolio.backtest.annualReturn > 0 ? 'text-up' : 'text-down'">
                  {{ rpPortfolio.backtest.annualReturn > 0 ? '+' : '' }}{{ rpPortfolio.backtest.annualReturn }}%
                </span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">最大回撤</span>
                <span class="ai-bt-val text-down">{{ rpPortfolio.backtest.maxDrawdown }}%</span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">夏普比率</span>
                <span class="ai-bt-val">{{ rpPortfolio.backtest.sharpe }}</span>
              </div>
              <div class="ai-bt-item">
                <span class="ai-bt-label">胜率</span>
                <span class="ai-bt-val">{{ rpPortfolio.backtest.winRate }}%</span>
              </div>
            </div>
          </div>
          <div class="ai-add-row">
            <button class="btn-primary" @click="addRpToCustom">+ 添加到自建组合</button>
          </div>

          <!-- 风险平价组合区间收益 -->
          <div class="pf-returns" v-if="rpPortfolio._returns">
            <div class="pf-returns-title">组合区间收益</div>
            <div class="pf-returns-grid">
              <div class="pf-ret-cell" v-for="col in RETURN_COLS" :key="col.key">
                <div class="pf-ret-label">{{ col.label }}</div>
                <div class="pf-ret-value" :class="retClass(rpPortfolio._returns[col.key])">{{ fmtRet(rpPortfolio._returns[col.key]) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>

    <!-- ==================== 3. AI 大 PK ==================== -->
    <div v-if="activeTab === 'aipk'">
      <AIPkPanel />
    </div>

    <!-- ==================== 4. 基金指数 ==================== -->
    <div v-if="activeTab === 'index'">
      <FundIndexPanel />
    </div>

    <!-- ==================== 5. 投顾产品 ==================== -->
    <div v-if="activeTab === 'tougu'">
      <TouguPage />
    </div>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { supabase } from '../../api/supabase'
import { fetchValue500All } from '../../utils/api'
import { getCategoryRankInfo, getCategoryRankInfoByScore, fetchFundMeta } from '../../api/data.js'
import { getIndexQuotes, buildMarketData, parseValue500Data } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights } from '../../utils/calc'
import { useAuth } from '../../composables/useAuth'
import { toast, confirm } from '../../composables/useToast.js'
import { createPortfolio as savePortfolioToDb, deletePortfolio } from '../../api/user-data'
import FundIndexPanel from './FundIndexPanel.vue'
import AIPkPanel from './AIPkPanel.vue'
import TouguPage from '../tougu/TouguPage.vue'

const {
  user, isLoggedIn,
  portfolios: customPortfolios,
  refreshUserData, showLogin
} = useAuth()

// ===== Tab =====
const tabs = [
  { key: 'custom', label: '自建组合' },
  { key: 'ai', label: 'AI 组合' },
  { key: 'aipk', label: 'AI 大 PK' },
  { key: 'index', label: '基金指数' },
  { key: 'tougu', label: '投顾产品' }
]
const activeTab = ref('custom')
const aiSubTab = ref('strategy')

function switchTab(key) {
  activeTab.value = key
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
  if (rpPortfolio.value?.funds) rpPortfolio.value.funds.forEach(f => f.code && codes.add(f.code))
  if (codes.size === 0) { catRankMap.value = {}; holdMetaMap.value = {}; return }
  try {
    catRankMap.value = await getCategoryRankInfo([...codes])
    holdMetaMap.value = await getCategoryRankInfoByScore([...codes], 'k1')
  } catch (e) {
    catRankMap.value = {}
    holdMetaMap.value = {}
  }
}

// 自建组合持仓的「类型(t0/t1_tt) + 全市场排名(k_all)」映射（与 AI 组合共用的 holdMetaMap 互不干扰）
const holdTypeMap = ref({})
// 收集自建组合全部持仓基金代码
function collectCustomCodes() {
  const codes = []
  customPortfolios.value.forEach(pf => (pf.portfolio_data || []).forEach(h => h.code && codes.push(h.code)))
  return codes
}
// 从 fund_scores 拉取每只持仓基金的类型与全市场排名(k_all)
async function loadHoldTypeRank(codes) {
  if (!supabase || !codes || codes.length === 0) { holdTypeMap.value = {}; return }
  const unique = [...new Set(codes.filter(Boolean))]
  try {
    const { data, error } = await supabase
      .from('fund_scores')
      .select('c,t0,t1_tt,k_all')
      .in('c', unique)
    if (error || !data) { holdTypeMap.value = {}; return }
    // 全市场基金总数（排名分母），来自 fund_scores_meta.total_count；缺失则只显示分子
    let total = null
    try {
      const meta = await fetchFundMeta()
      if (meta && meta.total_count) total = meta.total_count
    } catch (e) { /* 忽略，降级为仅显示排名分子 */ }
    const map = {}
    for (const f of data) {
      const type = (f.t1_tt && String(f.t1_tt).trim()) ? f.t1_tt : (f.t0 || '')
      const kAll = f.k_all == null ? null : Number(f.k_all)
      map[f.c] = { type, kAll, total }
    }
    holdTypeMap.value = map
  } catch (e) {
    console.error('[loadHoldTypeRank]', e)
    holdTypeMap.value = {}
  }
}
// 全市场排名格式化：#1234/20850（无分母时仅显示 #1234）
function fmtKAll(meta) {
  if (!meta || meta.kAll == null) return null
  return meta.total ? `#${meta.kAll}/${meta.total}` : `#${meta.kAll}`
}

// ===== 自建组合 =====
const showCreateModal = ref(false)
const newPfName = ref('')

async function loadCustomPortfolios() {
  await refreshUserData()
  await enrichRanks()
  await loadHoldTypeRank(collectCustomCodes())
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

// 通用：为任意持仓列表（AI 组合 / 风险平价）拉取成分基金区间收益并计算加权收益
async function loadReturnsForHoldings(holdings) {
  if (!supabase || !holdings || holdings.length === 0) return { _returns: null, _fundReturns: {} }
  const codes = holdings.map(h => h.code).filter(Boolean)
  if (codes.length === 0) return { _returns: null, _fundReturns: {} }
  const ofCodes = codes.filter(c => c.includes('.'))
  const etfCodes = codes.filter(c => !c.includes('.'))
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
    return { _returns: buildPortfolioReturns(holdings, fundMap), _fundReturns: fundMap }
  } catch (e) {
    console.error('[loadReturnsForHoldings]', e)
    return { _returns: null, _fundReturns: {} }
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
function loadAiFromHistory(pf) { aiPortfolio.value = pf; enrichRanks(); if (pf.funds?.length) loadReturnsForHoldings(pf.funds).then(ret => { if (ret) { pf._returns = ret._returns; pf._fundReturns = ret._fundReturns } }) }

// ==== 自定义弹窗 ====
const showCustomDialog = ref(false)
const customRequirement = ref('')

// 最高风控规则：识别「持有期 / 定开 / 定期开放」等带锁定期、月度调仓时卖不掉的产品（按名称，与 FundRankPage 口径一致）
const LOCKED_FUND_RE = /(持有期|定开|定期开放|最短持有|\d+\s*(年|个月|月|天|日)\s*持有|持有\s*\d+\s*(年|个月|月))/
function isLockedFund(name) {
  return !!name && LOCKED_FUND_RE.test(name)
}

async function generateAiPortfolio() {
  if (aiGenerating.value) return
  aiGenerating.value = true
  aiStatusText.value = '正在查询靠谱指数产品...'
  try {
    // 1. 真实基金池：全市场候选，从 fund_scores 拉取（最高风控规则：所有取基金均查 fund_scores，fund_combined 仅用于下载验证），
    //    按二级分类(t1_tt)分组，每类中性排序（规模/近1年收益倒序），每类约 50-60 只（不再用 k_all 引导排序）
    let fundPool = []
    if (supabase) {
      const perCat = 55
      const catList = aiCategory.value ? [aiCategory.value] : AI_ALL_CATEGORIES
      const queries = catList.map(cat => {
        let q = supabase.from('fund_scores')
          .select('c,n,t0,t1_tt,fund_scale,r1y,k_all,k1,score_grade')
        q = (cat === '货币型') ? q.eq('t0', '货币型') : q.eq('t1_tt', cat)
        return q.order('fund_scale', { ascending: false }).limit(perCat)
      })
      const results = await Promise.all(queries)
      const rows = results.flatMap(r => r.data || [])
      fundPool = rows.map(f => {
        const raw = (f.c || '').trim()
        const code = raw.endsWith('.OF') ? raw : raw + '.OF'   // fund_scores.c 已带 .OF，此处保持幂等
        return {
          c: code, n: f.n, t0: f.t0, t1tt: f.t1_tt,
          fundScale: f.fund_scale, r1y: f.r1y,
          kall: f.k_all, k1: f.k1, grade: f.score_grade
        }
      })
      // 最高风控规则：剔除持有期/定开等锁定期产品（候选池查询层无法用名称过滤，内存二次剔除）
      fundPool = fundPool.filter(f => !isLockedFund(f.n))
    }
    // 没有真实产品数据时，明确提示，绝不退回示例基金
    if (fundPool.length === 0) {
      aiStatusText.value = '当前暂无足够的靠谱指数产品数据，无法生成组合'
      aiPortfolio.value = null
      aiGenerating.value = false
      return
    }

    const isCatMode = aiCategoryMode.value && aiCategory.value
    const strategy = AI_STRATEGIES.find(s => s.key === aiStrategy.value)
    const strategyName = isCatMode ? `分类组合·${aiCategory.value}` : (strategy?.label || '均衡配置')
    const customReq = customRequirement.value.trim()
    const reqHint = customReq ? `\n用户额外要求：${customReq}` : ''
    const catHint = aiCategory.value ? `\n基金池已限定在「${aiCategory.value}」细分品类内（全市场该品类高分靠谱产品），请从该品类挑选。` : ''

    // 按二级分类分组展示，便于 DeepSeek 按分类挑选分散化组合
    const catMap = {}
    for (const f of fundPool) {
      const cat = f.t1tt || f.t0 || '其他'
      ;(catMap[cat] = catMap[cat] || []).push(f)
    }
    let poolText = ''
    for (const [cat, list] of Object.entries(catMap)) {
      poolText += `\n【${cat}】\n` + list.map(f => `${f.c} ${f.n} (靠谱${f.kall != null ? Math.round(f.kall) : '—'})`).join('\n')
    }

    const targetN = 10
    const intro = isCatMode
      ? `从以下「${aiCategory.value}」品类的靠谱基金池中，构建一份该品类主题组合。`
      : `从以下按分类组织的靠谱基金池中，为"${strategyName}"策略挑选 ${targetN} 只基金，覆盖多个品类以分散风险。`

    const prompt = `你是一位专业基金投顾。${intro}
以下均为真实存在的公募基金产品（来自靠谱指数数据库），按细分品类列出：
${poolText}
${reqHint}${catHint}
请返回纯JSON（不要markdown）：
{ "strategyName": "${strategyName}", "summary": "一句话概述（50字内）",
  "category_logic": "【第一层·品类选择逻辑】结合宏观研究、策略研究、行业研究、流动性研究、金融工程，以及胜率与赔率的研究，独立做出品类选择并给出清晰逻辑（说明为何选择这些品类、为何这样配比）。",
  "funds": [{"code":"基金代码","name":"基金名称","weight":10,
    "reason":"【第二层·单品多维度】逐维度说明，每行一个维度，覆盖：同类/收益/回撤/规模/持仓/费率/基金经理/基金公司/综合。数据缺失的维度请注明'以最新定期报告为准'，不得编造。示例格式：\\n同类：...\\n收益：...\\n回撤：...\\n规模：...\\n持仓：...\\n费率：...\\n基金经理：...\\n基金公司：...\\n综合：..."}],
  "backtest": {"annualReturn":预估年化收益率,"maxDrawdown":预估最大回撤,"sharpe":预估夏普比率,"winRate":预估月度胜率} }
要求：
【第一层·品类逻辑】category_logic 必须由你结合上述研究独立给出，清晰说明品类选择的依据与逻辑，不可为空。
【第二层·单品逻辑】每个所选基金均须从多个维度说明（同类/收益/回撤/规模/持仓/费率/基金经理/基金公司/综合），数据缺失维度注明"以最新定期报告为准"，严禁编造。
【最高风控规则·不可违反】严禁选择任何「持有期」或「定开」类基金（带锁定期、锁定期内无法赎回的产品）。这类产品在月度调仓时根本卖不掉，会破坏组合流动性。候选池已预先剔除此类产品，你必须再次确认不引入。
必须从上述基金池中选择真实存在的产品，挑${targetN}只，每只权重${Math.round(100 / targetN)}%，权重和=100%。不得编造代码，只能从上述清单中选。`

    aiStatusText.value = 'AI 正在生成组合...'
    const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY || ''}` },
      body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'system', content: '你是专业基金投顾，只从给定基金池选择真实产品，只返回JSON，不得编造代码。' }, { role: 'user', content: prompt }], temperature: 0.3, max_tokens: 3000 })
    })
    if (!response.ok) throw new Error(`API调用失败: ${response.status}`)
    const result = await response.json()
    const content = result.choices?.[0]?.message?.content || ''
    let parsed
    try { parsed = JSON.parse(content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim()) }
    catch { throw new Error('AI返回格式异常，请重试') }

    // 2. 校验：只保留 fund_scores 中真实存在的产品，并回填真实名称；不足则按真实池补齐
    const validated = await validateFunds(parsed.funds || [], fundPool, targetN)
    if (validated.length === 0) throw new Error('AI返回的产品均不在靠谱指数库中，请重试')

    const now = new Date()
    aiPortfolio.value = {
      id: Date.now().toString(),
      strategyName: parsed.strategyName || strategyName,
      summary: parsed.summary || '',
      category_logic: parsed.category_logic || '',
      funds: validated,
      backtest: parsed.backtest ? { annualReturn: Number(parsed.backtest.annualReturn) || 0, maxDrawdown: Number(parsed.backtest.maxDrawdown) || 0, sharpe: Number(parsed.backtest.sharpe) || 0, winRate: Number(parsed.backtest.winRate) || 0 } : null,
      createdAt: `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    }
    saveAiToHistory(aiPortfolio.value)
    aiStatusText.value = 'AI 组合生成完成'
    await enrichRanks()
    const aiRet = await loadReturnsForHoldings(aiPortfolio.value.funds)
    if (aiRet) { aiPortfolio.value._returns = aiRet._returns; aiPortfolio.value._fundReturns = aiRet._fundReturns }
    customRequirement.value = ''
    showCustomDialog.value = false
  } catch (err) { console.error(err); aiStatusText.value = '生成失败: ' + err.message; aiPortfolio.value = null }
  finally { aiGenerating.value = false }
}

// 校验 DeepSeek 返回的基金：只保留 fund_scores 中真实存在的产品，回填真实名称；
// 若有效数量不足 targetN，则从真实基金池中补齐（不引入任何示例/虚构基金）。
async function validateFunds(dsFunds, pool, targetN) {
  const want = (dsFunds || [])
    .map(f => ({
      code: String(f.code || '').trim(),
      weight: Number(f.weight) || 0,
      reason: f.reason || '',
      asset: f.assetClass || f.asset || ''
    }))
    .filter(x => x.code)
  if (want.length === 0) return []

  // 1) 与数据库核对，只认真实存在的产品
  let realMap = {}
  if (supabase) {
    const codes = [...new Set(want.map(x => x.code))]
    try {
      const { data } = await supabase.from('fund_scores')
        .select('c,n,t0,t1_tt,k_all,k1,score_grade')
        .in('c', codes)
      ;(data || []).forEach(f => { realMap[f.c] = f })
    } catch (e) { console.error('[validateFunds]', e) }
  }
  const out = []
  const seen = new Set()
  for (const x of want) {
    const real = realMap[x.code]
    if (real && !seen.has(real.c)) {
      seen.add(real.c)
      out.push({ code: real.c, name: real.n || x.code, weight: x.weight, reason: x.reason, asset: x.asset })
    }
  }

  // 2) 不足则从真实基金池补齐（权重暂置 0，稍后归一化）
  if (out.length < targetN && pool && pool.length) {
    for (const p of pool) {
      if (out.length >= targetN) break
      if (!seen.has(p.c)) {
        seen.add(p.c)
        out.push({ code: p.c, name: p.n, weight: 0, reason: '靠谱指数高分产品', asset: '' })
      }
    }
  }

  // 3) 权重归一化到 100
  const total = out.reduce((s, f) => s + (f.weight || 0), 0)
  if (total > 0) {
    out.forEach(f => { f.weight = Math.max(0, Math.round((f.weight / total) * 100)) })
    const diff = 100 - out.reduce((s, f) => s + f.weight, 0)
    if (diff !== 0 && out.length) out[0].weight = Math.max(0, out[0].weight + diff)
  } else if (out.length) {
    const w = Math.floor(100 / out.length)
    let rem = 100 - w * out.length
    out.forEach((f, i) => { f.weight = w + (i < rem ? 1 : 0) })
  }
  return out
}

// 通用：将指定组合（AI 策略 / 风险平价）添加到自建组合
async function addPortfolioToCustom(pf) {
  if (!pf?.funds) {
    toast('暂无组合数据', 'warning')
    return
  }
  if (!isLoggedIn.value) {
    toast('请先登录后再添加到自建组合', 'warning')
    return
  }

  const pfName = pf.strategyName || 'AI组合'
  const portfolioData = pf.funds.map(f => ({
    code: f.code,
    name: f.name,
    weight: f.weight || 10,
    reason: f.reason || ''
  }))

  try {
    const result = await savePortfolioToDb(pfName, portfolioData)
    if (!result.success) {
      toast('保存失败: ' + (result.error || '未知错误'), 'error')
      return
    }

    customPortfolios.value.unshift(result.data || {
      id: Date.now().toString(),
      name: pfName,
      portfolio_data: portfolioData,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })

    toast('已添加到自建组合', 'success')
    activeTab.value = 'custom'
    await nextTick()
    await enrichRanks()
    await loadHoldTypeRank(collectCustomCodes())
    loadPortfolioReturns()
  } catch (err) {
    console.error('[addPortfolioToCustom]', err)
    toast('添加失败: ' + (err.message || '未知错误'), 'error')
  }
}

async function addAiToCustom() { await addPortfolioToCustom(aiPortfolio.value) }
async function addRpToCustom() { await addPortfolioToCustom(rpPortfolio.value) }

// ===== 资产大类配置（用于风险平价候选基金池构建） =====
// 每个资产大类按「一级分类 t0」筛选；无 t0 的品类（商品/黄金/REIT）用名称关键字识别
// 选基优先级：ETF > 指数型产品 > 主动管理型（同品类内按 k1 降序取 top 10）
const ASSET_ETF_CONFIG = {
  // fallbackT0: 当该一级分类(t0)下 ETF/指数产品不足时，到「指数型」分类补回对应的指数/ETF 高分基金
  stock: { category: '股票', t0: '股票型', nameKeyword: null, fallbackT0: '指数型', topN: 3 },
  bond: { category: '债券', t0: '债券型', nameKeyword: null, fallbackT0: '指数型' },
  // nameKeyword: 以名称关键字识别品类；fallbackKeywords: 该品类命中太少时扩大名称关键字范围补充同类高分基金
  commodity: { category: '商品', t0: null, nameKeyword: '商品ETF', fallbackKeywords: ['商品', '豆粕', '能源'] },
  gold: { category: '黄金', t0: null, nameKeyword: '黄金', fallbackKeywords: ['黄金', '贵金属', '金ETF'] },
  reit: { category: 'REITs', t0: null, nameKeyword: 'REIT', fallbackKeywords: ['REIT', '不动产', '基础设施', 'reits'] },
  cash: { category: '现金', t0: '货币型', nameKeyword: null, noEtf: true }
}
// ===== 风险平价：DeepSeek 生成组合 =====
const RP_ASSET_ORDER = ['stock', 'bond', 'commodity', 'gold', 'reit', 'cash']
const RP_ASSET_LABELS = { stock: '股票', bond: '债券', commodity: '商品', gold: '黄金', reit: 'REITs', cash: '现金' }
function assetLabel(k) { return RP_ASSET_LABELS[k] || k }

const rpGenerating = ref(false)
const rpStatusText = ref('')
const rpPortfolio = ref(null)
const rpAssetWeights = ref(null)

// 让 DeepSeek 基于 Kan & Zhou 增强型风险平价模型自动生成组合：
// 1) 计算各大类资产目标权重；2) 为每个大类构建高分靠谱基金候选池；
// 3) 由 DeepSeek 在候选池内精选基金并按目标权重分配。
async function generateRiskParityPortfolio() {
  if (rpGenerating.value) return
  rpGenerating.value = true
  rpStatusText.value = '正在计算 Kan & Zhou 增强型风险平价权重...'
  try {
    const [quotes, v500] = await Promise.all([getIndexQuotes(), fetchValue500All()])
    const { bond: bondData, shibor: shiborData, cpi: cpiData, pe300: pe300Data, rf } = parseValue500Data(v500)
    const date = bondData.date || pe300Data.date || ''
    const marketData = buildMarketData(quotes, { pePercentile: pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null }, { yield10y: rf || 0, shibor: { on: shiborData.on || 0, date: '' } })
    const er = calcAllExpectedReturns({ stock: { pe: marketData.stock?.pe || null, pePercentile: marketData.stock?.pePercentile || null }, bond: { yield10y: rf }, cash: { shiborOn: marketData.cash?.shiborOn || 0 }, gold: { yield10y: rf, cpi: cpiData.cpi } })
    const rpResult = calcEnhancedRiskParityWeights(er, rf, 0.5)
    const weights = rpResult.weights
    rpAssetWeights.value = { date, weights }

    // 构建各大类候选基金池（高分靠谱基金）
    rpStatusText.value = '正在筛选各大类高分靠谱基金...'
    const pools = {}
    const allPool = []   // 各大类真实基金扁平池，用于输出校验/补齐
    for (const key of RP_ASSET_ORDER) {
      const w = weights[key] || 0
      if (w <= 0) continue
      const cfg = ASSET_ETF_CONFIG[key]
      if (!cfg) continue
      const funds = await fetchCategoryFunds(cfg, 8)
      const mapped = (funds || []).map(f => ({ c: f.c, n: f.n, k1: f.k1 }))
      pools[key] = mapped.map(f => `${f.c} ${f.n || ''} (靠谱${f.k1 != null ? f.k1.toFixed(0) : '—'})`)
      allPool.push(...mapped)
    }

    const activeClasses = RP_ASSET_ORDER.filter(k => weights[k] > 0 && pools[k] && pools[k].length > 0)
    let poolText = ''
    for (const key of activeClasses) {
      poolText += `\n【${RP_ASSET_LABELS[key]}】（目标权重 ${weights[key]}%）：\n` + pools[key].join('\n')
    }
    const weightSummary = activeClasses.map(k => `${RP_ASSET_LABELS[k]}: ${weights[k]}%`).join('，')

    const prompt = `你是一位专业基金投顾，精通风险平价配置。
我已用 Kan & Zhou (2007) 增强型风险平价模型计算出各大类资产的目标权重，并为你准备好了每个大类下的高分靠谱基金池（已按1年靠谱指数降序）。
请严格按以下规则生成组合：
0. 【最高风控规则·不可违反】严禁选择任何「持有期」或「定开」类基金（带锁定期、锁定期内无法赎回的产品）。这类产品在月度调仓时根本卖不掉，会破坏组合流动性。各大类基金池已预先剔除此类产品，你必须再次确认不引入。
1. 对每一个目标权重>0的大类，从该大类的基金池中精选 2~3 只基金；
2. 大类内部按风险平价思想分配权重（可参考基金靠谱指数高低微调），使该大类内基金权重之和 ≈ 该大类目标权重；
3. 所有基金权重之和 = 100%；
4. 必须只从给定基金池中选择，不得自行编造代码或超出清单。
5. 各大类的基金池已严格按一级分类筛选：例如【现金】池均为货币型基金(t0=货币型)、【债券】池均为债券型基金(t0=债券型)、【股票】池均为股票型/指数型基金。每个大类只能在「各自对应的基金池」内选择，严禁跨池串用（如不得把股票基金放进现金大类）。

各大类目标权重：${weightSummary}

各大类基金池：${poolText}

请返回纯JSON（不要markdown）：
{ "strategyName": "风险平价组合", "summary": "一句话概述（50字内）",
  "funds": [{"code":"基金代码","name":"基金名称","weight":数值,"assetClass":"大类名(股票/债券/商品/黄金/REITs/现金)","reason":"推荐理由（15字内）"}],
  "backtest": {"annualReturn":预估年化收益率,"maxDrawdown":预估最大回撤,"sharpe":预估夏普比率,"winRate":预估月度胜率} }
要求：权重和为100%，每个大类基金权重之和尽量接近其目标权重。`

    rpStatusText.value = 'AI 正在生成风险平价组合...'
    const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${import.meta.env.VITE_DEEPSEEK_API_KEY || ''}` },
      body: JSON.stringify({ model: 'deepseek-chat', messages: [{ role: 'system', content: '你是专业基金投顾，只从给定基金池选择真实产品，只返回JSON，不得编造代码。' }, { role: 'user', content: prompt }], temperature: 0.3, max_tokens: 2000 })
    })
    if (!response.ok) throw new Error(`API调用失败: ${response.status}`)
    const result = await response.json()
    const content = result.choices?.[0]?.message?.content || ''
    let parsed
    try { parsed = JSON.parse(content.replace(/```json\n?/g, '').replace(/```\n?/g, '').trim()) }
    catch { throw new Error('AI返回格式异常，请重试') }

    // 校验：只保留 fund_scores 中真实存在的产品，并回填真实名称
    const validated = await validateFunds(parsed.funds || [], allPool, 0)
    if (validated.length === 0) throw new Error('AI返回的产品均不在靠谱指数库中，请重试')

    const now = new Date()
    rpPortfolio.value = {
      id: Date.now().toString(),
      strategyName: parsed.strategyName || '风险平价组合',
      summary: parsed.summary || '',
      funds: validated,
      backtest: parsed.backtest ? { annualReturn: Number(parsed.backtest.annualReturn) || 0, maxDrawdown: Number(parsed.backtest.maxDrawdown) || 0, sharpe: Number(parsed.backtest.sharpe) || 0, winRate: Number(parsed.backtest.winRate) || 0 } : null,
      createdAt: `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
    }
    rpStatusText.value = '风险平价组合生成完成'
    await enrichRanks()
    const rpRet = await loadReturnsForHoldings(rpPortfolio.value.funds)
    if (rpRet) { rpPortfolio.value._returns = rpRet._returns; rpPortfolio.value._fundReturns = rpRet._fundReturns }
  } catch (err) { console.error('[generateRiskParityPortfolio]', err); rpStatusText.value = '生成失败: ' + err.message; rpPortfolio.value = null }
  finally { rpGenerating.value = false }
}

// 按品类精选高分基金：优先级 ETF > 指数型产品 > 主动管理型，同品类内按 k1（1年评分）降序取 top N
// 若某品类备选不足（< limit），自动启用 fallback：跨相关一级分类补充 / 扩大名称关键字范围，
// 确保每类资产都能展示足够多的高分基金
async function fetchCategoryFunds(cfg, limit) {
  if (!supabase) { console.warn('[fetchCategoryFunds] supabase client is null'); return [] }
  // 基础查询：按 t0（一级分类）或名称关键字定位品类，按 k1 降序
  const base = () => {
    let q = supabase.from('fund_scores').select('c,n,t0,t2,k1,k3,r3y')
      .not('k1', 'is', null)   // 最高风控规则在内存层按名称剔除持有期/定开产品
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
      // 核心：严格按一级分类(t0)筛选 —— 本资产大类必须全部取自该一级分类。
      // 例如 cash 权重→货币型(t0='货币型')取货币基金、bond→债券型取债券基金。
      // 1) 同 t0 内，ETF 优先
      const { data: etf, error: e1 } = await base().ilike('n', '%ETF%').order('k1', { ascending: false }).limit(limit)
      if (e1) console.error(`[fetchCategoryFunds] ${cfg.category} step1 ETF error:`, e1.message)
      funds = uniq(etf || [])
      // 2) 同 t0 内，指数型产品补充
      if (funds.length < limit) {
        const { data: idx, error: e2 } = await base().ilike('n', '%指数%').order('k1', { ascending: false }).limit(limit)
        if (e2) console.error(`[fetchCategoryFunds] ${cfg.category} step2 idx error:`, e2.message)
        funds = funds.concat(uniq(idx || [], new Set(funds.map(f => f.c))))
      }
      // 3) 同 t0 内，主动管理型兜底（不限名称，仍严格限定本 t0）
      if (funds.length < limit) {
        const { data: act, error: e3 } = await base().order('k1', { ascending: false }).limit(limit)
        if (e3) console.error(`[fetchCategoryFunds] ${cfg.category} step3 active error:`, e3.message)
        funds = funds.concat(uniq(act || [], new Set(funds.map(f => f.c))))
      }
      // 4) k1 稀疏时，同 t0 内按 k3(3年评分)降序补充，仍严格限定本一级分类
      if (funds.length < limit) {
        const have = new Set(funds.map(f => f.c))
        const { data: k3q, error: e4 } = await supabase.from('fund_scores')
          .select('c,n,t0,t2,k1,k3,r3y').not('k3', 'is', null)
          .eq('t0', cfg.t0).order('k3', { ascending: false }).limit(limit)
        if (e4) console.error(`[fetchCategoryFunds] ${cfg.category} step4 k3 error:`, e4.message)
        funds = funds.concat(uniq(k3q || [], have))
      }
      // 5) 跨相关一级分类补充（如股票→指数型），仅在同 t0 严重不足时启用，且指数型仍属权益大类
      if (funds.length < limit && cfg.fallbackT0) {
        const have = new Set(funds.map(f => f.c))
        const { data: fb, error: e5 } = await supabase.from('fund_scores')
          .select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
          .eq('t0', cfg.fallbackT0).order('k1', { ascending: false }).limit(limit)
        if (e5) console.error(`[fetchCategoryFunds] ${cfg.category} step5 fallback(${cfg.fallbackT0}) error:`, e5.message)
        funds = funds.concat(uniq(fb || [], have))
      }
      // 6) 终极兜底：同 t0 内全量按 k1 降序取 —— 绝不跨一级分类（确保货币基金/债券基金等保持品类纯粹）
      if (funds.length === 0) {
        console.warn(`[fetchCategoryFunds] ${cfg.category} 同 t0(${cfg.t0}) 全量兜底`)
        const { data: em, error: e6 } = await supabase.from('fund_scores')
          .select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
          .eq('t0', cfg.t0).order('k1', { ascending: false }).limit(limit)
        if (e6) console.error(`[fetchCategoryFunds] ${cfg.category} emergency error:`, e6.message)
        funds = em || []
      }
    } else if (cfg.nameKeyword) {
      // 商品/黄金/REIT 等以名称关键字识别的品类
      const { data, error: e0 } = await base().order('k1', { ascending: false }).limit(limit)
      if (e0) console.error(`[fetchCategoryFunds] ${cfg.category} nameKeyword error:`, e0.message)
      funds = data || []
      if (funds.length < limit && cfg.fallbackKeywords && cfg.fallbackKeywords.length) {
        const have = new Set(funds.map(f => f.c))
        for (const kw of cfg.fallbackKeywords) {
          if (funds.length >= limit) break
          const { data: fb, error: ek } = await supabase.from('fund_scores')
            .select('c,n,t0,t2,k1,k3,r3y').not('k1', 'is', null)
            .ilike('n', `%${kw}%`).order('k1', { ascending: false }).limit(limit)
          if (ek) console.error(`[fetchCategoryFunds] ${cfg.category} fallbackKeyword(${kw}) error:`, ek.message)
          funds = funds.concat(uniq(fb || [], have))
        }
      }
    }
  } catch (e) { console.error('[fetchCategoryFunds]', cfg.category, e) }
  // 最高风控规则：剔除持有期/定开等锁定期产品（名称匹配，月度调仓时卖不掉）
  return funds.filter(f => !isLockedFund(f.n)).slice(0, limit)
}

onMounted(() => {
  loadAiHistory()
  // 初始化：如果默认 tab 是自建组合且已登录，立即加载组合数据 + 元数据
  if (activeTab.value === 'custom' && isLoggedIn.value) {
    loadCustomPortfolios()
  }
})

// 监听：登录状态变为已登录 + 默认在自建组合 tab 时，自动加载
watch(isLoggedIn, (loggedIn) => {
  if (loggedIn && activeTab.value === 'custom') {
    loadCustomPortfolios()
  }
})

// 监听：自定义组合列表变化时（如从 AI 添加到自建），自动刷新元数据
watch(customPortfolios, (newVal) => {
  if (activeTab.value === 'custom' && newVal && newVal.length > 0) {
    enrichRanks()
    loadPortfolioReturns()
  }
}, { deep: true })
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

/* ===== 风险平价 / AI 组合 ===== */
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
.ai-category-logic { margin-bottom: var(--space-md); padding: var(--space-md); background: #eaf2fb; border-left: 4px solid #1d70b8; }
.ai-cl-title { font-size: 16px; font-weight: 700; color: #1d70b8; margin-bottom: var(--space-sm); }
.ai-cl-text { font-size: 14px; color: var(--text-primary); line-height: 1.7; white-space: pre-wrap; margin: 0; }
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

/* ===== AI 组合子标签（AI 策略 / 风险平价） ===== */
.ai-subtabs { display: flex; gap: var(--space-sm); margin-bottom: var(--space-lg); border-bottom: 1px solid var(--border); }
.ai-subtab { padding: var(--space-sm) var(--space-lg); font-size: 16px; font-weight: 700; color: var(--text-secondary); cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -1px; transition: all 0.15s; }
.ai-subtab:hover { color: var(--text-primary); }
.ai-subtab.active { color: #6c5ce7; border-bottom-color: #6c5ce7; }
.rp-card { background: #f4f9ff; border-left: 5px solid #1d70b8; }
.rp-weights { margin-bottom: var(--space-lg); padding: var(--space-md); background: #fff; border: 1px solid var(--border); }
.rp-w-title { font-size: 15px; font-weight: 700; color: var(--text-secondary); margin-bottom: var(--space-sm); }
.rp-w-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: var(--space-sm); }
.rp-w-cell { display: flex; flex-direction: column; align-items: center; padding: var(--space-sm); background: #eaf2fb; }
.rp-w-asset { font-size: 14px; color: var(--text-primary); }
.rp-w-val { font-size: 19px; font-weight: 700; color: #1d70b8; }
.ai-fund-asset { font-size: 12px; color: #fff; background: #1d70b8; padding: 1px 6px; margin-top: 2px; align-self: flex-start; }

/* ===== Utils ===== */
.text-up { color: var(--color-up); }
.text-down { color: var(--color-down); }
.footer-note { text-align: left; padding: var(--space-xl) 0; font-size: 14px; color: var(--text-secondary); border-top: 1px solid var(--border); }

/* ===== 移动端适配 ===== */
@media (max-width: 768px) {
  .ai-bt-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
