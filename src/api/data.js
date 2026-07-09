/**
 * 数据 API 封装层
 * - Supabase 已配置时：从云数据库读取
 * - 未配置时：返回 Mock 数据，方便本地开发
 */
import { supabase } from './supabase.js'
import { withCache } from '../utils/cache.js'

// ========== 工具函数 ==========
// 格式化函数已统一到 src/utils/format.js（fmtScore/fmtPct/scoreColor 等）

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
// fund_scores 表实际列（核心视图）：代码/名称/分类/详情/评分
const FUND_SCORES_COLS = 'c,n,t0,t1,t1_tt,sg,daily_change,company,fund_manager,fund_scale,share_scale,manage_fee,custody_fee,sale_fee,found_date,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k_all,score_grade'
export function fetchFundScores(params = {}) {
  const key = 'fundScores:' + JSON.stringify(params)
  return withCache(key, 60000, () => fetchFundScoresImpl(params))
}

// 升序数组中 ≤ v 的元素个数（bisect_right），用于计算「严格大于 v」的数量
function bisectRight(arr, v) {
  let lo = 0, hi = arr.length
  while (lo < hi) {
    const mid = (lo + hi) >> 1
    if (arr[mid] <= v) lo = mid + 1
    else hi = mid
  }
  return lo
}

// 计算基金在「细分品类(t1_tt)」内的靠谱分排名
// 返回 { [code]: { cat, rank, total } }：rank 为该品类内按 k_all 降序的名次（1 起），total 为该品类基金总数
// 用于在组合成份基金后展示「债券型-混合二级 1|1480」这样的细分品类排名
// 优化：仅 2 次查询 —— ①取给定基金自身(1次) ②一次性拉取涉及品类的全量 k_all 在内存排序算排名(1次)，
//       彻底消除原来「每只基金 2 次 count」的 N+1 隐患（列表放大到 300 只时原需 600+ 次请求）
export async function getCategoryRankInfo(codes) {
  if (!supabase || !codes || codes.length === 0) return {}
  const unique = [...new Set(codes.filter(Boolean))]
  try {
    // ① 取给定基金自身的 (code, 品类, k_all)
    const { data, error } = await supabase
      .from('fund_scores')
      .select('c,t1_tt,k_all')
      .in('c', unique)
    if (error || !data) return {}
    const info = {}
    const cats = []
    const catSet = new Set()
    for (const f of data) {
      const k = f.k_all == null ? null : Number(f.k_all)
      info[f.c] = { cat: f.t1_tt || null, kAll: k }
      if (f.t1_tt && !catSet.has(f.t1_tt)) { catSet.add(f.t1_tt); cats.push(f.t1_tt) }
    }
    if (cats.length === 0) {
      // 所有基金都无细分品类，直接返回空排名
      const result = {}
      for (const f of data) result[f.c] = { cat: info[f.c].cat, rank: null, total: 0 }
      return result
    }
    // ② 一次性拉取这些品类下的全部 (t1_tt, k_all)
    const { data: all, error: e2 } = await supabase
      .from('fund_scores')
      .select('t1_tt,k_all')
      .in('t1_tt', cats)
    if (e2 || !all) return {}
    // 按品类聚合 k_all（升序），用于二分查找排名
    const byCat = {}
    for (const f of all) {
      const k = f.k_all == null ? null : Number(f.k_all)
      if (k == null) continue
      if (!byCat[f.t1_tt]) byCat[f.t1_tt] = []
      byCat[f.t1_tt].push(k)
    }
    const totals = {}
    for (const cat of Object.keys(byCat)) {
      byCat[cat].sort((a, b) => a - b)
      totals[cat] = byCat[cat].length
    }
    // ③ 计算每只基金排名：品类内 k_all 严格大于本基金的数量 + 1
    const result = {}
    for (const f of data) {
      const r = info[f.c]
      if (!r.cat || r.kAll == null) {
        result[f.c] = { cat: r.cat, rank: null, total: r.cat ? (totals[r.cat] || 0) : 0 }
        continue
      }
      const total = totals[r.cat] || 0
      const rank = total - bisectRight(byCat[r.cat] || [], r.kAll) + 1
      result[f.c] = { cat: r.cat, rank, total }
    }
    return result
  } catch (e) {
    console.error('[getCategoryRankInfo]', e)
    return {}
  }
}

async function fetchFundScoresImpl(params = {}) {
  const { t0, t1, t1In, search, kKey = 'k1', page = 1, pageSize = 100, sortAsc, classSource, etf, lof, dk, sg, dailyLimit } = params
  if (supabase) {
    let query = supabase.from('fund_scores').select(FUND_SCORES_COLS, { count: 'exact', head: false })
    if (classSource === 'tt') {
      // 天天分类：t1_tt 已填充（覆盖 ~95%），直接按 t1_tt 过滤，避免依赖 t0（聚源列，部分为空）
      if (t1) {
        query = query.eq('t1_tt', t1)
      } else if (t0 === '货币型') {
        // 货币型无 t1_tt，按聚源 t0 过滤
        query = query.eq('t0', '货币型')
      } else if (t1In && t1In.length) {
        query = query.in('t1_tt', t1In)
      }
      // 注：tt 源不再用 t0 列过滤
    } else {
      // 恒生聚源分类：t0/t1 列全覆盖
      if (t0) query = query.eq('t0', t0)
      if (t1) query = query.eq('t1', t1)
    }
    if (search) query = query.or(`n.ilike.%${search}%,c.ilike.%${search}%`)
    // 服务端下推：产品类型/状态筛选（避免前端只过滤首页导致计数与展示不一致）
    if (etf) {
      if (etf === '1') query = query.ilike('n', '%ETF%')
      else if (etf === '0') query = query.not('n', 'ilike', '%ETF%')
    }
    if (lof) {
      if (lof === '1') query = query.ilike('n', '%LOF%')
      else if (lof === '0') query = query.not('n', 'ilike', '%LOF%')
    }
    if (dk) {
      if (dk === '1') query = query.or('n.ilike.%定开%,n.ilike.%定期开放%')
      else if (dk === '0') query = query.not('n', 'ilike', '%定开%').not('n', 'ilike', '%定期开放%')
    }
    if (sg) {
      if (sg === '1') query = query.eq('sg', 1)
      else if (sg === '0') query = query.neq('sg', 1)
    }
    if (dailyLimit) {
      if (dailyLimit === '1') query = query.gte('daily_change', 20)
      else if (dailyLimit === '0') query = query.or('daily_change.lt.20,daily_change.is.null')
    }
    // 不再过滤 null 评分（否则债券型-混合二级等数据源未覆盖的分类会显示为空）
    // 改用 nullsFirst: false 让 null 排到最后
    const from = (page - 1) * pageSize
    const { data, count, error } = await query
      .order(kKey, { ascending: !!sortAsc, nullsFirst: false })
      .range(from, from + pageSize - 1)
    if (error) throw error
    return { data: data || [], count }
  }
  // Mock fallback
  return { data: MOCK_FUNDS, count: MOCK_FUNDS.length }
}

// ========== 基金元信息 ==========
export function fetchFundMeta() {
  return withCache('fundMeta', 60000, fetchFundMetaImpl)
}

async function fetchFundMetaImpl() {
  if (supabase) {
    const { data, error } = await supabase
      .from('fund_scores_meta')
      .select('nav_date,total_count,scored_count,tsq')
      .order('tsq', { ascending: false })
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
