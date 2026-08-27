/**
 * utils/market-data.js - 实时市场数据服务 v2
 *
 * 数据来源（全部公开合规）：
 * 1. 腾讯股票API（qt.gtimg.cn）→ 指数实时行情 + PE/PB
 * 2. 东财 push2 API → 申万行业板块
 * 3. 新浪行业API → 申万行业（降级方案）
 */

import { calcPercentile } from './calc.js'
import { withCache } from './cache.js'
import EM_NAME_MAP from './sw-industry-map.json'

// ===== 工具函数 =====

/**
 * 通用请求封装（fetch 版）
 * @param {string} url
 * @param {number} timeout - 超时毫秒数，默认 5000
 * @returns {Promise<string>}
 */
function request(url, timeout = 5000) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  return fetch(url, { signal: controller.signal })
    .then(res => {
      clearTimeout(timer)
      if (!res.ok) throw new Error('HTTP ' + res.status)
      return res.text()
    })
    .catch(err => {
      clearTimeout(timer)
      throw err
    })
}

// ===== 1. 指数实时行情 =====

export const INDEX_CODES = {
  '上证指数': 'sh000001',
  '深证成指': 'sz399001',
  '创业板指': 'sz399006',
  '沪深300': 'sh000300',
  '上证50': 'sh000016',
  '中证500': 'sh000905',
  '中证1000': 'sh000852',
  '中证800': 'sh000906',
  '创业板50': 'sz399673',
  '上证国债': 'sh000012',
  '中证红利': 'sh000922',
  '国证价值': 'sz399371',
  '国证成长': 'sz399370',
  '黄金ETF': 'sh518880',
  '商品ETF': 'sz159934',
  '豆粕ETF': 'sz159985'
}

/**
 * 获取主要指数实时行情（腾讯API）
 * @returns {Promise<Object>} { 指数名/sh代码: { name, code, price, change, changePct, pe, pb, ... } }
 */
function getIndexQuotesImpl() {
  const codes = Object.values(INDEX_CODES).join(',')
  const url = 'https://qt.gtimg.cn/q=' + codes

  return request(url).then(text => {
    const result = {}
    const lines = text.split(';')
    for (const line of lines) {
      if (!line.trim()) continue
      const parts = line.split('~')
      if (parts.length < 5) continue

      let fullCode = ''
      const p0 = parts[0] || ''
      const m = p0.match(/v_(sh|sz)(\d+)/i)
      if (m) {
        fullCode = m[1].toLowerCase() + m[2]
      }
      const shortCode = (parts[2] || '').trim()
      if (!shortCode && !fullCode) continue

      const high52w = parts.length > 67 ? (parseFloat(parts[67]) || 0) : 0
      const low52w  = parts.length > 68 ? (parseFloat(parts[68]) || 0) : 0
      const highToday = parts.length > 33 ? (parseFloat(parts[33]) || 0) : 0
      const lowToday  = parts.length > 34 ? (parseFloat(parts[34]) || 0) : 0

      const data = {
        name: parts[1],
        code: fullCode || shortCode,
        price: parts.length > 3 ? (parseFloat(parts[3]) || 0) : 0,
        preClose: parts.length > 4 ? (parseFloat(parts[4]) || 0) : 0,
        open: parts.length > 5 ? (parseFloat(parts[5]) || 0) : 0,
        volume: parts.length > 6 ? (parseInt(parts[6]) || 0) : 0,
        amount: parts.length > 7 ? (parseFloat(parts[7]) || 0) : 0,
        change: parts.length > 31 ? (parseFloat(parts[31]) || 0) : 0,
        changePct: parts.length > 32 ? (parseFloat(parts[32]) || 0) : 0,
        pe: parts.length > 39 ? (parseFloat(parts[39]) || 0) : 0,
        pb: parts.length > 62 ? (parseFloat(parts[62]) || 0) : 0,
        high: high52w || highToday,
        low: low52w || lowToday,
        high52w,
        low52w,
        updateTime: parts.length > 30 ? (parts[30] || '') : ''
      }

      if (fullCode) result[fullCode] = data
      if (shortCode) result[shortCode] = data
      if (parts[1]) result[parts[1]] = data
    }
    return result
  })
}

// 带 60s TTL 缓存，避免首页/信号页重复拉取实时行情
export function getIndexQuotes() {
  return withCache('indexQuotes', 60000, getIndexQuotesImpl)
}

// ===== 2. 申万行业板块数据 =====

export const SW_L1_STANDARD = [
  '农林牧渔', '基础化工', '钢铁', '有色金属', '电子',
  '家用电器', '食品饮料', '纺织服饰', '轻工制造', '医药生物',
  '公用事业', '交通运输', '房地产', '商贸零售', '社会服务',
  '银行', '非银金融', '建筑材料', '建筑装饰', '电力设备',
  '国防军工', '计算机', '传媒', '通信', '煤炭',
  '石油石化', '环保', '美容护理', '机械设备', '汽车',
  '综合'
]

function mapEmToSw1(emName) {
  return EM_NAME_MAP[emName] || null
}

/**
 * 从东财 push2 API 获取申万一级行业数据
 */
function getSwIndustriesFromEastmoney() {
  const url = 'https://push2.eastmoney.com/api/qt/clist/get?pn=1&pz=100&po=1&np=1&fltt=2&invt=2&fid=f3&fs=m:90+t:2+f:!50&fields=f3,f12,f14,f24,f25,f128,f136'

  return request(url, 8000).then(text => {
    const data = JSON.parse(text)
    const diff = (data.data && data.data.diff) || []
    if (diff.length === 0) throw new Error('东财行业数据为空')

    const sw1Map = {}
    for (const item of diff) {
      const emName = (item.f14 || '').trim()
      if (!emName) continue

      const sw1Name = mapEmToSw1(emName)
      if (!sw1Name || !SW_L1_STANDARD.includes(sw1Name)) continue

      let pe = parseFloat(item.f24) || 0
      if (pe <= 0) pe = parseFloat(item.f25) || 0
      const changePct = parseFloat(item.f3) || 0
      const leaderName = (item.f128 || '').trim()
      const leaderChangePct = parseFloat(item.f136) || 0

      if (!sw1Map[sw1Name]) {
        sw1Map[sw1Name] = { peValues: [], changePctSum: 0, count: 0, leaderName: '', leaderChangePct: 0 }
      }
      const bucket = sw1Map[sw1Name]
      if (pe > 0 && pe < 1000) bucket.peValues.push(pe)
      bucket.changePctSum += changePct
      bucket.count += 1
      if (leaderChangePct > bucket.leaderChangePct) {
        bucket.leaderName = leaderName
        bucket.leaderChangePct = leaderChangePct
      }
    }

    const result = []
    for (const [name, b] of Object.entries(sw1Map)) {
      let avgPe = 0
      if (b.peValues.length > 0) {
        avgPe = b.peValues.reduce((s, v) => s + v, 0) / b.peValues.length
      }
      const avgChangePct = b.count > 0 ? (b.changePctSum / b.count) : 0

      result.push({
        name, code: '', pe: Math.round(avgPe * 100) / 100,
        changePct: Math.round(avgChangePct * 100) / 100,
        pePercentile: null, leaderName: b.leaderName, leaderCode: '',
        leaderChangePct: Math.round(b.leaderChangePct * 100) / 100, leaderPrice: 0,
        stockCount: b.count
      })
    }

    // 按申万一级行业平均涨跌幅降序排列
    result.sort((a, b) => (b.changePct || 0) - (a.changePct || 0))
    return result
  })
}

// 新浪旧版申万行业API（降级方案）
const SW_NAME_MAP_SINA = {
  'new_blhy': '建筑材料', 'new_cbzz': '国防军工', 'new_cmyl': '传媒', 'new_dlhy': '公用事业',
  'new_dqhy': '电力设备', 'new_dzqj': '电子', 'new_dzxx': '电子', 'new_fdc': '房地产',
  'new_fdsb': '电力设备', 'new_fjzz': '国防军工', 'new_fzhy': '纺织服饰', 'new_fzjx': '机械设备',
  'new_fzxl': '纺织服饰', 'new_glql': '交通运输', 'new_gsgq': '公用事业', 'new_gthy': '钢铁',
  'new_hbhy': '环保', 'new_hghy': '基础化工', 'new_hqhy': '基础化工', 'new_jdhy': '轻工制造',
  'new_jdly': '社会服务', 'new_jjhy': '轻工制造', 'new_jrhy': '非银金融', 'new_jtys': '交通运输',
  'new_jxhy': '机械设备', 'new_jzjc': '建筑材料', 'new_kfq': '房地产', 'new_ljhy': '食品饮料',
  'new_mtc': '汽车', 'new_mthy': '煤炭', 'new_nlmy': '农林牧渔', 'new_nyhf': '基础化工',
  'new_qczz': '汽车', 'new_qtxy': '汽车', 'new_slzp': '食品饮料', 'new_snhy': '建筑材料',
  'new_sphy': '食品饮料', 'new_stock': '新股', 'new_swzz': '医药生物', 'new_sybh': '商贸零售',
  'new_syhy': '石油石化', 'new_tchy': '建筑材料', 'new_wzwm': '商贸零售', 'new_ylqx': '医药生物',
  'new_yqyb': '机械设备', 'new_ysbz': '轻工制造', 'new_ysjs': '有色金属', 'new_zhhy': '综合',
  'new_zzhy': '轻工制造',
  'new_yh': '银行', 'new_bank': '银行',
  'new_zjhy': '非银金融', 'new_insurance': '非银金融',
  'new_yyyw': '医药生物', 'new_swbz': '医药生物',
  'new_jzjz': '建筑装饰', 'new_jzzs': '建筑装饰',
  'new_gfgj': '国防军工',
  'new_mrghl': '美容护理',
  'new_shjfw': '社会服务',
  'new_smls': '商贸零售'
}

function getSwIndustriesFromSina() {
  const url = 'https://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php?industry=sw1'

  return request(url).then(text => {
    const result = []
    const nameExist = {}
    let dataStr = ''
    for (const line of text.split('\n')) {
      if (line.indexOf('{') >= 0) { dataStr = line; break }
    }

    const entries = []
    const regex = /"(\w+)":"([^"]+)"/g
    let match
    while ((match = regex.exec(dataStr)) !== null) {
      entries.push({ key: match[1], value: match[2] })
    }

    for (const entry of entries) {
      const parts = entry.value.split(',')
      if (parts.length < 13) continue

      const code = entry.key
      const name = SW_NAME_MAP_SINA[code] || (parts[1] || '').trim()
      if (code === 'new_stock') continue
      if (!SW_L1_STANDARD.includes(name)) continue
      if (nameExist[name]) continue
      nameExist[name] = true

      const stockCount = parseInt(parts[2]) || 0
      const pe = parseFloat(parts[3]) || 0
      const changePct = parseFloat(parts[5]) || 0
      const leaderName = (parts[12] || '').trim()
      const leaderCode = (parts[8] || '').trim()
      const leaderChangePct = parseFloat(parts[9]) || 0
      const leaderPrice = parseFloat(parts[10]) || 0

      result.push({
        name, code, pe, changePct,
        pePercentile: null, leaderName, leaderCode,
        leaderChangePct, leaderPrice,
        stockCount
      })
    }

    // 按行业涨跌幅降序排列（新浪源无评分）
    result.sort((a, b) => (b.changePct || 0) - (a.changePct || 0))
    return result
  })
}

/**
 * 获取申万一级行业板块数据
 * 优先东财 push2，失败降级新浪
 */
export function getSwIndustries() {
  return withCache('swIndustries', 60000, () =>
    getSwIndustriesFromEastmoney().catch(err => {
      console.warn('[market-data] 东财行业API失败，降级新浪:', err.message)
      return getSwIndustriesFromSina()
    })
  )
}

// ===== 3. 原始市场数据构建 =====

/**
 * 构建用于 calcAllExpectedReturns 的原始数据
 * @param {Object} quotes - getIndexQuotes 返回
 * @param {Object} peData - { pePercentile: number }（蛋卷估值来源）或 { peHistory, latestDate }
 * @param {Object} options - { shibor: {on, date}, yield10y: number }
 */
export function buildMarketData(quotes, peData, options) {
  options = options || {}
  const hs300 = quotes['沪深300'] || quotes['sh000300'] || {}

  // ===== 股票 =====
  let stockPE = (hs300.pe && hs300.pe > 0) ? hs300.pe : 0
  let stockPEPercentile = null
  let peHistoryCount = 0
  let peHistoryDate = ''

  if (peData) {
    if (peData.pePercentile != null) {
      stockPEPercentile = peData.pePercentile
      peHistoryCount = -1
    } else if (peData.peHistory && peData.peHistory.length > 0 && stockPE > 0) {
      stockPEPercentile = calcPercentile(stockPE, peData.peHistory)
      peHistoryCount = peData.peHistory.length
      peHistoryDate = peData.latestDate || ''
    }
  }

  const goldETF = quotes['黄金ETF'] || quotes['sh518880'] || {}
  const commodityETF = quotes['商品ETF'] || quotes['sz159934'] || {}
  const shiborData = options.shibor || {}

  return {
    stock: {
      pe: stockPE,
      pePercentile: stockPEPercentile,
      peHistoryCount,
      peHistoryDate,
      price: hs300.price || 0,
      changePct: hs300.changePct || 0
    },
    bond: {
      yield10y: options.yield10y || 0
    },
    commodity: {
      price: commodityETF.price || 0,
      changePct: commodityETF.changePct || 0,
      source: '易方达商品ETF'
    },
    gold: {
      price: goldETF.price || 0,
      changePct: goldETF.changePct || 0,
      source: '华安黄金ETF'
    },
    reit: {
      price: null,
      changePct: null,
      source: '暂无实时数据'
    },
    cash: {
      shiborOn: shiborData.on || 0,
      shiborDate: shiborData.date || ''
    }
  }
}

/**
 * 从 macro-data Edge Function 返回的扁平 JSON 解析出宏观基准结构
 * @param {Object|null} flat - fetchMacroData() 的返回值
 * @returns {Object} { bond, shibor, m2, cpi, ep, pe300, pmi, rf, get }
 *   结构与历史 parseValue500Data 一致，前端 loadAll 可零改动消费：
 *   - bond.yield10y（小数）、bond.spread（10Y-2Y 百分点）
 *   - shibor.on（小数）、m2.m2yoy（百分数）、cpi.cpi（小数）
 *   - pe300.pe / pe300.pePercentile（百分数）
 *   - pmi.pmi
 *   - rf = bond.yield10y > 0 ? bond.yield10y : null
 *   - get(key): 取 flat[key] || {}（兼容 get('pmi') 写法）
 */
export function parseMacroData(flat) {
  const f = flat || {}
  const bondData = f.bond || {}
  const shiborData = f.shibor || {}
  const m2Data = f.m2 || {}
  const cpiData = f.cpi || {}
  const epData = f.ep || {}
  const pe300Data = f.pe300 || {}
  const pmiData = f.pmi || {}
  const us10yData = f.us10y || {}
  const ppiData = f.ppi || {}

  const rf = (bondData.yield10y && bondData.yield10y > 0) ? bondData.yield10y : null

  return {
    bond: bondData,
    shibor: shiborData,
    m2: m2Data,
    cpi: cpiData,
    ep: epData,
    pe300: pe300Data,
    pmi: pmiData,
    us10y: us10yData,
    ppi: ppiData,
    rf,
    get: (k) => f[k] || {}
  }
}
