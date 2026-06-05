/**
 * utils/calc.js - 资产配置计算引擎 v3
 *
 * 移植自 asset-config-miniapp，ES Module 版本
 *
 * 核心改造（v3）：
 * 1. 去掉温度计系统，改为预期收益率驱动
 * 2. 权重分配采用 Kan & Zhou (2007) 增强型风险平价
 * 3. 每个数据点必须有来源和截止时间，禁止模拟/兜底数据
 */

// ============================================
// 第一部分：基础计算公式
// ============================================

/**
 * 计算百分位（当前值在历史中的位置）
 * @param {number} current - 当前值
 * @param {number[]} history - 历史值数组
 * @returns {number|null} 百分位 0-100，无历史数据时返回 null
 */
export function calcPercentile(current, history) {
  if (!history || history.length === 0) return null
  const sorted = [...history].sort((a, b) => a - b)
  let below = 0
  for (const val of sorted) {
    if (val < current) below++
  }
  return Math.round((below / sorted.length) * 100)
}

/**
 * Gordon模型：隐含预期收益率
 * E[R] = (1/PE) × percentileAdjust
 * @param {number} pe - 当前市盈率（必须 > 0）
 * @param {number} percentile - PE百分位（0-100）
 * @returns {number} 隐含预期收益率（小数形式，如 0.08 表示 8%）
 */
export function calcImpliedReturn(pe, percentile) {
  if (pe <= 0 || percentile == null) return null
  const adjust = 1.5 - (percentile / 100)
  return (1 / pe) * adjust
}

/**
 * 风险溢价 = 预期收益率 - 无风险利率
 */
export function calcRiskPremium(expectedReturn, riskFreeRate) {
  if (expectedReturn == null) return null
  return expectedReturn - riskFreeRate
}

/**
 * 隐含夏普比率 Sharpe = (E[R] - Rf) / σ
 */
export function calcSharpe(expectedReturn, riskFreeRate, volatility) {
  if (expectedReturn == null || volatility <= 0) return null
  return (expectedReturn - riskFreeRate) / volatility
}

// ============================================
// 第二部分：各类资产预期收益率估算
// ============================================

/**
 * 股票预期收益率（Gordon模型）
 */
export function calcStockExpectedReturn(params) {
  const { pe, pePercentile } = params
  if (!pe || pe <= 0) {
    return { expectedReturn: null, source: '', method: '无有效PE数据' }
  }
  if (pePercentile == null) {
    const er = 1 / pe
    return {
      expectedReturn: er,
      source: 'Gordon模型(中性系数), PE=' + pe.toFixed(2),
      method: '无百分位数据，adjust=1.0'
    }
  }
  const er = calcImpliedReturn(pe, pePercentile)
  return {
    expectedReturn: er,
    source: 'Gordon模型, PE=' + pe.toFixed(2) + ', 百分位=' + pePercentile + '%',
    method: 'adjust=' + (1.5 - pePercentile / 100).toFixed(2)
  }
}

/**
 * 债券预期收益率（10Y国债YTM）
 */
export function calcBondExpectedReturn(params) {
  const { yield10y } = params
  if (yield10y == null || yield10y <= 0) {
    return { expectedReturn: null, source: '', method: '无国债收益率数据' }
  }
  return {
    expectedReturn: yield10y,
    source: '10Y国债YTM=' + (yield10y * 100).toFixed(2) + '%',
    method: '持有到期收益率'
  }
}

/**
 * 商品预期收益率（暂无合规数据源）
 */
export function calcCommodityExpectedReturn() {
  return {
    expectedReturn: null,
    source: '无数据源',
    method: '商品无直接估值指标，暂无合规数据源'
  }
}

/**
 * 黄金预期收益率（实际利率模型）
 */
export function calcGoldExpectedReturn(params) {
  var yield10y = (params && params.yield10y) || 0
  var cpi = (params && params.cpi) || 0
  var baseER = 0.05

  if (yield10y > 0 && cpi > 0) {
    var realRate = yield10y - cpi
    var adjust = (0.02 - realRate) * 1.5
    adjust = Math.max(-0.02, Math.min(0.02, adjust))
    var er = baseER + adjust
    return {
      expectedReturn: Math.max(0.01, er),
      source: '实际利率模型, 10Y=' + (yield10y*100).toFixed(2) + '%, CPI=' + (cpi*100).toFixed(1) + '%',
      method: 'E[R]=5%+(2%-实际利率)×1.5'
    }
  }

  if (yield10y > 0) {
    var signal = (0.03 - yield10y) * 0.8
    signal = Math.max(-0.01, Math.min(0.01, signal))
    return {
      expectedReturn: baseER + signal,
      source: '利率信号模型, 10Y=' + (yield10y*100).toFixed(2) + '%',
      method: '无CPI数据，用利率信号调整'
    }
  }

  return {
    expectedReturn: null,
    source: '无数据',
    method: '无利率数据'
  }
}

/**
 * REITs预期收益率（暂无合规数据源）
 */
export function calcReitExpectedReturn() {
  return {
    expectedReturn: null,
    source: '无数据源',
    method: 'REITs无直接估值指标，暂无合规数据源'
  }
}

/**
 * 现金预期收益率（Shibor隔夜）
 */
export function calcCashExpectedReturn(params) {
  var shiborOn = (params && params.shiborOn) || 0
  if (shiborOn > 0) {
    return {
      expectedReturn: shiborOn,
      source: 'Shibor隔夜=' + (shiborOn * 100).toFixed(3) + '%',
      method: 'Shibor隔夜利率'
    }
  }
  return {
    expectedReturn: null,
    source: '无数据',
    method: 'Shibor获取失败'
  }
}

/**
 * 统一计算所有资产的预期收益率
 */
export function calcAllExpectedReturns(params) {
  return {
    stock: calcStockExpectedReturn(params.stock || {}),
    bond: calcBondExpectedReturn(params.bond || {}),
    commodity: calcCommodityExpectedReturn(params.commodity || {}),
    gold: calcGoldExpectedReturn(params.gold || { yield10y: (params.bond || {}).yield10y }),
    reit: calcReitExpectedReturn(params.reit || {}),
    cash: calcCashExpectedReturn(params.cash || {})
  }
}

// ============================================
// 第三部分：Kan & Zhou (2007) 增强型风险平价
// ============================================

export const DEFAULT_VOLATILITIES = {
  cash: 0.005,
  bond: 0.04,
  stock: 0.22,
  commodity: 0.18,
  gold: 0.16,
  reit: 0.20
}

export const VOLATILITY_SOURCES = {
  cash: '货币基金/逆回购年化波动率',
  bond: '中债综合指数长期年化波动率',
  stock: '沪深300长期年化波动率',
  commodity: '南华综合指数长期年化波动率',
  gold: '上海金交所Au9999长期年化波动率',
  reit: '中证REITs指数年化波动率(参考值)'
}

/**
 * 步骤1：风险平价基础权重（1/σ 分配）
 */
export function calcRiskParityWeights(volatilities = DEFAULT_VOLATILITIES) {
  const invVols = {}
  let total = 0
  for (const [key, vol] of Object.entries(volatilities)) {
    invVols[key] = 1 / vol
    total += invVols[key]
  }
  const weights = {}
  for (const [key, invVol] of Object.entries(invVols)) {
    weights[key] = invVol / total
  }
  return weights
}

/**
 * 步骤2：Kan & Zhou (2007) 增强型风险平价权重
 * w_i* = w_i^RP × (1 + (SR_i - median_SR) × sensitivity)
 */
export function calcEnhancedRiskParityWeights(expectedReturns, riskFreeRate, sensitivity) {
  sensitivity = sensitivity || 0.5

  const baseWeights = calcRiskParityWeights()

  const sharpeMap = {}
  for (const [key, info] of Object.entries(expectedReturns)) {
    const vol = DEFAULT_VOLATILITIES[key]
    const er = info.expectedReturn
    if (er != null && er > 0 && riskFreeRate != null) {
      sharpeMap[key] = calcSharpe(er, riskFreeRate, vol)
    } else {
      sharpeMap[key] = null
    }
  }

  const validSharpes = Object.values(sharpeMap).filter(s => s != null)
  const medianSharpe = validSharpes.length > 0
    ? validSharpes.sort((a, b) => a - b)[Math.floor(validSharpes.length / 2)]
    : 0

  const adjustedWeights = {}
  for (const [key, base] of Object.entries(baseWeights)) {
    const sr = sharpeMap[key]
    if (sr != null) {
      const signal = sr - medianSharpe
      adjustedWeights[key] = base * (1 + signal * sensitivity)
    } else {
      adjustedWeights[key] = base
    }
  }

  const clampedWeights = {}
  for (const [key, w] of Object.entries(adjustedWeights)) {
    clampedWeights[key] = Math.max(0, Math.min(0.50, w))
  }

  const total = Object.values(clampedWeights).reduce((s, w) => s + w, 0)
  if (total === 0) {
    return {
      weights: normalizeWeights(baseWeights),
      sharpeMap,
      baseWeights,
      medianSharpe
    }
  }

  const normalized = {}
  for (const [key, w] of Object.entries(clampedWeights)) {
    normalized[key] = Math.round(w / total * 100)
  }

  const sum = Object.values(normalized).reduce((s, w) => s + w, 0)
  const diff = 100 - sum
  if (diff !== 0) {
    const maxKey = Object.keys(normalized).reduce((a, b) =>
      Math.abs(normalized[a]) > Math.abs(normalized[b]) ? a : b
    )
    normalized[maxKey] += diff
  }

  return {
    weights: normalized,
    sharpeMap,
    baseWeights,
    medianSharpe
  }
}

/**
 * 权重归一化
 */
export function normalizeWeights(weights) {
  const total = Object.values(weights).reduce((s, w) => s + w, 0)
  if (total === 0) return weights
  const normalized = {}
  for (const [key, w] of Object.entries(weights)) {
    normalized[key] = Math.round(w / total * 100)
  }
  return normalized
}

// ============================================
// 第四部分：全市场性价比指标
// ============================================

/**
 * 全市场加权平均隐含夏普
 */
export function calcMarketSharpe(sharpeMap) {
  const baseWeights = calcRiskParityWeights()
  let totalWeight = 0
  let weightedSum = 0
  for (const [key, sr] of Object.entries(sharpeMap)) {
    if (sr != null) {
      weightedSum += sr * baseWeights[key]
      totalWeight += baseWeights[key]
    }
  }
  if (totalWeight === 0) return null
  return weightedSum / totalWeight
}

// ============================================
// 第五部分：风格因子 & 行业评分
// ============================================

/**
 * Barra六因子性价比评分
 * Score = EP×0.25 + Size×0.15 + Growth×0.15 + Momentum×0.15 + Quality×0.15 + Vol×0.15
 */
export function calcFactorScore(factors) {
  const weights = { ep: 0.25, size: 0.15, growth: 0.15, momentum: 0.15, quality: 0.15, vol: 0.15 }
  let score = 0
  for (const [factor, weight] of Object.entries(weights)) {
    score += (factors[factor] || 50) * weight
  }
  return Math.round(score)
}

/**
 * 行业综合评分
 */
export function calcIndustryScore(metrics) {
  const { pePercentile = 50, pbPercentile = 50, growthRate = 10, roe = 10, dividendYield = 2, peg = 1.5 } = metrics

  const peScore = 100 - pePercentile
  const pbScore = 100 - pbPercentile
  const growthScore = Math.min(growthRate * 3, 100)
  const roeScore = Math.min(roe * 2.5, 100)
  const divScore = Math.min(dividendYield * 10, 100)
  const pegScore = Math.max(100 - peg * 30, 0)

  const score = peScore * 0.25 + pbScore * 0.15 + growthScore * 0.20
              + roeScore * 0.15 + divScore * 0.10 + pegScore * 0.15
  return Math.round(score)
}

/**
 * 券种利差性价比评分（债券用）
 */
export function calcBondScore(yieldToMaturity, creditSpread, duration) {
  const ytmScore = Math.min(yieldToMaturity * 6, 100)
  const spreadScore = Math.min(creditSpread / 3, 100)
  let durationScore = 100 - Math.abs(duration - 4) * 20
  durationScore = Math.max(0, Math.min(100, durationScore))

  return Math.round(ytmScore * 0.4 + spreadScore * 0.4 + durationScore * 0.2)
}

/**
 * 通用信号解读（兼容因子和行业评分）
 */
export function getSignalAdvice(score) {
  if (score >= 75) return { level: '强烈推荐', signal: 'hot', advice: '低估高性价比，建议超配', color: '#FF4757' }
  if (score >= 60) return { level: '推荐配置', signal: 'warm', advice: '性价比较好，建议标配或略超配', color: '#FF5252' }
  if (score >= 40) return { level: '中性持有', signal: 'cool', advice: '性价比一般，建议标配', color: '#FFA502' }
  if (score >= 25) return { level: '谨慎配置', signal: 'cold', advice: '性价比偏低，建议低配', color: '#8B949E' }
  return { level: '建议回避', signal: 'avoid', advice: '高估低性价比，建议空仓或做空', color: '#6E7681' }
}

/**
 * 基于百分位的信号解读（百分位高=过热=回避）
 */
export function getSignalFromPercentile(percentile) {
  if (percentile >= 75) return { level: '回避', signal: 'avoid', color: '#6E7681' }
  if (percentile >= 60) return { level: '低配', signal: 'cold', color: '#8B949E' }
  if (percentile >= 40) return { level: '中性', signal: 'cool', color: '#FFA502' }
  if (percentile >= 25) return { level: '标配', signal: 'warm', color: '#FF5252' }
  return { level: '超配', signal: 'hot', color: '#FF4757' }
}
