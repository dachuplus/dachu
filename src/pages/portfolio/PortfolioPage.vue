<template>
  <div class="page-portfolio">

    <!-- 三 Tab 导航 -->
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
        <p class="card-desc">登录后可创建和管理自己的基金组合</p>
        <div class="login-area">
          <input v-model="loginPhone" class="login-input" placeholder="输入手机号" maxlength="11" />
          <button class="login-btn" @click="doLogin" :disabled="loggingIn">
            {{ loggingIn ? '登录中...' : '登录 / 注册' }}
          </button>
          <span class="login-error" v-if="loginError">{{ loginError }}</span>
        </div>
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
        <p class="card-desc">选择投资策略，AI 分析当前市场并生成定制化基金组合</p>

        <div class="ai-strategies">
          <button
            v-for="st in AI_STRATEGIES"
            :key="st.key"
            class="ai-st-btn"
            :class="{ active: aiStrategy === st.key }"
            :disabled="aiGenerating"
            @click="aiStrategy = st.key"
          >
            {{ st.label }}
            <span class="ai-st-desc">{{ st.desc }}</span>
          </button>
          <button class="ai-st-btn ai-custom-st-btn" @click="showCustomDialog = true" :disabled="aiGenerating">
            自定义
            <span class="ai-st-desc">输入你的要求</span>
          </button>
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

    <!-- ==================== 3. 模型组合 ==================== -->
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
        <div class="portfolio-overview">
          <div class="po-item" v-for="item in portfolioItems" :key="item.assetKey">
            <div class="po-left">
              <SvgIcon :name="ASSET_ICONS[item.assetKey] || 'gear'" :size="20" class="po-icon" />
              <span class="po-name">{{ item.category }}</span>
            </div>
            <div class="po-right">
              <div class="po-bar"><div class="po-fill" :style="{ width: item.weight + '%' }"></div></div>
              <span class="po-weight">{{ item.weight }}%</span>
            </div>
          </div>
        </div>
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
                  <span class="etf-score">靠谱 {{ fmtScore(etf.k3) }}</span>
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

  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { supabase } from '../../api/supabase'
import SvgIcon from '../../components/SvgIcon.vue'
import { fetchValue500All } from '../../utils/api'
import { getIndexQuotes, buildMarketData } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights } from '../../utils/calc'
import { getMyPortfolios } from '../../api/user-data'

// ===== Tab =====
const tabs = [
  { key: 'custom', label: '自建组合' },
  { key: 'ai', label: 'AI 组合' },
  { key: 'model', label: '模型组合' }
]
const activeTab = ref('custom')

function switchTab(key) {
  activeTab.value = key
  if (key === 'model' && portfolioItems.value.length === 0) buildPortfolio()
  if (key === 'custom' && isLoggedIn.value) loadCustomPortfolios()
}

// ===== 登录 =====
const isLoggedIn = ref(false)
const loginPhone = ref('')
const loginError = ref('')
const loggingIn = ref(false)

function checkLogin() {
  const auth = localStorage.getItem('allfund_auth')
  if (auth) {
    try {
      const data = JSON.parse(auth)
      isLoggedIn.value = !!data.phone
    } catch { isLoggedIn.value = false }
  }
}

async function doLogin() {
  const phone = loginPhone.value.trim()
  if (!phone || phone.length !== 11) { loginError.value = '请输入正确的手机号'; return }
  loggingIn.value = true
  loginError.value = ''
  // 本地手机号认证
  const auth = { phone, name: phone, loginAt: Date.now() }
  localStorage.setItem('allfund_auth', JSON.stringify(auth))
  isLoggedIn.value = true
  loggingIn.value = false
  loadCustomPortfolios()
}

// ===== 自建组合 =====
const customPortfolios = ref([])
const showCreateModal = ref(false)
const newPfName = ref('')

async function loadCustomPortfolios() {
  try {
    const data = await getMyPortfolios()
    customPortfolios.value = data || []
  } catch {
    // fallback to localStorage
    const raw = localStorage.getItem('allfund_custom_pf')
    if (raw) {
      try { customPortfolios.value = JSON.parse(raw) } catch {}
    }
  }
}

function saveCustomToLocal() {
  localStorage.setItem('allfund_custom_pf', JSON.stringify(customPortfolios.value))
}

async function createPortfolio() {
  if (!newPfName.value.trim()) return
  const pf = {
    id: Date.now().toString(),
    name: newPfName.value.trim(),
    portfolio_data: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
  customPortfolios.value.unshift(pf)
  saveCustomToLocal()
  showCreateModal.value = false
  newPfName.value = ''
}

function deletePf(id) {
  if (!confirm('确定删除该组合？')) return
  customPortfolios.value = customPortfolios.value.filter(p => p.id !== id)
  saveCustomToLocal()
}

function editPortfolio(pf) {
  // 跳转到靠谱指数页面添加基金
  // 这里简单切换 tab 或不做操作
}

function updateWeight(pfId, code, weight) {
  const pf = customPortfolios.value.find(p => p.id === pfId)
  if (!pf) return
  const item = (pf.portfolio_data || []).find(i => i.code === code)
  if (item) item.weight = Math.max(0, Math.min(100, weight || 0))
  saveCustomToLocal()
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
const aiStrategy = ref('balanced')
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
function loadAiFromHistory(pf) { aiPortfolio.value = pf }

// ==== 自定义弹窗 ====
const showCustomDialog = ref(false)
const customRequirement = ref('')

async function generateAiPortfolio() {
  if (aiGenerating.value) return
  aiGenerating.value = true
  aiStatusText.value = '正在查询高分靠谱基金...'
  try {
    // 1. 从 Supabase 获取高分靠谱基金（k_all >= 70）
    let fundPool = []
    if (supabase) {
      const { data } = await supabase.from('fund_scores')
        .select('c,n,t0,k_all,score_grade')
        .not('k_all','is',null).gte('k_all', 70)
        .order('k_all', { ascending: false }).limit(30)
      fundPool = (data || []).map(f => `${f.c} ${f.n} (靠谱${f.k_all?.toFixed(0)})`)
    }
    if (fundPool.length === 0) {
      fundPool = ['510300 沪深300ETF', '159915 创业板ETF', '511260 10年国债ETF', '518880 黄金ETF', '512100 中证1000ETF', '510500 中证500ETF', '512880 证券ETF', '512010 医药ETF', '159928 消费ETF', '512480 半导体ETF', '512660 军工ETF', '512800 银行ETF', '515030 新能源ETF', '512980 传媒ETF', '159985 豆粕ETF']
    }

    const strategy = AI_STRATEGIES.find(s => s.key === aiStrategy.value)
    const strategyName = strategy?.label || '均衡配置'
    const customReq = customRequirement.value.trim()
    const reqHint = customReq ? `\n用户额外要求：${customReq}` : ''

    const prompt = `你是一位专业基金投顾。从以下高分靠谱基金池中，为"${strategyName}"策略选出10只基金构建组合。
基金池（代码 名称 靠谱分）：
${fundPool.join('\n')}
${reqHint}
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
      funds: (parsed.funds || []).map(f => ({ code: f.code, name: f.name, weight: Number(f.weight)||10, reason: f.reason||'' })),
      backtest: parsed.backtest ? { annualReturn: Number(parsed.backtest.annualReturn)||0, maxDrawdown: Number(parsed.backtest.maxDrawdown)||0, sharpe: Number(parsed.backtest.sharpe)||0, winRate: Number(parsed.backtest.winRate)||0 } : null,
      createdAt: `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}-${String(now.getDate()).padStart(2,'0')} ${String(now.getHours()).padStart(2,'0')}:${String(now.getMinutes()).padStart(2,'0')}`
    }
    saveAiToHistory(aiPortfolio.value)
    aiStatusText.value = 'AI 组合生成完成'
    customRequirement.value = ''
    showCustomDialog.value = false
  } catch (err) { console.error(err); aiStatusText.value = '生成失败: ' + err.message; aiPortfolio.value = null }
  finally { aiGenerating.value = false }
}

// 添加到自建组合
function addAiToCustom() {
  if (!aiPortfolio.value?.funds) return
  if (!isLoggedIn.value) { loginError.value = '请先登录'; return }
  const pfName = aiPortfolio.value.strategyName || 'AI组合'
  const pf = {
    id: Date.now().toString(),
    name: pfName,
    portfolio_data: aiPortfolio.value.funds.map(f => ({ code: f.code, name: f.name, weight: f.weight || 10, reason: f.reason || '' })),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString()
  }
  customPortfolios.value.unshift(pf)
  saveCustomToLocal()
  aiStatusText.value = '已添加到自建组合'
}

// ===== 模型组合（Kan & Zhou 风险平价） =====
const ASSET_ICONS = { stock: 'signal', bond: 'shield', commodity: 'gear', gold: 'medal', reit: 'portfolio', cash: 'dashboard' }
const ASSET_ETF_CONFIG = {
  stock: { category: '股票', t0: 'gp', period: 'k3', count: 3, keyword: 'ETF' },
  bond: { category: '债券', t0: 'zq', period: 'k3', count: 2, keyword: 'ETF' },
  commodity: { category: '商品', t0: null, period: 'k3', count: 1, keyword: '商品ETF' },
  gold: { category: '黄金', t0: null, period: 'k3', count: 1, keyword: '黄金' },
  reit: { category: 'REITs', t0: null, period: 'k3', count: 1, keyword: 'REIT' },
  cash: { category: '现金', t0: 'hb', period: 'k3', count: 0, noEtf: true }
}
const loading = ref(false)
const dataDate = ref('')
const weightSource = ref('')
const portfolioItems = ref([])

function fmtScore(val) { return val != null ? val.toFixed(1) : '--' }

async function buildPortfolio() {
  loading.value = true
  try {
    const [quotes, v500] = await Promise.all([getIndexQuotes(), fetchValue500All()])
    const bondData = v500.bond?.code === 0 ? v500.bond.data : {}
    const shiborData = v500.shibor?.code === 0 ? v500.shibor.data : {}
    const cpiData = v500.cpi?.code === 0 ? v500.cpi.data : {}
    const pe300Data = v500.pe300?.code === 0 ? v500.pe300.data : {}
    const rf = (bondData.yield10y && bondData.yield10y > 0) ? bondData.yield10y : null
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

async function fetchAllETFs(items) {
  if (!supabase) { portfolioItems.value = items.map(i => ({ ...i, loading: false, etfs: [] })); return }
  const results = await Promise.all(items.map(async item => {
    if (item.noEtf) return { ...item, loading: false }
    const cfg = ASSET_ETF_CONFIG[item.assetKey]; let query = supabase.from('fund_scores').select('c,n,t0,t2,k3,r3y').not('k3','is',null).gte('k3',0)
    if (cfg.t0) query = query.eq('t0', cfg.t0).ilike('n', `%${cfg.keyword}%`)
    else query = query.ilike('n', `%${cfg.keyword}%`)
    try {
      const { data } = await query.order('k3', { ascending: false }).limit(cfg.count)
      const funds = data || []; const etfs = []
      if (funds.length > 0) {
        const pw = Math.round(item.weight / funds.length); const used = pw * (funds.length - 1)
        funds.forEach((f, idx) => etfs.push({ code: f.c, name: f.n, weight: idx === funds.length - 1 ? item.weight - used : pw, k3: f.k3, r3y: f.r3y, reason: '靠谱指数(3年) ' + (f.k3||0).toFixed(1) }))
      }
      return { ...item, etfs, loading: false }
    } catch { return { ...item, etfs: [], loading: false } }
  }))
  portfolioItems.value = results
}

onMounted(() => {
  checkLogin()
  if (isLoggedIn.value) loadCustomPortfolios()
  loadAiHistory()
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
.login-area { display: flex; flex-wrap: wrap; gap: var(--space-sm); align-items: center; }
.login-input { padding: var(--space-sm); border: 1px solid var(--border); font-size: 16px; width: 200px; }
.login-btn { padding: var(--space-sm) var(--space-lg); background: #00703c; color: #fff; border: none; font-size: 16px; cursor: pointer; }
.login-btn:disabled { opacity: 0.6; }
.login-error { color: #d4351c; font-size: 14px; }

/* ===== 自建组合 ===== */
.pf-actions { margin-bottom: var(--space-md); }
.btn-primary { padding: var(--space-sm) var(--space-lg); background: #1d70b8; color: #fff; border: none; font-size: 16px; cursor: pointer; }
.btn-primary:disabled { opacity: 0.5; }
.btn-secondary { padding: var(--space-sm) var(--space-lg); background: #f3f2f1; color: var(--text-primary); border: 1px solid var(--border); font-size: 16px; cursor: pointer; }
.pf-card-hd { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-md); }
.pf-card-name { font-size: 19px; font-weight: 700; cursor: pointer; flex: 1; }
.pf-card-date { font-size: 14px; color: var(--text-secondary); }
.pf-card-del { padding: 2px var(--space-sm); border: 1px solid #d4351c; color: #d4351c; background: #fff; font-size: 13px; cursor: pointer; }
.pf-holdings { display: flex; flex-direction: column; gap: var(--space-sm); }
.pf-holding-item { display: flex; justify-content: space-between; align-items: center; padding: var(--space-sm); border: 1px solid var(--border); border-left: 4px solid #1d70b8; }
.pf-hold-left { display: flex; align-items: center; gap: var(--space-sm); }
.pf-hold-idx { width: 22px; height: 22px; line-height: 22px; text-align: center; background: #1d70b8; color: #fff; font-size: 13px; font-weight: 700; }
.pf-hold-name { font-size: 16px; font-weight: 700; }
.pf-hold-code { font-size: 13px; color: var(--text-secondary); }
.pf-hold-right { display: flex; align-items: center; gap: var(--space-sm); }
.pf-weight-input { width: 50px; padding: 2px var(--space-sm); border: 1px solid var(--border); font-size: 14px; text-align: center; }
.pf-hold-nav { font-size: 13px; color: var(--text-secondary); }
.pf-empty { padding: var(--space-lg); text-align: center; color: var(--text-secondary); }
.pf-summary { margin-top: var(--space-sm); padding-top: var(--space-sm); border-top: 1px solid var(--border); font-size: 14px; color: var(--text-secondary); }

/* ===== Modal ===== */
.modal-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 1000; }
.modal-box { background: #fff; padding: var(--space-xl); border: 1px solid var(--border); min-width: 300px; }
.modal-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.modal-input { width: 100%; padding: var(--space-sm); border: 1px solid var(--border); font-size: 16px; margin-bottom: var(--space-md); }
.modal-btns { display: flex; gap: var(--space-sm); justify-content: flex-end; }

/* ===== 模型组合 ===== */
.data-status { display: flex; align-items: center; gap: var(--space-sm); padding: var(--space-sm) 0; font-size: 14px; color: var(--text-secondary); }
.weight-source { font-weight: 700; }
.portfolio-overview { display: flex; flex-direction: column; gap: var(--space-sm); }
.po-item { display: flex; align-items: center; gap: var(--space-sm); }
.po-left { display: flex; align-items: center; gap: 6px; min-width: 90px; }
.po-name { font-size: 16px; font-weight: 700; }
.po-right { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.po-bar { flex: 1; height: 24px; background: #f3f2f1; overflow: hidden; }
.po-fill { height: 100%; background: #1d70b8; transition: width 0.6s; }
.po-weight { font-size: 16px; font-weight: 700; min-width: 48px; text-align: right; }
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
.ai-fund-item { display: flex; justify-content: space-between; align-items: center; padding: var(--space-sm) var(--space-md); border: 1px solid var(--border); border-left: 4px solid #6c5ce7; }
.ai-fund-left { display: flex; flex-direction: column; }
.ai-fund-name { font-size: 16px; font-weight: 700; }
.ai-fund-code { font-size: 13px; color: var(--text-secondary); }
.ai-fund-right { text-align: right; }
.ai-fund-weight { font-size: 19px; font-weight: 700; display: block; }
.ai-fund-reason { font-size: 13px; color: var(--text-secondary); }
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

/* ===== Utils ===== */
.text-up { color: var(--color-up); }
.text-down { color: var(--color-down); }
.footer-note { text-align: left; padding: var(--space-xl) 0; font-size: 14px; color: var(--text-secondary); border-top: 1px solid var(--border); }
</style>
