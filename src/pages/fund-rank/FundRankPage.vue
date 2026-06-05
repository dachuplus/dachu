<template>
  <div class="page-fund-rank">
    <!-- 顶部：标题 + 搜索 -->
    <div class="top-bar">
      <div class="top-title-row">
        <span class="top-title-text">靠谱指数</span>
        <span class="help-icon-btn" @click="showScoreHelp = true">?</span>
      </div>
      <div class="search-box">
        <input
          class="search-input"
          placeholder="搜基金名/代码"
          v-model="searchText"
          @keyup.enter="doSearch"
        />
        <span class="search-clear" v-if="searchText" @click="clearSearch">&#x2715;</span>
      </div>
    </div>

    <!-- 数据信息条 -->
    <div class="data-info-bar">
      <span class="data-info-row">
        数据：FundGuideapi · {{ meta.total_count || '--' }}只基金
      </span>
      <span class="data-info-row">
        <span v-if="meta.nav_date">时间：{{ meta.nav_date }}</span>
        <span v-else>加载中...</span>
        <span class="data-refresh" :class="{ refreshing }" @click="refreshData">
          {{ refreshing ? '刷新中' : '刷新' }}
        </span>
      </span>
    </div>

    <!-- 筛选区（可展开/收起） -->
    <div class="filter-section">
      <!-- 一级分类 -->
      <div class="filter-row">
        <span class="filter-label">一级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: filterT0 === '' }" @click="setT0('')">全部</div>
          <div v-for="t0 in t0List" :key="t0" class="filter-chip" :class="{ active: filterT0 === t0 }" @click="setT0(t0)">{{ t0 }}</div>
        </div>
      </div>

      <!-- 二级分类（依赖一级） -->
      <div class="filter-row" v-if="t1List.length > 0">
        <span class="filter-label">二级分类</span>
        <div class="filter-chips">
          <div class="filter-chip" :class="{ active: filterT1 === '' }" @click="setT1('')">全部</div>
          <div v-for="t1 in t1List" :key="t1" class="filter-chip" :class="{ active: filterT1 === t1 }" @click="setT1(t1)">{{ t1 }}</div>
        </div>
      </div>

      <!-- 更多筛选（展开/收起） -->
      <div class="more-filter-toggle" @click="showMoreFilter = !showMoreFilter">
        <span>更多筛选</span>
        <span class="toggle-arrow" :class="{ open: showMoreFilter }">▾</span>
      </div>

      <div class="more-filter-body" v-if="showMoreFilter">
        <!-- 份额类别 -->
        <div class="filter-row">
          <span class="filter-label">份额类别</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterSC === '' }" @click="setSC('')">全部</div>
            <div v-for="sc in shareClassOptions" :key="sc" class="filter-chip" :class="{ active: filterSC === sc }" @click="setSC(sc)">{{ sc }}类</div>
          </div>
        </div>

        <!-- 是否ETF -->
        <div class="filter-row">
          <span class="filter-label">ETF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterETF === '' }" @click="setFlag('ETF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterETF === '1' }" @click="setFlag('ETF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterETF === '0' }" @click="setFlag('ETF', '0')">否</div>
          </div>
        </div>

        <!-- 是否LOF -->
        <div class="filter-row">
          <span class="filter-label">LOF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterLOF === '' }" @click="setFlag('LOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterLOF === '1' }" @click="setFlag('LOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterLOF === '0' }" @click="setFlag('LOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否FOF -->
        <div class="filter-row">
          <span class="filter-label">FOF</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterFOF === '' }" @click="setFlag('FOF', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterFOF === '1' }" @click="setFlag('FOF', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterFOF === '0' }" @click="setFlag('FOF', '0')">否</div>
          </div>
        </div>

        <!-- 是否定开 -->
        <div class="filter-row">
          <span class="filter-label">定开</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterDK === '' }" @click="setFlag('DK', '')">全部</div>
            <div class="filter-chip" :class="{ active: filterDK === '1' }" @click="setFlag('DK', '1')">是</div>
            <div class="filter-chip" :class="{ active: filterDK === '0' }" @click="setFlag('DK', '0')">否</div>
          </div>
        </div>

        <!-- 单日涨跌≥20%（涨停/跌停基金，如T+2） -->
        <div class="filter-row">
          <span class="filter-label">单日±20%</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterDailyLimit === '' }" @click="setDailyLimit('')">全部</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '0' }" @click="setDailyLimit('0')">否</div>
            <div class="filter-chip" :class="{ active: filterDailyLimit === '1' }" @click="setDailyLimit('1')">是</div>
          </div>
        </div>

        <!-- 持有期 -->
        <div class="filter-row">
          <span class="filter-label">持有期</span>
          <div class="filter-chips">
            <div class="filter-chip" :class="{ active: filterHP === '' }" @click="setHP('')">全部</div>
            <div class="filter-chip" :class="{ active: filterHP === 'no' }" @click="setHP('no')">无限制</div>
            <div class="filter-chip" :class="{ active: filterHP === '7' }" @click="setHP('7')">7天</div>
            <div class="filter-chip" :class="{ active: filterHP === '30' }" @click="setHP('30')">30天</div>
            <div class="filter-chip" :class="{ active: filterHP === '90' }" @click="setHP('90')">90天</div>
            <div class="filter-chip" :class="{ active: filterHP === '180' }" @click="setHP('180')">180天</div>
            <div class="filter-chip" :class="{ active: filterHP === '365' }" @click="setHP('365')">1年+</div>
          </div>
        </div>

        <!-- 规模筛选说明 -->
        <div class="filter-tip">
          注：ETF/LOF/FOF/定开/持有期/±20%等属性基于基金名称智能识别，可能存在误判。<br>
          基金规模、机构占比、股票占比数据暂未收录，后续版本更新。
        </div>
      </div>
    </div>

    <!-- 周期Tab + 结果数 -->
    <div class="toolbar">
      <div class="period-tabs">
        <div
          v-for="p in periods"
          :key="p.key"
          class="period-tab"
          :class="{ active: currentPeriod === p.key }"
          @click="switchPeriod(p.key)"
        >{{ p.label }}</div>
      </div>
      <span class="result-count" v-if="funds.length > 0">
        {{ hasMore ? `已加载${funds.length}只` : `共${funds.length}只` }}
      </span>
    </div>

    <!-- 基金列表 -->
    <div class="fund-list" v-if="funds.length > 0">
      <div
        v-for="(fund, idx) in funds"
        :key="fund.c"
        class="fund-card"
        @click="openDetail(fund)"
      >
        <!-- 排名 + 评分 -->
        <div class="fund-rank-area">
          <span class="fund-rank-num">{{ (page - 1) * pageSize + idx + 1 }}</span>
          <div class="fund-score-wrap">
            <span class="fund-score" :class="scoreCls(fund[currentPeriod])">
              {{ fmtScore(fund[currentPeriod]) }}
            </span>
            <span class="fund-score-label">靠谱</span>
          </div>
        </div>
        <!-- 基金信息 -->
        <div class="fund-info">
          <div class="fund-name-row">
            <span class="fund-name">{{ fund.n }}</span>
          </div>
          <div class="fund-sub">
            <span class="fund-code">{{ fund.c }}</span>
            <span class="fund-sep">·</span>
            <span class="fund-type">{{ fund.t2 || fund.t1 || fund.t0 }}</span>
          </div>
          <!-- 多周期靠谱分 -->
          <div class="fund-scores-row">
            <div v-for="p in periods" :key="p.key" class="fs-item">
              <span class="fs-period">{{ p.label }}</span>
              <span class="fs-value" :class="scoreCls(fund[p.key])">
                {{ fmtScore(fund[p.key]) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 加载更多 -->
    <div class="load-more" v-if="hasMore && funds.length > 0" @click="loadMore">
      {{ loading ? '加载中...' : '加载更多' }}
    </div>

    <!-- 空状态 -->
    <div class="empty-state" v-if="dataLoaded && funds.length === 0 && !loading">
      <p class="empty-text">没有找到符合条件的基金</p>
      <p class="empty-hint">试试调整筛选条件或关键词</p>
    </div>

    <!-- 加载中（首次） -->
    <div class="loading-wrap" v-if="loading && funds.length === 0">
      <span class="loading-text">正在加载基金数据...</span>
    </div>

    <!-- 底部说明 -->
    <div class="bottom-info" v-if="dataLoaded">
      <span>数据来源：FundGuideapi · 风险指标自行计算（历史净值回算）</span>
      <span v-if="meta.nav_date">数据截止：{{ meta.nav_date }}</span>
      <span>仅供学习参考，不构成投资建议</span>
    </div>

    <!-- 详情弹窗 -->
    <Teleport to="body">
      <template v-if="detailFund">
        <div class="mask" @click="detailFund = null"></div>
        <div class="detail-panel">
          <div class="detail-header">
            <span class="detail-name">{{ detailFund.n }}</span>
            <span class="detail-close" @click="detailFund = null">&#x2715;</span>
          </div>
          <div class="detail-body">
            <!-- 基本信息 -->
            <div class="detail-section">
              <div class="attr-row">
                <span class="attr-label">基金代码</span>
                <span class="attr-value">{{ detailFund.c }}</span>
              </div>
              <div class="attr-row">
                <span class="attr-label">分类</span>
                <span class="attr-value">{{ detailFund.t0 }} › {{ detailFund.t1 }}</span>
              </div>
              <div class="attr-row" v-if="detailFund.nav">
                <span class="attr-label">最新净值</span>
                <span class="attr-value">{{ detailFund.nav }}<span v-if="detailFund.date" class="attr-date">（{{ detailFund.date }}）</span></span>
              </div>
            </div>

            <!-- 靠谱分 -->
            <div class="detail-section">
              <span class="detail-section-title">靠谱指数评分（v6）</span>
              <div class="detail-scores-grid">
                <div v-for="p in periods" :key="p.key" class="ds-item">
                  <span class="ds-period">{{ p.label }}</span>
                  <span class="ds-score" :class="scoreCls(detailFund[p.key])">
                    {{ fmtScore(detailFund[p.key]) }}
                  </span>
                </div>
              </div>
            </div>

            <!-- 阶段收益率 -->
            <div class="detail-section" v-if="hasReturns(detailFund)">
              <div class="section-title-row">
                <span class="detail-section-title">阶段收益率</span>
                <span class="section-source">天天基金{{ detailFund.date ? ' · 截至' + detailFund.date : '' }}</span>
              </div>
              <div class="returns-grid">
                <div class="return-col" v-if="detailFund.ytd != null">
                  <span class="ret-label">今年来</span>
                  <span class="ret-value" :class="retCls(detailFund.ytd)">{{ fmtRet(detailFund.ytd) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r0w != null">
                  <span class="ret-label">近1周</span>
                  <span class="ret-value" :class="retCls(detailFund.r0w)">{{ fmtRet(detailFund.r0w) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r1m != null">
                  <span class="ret-label">近1月</span>
                  <span class="ret-value" :class="retCls(detailFund.r1m)">{{ fmtRet(detailFund.r1m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r3m != null">
                  <span class="ret-label">近3月</span>
                  <span class="ret-value" :class="retCls(detailFund.r3m)">{{ fmtRet(detailFund.r3m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r6m != null">
                  <span class="ret-label">近6月</span>
                  <span class="ret-value" :class="retCls(detailFund.r6m)">{{ fmtRet(detailFund.r6m) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r1y != null">
                  <span class="ret-label">近1年</span>
                  <span class="ret-value" :class="retCls(detailFund.r1y)">{{ fmtRet(detailFund.r1y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r2y != null">
                  <span class="ret-label">近2年</span>
                  <span class="ret-value" :class="retCls(detailFund.r2y)">{{ fmtRet(detailFund.r2y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r3y != null">
                  <span class="ret-label">近3年</span>
                  <span class="ret-value" :class="retCls(detailFund.r3y)">{{ fmtRet(detailFund.r3y) }}</span>
                </div>
                <div class="return-col" v-if="detailFund.r5y != null">
                  <span class="ret-label">近5年</span>
                  <span class="ret-value" :class="retCls(detailFund.r5y)">{{ fmtRet(detailFund.r5y) }}</span>
                </div>
              </div>
            </div>

            <!-- 风险指标 -->
            <div class="detail-section" v-if="hasRisk(detailFund)">
              <div class="section-title-row">
                <span class="detail-section-title">风险指标</span>
                <span class="section-source">历史净值回算</span>
              </div>
              <div class="risk-table">
                <div class="risk-head">
                  <span class="risk-th" style="width:60px">周期</span>
                  <span class="risk-th" style="flex:1;text-align:center">最大回撤</span>
                  <span class="risk-th" style="flex:1;text-align:center">夏普比率</span>
                </div>
                <div v-for="rp in riskPeriods" :key="rp.label" class="risk-row"
                  v-show="detailFund[rp.dd] != null || detailFund[rp.sr] != null">
                  <span class="risk-label">{{ rp.label }}</span>
                  <span class="risk-val" :class="ddCls(detailFund[rp.dd])">
                    {{ fmtDD(detailFund[rp.dd]) }}
                  </span>
                  <span class="risk-val">{{ fmtSR(detailFund[rp.sr]) }}</span>
                </div>
              </div>
            </div>

            <!-- 天天基金跳转 -->
            <a :href="eastMoneyUrl(detailFund.c)" target="_blank" class="detail-goto">
              在天天基金查看详情 →
            </a>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 靠谱分说明弹窗 -->
    <Teleport to="body">
      <template v-if="showScoreHelp">
        <div class="mask" @click="showScoreHelp = false"></div>
        <div class="help-panel">
          <div class="help-header">
            <span class="help-title">靠谱指数评分说明（v6）</span>
            <span class="help-close" @click="showScoreHelp = false">&#x2715;</span>
          </div>
          <div class="help-body">
            <div class="help-section">
              <span class="help-desc">
                靠谱指数综合考虑基金的收益率、最大回撤和夏普比率，在全市场中进行百分位排名后加权计算。满分100分，分值越高代表该周期内综合表现越优秀。
              </span>
              <span class="help-desc" style="margin-top:12px;font-weight:600;">
                评分权重：收益排位 50% + 回撤排位 25% + 夏普排位 25%
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">颜色等级</span>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FFB800;"></span>
                <span class="help-color-text score-gold-text">85分及以上</span>
                <span class="help-color-desc">顶尖水平</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#FF6B35;"></span>
                <span class="help-color-text score-orange-text">75 ~ 84分</span>
                <span class="help-color-desc">优秀水平</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#06B6D4;"></span>
                <span class="help-color-text score-cyan-text">65 ~ 74分</span>
                <span class="help-color-desc">中等偏上</span>
              </div>
              <div class="help-color-row">
                <span class="help-dot" style="background:#8B949E;"></span>
                <span class="help-color-text score-default-text">65分以下</span>
                <span class="help-color-desc">中等及以下</span>
              </div>
            </div>
            <div class="help-section">
              <span class="help-section-label">参与条件</span>
              <span class="help-desc">
                阶段收益率 &gt; 0，且至少有回撤或夏普数据之一。不满足条件的基金显示"--"。
              </span>
            </div>
            <div class="help-section">
              <span class="help-section-label">数据更新</span>
              <span class="help-desc">
                基金数据每日 17:30 后更新（源自天天基金 FundGuideapi），靠谱分在数据更新后同步重算。净值日期见页面顶部。
              </span>
            </div>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchFundScores, fetchFundMeta } from '../../api/data.js'

// ========== 常量 ==========
const periods = [
  { key: 'k1',  label: '1年' },
  { key: 'k2',  label: '2年' },
  { key: 'k3',  label: '3年' },
]

const riskPeriods = [
  { label: '近1年', dd: 'dd1y', sr: 'sr1y' },
  { label: '近2年', dd: 'dd2y', sr: 'sr2y' },
  { label: '近3年', dd: 'dd3y', sr: 'sr3y' },
  { label: '近5年', dd: 'dd5y', sr: 'sr5y' },
]

// 三级分类树（基于天天基金 FundGuideapi 实际 t0/t1 值）
const CAT_TREE = {
  'FOF': {
    'FOF-进取型': ['FOF-进取型'],
    'FOF-稳健型': ['FOF-稳健型'],
    'FOF-均衡型': ['FOF-均衡型'],
  },
  'QDII基金': {
    'QDII-普通股票': ['QDII-普通股票'],
    'QDII-混合偏股': ['QDII-混合偏股'],
    'QDII-纯债': ['QDII-纯债'],
    '指数型-股票': ['指数型-股票'],
    '指数型-海外股票': ['指数型-海外股票'],
  },
  '债券型基金': {
    '债券型-长债': ['债券型-长债'],
    '债券型-混合二级': ['债券型-混合二级'],
    '债券型-混合一级': ['债券型-混合一级'],
    '债券型-中短债': ['债券型-中短债'],
    '指数型-固收': ['指数型-固收'],
  },
  '混合型基金': {
    '混合型-偏股': ['混合型-偏股'],
    '混合型-灵活': ['混合型-灵活'],
    '混合型-平衡': ['混合型-平衡'],
    '混合型-偏债': ['混合型-偏债'],
    '指数型-其他': ['指数型-其他'],
    '指数型-固收': ['指数型-固收'],
  },
  '股票型基金': {
    '指数型-股票': ['指数型-股票'],
    '股票型': ['股票型'],
  },
}

// ========== 状态 ==========
const funds = ref([])
const meta = ref({})

// 分类筛选
const filterT0 = ref('')
const filterT1 = ref('')

// 更多筛选
const showMoreFilter = ref(false)
const filterSC = ref('')
const filterETF = ref('')
const filterLOF = ref('')
const filterFOF = ref('')
const filterDK = ref('')
const filterHP = ref('')
const filterDailyLimit = ref('')

// 搜索/周期/分页
const searchText = ref('')
const currentPeriod = ref('k1')
const page = ref(1)
const pageSize = 30
const hasMore = ref(false)
const loading = ref(false)
const dataLoaded = ref(false)
const refreshing = ref(false)

// 弹窗
const detailFund = ref(null)
const showScoreHelp = ref(false)

// ========== 计算属性：分类联动 ==========
const t0List = computed(() => Object.keys(CAT_TREE))

const t1List = computed(() => {
  if (!filterT0.value || !CAT_TREE[filterT0.value]) return []
  return Object.keys(CAT_TREE[filterT0.value])
})

// ========== 格式化 ==========
function fmtScore(v) {
  const n = parseFloat(v)
  if (!n || n <= 0) return '--'
  return n.toFixed(2)
}

function fmtRet(v) {
  if (v == null) return '--'
  const n = parseFloat(v)
  if (isNaN(n)) return '--'
  return (n > 0 ? '+' : '') + n.toFixed(2) + '%'
}

function fmtDD(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(2) + '%'
}

function fmtSR(v) {
  if (v == null) return '--'
  return parseFloat(v).toFixed(4)
}

function scoreCls(v) {
  const n = parseFloat(v) || 0
  if (n >= 85) return 'score-gold'
  if (n >= 75) return 'score-orange'
  if (n >= 65) return 'score-cyan'
  return 'score-default'
}

function retCls(v) {
  const n = parseFloat(v) || 0
  if (n > 0) return 'ret-up'
  if (n < 0) return 'ret-down'
  return ''
}

function ddCls(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (n <= -20) return 'risk-high'
  if (n <= -10) return 'risk-mid'
  return 'risk-low'
}

// 分类名去掉前缀（显示用）
function t1Short(t1) {
  if (!filterT0.value) return t1
  const prefix = filterT0.value.replace(/基金$/, '') + '-'
  return t1.startsWith(prefix) ? t1.slice(prefix.length) : t1
}

function hasReturns(f) {
  return f.r1y != null || f.r3y != null || f.ytd != null
}

function hasRisk(f) {
  return riskPeriods.some(p => f[p.dd] != null || f[p.sr] != null)
}

function eastMoneyUrl(code) {
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `http://fund.eastmoney.com/${pureCode}.html`
}

// ========== 份额类别提取（基于基金名称末尾大写字母） ==========
// 常见份额类别：A/B/C/D/E/F/H/I/R/Y
const SHARE_CLASS_LETTERS = ['A', 'B', 'C', 'D', 'E', 'F', 'H', 'I', 'R', 'Y']
const shareClassOptions = SHARE_CLASS_LETTERS

/** 从基金名称提取份额类别字母，如 "华夏成长混合A" → "A"，"某某精选C" → "C" */
function extractShareClass(name) {
  if (!name) return ''
  const match = name.match(/([A-Z])$/)
  return match ? match[1] : ''
}

// ========== 智能识别筛选（基于基金名称） ==========
function buildNameFilter() {
  const filters = []
  if (filterETF.value === '1') filters.push({ type: 'name_contains', val: 'ETF' })
  if (filterETF.value === '0') filters.push({ type: 'name_not_contains', val: 'ETF' })
  if (filterLOF.value === '1') filters.push({ type: 'name_contains', val: 'LOF' })
  if (filterLOF.value === '0') filters.push({ type: 'name_not_contains', val: 'LOF' })
  if (filterFOF.value === '1') filters.push({ type: 't0_eq', val: 'FOF' })
  if (filterFOF.value === '0') filters.push({ type: 't0_neq', val: 'FOF' })
  if (filterDK.value === '1') filters.push({ type: 'name_contains', val: '定开' })
  if (filterDK.value === '0') filters.push({ type: 'name_not_contains', val: '定开' })
  return filters
}

// ========== 数据加载 ==========
async function loadData(reset = true) {
  if (loading.value) return
  loading.value = true
  if (reset) page.value = 1

  try {
    // 确定 t0 过滤（FOF 类型筛选用 t0_eq）
    let t0Filter = filterT0.value || undefined
    if (filterFOF.value === '1') t0Filter = 'FOF'
    if (filterFOF.value === '0' && !filterT0.value) t0Filter = undefined // 不能简单过滤

    const result = await fetchFundScores({
      t0: t0Filter,
      t1: filterT1.value || undefined,
      search: buildSearchText(),
      kKey: currentPeriod.value,
      page: page.value,
      pageSize,
      // 客户端附加筛选参数（后端不支持的由前端过滤）
      hp: filterHP.value || undefined,
      dailyLimit: filterDailyLimit.value || undefined,
      etf: filterETF.value || undefined,
      lof: filterLOF.value || undefined,
      dk: filterDK.value || undefined,
      fof: filterFOF.value || undefined,
    })

    if (result.data) {
      // 前端补充筛选（基于名称智能识别）
      let filtered = result.data
      if (filterSC.value) filtered = filtered.filter(f => extractShareClass(f.n) === filterSC.value)
      if (filterETF.value === '1') filtered = filtered.filter(f => /ETF/i.test(f.n))
      if (filterETF.value === '0') filtered = filtered.filter(f => !/ETF/i.test(f.n))
      if (filterLOF.value === '1') filtered = filtered.filter(f => /LOF/i.test(f.n))
      if (filterLOF.value === '0') filtered = filtered.filter(f => !/LOF/i.test(f.n))
      if (filterDK.value === '1') filtered = filtered.filter(f => /定开/.test(f.n))
      if (filterDK.value === '0') filtered = filtered.filter(f => !/定开/.test(f.n))
      if (filterFOF.value === '1') filtered = filtered.filter(f => f.t0 === 'FOF')
      if (filterFOF.value === '0') filtered = filtered.filter(f => f.t0 !== 'FOF')
      if (filterHP.value === 'no') filtered = filtered.filter(f => !f.hp)
      if (filterHP.value && filterHP.value !== 'no') {
        const hp = parseInt(filterHP.value)
        filtered = filtered.filter(f => f.hp && parseInt(f.hp) >= hp)
      }

      funds.value = reset ? filtered : funds.value.concat(filtered)
      hasMore.value = result.data.length >= pageSize
    }
  } catch (e) {
    console.error('[fund-rank] load error', e)
  } finally {
    loading.value = false
    dataLoaded.value = true
  }
}

function buildSearchText() {
  return searchText.value || undefined
}

async function loadMeta() {
  try {
    const m = await fetchFundMeta()
    if (m) meta.value = m
  } catch (e) { /* ignore */ }
}

function refreshData() {
  if (refreshing.value) return
  refreshing.value = true
  loadData(true)
  loadMeta()
  setTimeout(() => { refreshing.value = false }, 2000)
}

// ========== 交互 ==========
function setT0(val) {
  filterT0.value = val
  filterT1.value = ''
  loadData(true)
}

function setT1(val) {
  filterT1.value = val
  loadData(true)
}

function setSC(val) {
  filterSC.value = val
  loadData(true)
}

function setFlag(type, val) {
  if (type === 'ETF') filterETF.value = val
  else if (type === 'LOF') filterLOF.value = val
  else if (type === 'FOF') { filterFOF.value = val; if (val === '1') { filterT0.value = ''; filterT1.value = '' } }
  else if (type === 'DK') filterDK.value = val
  loadData(true)
}

function setHP(val) {
  filterHP.value = val
  loadData(true)
}

function setDailyLimit(val) {
  filterDailyLimit.value = val
  loadData(true)
}

function switchPeriod(key) {
  currentPeriod.value = key
  loadData(true)
}

function doSearch() { loadData(true) }

function clearSearch() {
  searchText.value = ''
  loadData(true)
}

function loadMore() {
  if (!loading.value && hasMore.value) {
    page.value++
    loadData(false)
  }
}

function openDetail(fund) {
  detailFund.value = fund
}

onMounted(() => {
  loadData()
  loadMeta()
})
</script>

<style scoped>
.page-fund-rank {
  min-height: 100vh;
}

/* 顶部栏 */
.top-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.top-title-row {
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-shrink: 0;
}

.top-title-text {
  font-size: 19px;
  font-weight: 700;
  color: var(--text-primary);
}

.help-icon-btn {
  width: 17px;
  height: 17px;
  line-height: 17px;
  text-align: center;
  font-size: 11px;
  color: var(--text-muted);
  border: 1px solid #484F58;
  border-radius: 50%;
  cursor: pointer;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.search-box {
  flex: 1;
  position: relative;
  max-width: 260px;
}

.search-input {
  width: 100%;
  padding: 7px 32px 7px 12px;
  background: var(--bg-primary);
  border: 1px solid var(--border);
  border-radius: 16px;
  font-size: 13px;
  color: var(--text-primary);
  outline: none;
  box-sizing: border-box;
}

.search-input::placeholder { color: var(--text-muted); }
.search-input:focus { border-color: var(--accent-red); }

.search-clear {
  position: absolute;
  right: 10px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  padding: 2px;
}

/* 数据信息条 */
.data-info-bar {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 6px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.data-info-row {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 8px;
}

.data-refresh {
  margin-left: 8px;
  padding: 2px 10px;
  font-size: 11px;
  color: var(--accent-red);
  background: rgba(255, 71, 87, 0.1);
  border-radius: 12px;
  cursor: pointer;
}

.data-refresh.refreshing { opacity: 0.5; }

/* ===== 筛选区 ===== */
.filter-section {
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  padding: 0 0 4px;
}

.filter-row {
  display: flex;
  align-items: flex-start;
  padding: 8px 12px 4px;
  gap: 8px;
  border-bottom: 1px solid rgba(48, 54, 61, 0.4);
}

.filter-label {
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
  width: 52px;
  padding-top: 6px;
  line-height: 1.2;
}

.filter-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  flex: 1;
}

.filter-chip {
  padding: 5px 12px;
  background: var(--bg-card-hover);
  border-radius: 14px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.15s;
  white-space: nowrap;
}

.filter-chip.active {
  background: var(--accent-red);
  color: #fff;
}

/* 更多筛选 */
.more-filter-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 8px 12px 6px;
  font-size: 12px;
  color: var(--text-secondary);
  cursor: pointer;
}

.toggle-arrow {
  display: inline-block;
  transition: transform 0.2s;
  font-size: 14px;
}

.toggle-arrow.open {
  transform: rotate(180deg);
}

.more-filter-body {
  border-top: 1px solid rgba(48, 54, 61, 0.4);
  padding-bottom: 4px;
}

.filter-tip {
  padding: 8px 12px 4px;
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.6;
}

/* 周期 + 结果 */
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 16px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
}

.period-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  white-space: nowrap;
  flex: 1;
}

.period-tab {
  flex-shrink: 0;
  padding: 5px 14px;
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-card-hover);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.15s;
}

.period-tab.active {
  background: var(--accent-red);
  color: #fff;
}

.result-count {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 500;
  flex-shrink: 0;
}

/* 基金列表 */
.fund-list {
  padding: 8px 12px;
}

.fund-card {
  display: flex;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 14px;
  margin-bottom: 8px;
  cursor: pointer;
  transition: background 0.15s;
}

.fund-card:hover { background: var(--bg-card-hover); }

.fund-rank-area {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 56px;
  flex-shrink: 0;
}

.fund-rank-num {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 600;
}

.fund-score-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-top: 6px;
}

.fund-score {
  font-size: 20px;
  font-weight: 700;
  line-height: 1;
}

.score-gold { color: #FFB800; }
.score-orange { color: #FF6B35; }
.score-cyan { color: #06B6D4; }
.score-default { color: #8B949E; }

.fund-score-label {
  font-size: 10px;
  color: var(--text-muted);
  margin-top: 4px;
}

.fund-info {
  flex: 1;
  margin-left: 12px;
  overflow: hidden;
}

.fund-name-row { display: flex; align-items: center; }

.fund-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.4;
}

.fund-sub {
  display: flex;
  align-items: center;
  gap: 5px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--text-secondary);
}

.fund-code { color: var(--accent-red); font-weight: 500; }
.fund-sep { color: var(--border); }

.fund-scores-row {
  display: flex;
  gap: 14px;
  margin-top: 10px;
}

.fs-item {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.fs-period {
  font-size: 10px;
  color: var(--text-muted);
  margin-bottom: 2px;
}

.fs-value {
  font-size: 12px;
  font-weight: 600;
}

/* 加载更多 */
.load-more {
  text-align: center;
  padding: 16px;
  font-size: 13px;
  color: var(--accent-red);
  cursor: pointer;
}

/* 空/加载状态 */
.empty-state { text-align: center; padding: 60px 24px; }
.empty-text { font-size: 15px; color: var(--text-secondary); margin-bottom: 6px; }
.empty-hint { font-size: 12px; color: var(--text-muted); }
.loading-wrap { display: flex; justify-content: center; padding: 60px 0; }
.loading-text { font-size: 13px; color: var(--text-muted); }

/* 底部说明 */
.bottom-info {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  padding: 24px 16px 48px;
}

.bottom-info span { font-size: 10px; color: var(--text-muted); }

/* 颜色 */
.ret-up { color: var(--accent-red); }
.ret-down { color: var(--accent-green); }

/* ===== 弹窗通用 ===== */
.mask {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  z-index: 100;
}

/* ===== 详情弹窗 ===== */
.detail-panel {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  max-height: 88vh;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.detail-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
  margin-right: 12px;
  line-height: 1.4;
}

.detail-close {
  font-size: 16px;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 32px;
}

.detail-section { margin-bottom: 20px; }

.detail-section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  display: block;
  margin-bottom: 10px;
}

.section-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.section-source { font-size: 10px; color: var(--text-muted); }

.attr-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  border-bottom: 1px solid rgba(48, 54, 61, 0.5);
}

.attr-label {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
  width: 70px;
}

.attr-value {
  font-size: 12px;
  color: var(--text-primary);
  text-align: right;
  flex: 1;
  line-height: 1.4;
}

.attr-date { font-size: 10px; color: var(--text-muted); }

.detail-scores-grid {
  display: flex;
  justify-content: space-around;
  background: var(--bg-primary);
  border-radius: 10px;
  padding: 12px;
}

.ds-item { display: flex; flex-direction: column; align-items: center; }
.ds-period { font-size: 11px; color: var(--text-muted); margin-bottom: 4px; }
.ds-score { font-size: 16px; font-weight: 700; }

.returns-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.return-col {
  display: flex;
  flex-direction: column;
  align-items: center;
  min-width: 60px;
}

.ret-label { font-size: 10px; color: var(--text-muted); margin-bottom: 3px; }
.ret-value { font-size: 13px; font-weight: 600; color: var(--text-primary); }

.risk-table { display: flex; flex-direction: column; }

.risk-head {
  display: flex;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  margin-bottom: 2px;
}

.risk-th { font-size: 10px; color: var(--text-muted); font-weight: 600; }

.risk-row {
  display: flex;
  align-items: center;
  padding: 8px 0;
}

.risk-label { width: 60px; font-size: 11px; color: var(--text-muted); flex-shrink: 0; }

.risk-val {
  flex: 1;
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}

.risk-val.risk-high { color: var(--accent-red); }
.risk-val.risk-mid { color: var(--accent-orange, #FF8C00); }
.risk-val.risk-low { color: var(--accent-green); }

/* 天天基金跳转按钮 */
.detail-goto {
  display: block;
  text-align: center;
  padding: 14px 0 4px;
  margin-top: 16px;
  border-top: 1px solid var(--border);
  font-size: 14px;
  color: var(--accent-red);
  font-weight: 500;
  text-decoration: none;
}

.detail-goto:hover { opacity: 0.8; }

/* ===== 帮助弹窗 ===== */
.help-panel {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  max-height: 70vh;
  background: var(--bg-card);
  border-radius: 16px 16px 0 0;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}

.help-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px 12px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.help-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.help-close { font-size: 16px; color: var(--text-muted); cursor: pointer; padding: 4px; }

.help-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 32px;
}

.help-section { margin-bottom: 14px; }

.help-section-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.help-desc {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.7;
}

.help-color-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 0;
}

.help-dot { width: 12px; height: 12px; border-radius: 50%; flex-shrink: 0; }

.help-color-text {
  font-size: 12px;
  font-weight: 500;
  flex-shrink: 0;
  min-width: 90px;
}

.score-gold-text { color: #FFB800; }
.score-orange-text { color: #FF6B35; }
.score-cyan-text { color: #06B6D4; }
.score-default-text { color: #8B949E; }

.help-color-desc { font-size: 12px; color: var(--text-muted); }
</style>
