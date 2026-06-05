/**
 * 数据 API 封装层
 * - Supabase 已配置时：从云数据库读取
 * - 未配置时：返回 Mock 数据，方便本地开发
 */
import { supabase } from './supabase.js'

// ========== 工具函数 ==========
function fmtPct(val, asDecimal = true) {
  if (val == null || val === '') return '--'
  if (asDecimal) return (val * 100).toFixed(2) + '%'
  return Number(val).toFixed(2) + '%'
}

/** 靠谱分颜色等级 */
function scoreColor(k) {
  if (k == null) return ''
  if (k >= 85) return 'gold'
  if (k >= 75) return 'orange'
  if (k >= 65) return 'cyan'
  return 'gray'
}

// ========== 投顾产品 ==========
export async function fetchTouguProducts(filters = {}) {
  if (supabase) {
    let query = supabase.from('tougu_products').select('*')
    if (filters.type) query = query.eq('type', filters.type)
    const { data, error } = await query.order('return1y', { ascending: false, nullsFirst: false })
    if (error) throw error
    return data
  }
  // Mock fallback
  return MOCK_TOUGU.filter(d => !filters.type || d.type === filters.type)
}

// ========== 基金靠谱指数 ==========
export async function fetchFundScores(params = {}) {
  const { t0, t1, search, kKey = 'k1', page = 1, pageSize = 30 } = params
  if (supabase) {
    let query = supabase.from('fund_scores').select('*')
    if (t0) query = query.eq('t0', t0)
    if (t1) query = query.eq('t1', t1)
    if (search) query = query.or(`n.ilike.%${search}%,c.ilike.%${search}%`)
    const from = (page - 1) * pageSize
    const { data, error } = await query
      .order(kKey, { ascending: false, nullsFirst: false })
      .range(from, from + pageSize - 1)
    if (error) throw error
    return { data: data || [] }
  }
  // Mock fallback
  return { data: MOCK_FUNDS }
}

// ========== 基金元信息 ==========
export async function fetchFundMeta() {
  if (supabase) {
    const { data, error } = await supabase
      .from('fund_scores_meta')
      .select('*')
      .order('id', { ascending: false })
      .limit(1)
      .single()
    if (error) return null
    return data
  }
  return null
}

// ========== 配置（API Key等）==========
export async function fetchConfig(type) {
  if (supabase) {
    const { data, error } = await supabase.from('config').eq('type', type).single()
    if (error) return null
    return data
  }
  return null
}

// ========== PE 历史 ==========
export async function fetchPEHistory(indexCode = '000300') {
  if (supabase) {
    const { data, error } = await supabase
      .from('index_pe_history')
      .select('*')
      .eq('index_code', indexCode)
      .order('trade_date', { ascending: true })
    if (error) throw error
    return data
  }
  return []
}

// ========== Mock 数据 ==========
const MOCK_TOUGU = [
  {
    name: '示例·均衡成长组合', company: '某某基金', type: 'high',
    typeName: '追求高收益', desc: '以权益类资产为主，追求长期超额收益',
    return3m: 0.0823, return1y: 0.2156, maxDrawdown: -0.1832,
    url: '#', updateDate: '2026-04-17'
  },
  {
    name: '示例·稳健固收组合', company: '某某基金', type: 'stable',
    typeName: '稳健理财', desc: '以固收类资产为主，追求稳定回报',
    return3m: 0.0132, return1y: 0.0675, maxDrawdown: -0.0312,
    url: '#', updateDate: '2026-04-17'
  },
  {
    name: '示例·养老储蓄组合', company: '某某基金', type: 'pension',
    typeName: '养老储蓄', desc: '长期配置，专注养老资金积累',
    return3m: 0.0215, return1y: 0.0882, maxDrawdown: -0.0521,
    url: '#', updateDate: '2026-04-17'
  },
]

const MOCK_FUNDS = [
  { c: '000001.OF', n: '华夏成长混合', t0: '混合型基金', k1: 72, k2: 65, k3: 88.5, k5: null, r1y: 23.41, r3y: 15.23, dd1y: -15.23, sr1y: 1.23, date: '2026-05-14' },
  { c: '110011.OF', n: '易方达优质精选', t0: '混合型基金', k1: 68, k2: 60, k3: 82.1, k5: null, r1y: 18.76, r3y: 12.56, dd1y: -18.34, sr1y: 0.98, date: '2026-05-14' },
  { c: '161725.OF', n: '招商中证白酒', t0: '股票型基金', k1: 55, k2: 48, k3: 75.4, k5: 70.2, r1y: 12.34, r3y: 8.45, dd1y: -21.56, sr1y: 0.72, date: '2026-05-14' },
]

export { fmtPct, scoreColor }
