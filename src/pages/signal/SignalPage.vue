<template>
  <div class="page-signal">
    <!-- Header -->
    <div class="header-bar">
      <span class="data-time">数据截止：{{ dataDate }}</span>
      <div class="signal-filters">
        <label class="filter-select">
          <span class="filter-select__label">周期</span>
          <select v-model="selPeriod" @change="onPeriodChange" class="filter-select__input">
            <option v-for="p in periodOptions" :key="p.key" :value="p.key">{{ p.label }}</option>
          </select>
        </label>
        <label class="filter-select">
          <span class="filter-select__label">市场</span>
          <select v-model="selMarket" @change="onMarketChange" class="filter-select__input">
            <option v-for="m in marketOptions" :key="m.key" :value="m.key">{{ m.label }}</option>
          </select>
        </label>
        <span class="refresh-btn" @click="loadAll">{{ refreshing ? '加载中...' : '刷新' }}</span>
      </div>
    </div>

    <!-- 市场维度建设中提示 -->
    <div class="market-notice" v-if="marketNotice">
      <span class="market-notice__icon">i</span>
      <span>{{ marketNotice }}</span>
    </div>

    <!-- Tab 导航 -->
    <div class="signal-tabs">
      <div
        v-for="tab in tabs" :key="tab.key"
        class="signal-tab"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >{{ tab.label }}</div>
    </div>

    <!-- 错误提示 -->
    <div class="error-card" v-if="dataError">
      <p>{{ dataError }}</p>
    </div>

    <!-- ==================== 0. 信号总览（专业机构风格） ==================== -->
    <div v-if="activeTab === 'overview'">
      <div class="card overview-banner">
        <div class="ov-banner-title">信号总览</div>
        <p class="ov-banner-text">{{ overviewConclusion }}</p>
      </div>
      <div class="ov-grid">
        <div class="ov-card" v-for="c in signalOverview" :key="c.key">
          <div class="ov-card-head">
            <div class="ov-card-name">{{ c.name }}</div>
            <HelpTip :text="c.help" />
          </div>
          <div class="ov-card-value">{{ c.valueLabel }}</div>
          <div class="ov-bar-wrap" v-if="c.pct != null">
            <div class="ov-bar"><div class="ov-fill" :style="{ width: c.pct + '%', background: c.color }"></div></div>
            <span class="ov-pct">{{ c.pct }}%</span>
          </div>
          <div class="ov-signal" :class="c.signal">{{ c.signalLabel }}</div>
          <div class="ov-signal-label" :class="adviceClass(c.advice)">信号：{{ c.adviceLabel }}</div>
          <div class="ov-benchmark" v-if="c.benchmark">统计基准：{{ c.benchmark }}</div>
          <div class="ov-card-hint" v-if="c.hint">{{ c.hint }}</div>
        </div>
      </div>
      <p class="ov-hint">信号基于公开宏观与市场数据计算，仅供参考研究，不构成投资建议。</p>
    </div>

    <!-- ==================== 1. 宏观策略 ==================== -->
    <div v-if="activeTab === 'macro'">
      <!-- 隐含夏普仪表盘 -->
      <div class="card" v-if="dashData">
        <div class="card-title">宏观信号<HelpTip :text="MACRO_SIGNAL_HELP" /></div>
        <p class="card-desc">全市场风险平价加权隐含夏普，正值 = 整体有超额收益吸引力</p>
        <div class="gauge-wrap" ref="gaugeEl"></div>
        <div class="gauge-range">取值范围：−1 ~ 1</div>
      </div>

      <!-- 宏观指标 6 个 + 10年历史 -->
      <div class="card">
        <div class="card-title">宏观指标（近10年）</div>
        <div class="macro-indicators">
          <div class="macro-item" v-for="m in macroList" :key="m.key">
            <div class="macro-label">{{ m.label }}<HelpTip v-if="m.help" :text="m.help" align="right" /></div>
            <div class="macro-value">{{ m.value }}</div>
            <div class="macro-date">{{ m.date }}</div>
            <div class="macro-chart-wrap" :class="{ 'macro-chart-expanded': macroExpand[m.key] }">
              <div class="macro-chart" :ref="el => setChartRef(m.key, el)"></div>
            </div>
            <div class="macro-more" v-if="macroHistory[m.key] && macroHistory[m.key].length > MACRO_DEFAULT_WINDOW && !macroExpand[m.key]">
              <span class="more-btn" @click="expandMacroChart(m.key)">更多</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 2. 股债对比 ==================== -->
    <div v-if="activeTab === 'fed'">
      <div class="card">
        <div class="card-title">
          股债性价比
          <span class="card-subtitle">FED Model — 风险溢价指标</span>
        </div>
        <p class="card-desc">股债利差 = 1/PE − 10年期国债收益率，利差越大股票越便宜</p>
        <div class="fed-grid">
          <div class="fed-card" v-for="idx in fedIndices" :key="idx.key">
            <div class="fed-name">{{ idx.name }}</div>
            <div class="fed-spread" :style="{ color: idx.spread > 3 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ idx.spread }}%
            </div>
            <div class="fed-label">股债利差</div>
            <div class="fed-details">
              <div class="fed-row"><span>PE</span><span>{{ idx.pe }}倍</span></div>
              <div class="fed-row"><span>PE百分位</span><span>{{ idx.pePercentile }}%</span></div>
            </div>
          </div>
        </div>
        <p class="data-source">数据参考：funddb.cn | 中国10年期国债收益率 {{ bondY10y }}%</p>
        <!-- FED 历史走势图 -->
        <div class="card-title" style="margin-top:20px">
          股债性价比历史走势（2002—今）
          <span class="card-subtitle">上证指数叠加 10Y 国债收益率 ± 标准差带</span>
        </div>
        <div ref="fedChartEl" style="height:420px"></div>
        <p class="chart-hint" style="margin-top:8px;font-size:12px;color:var(--text-muted)">
          蓝线 = 10Y国债收益率 | 浅蓝带 = ±1σ / ±2σ 标准差 | 灰底 = 上证指数 | 红线 = 当前股债利差参考线
        </p>
      </div>
    </div>

    <!-- ==================== 3. 资产对比 ==================== -->
    <div v-if="activeTab === 'compare'">
      <div class="card">
        <div class="card-title">资产对比 — 隐含夏普 / 预期收益 / 风险溢价</div>
        <p class="card-desc">现金用Shibor，债券用YTM，股票用Gordon模型，黄金用实际利率模型</p>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>资产</th>
                <th>指标</th>
                <th>隐含夏普</th>
                <th>预期收益</th>
                <th>风险溢价</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="item in assets" :key="item.key" :class="{ 'row-disabled': !item.hasData }">
                <td class="td-name">{{ item.name }}</td>
                <td>
                  <template v-if="item.isStock">
                    <span>{{ item.metricLabel }}</span>
                    <span class="metric-sub">百分位{{ item.metricSub }}</span>
                  </template>
                  <template v-else>
                    <span :class="metricClass(item.metricLabel)">{{ item.metricLabel }}</span>
                  </template>
                </td>
                <td :style="{ color: item.sharpeColor }">{{ item.sharpeStr }}</td>
                <td :class="item.hasData ? 'text-up' : ''">{{ item.expectedReturn }}</td>
                <td :class="rpClass(item.riskPremium)">{{ item.riskPremium }}</td>
              </tr>
            </tbody>
          </table>
        </div>
        <!-- 上证指数历史走势 -->
        <div class="card-title" style="margin-top:20px">上证指数历史走势</div>
        <div ref="compareIdxEl" style="height:200px"></div>
      </div>
    </div>

    <!-- ==================== 4. 资产配比 ==================== -->
    <div v-if="activeTab === 'allocate'">
      <div class="card">
        <div class="card-title">资产配比 — Kan & Zhou 增强型风险平价</div>
        <p class="card-desc">基础权重 × 夏普信号调整，限幅 [0%, 50%]</p>
        <div class="allocate-layout">
          <!-- 饼图 -->
          <div class="pie-section">
            <div class="pie-chart" ref="pieEl"></div>
          </div>
          <!-- 配置明细表 -->
          <div class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th>资产</th>
                  <th>基础权重</th>
                  <th>调整权重</th>
                  <th>变化</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="w in weightList" :key="w.key">
                  <td class="td-name">{{ w.name }}</td>
                  <td>{{ w.baseWeight }}%</td>
                  <td class="text-brand">{{ w.weight }}%</td>
                  <td :class="w.weight > w.baseWeight ? 'text-up' : 'text-down'">
                    {{ w.weight > w.baseWeight ? '+' : '' }}{{ (w.weight - w.baseWeight).toFixed(0) }}%
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 5. 风格因子 ==================== -->
    <div v-if="activeTab === 'factor'">
      <!-- 子Tab -->
      <div class="sub-tabs">
        <div
          v-for="st in factorSubTabs" :key="st.key"
          class="sub-tab" :class="{ active: factorSub === st.key }"
          @click="switchFactorSub(st.key)"
        >{{ st.label }}</div>
      </div>
      <div v-if="factorSub === 'stock'">
        <div class="card">
          <div class="card-title">Barra 六因子蛛网图（估值分，默认）</div>
          <div class="radar-wrap" ref="radarEl" v-show="factorFactors.length > 0"></div>
          <div class="empty-hint" v-if="factorFactors.length === 0">风格因子数据建设中，暂未提供真实数据（宁空不假）</div>
        </div>
          <div class="card">
          <div class="card-title">因子评分详情（估值分高=贵·性价比低；性价比分高=便宜·性价比高）</div>
          <div class="factor-grid">
            <div class="factor-item" v-for="f in factorFactors" :key="f.key">
              <div class="factor-head">
                <span class="factor-name">{{ f.name }}</span>
                <span class="factor-signal" :class="f.signal">{{ f.signalLabel }}</span>
              </div>
              <div class="factor-bar-wrap">
                <div class="factor-bar">
                  <div class="factor-fill" :style="{ width: f.percentile + '%', background: f.color }"></div>
                </div>
                <span class="factor-val">估值分 {{ f.percentile }}</span>
              </div>
              <div class="factor-scores">性价比分 <b>{{ f.cost_score }}</b>（高 = 便宜 · 性价比高）</div>
            </div>
          </div>
        </div>
      </div>
      <div v-if="factorSub === 'bond'" class="card">
        <div class="card-title">国债收益率曲线</div>
        <div class="chart-wrap" ref="bondCurveEl"></div>
        <div class="card-title" style="margin-top:20px">10Y国债历史走势</div>
        <div class="macro-chart" ref="bondHistEl" style="height:200px"></div>
        <div class="card-title" style="margin-top:20px">期限利差</div>
        <div class="spread-item" v-for="s in bondSpreads" :key="s.label">
          <span>{{ s.label }}</span>
          <span :class="s.bp > 0 ? 'text-up' : 'text-down'">{{ s.bp }}bp</span>
        </div>
      </div>
      <div v-if="factorSub === 'commodity'" class="card">
        <div class="card-title">核心商品价格</div>
        <div class="comm-grid">
          <div class="comm-item" v-for="c in commodityItems" :key="c.label">
            <div class="comm-label">{{ c.label }}</div>
            <div class="comm-value">{{ c.value }}</div>
            <div :class="c.change > 0 ? 'text-up' : 'text-down'">{{ c.change > 0 ? '+' : '' }}{{ c.change }}%</div>
          </div>
        </div>
      </div>
    </div>

    <!-- ==================== 6. 行业估值 ==================== -->
    <div v-if="activeTab === 'industry'">
      <div class="card">
        <div class="card-title">指数估值排行</div>
        <div class="filter-row">
          <span
            v-for="f in industryFilters" :key="f.key"
            class="filter-chip" :class="{ active: industryFilter === f.key }"
            @click="industryFilter = f.key"
          >{{ f.label }}</span>
        </div>
        <div class="table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th class="sortable" @click="sortIndustry('name')">名称 {{ sortIcon('name') }}</th>
                <th class="sortable" @click="sortIndustry('pe')">PE {{ sortIcon('pe') }}</th>
                <th class="sortable" @click="sortIndustry('pe_pct')">PE百分位 {{ sortIcon('pe_pct') }}</th>
                <th class="sortable" @click="sortIndustry('pb')">PB {{ sortIcon('pb') }}</th>
                <th class="sortable" @click="sortIndustry('pb_pct')">PB百分位 {{ sortIcon('pb_pct') }}</th>
                <th class="sortable" @click="sortIndustry('div_yield')">股息率 {{ sortIcon('div_yield') }}</th>
                <th class="sortable" @click="sortIndustry('roe')">ROE {{ sortIcon('roe') }}</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in industryList" :key="row.code" @click="toggleIndustryExpand(row)">
                <td>{{ row.name }}</td>
                <td>{{ row.pe }}</td>
                <td :class="row.pe_pct_color">{{ row.pe_pct }}%</td>
                <td>{{ row.pb }}</td>
                <td :class="row.pb_pct_color">{{ row.pb_pct }}%</td>
                <td>{{ row.div_yield }}%</td>
                <td>{{ row.roe }}%</td>
              </tr>
            </tbody>
          </table>
        </div>
        <p class="data-source">数据来源：蛋卷基金估值中心</p>
      </div>
    </div>

    <!-- ==================== 7. 特色指标 ==================== -->
    <div v-if="activeTab === 'jqr'">
      <div class="card">
        <div class="card-title">特色指标<span class="card-subtitle">自建复合算法 · 每日更新</span></div>
        <p class="card-desc">恐贪指数衡量市场短期情绪，市场温度反映估值冷热，基金发行热度体现权益基金募集景气——三者互补，辅助判断市场所处阶段。</p>
        <div class="jqr-grid">
          <div class="jqr-card" v-for="c in jqrCards" :key="c.key">
            <div class="jqr-card-name">{{ c.name }}</div>
            <div class="jqr-value" :style="{ color: c.color }">{{ c.valueLabel }}</div>
            <div class="jqr-signal" :class="c.signalClass">{{ c.signalLabel }}</div>
            <div class="jqr-range">取值范围：{{ c.range }}</div>
            <div class="jqr-date">数据日期：{{ c.date }}</div>
            <div class="jqr-sub" v-if="c.subLines.length">
              <div class="jqr-sub-row" v-for="s in c.subLines" :key="s.k"><span>{{ s.k }}</span><span>{{ s.v }}</span></div>
            </div>
          </div>
        </div>
      </div>
      <div class="card" v-for="c in jqrCards" :key="'chart-' + c.key">
        <div class="card-title">{{ c.name }} · 历史走势</div>
        <div class="jqr-chart" :ref="el => setJqrChartRef(c.key, el)"></div>
      </div>
      <p class="data-source">数据来源：akshare（沪深300日线 / 全市场市盈率 / 新发基金），自建复合算法，仅供参考研究，不构成投资建议。</p>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRoute } from 'vue-router'
import echarts from '../../utils/echarts-setup'
import { getIndexQuotes, buildMarketData, parseValue500Data } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights, calcMarketSharpe, calcRiskPremium } from '../../utils/calc'
import { fetchValue500All, fetchConfig, fetchIndexEva, fetchFactorScores } from '../../utils/api'
import { COLORS } from '../../utils/echarts-theme'
import { supabase } from '../../api/supabase'
import HelpTip from '../../components/HelpTip.vue'

// ===== Tab 结构 =====
const tabs = [
  { key: 'overview', label: '信号总览' },
  { key: 'macro',    label: '宏观策略' },
  { key: 'fed',      label: '股债对比' },
  { key: 'compare',  label: '资产对比' },
  { key: 'allocate', label: '资产配比' },
  { key: 'factor',   label: '风格因子' },
  { key: 'industry', label: '行业估值' },
  { key: 'jqr',      label: '特色指标' },
]
// ===== 标签页持久化（Req6）：刷新后保留浏览位置 =====
const ACTIVE_TAB_KEY = 'af_signal_active_tab'
const activeTab = ref(localStorage.getItem(ACTIVE_TAB_KEY) || 'overview')
watch(activeTab, (t) => { try { localStorage.setItem(ACTIVE_TAB_KEY, t) } catch (e) {} })

// ===== 周期 / 市场 筛选（Req1） =====
const periodOptions = [
  { key: 'week',    label: '周度', window: 250,    fedDays: 365 },
  { key: 'month',   label: '月度', window: 750,    fedDays: 1095 },
  { key: 'quarter', label: '季度', window: 1250,   fedDays: 1825 },
  { key: 'year',    label: '年度', window: 100000, fedDays: 999999 },
]
const marketOptions = [
  { key: 'all', label: '全市场' },
  { key: 'hs',  label: '沪深' },
  { key: 'hk',  label: '港股', building: true },
  { key: 'us',  label: '美股', building: true },
]
const selPeriod = ref('quarter')
const selMarket = ref('all')
const marketNotice = computed(() => {
  const m = marketOptions.find(x => x.key === selMarket.value)
  if (m && m.building) return `${m.label}信号模块建设中，当前展示全市场数据`
  return ''
})
function onPeriodChange() { updateMacroWindow(); redrawCurrentCharts() }
function onMarketChange() { redrawCurrentCharts() }

// ===== 通用状态 =====
const dataDate = ref('--')
const dataError = ref('')
const refreshing = ref(false)

// ===== 信号总览（仅呈现指标信号，不提供配置建议） =====
const signalOverview = ref([])
const pe300PctGlobal = ref(null)
const pmiValGlobal = ref(null)
const us10yVal = ref(null)
const overviewConclusion = computed(() => {
  const list = signalOverview.value
  if (!list.length) return ''
  const ow = list.filter(c => c.advice === 'overweight').length
  const uw = list.filter(c => c.advice === 'underweight').length
  const nt = list.length - ow - uw
  let head
  if (ow >= 3) head = '多数信号指向风险资产性价比提升'
  else if (uw >= 3) head = '多重信号偏紧'
  else head = '信号分化'
  // 仅陈述信号分布，不提供任何配置建议
  return `${head}（偏多 ${ow} · 偏空 ${uw} · 中性 ${nt}）`
})

// ===== 宏觀數據 =====
const bondY10y = ref(null)
const dashData = ref(null)

// ===== 资产配置 =====
const ASSET_META = {
  cash:      { name: '现金', color: '#505a5f' },
  bond:      { name: '债券', color: '#1d70b8' },
  stock:     { name: '股票', color: '#d4351c' },
  commodity: { name: '商品', color: '#f47738' },
  gold:      { name: '黄金', color: '#5694ca' },
  reit:      { name: 'REITs', color: '#4c2c92' }
}
const assets = ref([])
const weightList = ref([])

// ===== Macro indicators =====
const macroList = ref([
  { key: 'cn10y',  label: '中国10Y国债', value: '--', date: '', series: [], help: '中国10年期国债收益率\n含义：以中国10年期国债到期收益率为代表的无风险利率，是股债性价比与风险平价计算的核心输入。收益率越低，市场流动性越宽松、股票相对越便宜。\n数据来源：中债国债收益率曲线（经 akshare / value500 数据代理抓取）。\n更新时间：每个交易日收盘后更新（与页面顶部"数据截止"一致，每日 21:30 同步）。' },
  { key: 'us10y',  label: '美国10Y国债', value: '--', date: '', series: [], help: '美国10年期国债收益率\n含义：全球资产定价的锚，影响跨境流动性与风险偏好。越高越偏紧，对新兴市场与权益估值压制越大。\n数据来源：美国国债收益率（经 value500 数据代理抓取）。\n更新时间：美债收盘较晚，每日 22:00 后同步更新。' },
  { key: 'shibor', label: 'Shibor隔夜', value: '--', date: '', series: [], help: 'Shibor 隔夜利率\n含义：上海银行间同业拆放利率（隔夜），反映短端资金面松紧，是无风险利率 Rf 的近似。\n数据来源：上海银行间同业拆放利率（经 akshare / value500 抓取）。\n更新时间：每个交易日 11:00 左右公布，每日同步。' },
  { key: 'cpi',    label: 'CPI同比', value: '--', date: '', series: [], help: 'CPI 同比\n含义：居民消费价格同比涨幅，衡量通胀水平。通胀上行通常伴随货币政策收紧预期。\n数据来源：国家统计局。\n更新时间：每月 9-10 日左右公布上月数据。' },
  { key: 'm2',     label: 'M2同比', value: '--', date: '', series: [], help: 'M2 同比\n含义：广义货币供应量同比增速，反映货币投放与流动性总量。增速上行通常预示流动性宽松。\n数据来源：中国人民银行。\n更新时间：每月 10-15 日公布上月数据。' },
  { key: 'ppi',    label: 'PPI同比', value: '--', date: '', series: [], help: 'PPI 同比\n含义：工业生产者出厂价格同比涨幅，衡量工业品通缩/通胀，领先于企业盈利。\n数据来源：国家统计局。\n更新时间：每月 9-10 日左右公布上月数据。' },
])

// 「宏观信号」仪表盘详细说明（含义 / 取值范围 / 计算公式 / 数据来源 / 更新时间）
const MACRO_SIGNAL_HELP = [
  '宏观信号（原"全市场加权平均隐含夏普"）',
  '含义：用风险平价权重对现金 / 债券 / 股票 / 商品 / 黄金 / REITs 六大类资产的隐含夏普比率做加权平均，衡量当前股债商整体性价比。数值越正，权益资产相对越有吸引力；越负，防御资产越占优。',
  '取值范围：−1 ~ 1（仪表盘两端已标注）。',
  '计算公式：单资产隐含夏普 SR_i = (E[R_i] − Rf) / σ_i；宏观信号 = Σ_i w_i^RP × SR_i，其中 w_i^RP 为风险平价权重，Rf 为无风险利率（取 Shibor 隔夜）。',
  '数据来源：沪深300 / 中证500 / 中证1000 的 PE 与历史分位、中国10Y国债收益率、Shibor、CPI、黄金价格、PMI 等公开宏观与市场数据。',
  '更新时间：每日 21:30 自动更新（与页面顶部"数据截止"一致）。'
].join('\n\n')
// "更多"展开状态
const macroExpand = reactive({})
const macroHistory = reactive({}) // 完整历史数据缓存
let MACRO_DEFAULT_WINDOW = 1250 // dataZoom 默认窗口（随周期筛选动态变化，见 updateMacroWindow）
function updateMacroWindow() {
  const p = periodOptions.find(x => x.key === selPeriod.value)
  MACRO_DEFAULT_WINDOW = p ? p.window : 1250
}

const chartRefs = {}
function setChartRef(key, el) {
  if (el) chartRefs[key] = el
}

// ===== FED 模型 =====
const fedIndices = ref([
  { key: 'hs300', name: '沪深300', spread: '--', pe: '--', pePercentile: '--' },
  { key: 'zz500', name: '中证500', spread: '--', pe: '--', pePercentile: '--' },
  { key: 'zz1000', name: '中证1000', spread: '--', pe: '--', pePercentile: '--' }
])

// ===== 风格因子 =====
const factorSubTabs = [
  { key: 'stock', label: '股票风格' },
  { key: 'bond', label: '债券' },
  { key: 'commodity', label: '商品宏观' }
]
const factorSub = ref('stock')
const factorFactors = ref([])
const bondSpreads = ref([])
const commodityItems = ref([])

// ===== ECharts instances =====
let gaugeChart = null
let pieChart = null
let radarChart = null
let bondCurveChart = null
let fedChart = null
let compareIdxChart = null
let fedHistChart = null

// ===== 行业估值 =====
const industryFilters = [
  { key: 'all', label: '全部' },
  { key: 'broad', label: '宽基' },
  { key: 'strategy', label: '策略' },
  { key: 'sector', label: '行业主题' }
]
const industryFilter = ref('all')
const industryRaw = ref([])
const industrySort = reactive({ field: 'pe_pct', asc: true })

const filteredIndustry = computed(() => {
  let list = [...industryRaw.value]
  if (industryFilter.value === 'broad') {
    list = list.filter(r => r.cat === 'broad')
  } else if (industryFilter.value === 'strategy') {
    list = list.filter(r => r.cat === 'strategy')
  } else if (industryFilter.value === 'sector') {
    list = list.filter(r => r.cat === 'sector')
  }
  const f = industrySort.field
  list.sort((a, b) => {
    const va = a[f]; const vb = b[f]
    if (va == null && vb == null) return 0
    if (va == null) return 1; if (vb == null) return -1
    return industrySort.asc ? va - vb : vb - va
  })
  return list.map(r => ({
    ...r,
    pe_pct_color: r.pe_pct > 70 ? 'text-up' : r.pe_pct < 30 ? 'text-down' : '',
    pb_pct_color: r.pb_pct > 70 ? 'text-up' : r.pb_pct < 30 ? 'text-down' : '',
  }))
})

const industryList = computed(() => filteredIndustry.value.slice(0, 100))

// ===== 工具函数 =====
function metricClass(label) {
  if (!label || label === '--') return ''
  return label[0] === '+' ? 'text-up' : (label[0] === '-' ? 'text-down' : '')
}

function rpClass(val) {
  if (!val || val === '--') return ''
  return val[0] === '+' ? 'text-up' : 'text-down'
}

function sortIndustry(field) {
  if (industrySort.field === field) {
    industrySort.asc = !industrySort.asc
  } else {
    industrySort.field = field
    industrySort.asc = field === 'pe_pct' || field === 'pb_pct'
  }
}

function sortIcon(field) {
  if (industrySort.field !== field) return ''
  return industrySort.asc ? '▲' : '▼'
}

function toggleIndustryExpand(row) {
  // placeholder for expand
}

function switchFactorSub(key) {
  factorSub.value = key
  if (key === 'bond') {
    nextTick(() => drawBondCurve())
  }
}

// ===== 数据加载 =====
async function loadAll() {
  refreshing.value = true
  dataError.value = ''

  try {
    const [quotes, v500] = await Promise.all([
      getIndexQuotes(),
      fetchValue500All()
    ])

    const { bond: bondData, shibor: shiborData, m2: m2Data, cpi: cpiData, ep: epData, pe300: pe300Data, rf, get: v500Get } = parseValue500Data(v500)
    const goldData = v500Get('gold')
    const usdxData = v500Get('usdx')
    const bdiData = v500Get('bdi')
    const ppiData = v500Get('ppi')
    const pmiData = v500Get('pmi')

    // 宏观数据
    bondY10y.value = bondData.yield10y ?? null

    // 更新时间
    const firstQuote = quotes['sh000001'] || quotes['sh000300'] || {}
    const updateTime = firstQuote.updateTime || ''
    dataDate.value = updateTime.length === 14
      ? `${updateTime.slice(0,4)}-${updateTime.slice(4,6)}-${updateTime.slice(6,8)} ${updateTime.slice(8,10)}:${updateTime.slice(10,12)}`
      : new Date().toLocaleString('zh-CN')

    // ===== 从 Supabase macro_history 表获取历史数据 =====
    // 先用 v500 数据构建 macroList，再异步填充 series（不阻塞主流程）
    const v500Values = {
      cn10y:  { value: bondData.yield10y != null ? (bondData.yield10y * 100).toFixed(2) + '%' : '--', date: bondData.date || '' },
      shibor: { value: shiborData.on != null ? (shiborData.on * 100).toFixed(3) + '%' : '--', date: shiborData.date || '' },
      cpi:    { value: cpiData.cpi != null ? (cpiData.cpi * 100).toFixed(1) + '%' : '--', date: cpiData.date || '' },
      m2:     { value: m2Data.m2yoy != null ? m2Data.m2yoy + '%' : '--', date: m2Data.date || '' },
      us10y:  { value: '--', date: '' },
      ppi:    { value: '--', date: '' }
    }
    macroList.value = ['cn10y', 'us10y', 'shibor', 'cpi', 'm2', 'ppi'].map(k => {
      const labels = { cn10y: '中国10Y国债', us10y: '美国10Y国债', shibor: 'Shibor隔夜', cpi: 'CPI同比', m2: 'M2同比', ppi: 'PPI同比' }
      return { key: k, label: labels[k], value: v500Values[k]?.value || '--', date: v500Values[k]?.date || '', series: [] }
    })

    // 异步加载历史数据（不阻塞主流程）
    loadMacroHistoryAsync()

    // 市场数据

    // 市场数据
    const v300Pct = pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null
    const marketData = buildMarketData(quotes, { pePercentile: v300Pct }, {
      yield10y: rf || 0,
      shibor: { on: shiborData.on || 0, date: shiborData.date }
    })

    // 预期收益率
    const erParams = {
      stock: { pe: marketData.stock.pe, pePercentile: marketData.stock.pePercentile },
      bond: { yield10y: rf },
      gold: { yield10y: rf, cpi: cpiData.cpi },
      cash: { shiborOn: marketData.cash.shiborOn || 0 }
    }
    const expectedReturns = calcAllExpectedReturns(erParams)
    const rpResult = calcEnhancedRiskParityWeights(expectedReturns, rf, 0.5)

    // 全市场夏普
    const ms = calcMarketSharpe(rpResult.sharpeMap)
    dashData.value = {
      value: ms != null ? ms : 0,
      label: ms != null ? (ms > 0 ? '市场性价比偏正面' : '市场性价比偏负面') : '无数据'
    }

    // 资产卡片
    const assetKeys = ['cash', 'bond', 'stock', 'commodity', 'gold', 'reit']
    const stockPE = pe300Data.pe || marketData.stock.pe || 0
    const tmpAssets = []
    for (const key of assetKeys) {
      const meta = ASSET_META[key]
      const er = expectedReturns[key]
      const sharpe = rpResult.sharpeMap[key]
      const hasData = er.expectedReturn != null
      let metricLabel = '--', metricSub = ''
      if (key === 'stock') {
        metricLabel = stockPE > 0 ? stockPE.toFixed(2) : '--'
        metricSub = marketData.stock.pePercentile != null ? marketData.stock.pePercentile + '%' : '--'
      } else if (marketData[key]?.changePct) {
        const cp = marketData[key].changePct
        metricLabel = (cp > 0 ? '+' : '') + cp.toFixed(2) + '%'
      }
      tmpAssets.push({
        key, name: meta.name, isStock: key === 'stock',
        metricLabel, metricSub,
        impliedSharpe: sharpe,
        sharpeStr: sharpe != null ? (sharpe > 0 ? '+' : '') + sharpe.toFixed(3) : '--',
        sharpeColor: sharpe != null ? (sharpe > 0 ? 'var(--color-up)' : 'var(--color-down)') : 'var(--text-secondary)',
        expectedReturn: hasData ? (er.expectedReturn * 100).toFixed(2) + '%' : '--',
        riskPremium: hasData && rf != null
          ? (() => { const rp = calcRiskPremium(er.expectedReturn, rf); return rp != null ? (rp > 0 ? '+' : '') + (rp * 100).toFixed(2) + '%' : '--' })()
          : '--',
        hasData
      })
    }
    assets.value = tmpAssets

    // 权重
    const baseWeights = rpResult.baseWeights
    weightList.value = assetKeys.map(key => ({
      key,
      name: ASSET_META[key].name,
      weight: rpResult.weights[key] != null ? rpResult.weights[key] : 0,
      baseWeight: baseWeights[key] != null ? Math.round(baseWeights[key] * 100) : 0,
      color: ASSET_META[key].color
    }))

    // 债券利差
    bondSpreads.value = bondData.spread != null
      ? [{ label: '10Y-1Y期限利差', bp: bondData.spread }]
      : []

    // 商品数据
    commodityItems.value = [
      { label: '黄金(美元/盎司)', value: goldData.price != null ? '$' + goldData.price : '--', change: goldData.changePct ?? 0 },
      { label: '美元指数', value: usdxData.price != null ? usdxData.price.toFixed(2) : '--', change: usdxData.changePct ?? 0 },
      { label: 'BDI 波罗的海', value: bdiData.price != null ? bdiData.price : '--', change: bdiData.changePct ?? 0 },
      { label: 'PPI 同比', value: ppiData.ppi != null ? ppiData.ppi + '%' : '--', change: 0 },
      { label: 'PMI', value: pmiData.pmi != null ? pmiData.pmi : '--', change: 0 }
    ]

    // FED
    calcFED(quotes, rf)

    // 信号总览全局值 + 计算
    pe300PctGlobal.value = v300Pct
    pmiValGlobal.value = pmiData.pmi != null ? pmiData.pmi : null
    buildSignalOverview()

    // Charts
    await nextTick()
    drawGauge()
    drawMacroCharts()

    // 风格因子 + 行业估值 + 特色指标（读生产表，异步不阻塞主流程）
    loadFactorScores()
    loadIndustry()
    loadJqr()

  } catch (err) {
    let msg = '数据加载失败'
    if (err?.message) msg = err.message.includes('timeout') ? '请求超时' : err.message
    dataError.value = msg
  } finally {
    refreshing.value = false
  }
}

// ===== 风格因子（暂未接入真实因子数据源，宁空不假） =====
// 原先的 calcStyleFactors 以指数 PE 比值估算各 Barra 因子百分位，属于启发式伪造数据，
// 已移除。等待接入真实多因子模型数据后再填充 factorFactors，当前展示"建设中"空状态。
function drawRadar() {
  const el = radarEl.value
  if (!el) return
  if (radarChart) radarChart.dispose()
  if (!factorFactors.value || factorFactors.value.length === 0) return

  const indicator = factorFactors.value.map(f => ({ name: f.name, max: 100 }))
  const valValues = factorFactors.value.map(f => f.percentile)   // 估值分 高=贵
  radarChart = echarts.init(el)
  radarChart.setOption({
    color: ['#d4351c'],
    tooltip: { trigger: 'item' },
    legend: {
      data: ['估值分（高=贵）'],
      bottom: 0, textStyle: { color: '#505a5f', fontSize: 12 }, itemGap: 18
    },
    radar: {
      indicator, shape: 'polygon', splitNumber: 4,
      center: ['50%', '47%'], radius: '62%',
      axisName: { color: '#505a5f', fontSize: 12 },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
      splitArea: { areaStyle: { color: ['#ffffff', '#f8f8f8'] } },
      axisLine: { lineStyle: { color: '#b1b4b6' } }
    },
    series: [{
      type: 'radar',
      data: [
        {
          value: valValues, name: '估值分（高=贵）',
          areaStyle: { color: 'rgba(212,53,28,0.15)' },
          lineStyle: { color: '#d4351c', width: 2 },
          itemStyle: { color: '#d4351c' }, symbol: 'circle', symbolSize: 5
        }
      ]
    }]
  })
}

function drawBondCurve() {
  const el = bondCurveEl.value
  if (!el) return
  if (bondCurveChart) bondCurveChart.dispose()
  bondCurveChart = echarts.init(el)
  bondCurveChart.setOption({
    xAxis: { type: 'category', data: ['1Y','2Y','3Y','5Y','7Y','10Y','30Y'], axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false } },
    yAxis: { type: 'value', name: '%', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false } },
    series: [{ type: 'line', data: [1.5, 1.6, 1.7, 1.9, 2.1, bondY10y.value ? (bondY10y.value * 100).toFixed(1) : 2.3, 2.7], lineStyle: { width: 2, color: COLORS[0] }, symbol: 'circle', symbolSize: 6, itemStyle: { color: COLORS[0] } }]
  })

  // 10Y 国债历史走势（复用 macroHistory 中的 cn10y 数据）
  const histEl = bondHistEl.value
  if (histEl && macroHistory['cn10y']) {
    const hdom = histEl.querySelector ? (histEl.querySelector('.macro-chart') || histEl) : histEl
    const hchart = echarts.getInstanceByDom(hdom) || echarts.init(hdom)
    fedHistChart = hchart
    const hist = [...macroHistory['cn10y']].reverse() // ASC
    const dates = hist.map(d => d.date)
    const values = hist.map(d => d.value)
    const total = dates.length
    const defWin = MACRO_DEFAULT_WINDOW
    const useDataZoom = total > defWin
    const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
    const labelStep = Math.max(1, Math.floor(total / 8))
    hchart.setOption({
      grid: { left: 45, right: 10, top: 10, bottom: useDataZoom ? 30 : 15 },
      xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 } },
      yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: v => v + '%' } },
      dataZoom: useDataZoom ? [{ type: 'slider', show: true, xAxisIndex: 0, start: startPct, end: 100, height: 18, bottom: 0, borderColor: '#b1b4b6', fillerColor: 'rgba(29,112,184,0.12)', handleStyle: { color: '#1d70b8' }, textStyle: { fontSize: 9, color: '#b1b4b6' } }] : [],
      series: [{ type: 'line', data: values, lineStyle: { width: 1.5, color: COLORS[0] }, symbol: 'none', areaStyle: { color: 'rgba(29,112,184,0.08)' }, smooth: false }],
      tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${p[0].value}%` }
    }, true)
    hchart.resize()
  }
}

// ===== FED 历史图（股债性价比 + 上证指数叠加） =====
async function drawFedChart() {
  const el = fedChartEl.value
  if (!el) return
  if (fedChart) { fedChart.dispose(); fedChart = null }

  // 已有缓存则直接绘制
  if (fedSeriesData.value) {
    _renderFedChart(el, fedSeriesData.value)
    return
  }

  // 从 macro_history 拉取数据
  if (!supabase) return
  try {
    const [cn10yRes, idxRes] = await Promise.all([
      supabase.from('macro_history').select('date, value').eq('metric', 'cn10y').order('date', { ascending: true }).limit(10000),
      supabase.from('macro_history').select('date, value').eq('metric', 'sh000001').order('date', { ascending: true }).limit(10000)
    ])
    if (cn10yRes.error || !cn10yRes.data?.length) return

    const cn10yData = cn10yRes.data
    const idxMap = {}
    if (!idxRes.error && idxRes.data) {
      idxRes.data.forEach(d => { idxMap[d.date] = d.value })
    }

    const dates = cn10yData.map(d => d.date)
    const yields = cn10yData.map(d => d.value)
    const indices = cn10yData.map(d => idxMap[d.date] ?? null)

    // 计算均值和标准差（用于绘制带）
    const validYields = yields.filter(v => v != null)
    const n = validYields.length
    const mean = validYields.reduce((a, b) => a + b, 0) / n
    const variance = validYields.reduce((s, v) => s + (v - mean) ** 2, 0) / n
    const std = Math.sqrt(variance)

    // 获取当前股债利差参考线
    const currentSpread = fedIndices.value[0]?.spread !== '--' ? parseFloat(fedIndices.value[0].spread) : null

    const data = { dates, yields, indices, mean, std, currentSpread, validCount: n }
    fedSeriesData.value = data
    _renderFedChart(el, data)
  } catch (err) {
    console.error('[SignalPage] drawFedChart error:', err)
  }
}

// 缓存 FED 数据避免重复拉取
const fedSeriesData = ref(null)

function _renderFedChart(el, data) {
  const { dates, yields, indices, mean, std, currentSpread, validCount } = data
  fedChart = echarts.init(el)

  // 生成标准差带
  const plus1 = yields.map(v => v != null ? mean + std : null)
  const minus1 = yields.map(v => v != null ? mean - std : null)
  const plus2 = yields.map(v => v != null ? mean + 2 * std : null)
  const minus2 = yields.map(v => v != null ? mean - 2 * std : null)

  // 上证指数归一化（对左轴映射到合理范围，取 min/max 归一化到 cn10y 范围附近）
  const validIdx = indices.filter(v => v != null)
  let idxMin = Infinity, idxMax = -Infinity
  if (validIdx.length > 0) {
    idxMin = Math.min(...validIdx)
    idxMax = Math.max(...validIdx)
  }
  // 将指数映射到国债收益率轴范围：scale idx to [mean - 3*std, mean + 3*std]
  const yMin = mean - 3 * std
  const yMax = mean + 3 * std
  const plotRange = yMax - yMin
  const idxNorm = indices.map(v => {
    if (v == null || idxMax === idxMin) return null
    return yMin + ((v - idxMin) / (idxMax - idxMin)) * plotRange
  })

  const winDays = { week: 365, month: 1095, quarter: 1825, year: 999999 }[selPeriod.value] || 1825
  const useDataZoom = dates.length > winDays
  const startPct = useDataZoom ? Math.max(0, Math.round((1 - winDays / dates.length) * 100)) : 0
  const labelStep = Math.max(1, Math.floor(dates.length / 10))

  const option = {
    grid: { left: 60, right: 50, top: 20, bottom: useDataZoom ? 50 : 20 },
    xAxis: {
      type: 'category', data: dates, boundaryGap: false,
      axisLine: { lineStyle: { color: '#b1b4b6' } },
      axisTick: { show: false },
      axisLabel: { fontSize: 10, color: '#505a5f', interval: labelStep - 1 }
    },
    yAxis: {
      type: 'value', name: '收益率 %', nameTextStyle: { fontSize: 10, color: '#505a5f' },
      splitLine: { lineStyle: { color: '#f3f2f1' } },
      axisLine: { show: false },
      axisLabel: { fontSize: 10, color: '#505a5f', formatter: v => v.toFixed(1) + '%' }
    },
    dataZoom: useDataZoom ? [{
      type: 'slider', show: true, xAxisIndex: 0,
      start: startPct, end: 100,
      height: 24, bottom: 6,
      borderColor: '#b1b4b6',
      fillerColor: 'rgba(29,112,184,0.1)',
      handleStyle: { color: '#1d70b8' },
      textStyle: { fontSize: 9, color: '#505a5f' }
    }] : [],
    tooltip: {
      trigger: 'axis',
      formatter: params => {
        const p = Array.isArray(params) ? params : [params]
        let html = '<b>' + p[0].axisValue + '</b>'
        for (const item of p) {
          if (item.seriesName === '上证指数(归一化)') {
            // 反归一化显示真实指数值
            const origIdx = indices[item.dataIndex]
            if (origIdx != null) html += `<br/>上证指数: ${origIdx.toFixed(0)}`
          } else if (item.value != null) {
            html += `<br/>${item.seriesName}: ${item.value.toFixed(2)}%`
          }
        }
        return html
      }
    },
    series: [
      // 上证指数背景（灰色填充区域，归一化后）
      {
        name: '上证指数(归一化)', type: 'line', data: idxNorm,
        lineStyle: { width: 0 },
        symbol: 'none',
        areaStyle: { color: 'rgba(180,180,180,0.18)' },
        silent: true, z: 1
      },
      // ±2σ 带
      {
        name: '+2σ', type: 'line', data: plus2,
        lineStyle: { width: 0.5, color: '#e0e0e0', type: 'dashed' },
        symbol: 'none', silent: true, z: 2
      },
      {
        name: '−2σ', type: 'line', data: minus2,
        lineStyle: { width: 0.5, color: '#e0e0e0', type: 'dashed' },
        areaStyle: { color: 'rgba(29,112,184,0.04)' },
        symbol: 'none', silent: true, z: 2
      },
      // ±1σ 带
      {
        name: '+1σ', type: 'line', data: plus1,
        lineStyle: { width: 0.5, color: '#c0c0c0', type: 'dashed' },
        symbol: 'none', silent: true, z: 3
      },
      {
        name: '−1σ', type: 'line', data: minus1,
        lineStyle: { width: 0.5, color: '#c0c0c0', type: 'dashed' },
        areaStyle: { color: 'rgba(29,112,184,0.06)' },
        symbol: 'none', silent: true, z: 3
      },
      // 均值线
      {
        name: '均值', type: 'line',
        data: new Array(dates.length).fill(mean),
        lineStyle: { width: 1, color: '#888', type: 'dotted' },
        symbol: 'none', silent: true, z: 4
      },
      // 10Y国债收益率主曲线
      {
        name: '10Y国债收益率', type: 'line', data: yields,
        lineStyle: { width: 2, color: '#1d70b8' },
        areaStyle: { color: {
          type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
          colorStops: [{ offset: 0, color: 'rgba(29,112,184,0.15)' }, { offset: 1, color: 'rgba(29,112,184,0.02)' }]
        }},
        symbol: 'none', smooth: false, z: 5
      },
      // 当前股债利差参考线
      ...(currentSpread != null ? [{
        name: `当前股债利差 ${currentSpread.toFixed(2)}%`,
        type: 'line',
        data: new Array(dates.length).fill(null),
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#d4351c', width: 2, type: 'dashed' },
          label: { fontSize: 10, color: '#d4351c', formatter: `股债利差 ${currentSpread.toFixed(2)}%` },
          data: [{ yAxis: mean, name: '参考' }]
        },
        z: 6
      }] : [])
    ]
  }

  fedChart.setOption(option)
  fedChart.resize()
}

// ===== 资产对比 上证指数历史图 =====
function drawCompareIdxChart() {
  const el = compareIdxEl.value
  if (!el) return
  // 从 macroHistory 中查 上证指数
  supabase.from('macro_history')
    .select('date, value')
    .eq('metric', 'sh000001')
    .order('date', { ascending: false })
    .limit(7000)
    .then(({ data }) => {
      if (!data || data.length === 0) return
      drawMiniHistoryChart(el, data.map(d => ({ date: d.date, value: d.value })), '上证指数', false)
    })
}

// ===== 通用迷你历史图表 =====
function drawMiniHistoryChart(el, rawData, label, isPercent = true) {
  const dom = el.querySelector ? (el.querySelector('.macro-chart') || el) : el
  const chart = echarts.getInstanceByDom(dom) || echarts.init(dom)
  const hist = [...rawData].reverse() // ASC
  const dates = hist.map(d => d.date)
  const values = hist.map(d => d.value)
  const total = dates.length
  const defWin = MACRO_DEFAULT_WINDOW
  const useDataZoom = total > defWin
  const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
  const labelStep = Math.max(1, Math.floor(total / 8))
  const yFormatter = isPercent ? (v => v + '%') : (v => v >= 1000 ? (v / 1000).toFixed(1) + 'k' : v.toFixed(0))

  chart.setOption({
    grid: { left: 55, right: 10, top: 10, bottom: useDataZoom ? 30 : 15 },
    xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: yFormatter } },
    dataZoom: useDataZoom ? [{ type: 'slider', show: true, xAxisIndex: 0, start: startPct, end: 100, height: 18, bottom: 0, borderColor: '#b1b4b6', fillerColor: 'rgba(29,112,184,0.12)', handleStyle: { color: '#1d70b8' }, textStyle: { fontSize: 9, color: '#b1b4b6' } }] : [],
    series: [{ type: 'line', data: values, lineStyle: { width: 1.5, color: COLORS[0] }, symbol: 'none', areaStyle: { color: 'rgba(29,112,184,0.08)' }, smooth: false }],
    tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${label}: ${isPercent ? p[0].value + '%' : p[0].value}` }
  }, true)
  chart.resize()
}

// ===== 仪表盘 =====
function drawGauge() {
  const el = gaugeEl.value
  if (!el) return
  if (gaugeChart) gaugeChart.dispose()
  if (!dashData.value) return
  gaugeChart = echarts.init(el)
  const val = Math.max(-1, Math.min(1, dashData.value.value))
  gaugeChart.setOption({
    series: [{
      type: 'gauge',
      startAngle: 210, endAngle: -30,
      min: -1, max: 1,
      center: ['50%', '55%'],
      radius: '85%',
      axisLine: {
        show: true,
        lineStyle: {
          width: 18,
          color: [[0.25, '#d4351c'], [0.5, '#f47738'], [0.75, '#b1b4b6'], [1, '#00703c']]
        }
      },
      pointer: { length: '65%', width: 5, itemStyle: { color: '#1d70b8' } },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: { show: false },
      detail: {
        formatter: '{value}',
        fontSize: 36, fontWeight: 700,
        offsetCenter: [0, '65%'],
        color: val > 0 ? '#d4351c' : '#00703c'
      },
      data: [{ value: +val.toFixed(3), name: '隐含夏普' }]
    }]
  })
}

// Vue ref 绑定到图表容器（Vue3 不会把 template ref 渲染成 DOM 属性，必须用 ref 变量）
const gaugeEl = ref(null)
const pieEl = ref(null)
const radarEl = ref(null)
const bondCurveEl = ref(null)
const fedChartEl = ref(null)
const compareIdxEl = ref(null)
const bondHistEl = ref(null)

// ===== 宏观历史数据加载 =====
const macroMetricMap = {
  cn10y: 'cn10y', us10y: 'us10y', shibor: 'shibor_on',
  cpi: 'cpi', m2: 'm2_growth', ppi: 'ppi'
}

async function loadMacroHistoryAsync() {
  if (!supabase) return
  try {
    // 1. 拉取上证指数历史（用于所有图表叠加）
    const indexPromise = supabase
      .from('macro_history')
      .select('date, value')
      .eq('metric', 'sh000001')
      .order('date', { ascending: false })
      .limit(10000)

    // 2. 拉取六个宏观指标历史
    const macroPromises = macroList.value.map(async (m) => {
      const metric = macroMetricMap[m.key]
      if (!metric) return { key: m.key, data: null }
      const { data, error } = await supabase
        .from('macro_history')
        .select('date, value')
        .eq('metric', metric)
        .order('date', { ascending: false })
        .limit(10000)
      if (error) { console.warn('macro_history query error:', m.key, error); return { key: m.key, data: null } }
      return { key: m.key, data }
    })

    // 3. 同时等待所有请求
    const [indexResult, ...macroResults] = await Promise.all([
      indexPromise,
      ...macroPromises
    ])

    // 4. 构建上证指数日期索引（date → value）
    const indexMap = {}
    if (!indexResult.error && indexResult.data) {
      indexResult.data.forEach(d => { indexMap[d.date] = d.value })
    }

    // 5. 处理每个宏观指标
    macroResults.forEach(r => {
      const { key, data } = r
      if (!data || data.length === 0) return
      // 更新最新值（us10y / ppi 没有 v500 数据源）
      if ((key === 'us10y' || key === 'ppi') && data[0]) {
        const item = macroList.value.find(x => x.key === key)
        if (item && item.value === '--') {
          item.value = data[0].value.toFixed(2) + '%'
          item.date = data[0].date
        }
        if (key === 'us10y') {
          us10yVal.value = parseFloat(data[0].value)
          buildSignalOverview()
        }
      }
      // 存储完整历史（保持 DESC 顺序）
      macroHistory[key] = data.map(d => ({
        date: d.date, value: d.value,
        index: indexMap[d.date] ?? null  // 对齐上证指数
      }))
      // 初始显示：所有数据 ASC 排序，默认窗口展示最近 MACRO_DEFAULT_WINDOW 条
      const asc = [...data].reverse()
      const item = macroList.value.find(x => x.key === key)
      if (item) {
        item.series = {
          dates: asc.map(d => d.date),
          values: asc.map(d => d.value),
          indices: asc.map(d => indexMap[d.date] ?? null),
          total: data.length,
          expanded: false,
          defaultWindow: MACRO_DEFAULT_WINDOW
        }
      }
    })

    await nextTick()
    drawMacroCharts()
  } catch (e) {
    console.warn('loadMacroHistoryAsync error:', e)
  }
}

function expandMacroChart(key) {
  macroExpand[key] = true
  const history = macroHistory[key]
  const item = macroList.value.find(m => m.key === key)
  if (!item || !history) return
  // 展开全部历史数据：history 是 DESC，图表需 ASC（旧→新）
  const asc = [...history].reverse()
  item.series = {
    dates: asc.map(d => d.date),
    values: asc.map(d => d.value),
    indices: asc.map(d => d.index),
    total: asc.length,
    expanded: true,
    defaultWindow: MACRO_DEFAULT_WINDOW
  }
  nextTick(() => drawMacroCharts())
}

// ===== 宏观图表 =====
function drawMacroCharts() {
  macroList.value.forEach(m => {
    const el = chartRefs[m.key]
    if (!el) return
    const dom = el.querySelector ? el.querySelector('.macro-chart') || el : el
    if (!dom) return
    const chart = echarts.getInstanceByDom(dom) || echarts.init(dom)
    const sd = m.series || {}
    const dates = sd.dates || []
    const values = sd.values || []
    const indices = sd.indices || []
    const total = sd.total || dates.length
    const defWin = MACRO_DEFAULT_WINDOW

    // dataZoom：始终显示，默认窗口展示最近 defWin 个数据点
    const useDataZoom = total > defWin
    const startPct = useDataZoom ? Math.max(0, Math.round((1 - defWin / total) * 100)) : 0
    const dataZoomConfig = useDataZoom ? [{
      type: 'slider',
      show: true,
      xAxisIndex: 0,
      start: startPct,
      end: 100,
      height: 18,
      bottom: 0,
      handleSize: '80%',
      borderColor: '#b1b4b6',
      fillerColor: 'rgba(29,112,184,0.12)',
      handleStyle: { color: '#1d70b8' },
      textStyle: { fontSize: 9, color: '#b1b4b6' }
    }] : []

    // 上证指数叠加：仅当有有效 index 数据时
    const hasIndex = indices && indices.some(v => v != null)
    const indexValid = hasIndex ? indices.map(v => (v != null) ? v : '-') : []

    const bottomPad = useDataZoom ? 30 : 15
    const labelStep = Math.max(1, Math.floor(dates.length / 8))

    const tooltipFormatter = hasIndex
      ? (params) => `${params[0].axisValue}<br/>${m.label}: ${params[0].value}%<br/>上证指数: ${params[1]?.value ?? '--'}`
      : (params) => `${params[0].axisValue}<br/>${params[0].value}%`

    chart.setOption({
      grid: { left: 45, right: hasIndex ? 50 : 10, top: 10, bottom: bottomPad },
      xAxis: {
        type: 'category', data: dates, show: true,
        axisLine: { lineStyle: { color: '#b1b4b6' } },
        axisTick: { show: false },
        axisLabel: { show: true, fontSize: 9, color: '#b1b4b6', interval: labelStep - 1 }
      },
      yAxis: [
        {
          type: 'value', splitLine: { lineStyle: { color: '#f3f2f1' } },
          axisLine: { show: false },
          axisLabel: { fontSize: 9, color: '#b1b4b6', formatter: v => v + '%' }
        },
        ...(hasIndex ? [{
          type: 'value',
          axisLine: { show: false },
          axisLabel: { fontSize: 9, color: '#d4351c' },
          splitLine: { show: false }
        }] : [])
      ],
      dataZoom: dataZoomConfig,
      series: [
        {
          name: m.label,
          type: 'line', data: values,
          lineStyle: { width: 1.5, color: COLORS[0] },
          symbol: 'none',
          areaStyle: { color: 'rgba(29,112,184,0.08)' },
          smooth: false
        },
        ...(hasIndex ? [{
          name: '上证指数',
          type: 'line', data: indexValid,
          yAxisIndex: 1,
          lineStyle: { width: 1, color: '#d4351c', type: 'dashed' },
          symbol: 'none',
          smooth: false
        }] : [])
      ],
      tooltip: { trigger: 'axis', formatter: tooltipFormatter },
      legend: hasIndex ? { show: true, bottom: 0, data: [m.label, '上证指数'], textStyle: { fontSize: 10 } } : undefined
    }, true)
    chart.resize()
  })
}

// ===== FED 计算 =====
function calcFED(quotes, rf) {
  const indices = [
    { key: 'hs300', code: 'sh000300', name: '沪深300' },
    { key: 'zz500', code: 'sh000905', name: '中证500' },
    { key: 'zz1000', code: 'sh000852', name: '中证1000' },
  ]
  const results = indices.map(idx => {
    const q = quotes[idx.code]
    const pe = q?.pe || 0
    const pePct = q?.pePercentile || 0
    const spread = rf ? ((1 / pe) - rf) * 100 : 0
    return {
      key: idx.key, name: idx.name,
      spread: spread > 0 ? spread.toFixed(2) : '--',
      pe: pe > 0 ? pe.toFixed(2) : '--',
      pePercentile: pePct > 0 ? pePct.toFixed(0) : '--'
    }
  })
  fedIndices.value = results
}

// ===== 信号总览计算 =====
function adviceClass(advice) {
  return advice === 'overweight' ? 'text-up' : advice === 'underweight' ? 'text-down' : ''
}

function makeCard(key, name, valueLabel, pct, signal, signalLabel, advice, adviceLabel, desc = '', benchmark = '', hint = '') {
  const colorMap = { hot: 'var(--color-up)', cold: 'var(--color-down)', neutral: '#505a5f' }
  const help = [
    desc,
    benchmark ? '统计基准：' + benchmark : '',
    hint,
    '更新时间：每日 21:30 自动更新（与页面顶部"数据截止"一致）。'
  ].filter(Boolean).join('\n\n')
  return { key, name, valueLabel, pct, signal, signalLabel, advice, adviceLabel, desc, benchmark, hint, help, color: colorMap[signal] || '#505a5f' }
}

// 专业机构框架：6 大信号模块 → 指标值 + 历史分位 + 配置建议
function buildSignalOverview() {
  const cards = []
  // 1. 市场温度：全市场加权平均隐含夏普
  const sharpe = dashData.value ? dashData.value.value : null
  cards.push(makeCard('temp', '市场温度',
    sharpe != null ? sharpe.toFixed(2) : '--', null,
    sharpe != null ? (sharpe > 0.1 ? 'hot' : sharpe < -0.1 ? 'cold' : 'neutral') : 'neutral',
    sharpe != null ? (sharpe > 0.1 ? '偏热' : sharpe < -0.1 ? '偏冷' : '中性') : '中性',
    sharpe != null ? (sharpe > 0.1 ? 'underweight' : sharpe < -0.1 ? 'overweight' : 'neutral') : 'neutral',
    sharpe != null ? (sharpe > 0.1 ? '低配' : sharpe < -0.1 ? '超配' : '标配') : '标配',
    '全市场风险平价加权隐含夏普比率，衡量权益资产整体性价比：数值越正，性价比越高。取值区间 −1 ~ 1。',
    '风险平价权重加权平均 · 区间 −1 ~ 1'))
  // 2. 估值水位：沪深300 PE 百分位
  const pePct = pe300PctGlobal.value
  cards.push(makeCard('val', '估值水位',
    pePct != null ? pePct + '%' : '--', pePct,
    pePct != null ? (pePct > 70 ? 'hot' : pePct < 30 ? 'cold' : 'neutral') : 'neutral',
    pePct != null ? (pePct > 70 ? '偏贵' : pePct < 30 ? '偏低' : '中性') : '中性',
    pePct != null ? (pePct > 70 ? 'underweight' : pePct < 30 ? 'overweight' : 'neutral') : 'neutral',
    pePct != null ? (pePct > 70 ? '低配' : pePct < 30 ? '超配' : '标配') : '标配',
    '沪深300指数 PE 所处历史分位：0% = 历史最便宜，100% = 历史最贵，越高越贵。',
    '近10年历史分位（沪深300 PE）'))
  // 3. 流动性：10Y 国债收益率（越低越宽松）
  const y10 = bondY10y.value
  cards.push(makeCard('liq', '流动性',
    y10 != null ? (y10 * 100).toFixed(2) + '%' : '--', null,
    y10 != null ? (y10 < 0.025 ? 'cold' : y10 > 0.03 ? 'hot' : 'neutral') : 'neutral',
    y10 != null ? (y10 < 0.025 ? '宽松' : y10 > 0.03 ? '收紧' : '中性') : '中性',
    y10 != null ? (y10 < 0.025 ? 'overweight' : 'neutral') : 'neutral',
    y10 != null ? (y10 < 0.025 ? '超配' : '标配') : '标配',
    '10年期国债收益率反映货币政策松紧：收益率越低，市场流动性越宽松。',
    '中国10年期国债收益率（实时）'))
  // 4. 信用景气：PMI（>50 扩张）
  const pmi = pmiValGlobal.value
  cards.push(makeCard('credit', '信用景气',
    pmi != null ? pmi.toFixed(1) : '--', null,
    pmi != null ? (pmi > 50 ? 'hot' : 'cold') : 'neutral',
    pmi != null ? (pmi > 50 ? '扩张' : '收缩') : '中性',
    pmi != null ? (pmi > 50 ? 'overweight' : 'underweight') : 'neutral',
    pmi != null ? (pmi > 50 ? '超配' : '低配') : '标配',
    '官方制造业 PMI 衡量经济扩张/收缩：高于 50 为扩张，低于 50 为收缩。',
    '官方制造业 PMI（月度）',
    pmi == null ? '信用数据待披露：官方 PMI 于每月初发布，最新一期尚未更新。' : ''))
  // 5. 海外联动：美债收益率（>4.5% 偏紧）
  const uy = us10yVal.value
  cards.push(makeCard('oversea', '海外联动',
    uy != null ? uy.toFixed(2) + '%' : '待更新', null,
    uy != null ? (uy > 4.5 ? 'hot' : 'cold') : 'neutral',
    uy != null ? (uy > 4.5 ? '收紧' : '宽松') : '中性',
    uy != null ? (uy > 4.5 ? 'underweight' : 'overweight') : 'neutral',
    uy != null ? (uy > 4.5 ? '低配' : '超配') : '标配',
    '美国10年期国债收益率影响全球流动性与风险偏好：越高越偏紧，对权益资产估值压制越大。',
    '美国10年期国债收益率（每日）',
    uy == null ? '海外数据待同步：美债收盘较晚，每日 22:00 后同步更新。' : ''))
  // 6. 风格：价值因子百分位（<30% 低配价值/超配成长，>70% 反之）
  const valFactor = factorFactors.value.find(f => f.key === 'value')
  cards.push(makeCard('style', '风格(价值)',
    valFactor ? valFactor.percentile + '%' : '待更新', valFactor ? valFactor.percentile : null,
    valFactor ? (valFactor.percentile > 70 ? 'hot' : valFactor.percentile < 30 ? 'cold' : 'neutral') : 'neutral',
    valFactor ? (valFactor.percentile > 70 ? '偏高' : valFactor.percentile < 30 ? '偏低' : '中性') : '中性',
    valFactor ? (valFactor.percentile > 70 ? 'underweight' : 'overweight') : 'neutral',
    valFactor ? (valFactor.percentile > 70 ? '低配' : '超配') : '标配',
    '价值因子估值分（0~100，越高越贵）。结合性价比分判断成长/价值风格的相对吸引力。',
    'Barra 价值因子估值分（0~100）'))
  signalOverview.value = cards
}

// ===== 加载行业估值（读 index_eva 生产表，来源：蛋卷估值中心，由后台脚本定时抓取） =====
async function loadIndustry() {
  try {
    const rows = await fetchIndexEva()
    if (!rows || rows.length === 0) {
      console.warn('index_eva 无数据，等待后台抓取')
      return
    }
    industryRaw.value = rows.map(r => ({
      code: r.index_code,
      name: r.name,
      cat: r.cat || 'other',
      ttype: r.ttype,
      pe: r.pe != null ? r.pe : null,
      pe_pct: r.pe_percentile != null ? parseFloat(r.pe_percentile) : null,
      pb: r.pb != null ? r.pb : null,
      pb_pct: r.pb_percentile != null ? parseFloat(r.pb_percentile) : null,
      div_yield: r.dividend_yield != null ? parseFloat(r.dividend_yield) : null,
      roe: r.roe != null ? parseFloat(r.roe) : null,
    }))
  } catch (e) {
    console.error('行业估值加载失败', e)
  }
}

// ===== 加载风格因子评分（读 factor_scores 生产表，Barra 六因子性价比评分） =====
async function loadFactorScores() {
  try {
    const rows = await fetchFactorScores()
    if (!rows || rows.length === 0) {
      factorFactors.value = []
      return
    }
    factorFactors.value = rows.map(r => ({
      key: r.factor_key,
      name: r.name,
      // percentile：雷达图与进度条沿用"估值分"(0-100, 高=贵)
      percentile: r.value_score != null ? parseFloat(r.value_score)
        : (r.percentile != null ? parseFloat(r.percentile) : 0),
      value_score: r.value_score != null ? parseFloat(r.value_score) : null,
      cost_score: r.cost_score != null ? parseFloat(r.cost_score) : null,
      signal: r.signal || 'neutral',
      signalLabel: r.signal_label || '',
      color: r.color || '#1d70b8',
    }))
    // 刷新信号总览中的"风格(价值)"卡片
    if (signalOverview.value.length) buildSignalOverview()
    if (factorSub.value === 'stock') nextTick(drawRadar)
  } catch (e) {
    console.error('风格因子加载失败', e)
    factorFactors.value = []
  }
}

// ===== 特色指标（自建复合算法，数据存 jqr_indicators 表） =====
const jqrCards = ref([])
const jqrSeries = reactive({})
const jqrChartRefs = {}
function setJqrChartRef(key, el) { if (el) jqrChartRefs[key] = el }

const JQR_META = {
  fear_greed:    { name: '恐惧贪婪指数', desc: '短期情绪', color: '#d4351c', range: '0 - 100' },
  market_temp:   { name: '市场温度',     desc: '估值冷热', color: '#1d70b8', range: '0 - 100' },
  fund_issuance: { name: '基金发行热度', desc: '募集景气', color: '#00703c', range: '0 - 100' },
}

function buildJqrCard(metric, row) {
  const meta = JQR_META[metric]
  const detail = row.detail || {}
  const v = row.value
  let signalLabel = '中性', signalClass = 'neutral'
  if (metric === 'fear_greed') {
    if (v < 25) { signalLabel = '极度恐惧'; signalClass = 'cold' }
    else if (v < 45) { signalLabel = '恐惧'; signalClass = 'cold' }
    else if (v < 55) { signalLabel = '中性'; signalClass = 'neutral' }
    else if (v < 75) { signalLabel = '贪婪'; signalClass = 'hot' }
    else { signalLabel = '极度贪婪'; signalClass = 'hot' }
  } else if (metric === 'market_temp') {
    if (v < 30) { signalLabel = '低估偏冷'; signalClass = 'cold' }
    else if (v < 70) { signalLabel = '适中'; signalClass = 'neutral' }
    else { signalLabel = '高估偏热'; signalClass = 'hot' }
  } else if (metric === 'fund_issuance') {
    if (v < 25) { signalLabel = '冰点'; signalClass = 'cold' }
    else if (v < 45) { signalLabel = '偏冷'; signalClass = 'cold' }
    else if (v < 55) { signalLabel = '中性'; signalClass = 'neutral' }
    else if (v < 75) { signalLabel = '偏热'; signalClass = 'hot' }
    else { signalLabel = '狂热'; signalClass = 'hot' }
  }
  const subLines = []
  if (metric === 'fear_greed') {
    const sub = detail.sub || {}
    if (sub.momentum_3m != null) subLines.push({ k: '动量(3月收益分位)', v: sub.momentum_3m })
    if (sub.volatility_inv != null) subLines.push({ k: '波动(反向)', v: sub.volatility_inv })
    if (sub.valuation_inv != null) subLines.push({ k: '估值(反向)', v: sub.valuation_inv })
    if (sub.amount != null) subLines.push({ k: '量能', v: sub.amount })
    if (detail.pe_percentile != null) subLines.push({ k: '全市场PE分位', v: detail.pe_percentile + '%' })
  } else if (metric === 'market_temp') {
    if (detail.pe != null) subLines.push({ k: '全市场PE(TTM)', v: detail.pe })
    if (detail.pe_percentile != null) subLines.push({ k: 'PE历史分位', v: detail.pe_percentile + '%' })
    if (detail.history_min != null) subLines.push({ k: '历史最低PE', v: detail.history_min })
    if (detail.history_max != null) subLines.push({ k: '历史最高PE', v: detail.history_max })
    if (detail.label) subLines.push({ k: '估值状态', v: detail.label })
  } else if (metric === 'fund_issuance') {
    if (detail.recent_90d_count != null) subLines.push({ k: '近90日新发数', v: detail.recent_90d_count })
    if (detail.recent_90d_share_sum != null) subLines.push({ k: '近90日募集份额(亿)', v: detail.recent_90d_share_sum })
    if (detail.heat_percentile != null) subLines.push({ k: '发行热度分位', v: detail.heat_percentile + '%' })
  }
  return {
    key: metric, name: meta.name, desc: meta.desc,
    valueLabel: v != null ? v : '--', color: meta.color, range: meta.range,
    signalLabel, signalClass, date: row.date || '--', subLines,
  }
}

async function loadJqr() {
  if (!supabase) return
  try {
    const metrics = ['fear_greed', 'market_temp', 'fund_issuance']
    const res = await Promise.all(metrics.map(m =>
      supabase.from('jqr_indicators').select('date,value,detail').eq('metric', m).order('date', { ascending: true }).limit(3000)
    ))
    const cards = []
    const series = {}
    for (let i = 0; i < metrics.length; i++) {
      const { data, error } = res[i]
      if (error || !data || !data.length) continue
      const latest = data[data.length - 1]
      series[metrics[i]] = data.map(d => ({ date: d.date, value: d.value }))
      cards.push(buildJqrCard(metrics[i], latest))
    }
    jqrCards.value = cards
    Object.assign(jqrSeries, series)
    await nextTick()
    drawJqrCharts()
  } catch (e) {
    console.error('特色指标加载失败', e)
  }
}

function drawJqrCharts() {
  if (!jqrCards.value.length) return
  jqrCards.value.forEach(c => {
    const el = jqrChartRefs[c.key]
    if (!el) return
    const chart = echarts.getInstanceByDom(el) || echarts.init(el)
    const hist = (jqrSeries[c.key] || []).slice(-500)
    const dates = hist.map(d => d.date)
    const values = hist.map(d => d.value)
    const total = dates.length
    const useDataZoom = total > 250
    const startPct = useDataZoom ? Math.max(0, Math.round((1 - 500 / total) * 100)) : 0
    const labelStep = Math.max(1, Math.floor(total / 8))
    chart.setOption({
      grid: { left: 45, right: 15, top: 20, bottom: useDataZoom ? 35 : 20 },
      xAxis: { type: 'category', data: dates, axisLine: { lineStyle: { color: '#b1b4b6' } }, axisTick: { show: false }, axisLabel: { fontSize: 9, color: '#505a5f', interval: labelStep - 1 } },
      yAxis: { type: 'value', min: 0, max: 100, splitLine: { lineStyle: { color: '#f3f2f1' } }, axisLine: { show: false }, axisLabel: { fontSize: 9, color: '#505a5f' } },
      dataZoom: useDataZoom ? [{ type: 'slider', show: true, xAxisIndex: 0, start: startPct, end: 100, height: 18, bottom: 0, borderColor: '#b1b4b6', fillerColor: 'rgba(29,112,184,0.12)', handleStyle: { color: '#1d70b8' }, textStyle: { fontSize: 9, color: '#505a5f' } }] : [],
      series: [{ type: 'line', data: values, lineStyle: { width: 2, color: c.color }, symbol: 'none', areaStyle: { color: c.color + '1a' }, smooth: false }],
      tooltip: { trigger: 'axis', formatter: p => `${p[0].axisValue}<br/>${c.name}: ${p[0].value}` }
    }, true)
    chart.resize()
  })
}

// ===== 资产配比饼图 =====
function drawPie() {
  const el = pieEl.value
  if (!el || weightList.value.length === 0) return
  if (pieChart) pieChart.dispose()
  pieChart = echarts.init(el)
  pieChart.setOption({
    tooltip: { trigger: 'item', formatter: '{b}: {c}%' },
    series: [{
      type: 'pie',
      radius: ['40%', '70%'],
      center: ['50%', '50%'],
      itemStyle: { borderColor: '#fff', borderWidth: 2 },
      label: { show: true, formatter: '{b}\n{c}%', fontSize: 12 },
      data: weightList.value.map(w => ({ name: w.name, value: w.weight, itemStyle: { color: w.color } }))
    }]
  })
}

// ===== 切换 tab / 周期时初始化图表 =====
function redrawCurrentCharts() {
  nextTick(() => {
    const tab = activeTab.value
    if (tab === 'macro') { drawGauge(); drawMacroCharts() }
    else if (tab === 'fed') drawFedChart()
    else if (tab === 'compare') drawCompareIdxChart()
    else if (tab === 'allocate') drawPie()
    else if (tab === 'factor') {
      if (factorFactors.value.length === 0) loadFactorScores()
      if (factorSub.value === 'stock') drawRadar()
      else if (factorSub.value === 'bond') drawBondCurve()
    }
    else if (tab === 'industry') {
      if (industryRaw.value.length === 0) loadIndustry()
    }
    else if (tab === 'jqr') {
      if (jqrCards.value.length === 0) loadJqr()
      else nextTick(drawJqrCharts)
    }
  })
}
watch(activeTab, () => redrawCurrentCharts())

onMounted(() => {
  const route = useRoute()
  const tabFromQuery = route.query.tab
  if (tabFromQuery && tabs.some(t => t.key === tabFromQuery)) {
    activeTab.value = tabFromQuery
  }
  loadAll()

  // 窗口 resize 时自动调整图表大小
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
})

function handleResize() {
  const charts = [gaugeChart, pieChart, radarChart, bondCurveChart, fedHistChart, compareIdxChart]
  charts.forEach(c => c?.resize())
  Object.values(chartRefs).forEach(el => {
    const instance = echarts.getInstanceByDom(el)
    if (instance) instance.resize()
  })
  Object.values(jqrChartRefs).forEach(el => {
    const instance = echarts.getInstanceByDom(el)
    if (instance) instance.resize()
  })
}
</script>

<style scoped>
/* ========== gov.uk 蓝白灰 指标信号页 ========== */
.page-signal { padding-bottom: var(--space-2xl); overflow-x: hidden; max-width: 100%; }

.header-bar {
  display: flex; justify-content: space-between; padding: var(--space-sm) 0;
  font-size: 14px; color: var(--text-secondary); border-bottom: 1px solid var(--border);
}
.refresh-btn { color: var(--link); cursor: pointer; text-decoration: underline; }

/* Tab 导航 */
.signal-tabs {
  display: flex; gap: 0; border-bottom: 2px solid var(--border);
  margin: var(--space-md) 0 var(--space-lg); overflow-x: auto;
}
.signal-tab {
  padding: var(--space-sm) var(--space-md); font-size: 16px; font-weight: 700;
  color: var(--text-secondary); cursor: pointer; white-space: nowrap;
  border-bottom: 3px solid transparent; margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}
.signal-tab.active {
  color: #1d70b8; border-bottom-color: #1d70b8;
}
.signal-tab:hover { color: var(--text-primary); }

/* 子 Tab */
.sub-tabs { display: flex; gap: var(--space-md); border-bottom: 2px solid var(--border); margin-bottom: var(--space-lg); }
.sub-tab { padding: var(--space-xs) var(--space-sm); font-size: 14px; font-weight: 700; color: var(--text-secondary); cursor: pointer; border-bottom: 3px solid transparent; margin-bottom: -2px; }
.sub-tab.active { color: #1d70b8; border-bottom-color: #1d70b8; }

/* 卡片 */
.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); }
.card-subtitle { font-size: 14px; color: var(--text-secondary); margin-left: 6px; font-weight: 400; }
.card-desc { font-size: 14px; color: var(--text-secondary); margin-bottom: var(--space-md); }
.error-card { border-left: 5px solid #d4351c; padding: var(--space-md); margin-bottom: var(--space-xl); background: #fff; }
.error-card p { margin: 0; font-size: 16px; color: #d4351c; }

/* 仪表盘 */
.gauge-wrap { width: 100%; height: 280px; }
.gauge-range { text-align: center; font-size: 13px; color: var(--text-secondary); margin-top: 4px; }

/* 宏观指标 */
.macro-indicators { display: flex; flex-direction: column; gap: var(--space-lg); }
.macro-item { border: 1px solid var(--border); padding: var(--space-md); }
.macro-label { font-size: 14px; color: var(--text-secondary); }
.macro-value { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: var(--space-xs) 0; }
.macro-date { font-size: 12px; color: var(--text-secondary); margin-bottom: var(--space-sm); }
.macro-chart-wrap { width: 100%; height: 200px; overflow: hidden; }
.macro-chart-wrap.macro-chart-expanded { height: 200px; overflow: visible; }
.macro-chart { width: 100%; height: 200px; }
.macro-more { text-align: center; margin-top: var(--space-sm); }
.more-btn {
  display: inline-block; padding: var(--space-xs) var(--space-lg); font-size: 13px;
  color: var(--brand); border: 1px solid var(--brand); background: var(--bg-card);
  cursor: pointer; text-decoration: none; user-select: none;
}
.more-btn:hover { background: var(--brand); color: #fff; }

/* FED */
.fed-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-md); }
.fed-card { border: 1px solid var(--border); padding: var(--space-md); text-align: center; }
.fed-name { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-xs); }
.fed-spread { font-size: 28px; font-weight: 700; }
.fed-label { font-size: 12px; color: var(--text-secondary); margin: var(--space-xs) 0; }
.fed-details { margin-top: var(--space-sm); }
.fed-row { display: flex; justify-content: space-between; font-size: 13px; padding: 2px 0; }
.fed-row span:first-child { color: var(--text-secondary); }

/* 表格 */
.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th { text-align: left; padding: var(--space-sm); color: var(--text-secondary); border-bottom: 2px solid var(--border); font-weight: 700; white-space: nowrap; }
.data-table td { padding: var(--space-sm); color: var(--text-primary); border-bottom: 1px solid var(--border); white-space: nowrap; }
.td-name { font-weight: 700; }
.metric-sub { display: block; font-size: 12px; color: var(--text-secondary); }
.row-disabled { opacity: 0.4; }
.text-brand { color: #1d70b8 !important; font-weight: 700; }

/* 分配布局 */
.allocate-layout { display: flex; flex-direction: column; gap: var(--space-lg); }
@media (min-width: 769px) {
  .allocate-layout { flex-direction: row; }
  .allocate-layout .pie-section { flex: 0 0 320px; }
  .allocate-layout .table-wrap { flex: 1; }
}
.pie-section { display: flex; align-items: center; justify-content: center; }
.pie-chart { width: 100%; height: 280px; }

/* 雷达 */
.radar-wrap { width: 100%; height: 320px; }
.empty-hint { text-align: center; color: var(--text-secondary); padding: var(--space-xl); }

/* 因子 */
.factor-grid { display: flex; flex-direction: column; gap: var(--space-md); }
.factor-item { display: flex; flex-direction: column; gap: 6px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
.factor-head { display: flex; align-items: center; justify-content: space-between; }
.factor-name { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.factor-bar-wrap { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.factor-bar { flex: 1; height: 16px; background: #f3f2f1; }
.factor-fill { height: 100%; transition: width 0.5s ease; }
.factor-val { width: 76px; font-size: 12px; text-align: right; font-weight: 700; white-space: nowrap; }
.factor-scores { font-size: 12px; color: var(--text-secondary); }
.factor-scores b { color: var(--text-primary); }
.factor-signal { font-size: 12px; text-align: center; padding: 1px 6px; border-radius: 3px; white-space: nowrap; }
.factor-signal.cheap { color: var(--color-down); }
.factor-signal.neutral { color: #1d70b8; }
.factor-signal.expensive { color: var(--color-up); }

/* 利差 */
.spread-item { display: flex; justify-content: space-between; padding: var(--space-sm) 0; border-bottom: 1px solid var(--border); font-size: 16px; }
.chart-wrap { width: 100%; height: 250px; }

/* 商品 */
.comm-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: var(--space-md); }
.comm-item { border: 1px solid var(--border); padding: var(--space-md); text-align: center; }
.comm-label { font-size: 14px; color: var(--text-secondary); }
.comm-value { font-size: 20px; font-weight: 700; color: var(--text-primary); margin: var(--space-xs) 0; }

/* 筛选 */
.filter-row { display: flex; gap: var(--space-md); margin-bottom: var(--space-md); padding-bottom: var(--space-sm); border-bottom: 1px solid var(--border); }
.filter-chip { font-size: 14px; color: var(--text-secondary); cursor: pointer; padding: 2px 0; border-bottom: 2px solid transparent; }
.filter-chip.active { color: #1d70b8; border-bottom-color: #1d70b8; font-weight: 700; }
.sortable { cursor: pointer; user-select: none; }
.sortable:hover { color: #1d70b8; }

.data-source { font-size: 12px; color: var(--text-secondary); margin-top: var(--space-sm); }
.text-up { color: var(--color-up) !important; }
.text-down { color: var(--color-down) !important; }

/* 特色指标 */
.jqr-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); }
.jqr-card { border: 1px solid var(--border); padding: var(--space-lg); text-align: center; background: #fff; }
.jqr-card-name { font-size: 14px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-xs); }
.jqr-value { font-size: 40px; font-weight: 700; line-height: 1.1; margin: var(--space-xs) 0; }
.jqr-signal { display: inline-block; font-size: 14px; font-weight: 700; padding: 2px 12px; border-radius: 3px; }
.jqr-signal.hot { color: #fff; background: var(--color-up); }
.jqr-signal.cold { color: #fff; background: var(--color-down); }
.jqr-signal.neutral { color: #fff; background: #505a5f; }
.jqr-date { font-size: 12px; color: var(--text-secondary); margin: var(--space-xs) 0; }
.jqr-range { font-size: 12px; color: var(--text-muted); margin: 2px 0; }
.jqr-sub { margin-top: var(--space-sm); border-top: 1px solid var(--border); padding-top: var(--space-sm); text-align: left; }
.jqr-sub-row { display: flex; justify-content: space-between; font-size: 12px; padding: 2px 0; }
.jqr-sub-row span:first-child { color: var(--text-secondary); }
.jqr-sub-row span:last-child { font-weight: 700; color: var(--text-primary); }
.jqr-chart { width: 100%; height: 240px; }

/* ===== 移动端适配 ===== */
/* 信号总览 */
.overview-banner { background: #1d70b8; color: #fff; border-color: #1d70b8; }
.ov-banner-title { font-size: 14px; font-weight: 700; opacity: 0.9; margin-bottom: 6px; }
.ov-banner-text { font-size: 18px; font-weight: 700; margin: 0; line-height: 1.5; }
.ov-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--space-md); margin-bottom: var(--space-xl); }
.ov-card { border: 1px solid var(--border); padding: var(--space-md); background: #fff; }
.ov-card-name { font-size: 13px; color: var(--text-secondary); font-weight: 700; }
.ov-card-value { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: 4px 0 8px; }
.ov-bar-wrap { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.ov-bar { flex: 1; height: 8px; background: #f3f2f1; }
.ov-fill { height: 100%; }
.ov-pct { font-size: 12px; color: var(--text-secondary); width: 38px; text-align: right; }
.ov-signal { display: inline-block; font-size: 13px; font-weight: 700; padding: 1px 8px; margin-bottom: 6px; }
.ov-signal.hot { color: var(--color-up); }
.ov-signal.cold { color: var(--color-down); }
.ov-signal.neutral { color: var(--text-secondary); }
.ov-signal-label { font-size: 14px; font-weight: 700; }
.ov-hint { font-size: 12px; color: var(--text-secondary); }

@media (max-width: 768px) {
  .jqr-grid { grid-template-columns: 1fr; }
  .ov-grid { grid-template-columns: repeat(2, 1fr); }
  .fed-grid { grid-template-columns: repeat(1, 1fr); }
  .comm-grid { grid-template-columns: repeat(1, 1fr); }
  .macro-indicators { grid-template-columns: repeat(1, 1fr); }
  .macro-chart-wrap { height: 160px; }
  .macro-chart { height: 160px; }
  .gauge-wrap { height: 240px; }
  .pie-chart { height: 240px; }
  .radar-wrap { height: 280px; }
  .chart-wrap { height: 200px; }
  .allocate-layout { flex-direction: column; }
}

/* ===== 周期 / 市场 筛选 ===== */
.signal-filters { display: flex; align-items: center; gap: var(--space-md); flex-wrap: wrap; }
.filter-select { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; color: var(--text-secondary); }
.filter-select__label { white-space: nowrap; }
.filter-select__input { font-size: 13px; padding: 3px 6px; border: 1px solid var(--border); border-radius: 3px; background: #fff; color: var(--text-primary); }

/* 市场维度建设中提示 */
.market-notice { display: flex; align-items: center; gap: 8px; margin: var(--space-sm) 0 var(--space-md); padding: var(--space-sm) var(--space-md); background: #f3f2f1; border-left: 4px solid var(--brand); font-size: 13px; color: var(--text-secondary); }
.market-notice__icon { display: inline-flex; align-items: center; justify-content: center; width: 18px; height: 18px; border-radius: 50%; background: var(--brand); color: #fff; font-size: 12px; font-style: normal; font-weight: 700; flex: 0 0 auto; }

/* 信号总览卡片注释（问号悬浮 + 统计基准） */
.ov-card-head { display: flex; align-items: center; justify-content: space-between; gap: 6px; }
.ov-help { display: inline-flex; align-items: center; justify-content: center; width: 16px; height: 16px; border-radius: 50%; border: 1px solid var(--text-secondary); color: var(--text-secondary); font-size: 11px; font-weight: 700; cursor: help; flex: 0 0 auto; }
.ov-benchmark { font-size: 11px; color: var(--text-muted); margin-top: 4px; line-height: 1.4; }
.ov-card-hint { font-size: 11px; color: #b95900; margin-top: 4px; line-height: 1.4; }

/* 中屏（平板 / 小屏笔记本）提前堆叠，避免横向滚动 */
@media (max-width: 1100px) {
  .ov-grid { grid-template-columns: repeat(2, 1fr); }
  .jqr-grid { grid-template-columns: repeat(2, 1fr); }
  .fed-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
