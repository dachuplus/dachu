<template>
  <div class="page-asset-class">
    <!-- 数据更新时间 + 刷新 -->
    <div class="header-bar">
      <span class="data-time">数据截止：{{ dataDate }}</span>
      <span class="refresh-btn" @click="loadData">{{ refreshing ? '加载中...' : '↻ 刷新' }}</span>
    </div>

    <!-- 错误提示 -->
    <div class="card error-card" v-if="dataError">
      <p>{{ dataError }}</p>
    </div>

    <!-- 全市场加权平均隐含夏普 -->
    <div class="card" v-if="marketSharpe !== '--'">
      <div class="card-title">
        全市场加权平均隐含夏普
        <span class="help-icon" @click="showHelp('marketSharpe')">❓</span>
      </div>
      <p class="card-desc">基于风险平价权重加权平均，正值=整体有超额收益吸引力</p>
      <div class="market-sharpe-box">
        <div class="ms-value" :class="marketSharpe > 0 ? 'text-up' : 'text-down'">
          {{ marketSharpe > 0 ? '+' : '' }}{{ marketSharpe }}
        </div>
        <div class="ms-label">{{ marketSharpe > 0 ? '市场整体性价比偏正面' : '市场整体性价比偏负面' }}</div>
      </div>
    </div>

    <!-- 股债性价比 -->
    <div class="card" v-if="sbvLatest">
      <div class="card-title">
        股债性价比
        <span class="card-subtitle">Fed Model</span>
        <span class="help-icon" @click="showHelp('stockBondValue')">❓</span>
      </div>
      <div class="sbv-row">
        <div class="sbv-main">
          <div class="sbv-value text-up">{{ sbvLatest.sh_spread }}%</div>
          <div class="sbv-label">上交所股债利差</div>
        </div>
        <div class="sbv-details">
          <div class="sbv-item"><span>上交所PE</span><span>{{ sbvLatest.sh_pe }}倍</span></div>
          <div class="sbv-item"><span>深交所PE</span><span>{{ sbvLatest.sz_pe }}倍</span></div>
          <div class="sbv-item">
            <span>深交所利差</span>
            <span :style="{ color: sbvLatest.sz_spread >= 3 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ sbvLatest.sz_spread }}%
            </span>
          </div>
          <div class="sbv-item"><span>数据日期</span><span>{{ epDate }}</span></div>
        </div>
      </div>
    </div>

    <!-- 宏观指标卡片 -->
    <div class="macro-grid">
      <div class="card macro-card" v-if="bondY10y !== null">
        <div class="macro-label">10Y国债</div>
        <div class="macro-value">{{ (bondY10y * 100).toFixed(2) }}%</div>
        <div class="macro-sub">期限利差 {{ bondSpread !== null ? bondSpread + 'bp' : '--' }}</div>
      </div>
      <div class="card macro-card" v-if="shiborOn !== null">
        <div class="macro-label">Shibor隔夜</div>
        <div class="macro-value">{{ (shiborOn * 100).toFixed(3) }}%</div>
        <div class="macro-sub">{{ shiborDate }}</div>
      </div>
      <div class="card macro-card" v-if="m2Growth !== null">
        <div class="macro-label">M2同比</div>
        <div class="macro-value">{{ m2Growth }}%</div>
        <div class="macro-sub">M1-M2 {{ m1m2diff !== null ? m1m2diff : '--' }}</div>
      </div>
      <div class="card macro-card" v-if="cpi !== null">
        <div class="macro-label">CPI同比</div>
        <div class="macro-value">{{ (cpi * 100).toFixed(1) }}%</div>
        <div class="macro-sub">{{ cpiDate }}</div>
      </div>
    </div>

    <!-- 预期收益率 vs 风险溢价 -->
    <div class="card">
      <div class="card-title">
        预期收益率 vs 风险溢价
        <span class="help-icon" @click="showHelp('expectedReturn')">❓</span>
      </div>
      <p class="card-desc">现金用Shibor，债券用YTM，股票用Gordon模型，黄金用实际利率模型</p>
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>资产</th>
              <th>指标</th>
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
              <td :class="item.hasData ? 'text-up' : ''">{{ item.expectedReturn }}</td>
              <td :class="rpClass(item.riskPremium)">{{ item.riskPremium }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- 隐含夏普比率 -->
    <div class="card">
      <div class="card-title">
        隐含夏普比率
        <span class="card-subtitle">风险调整后性价比</span>
        <span class="help-icon" @click="showHelp('sharpe')">❓</span>
      </div>
      <p class="card-desc">Sharpe = (预期收益 - 无风险利率) / 年化波动率</p>
      <div class="sharpe-list">
        <div class="sharpe-item" v-for="item in sharpeList" :key="item.name">
          <div class="sharpe-name">{{ item.name }}</div>
          <div class="sharpe-bar-wrap">
            <div class="sharpe-bar">
              <div
                class="sharpe-fill"
                v-if="item.hasData"
                :style="{ width: item.barWidth + '%', background: item.color }"
              ></div>
              <div class="sharpe-zero"></div>
            </div>
            <span class="sharpe-value" :style="{ color: item.hasData ? item.color : 'var(--text-dim)' }">
              {{ item.sharpe }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 建议配置权重 -->
    <div class="card">
      <div class="card-title">
        建议配置权重
        <span class="help-icon" @click="showHelp('weight')">❓</span>
      </div>
      <p class="card-desc">Kan & Zhou (2007) 增强型风险平价：基础权重 × 夏普信号调整</p>
      <div class="weight-section">
        <div class="weight-visual">
          <div class="weight-bar">
            <div
              v-for="w in weightList"
              :key="w.key"
              class="weight-segment"
              :style="{ width: w.weight + '%', background: w.color }"
              :title="w.name + ' ' + w.weight + '%'"
            ></div>
          </div>
          <div class="weight-legend">
            <div class="legend-item" v-for="w in weightList" :key="w.key">
              <span class="legend-dot" :style="{ background: w.color }"></span>
              <span class="legend-name">{{ w.name }}</span>
              <span class="legend-val">{{ w.weight }}%</span>
            </div>
          </div>
        </div>
        <div class="weight-details">
          <div class="wd-item" v-for="w in weightList" :key="w.key">
            <span class="wd-name">{{ w.name }}</span>
            <span class="wd-base">基础{{ w.baseWeight }}%</span>
            <span class="wd-arrow">→</span>
            <span class="wd-final" :style="{ color: w.weight > w.baseWeight ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ w.weight }}%
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- 帮助弹窗 -->
    <div class="help-overlay" v-if="helpKey" @click.self="helpKey = null">
      <div class="help-popup">
        <div class="help-title">{{ helpTitles[helpKey] }}</div>
        <div class="help-content">{{ helpTexts[helpKey] }}</div>
        <div class="help-update-info">
          <div class="help-section-label">数据更新频率</div>
          <div>指数行情：交易日实时</div>
          <div>国债/Shibor：跟随 value500.com（日度）</div>
          <div>M2/CPI：跟随国家统计局发布（月度）</div>
        </div>
        <div class="help-close" @click="helpKey = null">关闭</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { getIndexQuotes, buildMarketData } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights, calcMarketSharpe, calcRiskPremium } from '../../utils/calc'
import { fetchValue500All } from '../../utils/api'

// 资产元信息
const ASSET_META = {
  cash:      { name: '现金', color: '#8B949E' },
  bond:      { name: '债券', color: '#2196F3' },
  stock:     { name: '股票', color: '#FF4757' },
  commodity: { name: '商品', color: '#FF9800' },
  gold:      { name: '黄金', color: '#FFC107' },
  reit:      { name: 'REITs', color: '#9C27B0' }
}

const dataDate = ref('--')
const dataError = ref('')
const refreshing = ref(false)
const marketSharpe = ref('--')
const helpKey = ref(null)

// 宏观数据
const bondY10y = ref(null)
const bondSpread = ref(null)
const shiborOn = ref(null)
const shiborDate = ref('')
const m2Growth = ref(null)
const m1m2diff = ref(null)
const cpi = ref(null)
const cpiDate = ref('')
const epDate = ref('')
const sbvLatest = ref(null)

// 计算结果
const assets = ref([])
const sharpeList = ref([])
const weightList = ref([])

// 帮助文案
const helpTitles = {
  marketSharpe: '全市场加权平均隐含夏普',
  expectedReturn: '预期收益率计算方法',
  sharpe: '隐含夏普比率',
  weight: '增强型风险平价权重',
  stockBondValue: '股债性价比'
}
const helpTexts = {
  marketSharpe: '将6大类资产的隐含夏普比率按风险平价基础权重加权平均。正值表示市场整体有风险调整后的超额收益吸引力，数值越大性价比越高。',
  expectedReturn: '股票：Gordon模型 E[R]=(1/PE)×adjust，adjust基于PE百分位\n债券：10Y国债YTM\n黄金：实际利率模型 E[R]=5%+(2%-实际利率)×1.5\n现金：Shibor隔夜利率',
  sharpe: 'Sharpe = (预期收益率 - 无风险利率) / 年化波动率\n正值=有超额收益吸引力，负值=性价比不如无风险资产\n柱状条越正越长，性价比越高',
  weight: 'Kan & Zhou (2007) 增强型风险平价：\n1. 基础权重按 1/σ 分配（风险平价）\n2. 乘以 (1 + (SR - median_SR) × 0.5) 信号调整\n3. 限幅 [0%, 50%]，归一化到 100%\n\n夏普高于中位数的资产加仓，低于中位数的减仓',
  stockBondValue: '股债利差 = 股票盈利收益率(1/PE) - 国债收益率\n\n正利差说明股票相对债券更便宜\n利差越大，股票性价比越高\n\n数据来源：value500.com'
}

function showHelp(key) { helpKey.value = key }

function metricClass(label) {
  if (!label || label === '--') return ''
  return label[0] === '+' ? 'text-up' : (label[0] === '-' ? 'text-down' : '')
}

function rpClass(val) {
  if (!val || val === '--') return ''
  return val[0] === '+' ? 'text-up' : 'text-down'
}

async function loadData() {
  refreshing.value = true
  dataError.value = ''

  try {
    const [quotes, v500] = await Promise.all([
      getIndexQuotes(),
      fetchValue500All()
    ])

    // 解析 value500
    const bondData = v500.bond?.code === 0 ? v500.bond.data : {}
    const shiborData = v500.shibor?.code === 0 ? v500.shibor.data : {}
    const m2Data = v500.m2?.code === 0 ? v500.m2.data : {}
    const cpiData = v500.cpi?.code === 0 ? v500.cpi.data : {}
    const epData = v500.ep?.code === 0 ? v500.ep.data : {}
    const pe300Data = v500.pe300?.code === 0 ? v500.pe300.data : {}

    // 无风险利率
    const rf = (bondData.yield10y && bondData.yield10y > 0) ? bondData.yield10y : null

    // 宏观数据
    bondY10y.value = bondData.yield10y ?? null
    bondSpread.value = bondData.spread ?? null
    shiborOn.value = shiborData.on ?? null
    shiborDate.value = shiborData.date || ''
    m2Growth.value = m2Data.m2yoy ?? null
    m1m2diff.value = m2Data.m1m2diff ?? null
    cpi.value = cpiData.cpi ?? null
    cpiDate.value = cpiData.date || ''
    epDate.value = epData.date || ''

    // PE百分位
    const v300Pct = pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null

    // 构建市场数据
    const marketData = buildMarketData(quotes, { pePercentile: v300Pct }, {
      yield10y: rf || 0,
      shibor: { on: shiborData.on || 0, date: shiborData.date }
    })

    // 计算预期收益率
    const erParams = {
      stock: { pe: marketData.stock.pe, pePercentile: marketData.stock.pePercentile },
      bond: { yield10y: rf },
      gold: { yield10y: rf, cpi: cpiData.cpi },
      cash: { shiborOn: marketData.cash.shiborOn || 0 }
    }
    const expectedReturns = calcAllExpectedReturns(erParams)

    // 增强型风险平价
    const rpResult = calcEnhancedRiskParityWeights(expectedReturns, rf, 0.5)

    // 全市场夏普
    const ms = calcMarketSharpe(rpResult.sharpeMap)
    marketSharpe.value = ms != null ? (ms > 0 ? '+' : '') + ms.toFixed(3) : '--'

    // 股债性价比
    const epShRatio = epData.shRatio
    const epSzRatio = epData.szRatio
    if (epShRatio != null && rf) {
      const shSpread = (rf * (epShRatio - 1) * 100).toFixed(2)
      const szSpread = epSzRatio ? (rf * (epSzRatio - 1) * 100).toFixed(2) : null
      sbvLatest.value = {
        sh_pe: (100 / epShRatio).toFixed(1),
        sh_spread: shSpread,
        sz_pe: epSzRatio ? (100 / epSzRatio).toFixed(1) : '--',
        sz_spread: szSpread
      }
    }

    // 数据截止时间
    const firstQuote = quotes['sh000001'] || quotes['sh000300'] || {}
    const updateTime = firstQuote.updateTime || ''
    dataDate.value = updateTime.length === 14
      ? `${updateTime.slice(0,4)}-${updateTime.slice(4,6)}-${updateTime.slice(6,8)} ${updateTime.slice(8,10)}:${updateTime.slice(10,12)}`
      : new Date().toLocaleString('zh-CN')

    // 组装资产卡片
    const assetKeys = ['cash', 'bond', 'stock', 'commodity', 'gold', 'reit']
    const stockPE = pe300Data.pe || marketData.stock.pe || 0
    const tmpAssets = []

    for (const key of assetKeys) {
      const meta = ASSET_META[key]
      const er = expectedReturns[key]
      const sharpe = rpResult.sharpeMap[key]
      const weight = rpResult.weights[key] || 0
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
        expectedReturn: hasData ? (er.expectedReturn * 100).toFixed(2) + '%' : '--',
        riskPremium: hasData && rf != null
          ? (() => { const rp = calcRiskPremium(er.expectedReturn, rf); return rp != null ? (rp > 0 ? '+' : '') + (rp * 100).toFixed(2) + '%' : '--' })()
          : '--',
        hasData,
        color: sharpe != null ? (sharpe > 0 ? '#FF4757' : '#2ED573') : '#6E7681'
      })
    }
    assets.value = tmpAssets

    // 夏普列表
    const maxAbsSharpe = Math.max(...assetKeys.map(k => {
      const s = rpResult.sharpeMap[k]
      return s != null ? Math.abs(s) : 0
    }), 0.5)
    sharpeList.value = assetKeys.map(key => {
      const sharpe = rpResult.sharpeMap[key]
      const hasData = sharpe != null
      const barWidth = hasData ? Math.min(Math.abs(sharpe) / maxAbsSharpe * 45 + 5, 50) : 0
      return {
        name: ASSET_META[key].name,
        sharpe: hasData ? (sharpe > 0 ? '+' : '') + sharpe.toFixed(3) : '--',
        hasData, barWidth,
        color: hasData ? (sharpe > 0 ? '#FF4757' : '#2ED573') : '#6E7681'
      }
    })

    // 权重列表
    const baseWeights = rpResult.baseWeights
    weightList.value = assetKeys.map(key => ({
      key,
      name: ASSET_META[key].name,
      weight: rpResult.weights[key] || 0,
      baseWeight: baseWeights[key] ? Math.round(baseWeights[key] * 100) : 0,
      color: ASSET_META[key].color
    }))

  } catch (err) {
    let msg = '数据加载失败'
    if (err?.message) {
      msg = err.message.includes('timeout') ? '请求超时，可能为非交易时间' : err.message
    }
    dataError.value = msg
  } finally {
    refreshing.value = false
  }
}

onMounted(loadData)
</script>

<style scoped>
/* ========== gov.uk 风格大类资产配置 ========== */
.page-asset-class { padding-bottom: var(--space-2xl); }
.header-bar { display: flex; justify-content: space-between; padding: var(--space-sm) 0; font-size: 14px; color: var(--text-secondary); border-bottom: 1px solid var(--border); }
.refresh-btn { color: var(--link); cursor: pointer; text-decoration: underline; }

/* 卡片通用 */
.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-sm); }
.card-subtitle { font-size: 14px; color: var(--text-secondary); margin-left: 6px; font-weight: 400; }
.card-desc { font-size: 14px; color: var(--text-secondary); margin-bottom: var(--space-md); }
.help-icon { cursor: pointer; }
.help-update-info { margin-top: var(--space-md); padding-top: var(--space-sm); border-top: 1px solid var(--border); font-size: 14px; color: var(--text-secondary); line-height: 1.8; }
.help-update-info .help-section-label { font-weight: 700; }

.error-card { border-left: 5px solid #d4351c; }
.error-card p { margin: 0; font-size: 16px; color: #d4351c; }

.text-up { color: var(--color-up) !important; }
.text-down { color: var(--color-down) !important; }

.market-sharpe-box { text-align: center; padding: var(--space-md) 0; }
.ms-value { font-size: 48px; font-weight: 700; }
.ms-label { font-size: 16px; color: var(--text-secondary); margin-top: var(--space-sm); }

.sbv-row { display: flex; gap: var(--space-xl); align-items: center; }
.sbv-main { text-align: center; min-width: 100px; }
.sbv-value { font-size: 36px; font-weight: 700; }
.sbv-label { font-size: 14px; color: var(--text-secondary); }
.sbv-details { flex: 1; }
.sbv-item { display: flex; justify-content: space-between; font-size: 16px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
.sbv-item span:first-child { color: var(--text-secondary); }

.macro-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--space-lg); margin-bottom: var(--space-xl); }
.macro-card { padding: var(--space-md); text-align: center; border: 1px solid var(--border); background: #ffffff; }
.macro-label { font-size: 14px; color: var(--text-secondary); }
.macro-value { font-size: 24px; font-weight: 700; color: var(--text-primary); margin: var(--space-xs) 0; }
.macro-sub { font-size: 14px; color: var(--text-secondary); }

.table-wrap { overflow-x: auto; }
.data-table { width: 100%; border-collapse: collapse; font-size: 14px; }
.data-table th { text-align: left; padding: var(--space-sm); color: var(--text-secondary); border-bottom: 2px solid var(--border); font-weight: 700; white-space: nowrap; }
.data-table td { padding: var(--space-sm); color: var(--text-primary); border-bottom: 1px solid var(--border); white-space: nowrap; }
.td-name { font-weight: 700; }
.metric-sub { display: block; font-size: 12px; color: var(--text-secondary); }
.row-disabled { opacity: 0.4; }

.sharpe-list { display: flex; flex-direction: column; gap: var(--space-md); }
.sharpe-item { display: flex; align-items: center; gap: var(--space-sm); }
.sharpe-name { width: 50px; font-size: 14px; color: var(--text-secondary); text-align: right; flex-shrink: 0; }
.sharpe-bar-wrap { flex: 1; display: flex; align-items: center; gap: var(--space-sm); }
.sharpe-bar { flex: 1; height: 20px; background: #f3f2f1; position: relative; overflow: hidden; }
.sharpe-fill { position: absolute; top: 0; left: 50%; height: 100%; transition: width 0.5s ease; }
.sharpe-zero { position: absolute; top: 0; left: 50%; width: 1px; height: 100%; background: var(--border); }
.sharpe-value { width: 60px; text-align: right; font-size: 14px; font-weight: 700; }

.weight-section { margin-top: var(--space-md); }
.weight-bar { display: flex; height: 30px; overflow: hidden; margin-bottom: var(--space-md); }
.weight-segment { transition: width 0.5s ease; }
.weight-legend { display: flex; flex-wrap: wrap; gap: var(--space-sm) var(--space-md); margin-bottom: var(--space-md); }
.legend-item { display: flex; align-items: center; gap: 4px; font-size: 14px; }
.legend-dot { width: 8px; height: 8px; }
.legend-name { color: var(--text-secondary); }
.legend-val { color: var(--text-primary); font-weight: 700; }

.weight-details { border-top: 2px solid var(--border); padding-top: var(--space-sm); }
.wd-item { display: flex; align-items: center; font-size: 14px; padding: var(--space-xs) 0; border-bottom: 1px solid var(--border); }
.wd-name { width: 50px; color: var(--text-secondary); }
.wd-base { flex: 1; color: var(--text-secondary); }
.wd-arrow { margin: 0 8px; color: var(--text-secondary); }
.wd-final { font-weight: 700; }

.help-overlay { position: fixed; inset: 0; background: rgba(11,12,12,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; padding: var(--space-lg); }
.help-popup { background: #ffffff; border: 1px solid var(--border); padding: var(--space-xl); max-width: 400px; width: 100%; }
.help-title { font-size: 24px; font-weight: 700; margin-bottom: var(--space-md); }
.help-content { font-size: 16px; color: var(--text-primary); line-height: 1.7; white-space: pre-line; }
.help-close { margin-top: var(--space-md); text-align: center; color: var(--link); cursor: pointer; font-size: 16px; text-decoration: underline; }
</style>
