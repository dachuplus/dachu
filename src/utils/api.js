/**
 * utils/api.js - 前端 API 层
 *
 * 数据获取统一入口：
 * - 开发环境：通过 Vite proxy 代理 value500.com（/api/v500/...）
 * - 生产环境：优先 Supabase Edge Function，降级走 CORS 代理
 * - 腾讯行情API：直连（qt.gtimg.cn 无 CORS 限制）
 * - 东财 push2 API：直连（push2.eastmoney.com 支持 CORS）
 * - Supabase 数据库：通过 @supabase/supabase-js
 */

import { supabase } from '../api/supabase'
import { VALUE500_PAGES } from './value500'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL
const IS_DEV = import.meta.env.DEV

// ========== value500 数据获取 ==========

const V500_ORIGIN = 'https://www.value500.com'
const CORS_PROXY = 'https://corsproxy.io/?'

/**
 * 获取 value500 单个页面数据
 * 开发环境：通过 Vite proxy（/api/v500/...）获取 HTML，前端解析
 * 生产环境：通过 CORS 代理获取 HTML，前端解析（Edge Function 降级时使用）
 */
async function fetchValue500Page(key) {
  const page = VALUE500_PAGES[key]
  if (!page) return { code: -1, data: null, msg: '未知页面: ' + key }

  const targetUrl = V500_ORIGIN + page.path

  try {
    let html
    if (IS_DEV) {
      // 开发环境：Vite proxy
      const res = await fetch('/api/v500' + page.path, { signal: AbortSignal.timeout(8000) })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      html = await res.text()
    } else {
      // 生产环境：CORS 代理（降级方案）
      const res = await fetch(CORS_PROXY + encodeURIComponent(targetUrl), {
        signal: AbortSignal.timeout(10000)
      })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      html = await res.text()
    }
    return page.parse(html)
  } catch (err) {
    return { code: -1, data: null, msg: err.message }
  }
}

/**
 * 一站式获取 value500 所有参考基准数据
 * @param {string[]} pages - 要获取的页面列表，默认全部
 * @returns {Promise<Object>} { bond, shibor, m2, cpi, ep, pe300 }
 */
export async function fetchValue500All(pages) {
  const keys = pages || ['bond', 'shibor', 'm2', 'cpi', 'ep', 'pe300']

  if (IS_DEV) {
    // 开发环境：并行通过 Vite proxy 获取各页面
    const results = await Promise.allSettled(
      keys.map(key => fetchValue500Page(key))
    )
    const data = {}
    keys.forEach((key, i) => {
      data[key] = results[i].status === 'fulfilled'
        ? results[i].value
        : { code: -1, data: null, msg: results[i].reason?.message }
    })
    return data
  } else {
    // 生产环境：优先 Edge Function（一次请求获取全部）
    try {
      const res = await fetch(`${SUPABASE_URL}/functions/v1/value500`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pages: keys }),
        signal: AbortSignal.timeout(12000)
      })
      return await res.json()
    } catch (err) {
      console.error('[api] value500 Edge Function 失败，降级 CORS 代理:', err)
      const results = await Promise.allSettled(
        keys.map(key => fetchValue500Page(key))
      )
      const data = {}
      keys.forEach((key, i) => {
        data[key] = results[i].status === 'fulfilled'
          ? results[i].value
          : { code: -1, data: null, msg: results[i].reason?.message }
      })
      return data
    }
  }
}

// ========== 蛋卷基金估值 ==========

const DANJUAN_DEV_URL = '/api/danjuan/djapi/index_eva/dj'
const DANJUAN_API      = 'https://danjuanfunds.com/djapi/index_eva/dj'

/**
 * 获取蛋卷基金指数估值数据
 * 开发环境：通过 Vite proxy 直连
 * 生产环境：优先 Supabase Edge Function，降级走 CORS 代理
 * 返回：{ code: 0, data: [...], total: number, source: string }
 */
export async function fetchDanjuanEva() {
  try {
    let raw
    if (IS_DEV) {
      // 开发环境：Vite proxy
      const res = await fetch(DANJUAN_DEV_URL, { signal: AbortSignal.timeout(8000) })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      raw = await res.json()
    } else {
      // 生产环境：优先 Edge Function
      try {
        const res = await fetch(`${SUPABASE_URL}/functions/v1/value500`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ pages: ['danjuan'] }),
          signal: AbortSignal.timeout(12000)
        })
        const efData = await res.json()
        if (efData?.danjuan?.code === 0) {
          return efData.danjuan
        }
      } catch (efErr) {
        console.error('[api] danjuan Edge Function 失败，降级 CORS 代理:', efErr)
      }
      // 降级：CORS 代理直连蛋卷 API
      const res = await fetch(CORS_PROXY + encodeURIComponent(DANJUAN_API), {
        signal: AbortSignal.timeout(10000)
      })
      if (!res.ok) throw new Error('HTTP ' + res.status)
      raw = await res.json()
    }

    // 解析蛋卷返回格式
    if (!raw?.data?.items) return { code: -1, data: null, msg: '蛋卷数据格式异常' }
    const items = raw.data.items.map(item => ({
      name:        item.name,
      code:        item.index_code,
      ttype:       item.ttype,
      pe:          item.pe > 0           ? item.pe           : null,
      pePercentile: item.pe_percentile > 0 ? Math.round(item.pe_percentile * 10000) / 100 : null,
      pb:          item.pb > 0           ? item.pb           : null,
      pbPercentile: item.pb_percentile > 0 ? Math.round(item.pb_percentile * 10000) / 100 : null,
      dividendYield: item.yeild > 0         ? Math.round(item.yeild * 10000) / 100   : null,
      roe:         item.roe > 0          ? Math.round(item.roe * 10000) / 100    : null,
      peg:         item.peg > 0          ? item.peg          : null,
      evaType:     item.eva_type || '',
      evaText:     evaTypeText(item.eva_type),
      evaColor:    evaTypeColor(item.eva_type),
      date:         item.date || '',
    }))
    return { code: 0, data: items, total: items.length, source: 'danjuanfunds.com' }
  } catch (err) {
    return { code: -1, data: null, msg: err.message }
  }
}

function evaTypeText(type) {
  if (type === 'low')    return '低估'
  if (type === 'normal') return '适中'
  if (type === 'high')   return '高估'
  return '--'
}

function evaTypeColor(type) {
  if (type === 'low')    return '#FF5252'
  if (type === 'normal') return '#FFA502'
  if (type === 'high')   return '#2ED573'
  return '#6E7681'
}

// ========== Supabase 数据库查询 ==========

/**
 * 查询靠谱基金列表
 */
export async function fetchFundScores(options = {}) {
  const {
    category = null,
    minScore = 0,
    orderBy = 'score',
    orderDir = 'desc',
    limit = 50,
    offset = 0
  } = options

  let query = supabase
    .from('fund_scores')
    .select('*')
    .gte('score', minScore)

  if (category) {
    query = query.eq('category', category)
  }

  query = query
    .order(orderBy, { ascending: orderDir === 'asc' })
    .range(offset, offset + limit - 1)

  const { data, error, count } = await query
  if (error) throw error
  return { data, count }
}

/**
 * 查询投顾产品列表
 */
export async function fetchTouguProducts(options = {}) {
  const { type, limit = 50 } = options
  let query = supabase.from('tougu_products').select('*')
  if (type && type !== 'all') query = query.eq('type', type)
  query = query.order('return1y', { ascending: false, nullsFirst: false }).limit(limit)
  const { data, error } = await query
  if (error) throw error
  return data
}

/**
 * 查询配置项
 */
export async function fetchConfig(type) {
  const { data, error } = await supabase
    .from('config')
    .select('value, v')
    .eq('type', type)
    .limit(1)
    .single()
  if (error) return null
  return data?.value || data?.v || null
}
