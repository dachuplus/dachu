<template>
  <div class="page-home">
    <!-- 金刚区：核心功能入口 -->
    <div class="kingkong-area">
      <router-link
        v-for="entry in entries"
        :key="entry.path"
        :to="entry.path"
        class="kingkong-item"
      >
        <span class="kingkong-icon">{{ entry.icon }}</span>
        <span class="kingkong-label">{{ entry.label }}</span>
      </router-link>
    </div>

    <!-- 实时指数概览 -->
    <div class="card index-quote-bar" v-if="quotesLoaded">
      <div class="quote-scroll-wrap">
        <div class="quote-list">
          <div
            v-for="q in quoteList"
            :key="q.key"
            class="quote-item"
          >
            <div class="quote-label">{{ q.label }}</div>
            <div class="quote-price" :style="{ color: q.changePct >= 0 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ q.price || '--' }}
            </div>
            <div class="quote-change" :style="{ color: q.changePct >= 0 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ q.changePct >= 0 ? '+' : '' }}{{ q.changePct != null ? q.changePct.toFixed(2) : '--' }}%
            </div>
          </div>
        </div>
      </div>
      <div class="data-source-tag" @click="loadQuotes">实时数据 · {{ dataTime }} ↻</div>
    </div>

    <!-- 全市场性价比 Banner -->
    <div class="card market-banner">
      <div class="banner-header">
        <span class="banner-title">全市场加权平均隐含夏普</span>
        <span class="help-icon" @click="helpKey = 'marketGauge'">❓</span>
      </div>
      <div class="market-sharpe-wrap">
        <div class="market-sharpe-value" :class="marketSharpe > 0 ? 'text-up' : 'text-down'">
          {{ marketSharpe !== '--' && marketSharpe > 0 ? '+' : '' }}{{ marketSharpe }}
        </div>
        <div class="market-sharpe-label">{{ marketSharpeLabel || '数据加载中...' }}</div>
      </div>
      <router-link class="view-detail" to="/config">查看大类资产详情 ></router-link>
    </div>

    <!-- 股债性价比概览 -->
    <div class="card" v-if="sbvLatest">
      <div class="card-title">
        股债性价比
        <span class="card-subtitle">Fed Model</span>
        <span class="help-icon" @click="helpKey = 'stockBondValue'">❓</span>
      </div>
      <div class="sbv-summary">
        <div class="sbv-big">
          <div class="sbv-big-value text-up">{{ sbvLatest.sh_spread }}%</div>
          <div class="sbv-big-label">上交所股债利差</div>
        </div>
        <div class="sbv-detail">
          <div class="sbv-detail-item">
            <span class="sbv-dl">上交所PE</span>
            <span class="sbv-dv">{{ sbvLatest.sh_pe }}倍</span>
          </div>
          <div class="sbv-detail-item">
            <span class="sbv-dl">深交所PE</span>
            <span class="sbv-dv">{{ sbvLatest.sz_pe }}倍</span>
          </div>
          <div class="sbv-detail-item">
            <span class="sbv-dl">深交所利差</span>
            <span class="sbv-dv" :style="{ color: sbvLatest.sz_spread >= 3 ? 'var(--color-up)' : 'var(--color-down)' }">
              {{ sbvLatest.sz_spread }}%
            </span>
          </div>
          <div class="sbv-detail-item">
            <span class="sbv-dl">历史百分位</span>
            <span class="sbv-dv" :style="{ color: sbvLatest.percentile != null ? (sbvLatest.percentile >= 50 ? 'var(--color-up)' : 'var(--color-down)') : 'var(--text-muted)' }">
              {{ sbvLatest.percentile != null ? sbvLatest.percentile + '%' : '--' }}
            </span>
          </div>
        </div>
      </div>
      <span class="sbv-source">value500.com · {{ sbvLatest.date }}月度</span>
    </div>

    <!-- 大类资产性价比 -->
    <div class="card">
      <div class="card-title">
        大类资产性价比
        <span class="help-icon" @click="helpKey = 'impliedReturn'">❓</span>
      </div>
      <div class="asset-subtitle">现金用Shibor，债券用YTM，股票用Gordon模型，黄金用实际利率模型</div>
      <div class="asset-grid" v-if="assets.length">
        <div class="asset-row asset-header">
          <span class="ar-name">资产</span>
          <span class="ar-val">指标</span>
          <span class="ar-val">预期收益</span>
          <span class="ar-val">风险溢价</span>
        </div>
        <div class="asset-row" v-for="item in assets" :key="item.key">
          <div class="ar-name-wrap">
            <span class="ar-name">{{ item.name }}</span>
          </div>
          <span class="ar-val">{{ item.metricLabel }}</span>
          <span class="ar-val" :class="item.hasData ? 'text-up' : ''">{{ item.impliedReturn }}</span>
          <span class="ar-val" :class="item.riskPremium !== '--' ? (item.riskPremium[0] === '+' ? 'text-up' : 'text-down') : ''">
            {{ item.riskPremium }}
          </span>
        </div>
      </div>
      <div class="loading-placeholder" v-else>
        <div class="skeleton" style="height:14px; width:100%; margin-bottom:8px;"></div>
        <div class="skeleton" style="height:14px; width:80%;"></div>
      </div>
      <router-link class="view-detail" to="/config">查看大类资产性价比详情 ></router-link>
    </div>

    <!-- 参考基准 -->
    <div class="card" v-if="refData">
      <div class="card-title">
        参考基准
        <span class="card-subtitle">value500.com</span>
      </div>
      <!-- 利率走廊 -->
      <div class="ref-section-title">利率走廊</div>
      <div class="ref-grid ref-grid-3">
        <div class="ref-cell">
          <span class="ref-cell-label">1Y国债</span>
          <span class="ref-cell-value">{{ refData.bondY1 }}</span>
        </div>
        <div class="ref-cell">
          <span class="ref-cell-label">5Y国债</span>
          <span class="ref-cell-value">{{ refData.bondY5 }}</span>
        </div>
        <div class="ref-cell">
          <span class="ref-cell-label">10Y国债</span>
          <span class="ref-cell-value" style="color:var(--color-up);font-weight:700">{{ refData.bondY10 }}</span>
        </div>
      </div>
      <div class="ref-row" v-if="refData.bondDate">
        <span class="ref-source">数据日期：{{ refData.bondDate }}</span>
      </div>
      <!-- 资金面 -->
      <div class="ref-section-title">资金面</div>
      <div class="ref-row" v-if="refData.shiborOn !== '--'">
        <span class="ref-label">Shibor隔夜</span>
        <span class="ref-value">{{ refData.shiborOn }}</span>
      </div>
      <!-- 宏观经济 -->
      <div class="ref-section-title">宏观经济</div>
      <div class="ref-grid ref-grid-3">
        <div class="ref-cell" v-if="refData.m1Growth !== '--'">
          <span class="ref-cell-label">M1增速</span>
          <span class="ref-cell-value">{{ refData.m1Growth }}</span>
        </div>
        <div class="ref-cell" v-if="refData.m2Growth !== '--'">
          <span class="ref-cell-label">M2增速</span>
          <span class="ref-cell-value" style="color:var(--color-up)">{{ refData.m2Growth }}</span>
        </div>
        <div class="ref-cell" v-if="refData.m1m2diff !== '--'">
          <span class="ref-cell-label">M1-M2差</span>
          <span class="ref-cell-value" :style="{ color: refData.m1m2diff[0] === '-' ? 'var(--color-down)' : 'var(--color-up)' }">
            {{ refData.m1m2diff }}
          </span>
        </div>
      </div>
      <div class="ref-row" v-if="refData.cpi !== '--'">
        <span class="ref-label">CPI同比</span>
        <span class="ref-value">{{ refData.cpi }}</span>
      </div>
      <!-- 估值参考 -->
      <div class="ref-section-title">估值参考</div>
      <div class="ref-grid ref-grid-3">
        <div class="ref-cell" v-if="refData.epShRatio">
          <span class="ref-cell-label">上交所股债比</span>
          <span class="ref-cell-value" :style="{ color: refData.epShRatio >= 2 ? 'var(--color-up)' : 'var(--color-down)' }">
            {{ refData.epShRatio }}
          </span>
        </div>
        <div class="ref-cell" v-if="refData.epSzRatio">
          <span class="ref-cell-label">深交所股债比</span>
          <span class="ref-cell-value" :style="{ color: refData.epSzRatio >= 2 ? 'var(--color-up)' : 'var(--color-down)' }">
            {{ refData.epSzRatio }}
          </span>
        </div>
      </div>
    </div>

    <!-- 指数估值概览 -->
    <div class="card" v-if="evaTop5.length || evaHigh5.length">
      <div class="card-title">
        指数估值概览
        <span class="card-subtitle">PE百分位</span>
        <span class="help-icon" @click="goToIndustryRank">详情 ></span>
      </div>
      <div class="eva-quick">
        <div class="eva-section">
          <span class="section-label low-label">低估 TOP5</span>
          <div class="eva-item" v-for="(item, idx) in evaTop5" :key="item.name">
            <span class="rank-num">{{ idx + 1 }}</span>
            <span class="ind-name">{{ item.name }}</span>
            <span class="ind-pct" :style="{ color: item.color }">{{ item.pct }}</span>
          </div>
        </div>
        <div class="eva-section">
          <span class="section-label high-label">高估 TOP5</span>
          <div class="eva-item" v-for="(item, idx) in evaHigh5" :key="item.name">
            <span class="rank-num">{{ idx + 1 }}</span>
            <span class="ind-name">{{ item.name }}</span>
            <span class="ind-pct" :style="{ color: item.color }">{{ item.pct }}</span>
          </div>
        </div>
      </div>
      <router-link class="view-detail" to="/tools/industry-rank">查看全部指数估值 ></router-link>
    </div>

    <!-- 帮助弹窗 -->
    <div class="home-help-overlay" v-if="helpKey" @click.self="helpKey = null">
      <div class="home-help-popup">
        <div class="home-help-title">{{ homeHelpMap[helpKey]?.title }}</div>
        <p class="home-help-desc">{{ homeHelpMap[helpKey]?.desc }}</p>
        <p class="home-help-update">数据更新频率：{{ homeHelpMap[helpKey]?.update }}</p>
        <div class="home-help-close" @click="helpKey = null">关闭</div>
      </div>
    </div>

    <!-- 底部声明 -->
    <div class="footer-note-bar">
      <div>数据来源：腾讯API(行情)、value500(国债/Shibor/M2/CPI/股债比)</div>
      <div>数据仅供参考，不构成投资建议</div>
      <div>权重模型：Kan &amp; Zhou (2007) 增强型风险平价</div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchValue500All, fetchDanjuanEva } from '../../utils/api'
import { getIndexQuotes, buildMarketData } from '../../utils/market-data'
import { calcAllExpectedReturns, calcEnhancedRiskParityWeights, calcMarketSharpe, calcRiskPremium } from '../../utils/calc'

const entries = [
  { path: '/config',             icon: '📈', label: '大类资产' },
  { path: '/style-factor',       icon: '🎯', label: '风格因子' },
  { path: '/tools/industry-rank',icon: '📊', label: '指数估值' },
  { path: '/tools/fund-rank',    icon: '🏅', label: '靠谱指数' },
  { path: '/portfolio',           icon: '💰', label: '基金组合' },
  { path: '/tools',              icon: '🔧', label: '指数工具' },
  { path: '/tools',              icon: '👑', label: '大V榜单'  },
  { path: '/lab',                icon: '✍️', label: '运营助手' },
]

// 行情数据
const quotesLoaded = ref(false)
const dataTime = ref('')
const quoteList = ref([
  { key: 'sh000001', label: '上证',    price: null, changePct: null },
  { key: 'sh000300', label: '沪深300', price: null, changePct: null },
  { key: 'sz399006', label: '创业板',  price: null, changePct: null },
  { key: 'sh000905', label: '中证500', price: null, changePct: null },
])

// 市场夏普
const marketSharpe = ref('--')
const marketSharpeLabel = ref('')

// 股债性价比
const sbvLatest = ref(null)

// 大类资产
const assets = ref([])

// 参考基准
const refData = ref(null)

// 指数估值概览
const evaTop5        = ref([])
const evaHigh5       = ref([])
const evaUpdateTime = ref('')

// 帮助弹窗
const helpKey = ref(null)
const homeHelpMap = {
  marketGauge: {
    title: '全市场加权平均隐含夏普',
    desc: '将6大类资产的隐含夏普比率按风险平价基础权重加权平均。正值表示市场整体有风险调整后的超额收益吸引力。',
    update: '指数行情交易日实时，宏观数据跟随 value500.com（日度）'
  },
  stockBondValue: {
    title: '股债性价比（Fed Model）',
    desc: '股债利差 = 股票盈利收益率(1/PE) - 国债收益率。正利差说明股票相对债券更便宜，利差越大性价比越高。',
    update: '跟随 value500.com 更新（日度）'
  },
  impliedReturn: {
    title: '大类资产预期收益率',
    desc: '股票：Gordon模型 E[R]=(1/PE)×adjust；债券：10Y国债YTM；黄金：实际利率模型；现金：Shibor隔夜。',
    update: '指数行情交易日实时，国债/Shibor 跟随 value500.com（日度）'
  }
}

// 获取实时行情（腾讯API，直连）
async function loadQuotes() {
  try {
    const codes = ['sh000001', 'sh000300', 'sz399006', 'sh000905']
    const url = `https://qt.gtimg.cn/q=${codes.join(',')}`
    const res = await fetch(url)
    const text = await res.text()
    const lines = text.split('\n')
    lines.forEach(line => {
      const m = line.match(/v_(\w+)="([^"]+)"/)
      if (!m) return
      const key = m[1]
      const parts = m[2].split('~')
      const idx = quoteList.value.findIndex(q => q.key === key)
      if (idx >= 0) {
        quoteList.value[idx] = {
          ...quoteList.value[idx],
          price: parts[3],
          changePct: parseFloat(parts[32]) || 0,
        }
      }
    })
    quotesLoaded.value = true
    const now = new Date()
    dataTime.value = `${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}`
  } catch (e) {
    console.error('[home] 行情获取失败', e)
    quotesLoaded.value = true
  }
}

// 获取 value500 + 蛋卷估值 数据
async function loadValue500() {
  try {
    // 原有并行获取（保持 Promise.all，两个函数内部已处理错误）
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

    const rf = (bondData.yield10y && bondData.yield10y > 0) ? bondData.yield10y : null

    // 参考基准
    refData.value = {
      bondY1: bondData.yield1y != null ? (bondData.yield1y * 100).toFixed(2) + '%' : '--',
      bondY5: bondData.yield5y != null ? (bondData.yield5y * 100).toFixed(2) + '%' : '--',
      bondY10: bondData.yield10y != null ? (bondData.yield10y * 100).toFixed(2) + '%' : '--',
      bondDate: bondData.date || '',
      shiborOn: shiborData.on != null ? (shiborData.on * 100).toFixed(3) + '%' : '--',
      shiborDate: shiborData.date || '',
      m1Growth: m2Data.m1yoy != null ? m2Data.m1yoy + '%' : '--',
      m2Growth: m2Data.m2yoy != null ? m2Data.m2yoy + '%' : '--',
      m1m2diff: m2Data.m1m2diff != null ? m2Data.m1m2diff + '%' : '--',
      m2Date: m2Data.date || '',
      cpi: cpiData.cpi != null ? (cpiData.cpi * 100).toFixed(1) + '%' : '--',
      cpiDate: cpiData.date || '',
      epShRatio: epData.shRatio || null,
      epSzRatio: epData.szRatio || null,
      epDate: epData.date || '',
    }

    // 股债性价比
    const epShRatio = epData.shRatio
    if (epShRatio && rf) {
      sbvLatest.value = {
        sh_spread: (rf * (epShRatio - 1) * 100).toFixed(2),
        sh_pe: (100 / epShRatio).toFixed(1),
        sz_pe: epData.szRatio ? (100 / epData.szRatio).toFixed(1) : '--',
        sz_spread: epData.szRatio ? (rf * (epData.szRatio - 1) * 100).toFixed(2) : null,
        percentile: null,
        date: epData.date || '',
      }
    }

    // 大类资产
    const v300Pct = pe300Data.pePercentile != null ? Math.round(pe300Data.pePercentile) : null
    const marketData = buildMarketData(quotes, { pePercentile: v300Pct }, {
      yield10y: rf || 0,
      shibor: { on: shiborData.on || 0 }
    })
    const expectedReturns = calcAllExpectedReturns({
      stock: { pe: marketData.stock.pe, pePercentile: marketData.stock.pePercentile },
      bond: { yield10y: rf },
      gold: { yield10y: rf, cpi: cpiData.cpi },
      cash: { shiborOn: marketData.cash.shiborOn || 0 }
    })
    const rpResult = calcEnhancedRiskParityWeights(expectedReturns, rf, 0.5)
    const ms = calcMarketSharpe(rpResult.sharpeMap)

    const ASSET_META = { cash: '现金', bond: '债券', stock: '股票', commodity: '商品', gold: '黄金', reit: 'REITs' }
    const stockPE = pe300Data.pe || marketData.stock.pe || 0

    assets.value = ['cash', 'bond', 'stock', 'commodity', 'gold', 'reit'].map(key => {
      const er = expectedReturns[key]
      const hasData = er.expectedReturn != null
      let metricLabel = '--'
      if (key === 'stock') metricLabel = stockPE > 0 ? 'PE ' + stockPE.toFixed(2) : '--'
      else if (marketData[key]?.changePct) metricLabel = (marketData[key].changePct > 0 ? '+' : '') + marketData[key].changePct.toFixed(2) + '%'
      return {
        key, name: ASSET_META[key], metricLabel,
        impliedReturn: hasData ? (er.expectedReturn * 100).toFixed(2) + '%' : '--',
        riskPremium: hasData && rf ? (() => { const rp = calcRiskPremium(er.expectedReturn, rf); return rp != null ? (rp > 0 ? '+' : '') + (rp * 100).toFixed(2) + '%' : '--' })() : '--',
        hasData
      }
    })

    marketSharpe.value = ms != null ? (ms > 0 ? '+' : '') + ms.toFixed(3) : '--'
    marketSharpeLabel.value = ms != null ? (ms > 0 ? '市场整体性价比偏正面' : '市场整体性价比偏负面') : '数据不足'

    // 指数估值概览（A股 ttype=3）
    try {
      const evaResult = await fetchDanjuanEva()
      if (evaResult?.code === 0 && evaResult.data) {
        const aStock = evaResult.data.filter(d => d.ttype === '3' && d.pePercentile != null)
        const sorted = aStock.sort((a, b) => a.pePercentile - b.pePercentile)
        evaTop5.value = sorted.slice(0, 5).map(d => ({
          name: d.name,
          pct: d.pePercentile != null ? d.pePercentile.toFixed(2) + '%' : '--',
          color: d.evaColor || '#FF5252'
        }))
        evaHigh5.value = sorted.slice(-5).reverse().map(d => ({
          name: d.name,
          pct: d.pePercentile != null ? d.pePercentile.toFixed(2) + '%' : '--',
          color: d.evaColor || '#2ED573'
        }))
        const dated = aStock.find(d => d.date)
        if (dated) evaUpdateTime.value = dated.date
      }
    } catch (ee) {
      console.error('[home] 蛋卷估值获取失败', ee)
    }

  } catch (e) {
    console.error('[home] value500 数据获取失败', e)
  }
}

onMounted(() => {
  loadQuotes()
  loadValue500()
})
</script>

<style scoped>
.page-home {
  padding-bottom: 16px;
}

/* 帮助弹窗 */
.home-help-overlay { position: fixed; inset: 0; background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center; z-index: 100; padding: 20px; }
.home-help-popup { background: var(--card-bg, #1a1d23); border-radius: 12px; padding: 20px; max-width: 360px; width: 100%; }
.home-help-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; }
.home-help-desc { font-size: 13px; color: var(--text-secondary, #aab); line-height: 1.6; margin: 0; }
.home-help-update { font-size: 12px; color: var(--text-dim, #8B949E); margin: 12px 0 0; padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.1); }
.home-help-close { text-align: center; margin-top: 16px; padding: 8px; background: rgba(255,255,255,0.08); border-radius: 8px; font-size: 14px; cursor: pointer; }

/* 金刚区 */
.kingkong-area {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--border);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  margin-bottom: 12px;
}

.kingkong-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 4px;
  padding: 14px 8px;
  background: var(--bg-card);
  text-decoration: none;
  transition: background 0.15s;
}

.kingkong-item:hover {
  background: var(--bg-hover);
}

.kingkong-icon {
  font-size: 22px;
  line-height: 1;
}

.kingkong-label {
  font-size: 11px;
  color: var(--text-secondary);
}

/* 行情 */
.index-quote-bar {}

.quote-scroll-wrap {
  overflow-x: auto;
}

.quote-list {
  display: flex;
  gap: 0;
  min-width: max-content;
}

.quote-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 4px 12px;
  border-right: 1px solid var(--border);
}

.quote-item:last-child { border-right: none; }

.quote-label {
  font-size: 11px;
  color: var(--text-muted);
}

.quote-price {
  font-size: 14px;
  font-weight: 700;
}

.quote-change {
  font-size: 11px;
  font-weight: 500;
}

.data-source-tag {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 8px;
  cursor: pointer;
}

/* 市场夏普 */
.market-banner {
  background: linear-gradient(135deg, var(--bg-card) 0%, #1a1f2e 100%);
}

.banner-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
}

.banner-title {
  font-size: 13px;
  color: var(--text-secondary);
}

.market-sharpe-wrap {
  display: flex;
  align-items: baseline;
  gap: 10px;
  margin-bottom: 12px;
}

.market-sharpe-value {
  font-size: 32px;
  font-weight: 700;
}

.market-sharpe-label {
  font-size: 13px;
  color: var(--text-muted);
}

.view-detail {
  font-size: 12px;
  color: var(--text-muted);
  text-decoration: none;
  display: block;
  margin-top: 8px;
}

.view-detail:hover {
  color: var(--text-secondary);
}

/* 股债性价比 */
.sbv-summary {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.sbv-big {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sbv-big-value {
  font-size: 28px;
  font-weight: 700;
}

.sbv-big-label {
  font-size: 11px;
  color: var(--text-muted);
}

.sbv-detail {
  flex: 1;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 6px;
}

.sbv-detail-item {
  display: flex;
  justify-content: space-between;
}

.sbv-dl {
  font-size: 11px;
  color: var(--text-muted);
}

.sbv-dv {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.sbv-source {
  font-size: 11px;
  color: var(--text-muted);
}

/* 大类资产 */
.asset-subtitle {
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.asset-grid {}

.asset-row {
  display: grid;
  grid-template-columns: 60px 1fr 1fr 1fr;
  gap: 4px;
  padding: 6px 0;
  border-bottom: 1px solid var(--border);
  font-size: 12px;
}

.asset-row.asset-header {
  color: var(--text-muted);
  font-size: 11px;
  border-bottom-color: var(--border);
}

.asset-row:last-child {
  border-bottom: none;
}

.ar-name {
  font-weight: 500;
  color: var(--text-secondary);
  font-size: 12px;
}

.ar-name-wrap {
  display: flex;
  align-items: center;
}

.ar-val {
  text-align: right;
  color: var(--text-secondary);
}

.loading-placeholder {
  padding: 8px 0;
}

/* 参考基准 */
.ref-section-title {
  font-size: 11px;
  color: var(--text-muted);
  font-weight: 600;
  margin: 10px 0 6px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.ref-grid {
  display: flex;
  gap: 8px;
  margin-bottom: 6px;
}

.ref-grid-3 {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
}

.ref-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.ref-cell-label {
  font-size: 10px;
  color: var(--text-muted);
}

.ref-cell-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ref-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ref-label {
  font-size: 12px;
  color: var(--text-secondary);
}

.ref-value {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.ref-source {
  font-size: 10px;
  color: var(--text-muted);
}

/* 指数估值概览 */
.eva-quick {
  display: flex;
  gap: 16px;
  margin-bottom: 8px;
}

.eva-section {
  flex: 1;
}

.section-label {
  font-size: 11px;
  font-weight: 600;
  margin-bottom: 6px;
  display: block;
}

.low-label { color: var(--color-up); }
.high-label { color: var(--color-down); }

.eva-item {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 3px 0;
  font-size: 12px;
}

.rank-num {
  width: 16px;
  color: var(--text-muted);
  font-size: 11px;
  flex-shrink: 0;
}

.ind-name {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ind-pct {
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
}

/* 底部声明 */
.footer-note-bar {
  text-align: center;
  padding: 16px 8px;
  font-size: 10px;
  color: var(--text-muted);
  line-height: 1.8;
}
</style>

