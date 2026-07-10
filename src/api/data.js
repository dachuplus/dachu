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
const FUND_SCORES_COLS = 'c,n,t0,t1,t1_tt,sg,daily_change,company,fund_manager,fund_scale,share_scale,manage_fee,custody_fee,sale_fee,found_date,k0w,k1m,k3m,k6m,k1,k2,k3,k5,k_all,score_grade,r1y,r2y,r3y,r5y'
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

// 按指定评分列（默认 k1=1年评分）在「细分品类(t1_tt)」内排名
// 返回 { [code]: { cat, score, rank, total } }：
//   - cat: 细分品类名（t1_tt）
//   - score: 该基金在 scoreCol 上的评分（如 k1）
//   - rank: 该品类内按 scoreCol 降序的名次（1 起），total 为该品类基金总数
// 用于在组合成份基金后展示「分类 + 1年评分 + 排名 153|1480」
// 允许作为 scoreCol 的列名白名单（避免拼接进查询字符串时产生 SQL 注入）
const SCORE_COLS = new Set(['k0w', 'k1m', 'k3m', 'k6m', 'k1', 'k2', 'k3', 'k5', 'k_all'])
// 品类总数缓存：同一组合里多只基金常属同一品类，避免重复 COUNT
const _catTotalCache = new Map()

export async function getCategoryRankInfoByScore(codes, scoreCol = 'k1') {
  if (!supabase || !codes || codes.length === 0) return {}
  if (!SCORE_COLS.has(scoreCol)) {
    console.error('[getCategoryRankInfoByScore] 非法 scoreCol:', scoreCol)
    return {}
  }
  const unique = [...new Set(codes.filter(Boolean))]
  try {
    // ① 批量取所有基金的 (code, 细分品类 t1_tt, 评分) —— 1 次查询搞定全部基金
    const { data, error } = await supabase
      .from('fund_scores')
      .select(`c,t1_tt,${scoreCol}`)
      .in('c', unique)
    if (error || !data) return {}
    const info = {}
    const cats = []
    const catSet = new Set()
    for (const f of data) {
      const k = f[scoreCol] == null ? null : Number(f[scoreCol])
      info[f.c] = { cat: f.t1_tt || null, score: k }
      if (f.t1_tt && !catSet.has(f.t1_tt)) { catSet.add(f.t1_tt); cats.push(f.t1_tt) }
    }
    if (cats.length === 0) {
      const result = {}
      for (const f of data) result[f.c] = { cat: info[f.c].cat, score: info[f.c].score, rank: null, total: 0 }
      return result
    }
    // ② 批量取这些品类下的全部 (t1_tt, 评分) —— 分页拉全量后内存排序算排名（避免 1000 行上限截断导致排名错）
    const all = []
    let from = 0
    const PAGE = 1000
    while (true) {
      const { data: page, error: e2 } = await supabase
        .from('fund_scores')
        .select(`t1_tt,${scoreCol}`)
        .in('t1_tt', cats)
        .range(from, from + PAGE - 1)
      if (e2) { console.error('[getCategoryRankInfoByScore] cats query', e2); return {} }
      if (!page || page.length === 0) break
      all.push(...page)
      if (page.length < PAGE) break
      from += PAGE
    }
    const byCat = {}
    for (const f of all) {
      const k = f[scoreCol] == null ? null : Number(f[scoreCol])
      if (k == null) continue
      if (!byCat[f.t1_tt]) byCat[f.t1_tt] = []
      byCat[f.t1_tt].push(k)
    }
    const totals = {}
    for (const cat of Object.keys(byCat)) {
      byCat[cat].sort((a, b) => a - b) // 升序，配合 bisectRight 计算降序名次
      totals[cat] = byCat[cat].length
    }
    // ③ 计算排名：品类内 score 严格大于本基金的只数 + 1（降序名次），纯内存计算
    const result = {}
    for (const f of data) {
      const r = info[f.c]
      if (!r.cat || r.score == null) {
        result[f.c] = { cat: r.cat, score: r.score, rank: null, total: r.cat ? (totals[r.cat] || 0) : 0 }
        continue
      }
      const total = totals[r.cat] || 0
      const rank = total - bisectRight(byCat[r.cat] || [], r.score) + 1
      result[f.c] = { cat: r.cat, score: r.score, rank, total }
    }
    return result
  } catch (e) {
    console.error('[getCategoryRankInfoByScore]', e)
    return {}
  }
}

async function fetchFundScoresImpl(params = {}) {
  const { t0, t1, search, kKey = 'k1', page = 1, pageSize = 100, sortAsc, etf, lof, dk, sg, dailyLimit, scaleMin, scaleMax } = params
  if (supabase) {
    let query = supabase.from('fund_scores').select(FUND_SCORES_COLS, { count: 'exact', head: false })
    // 分类筛选：直接采用 fund_scores 的「一级分类 t0」与「二级分类 t1_tt」
    // （从总表服务端过滤，而非客户端对前 100 条再筛）
    if (t1) {
      // 二级分类：按天天分类 t1_tt 精确过滤
      query = query.eq('t1_tt', t1)
    } else if (t0) {
      // 一级分类：按聚源 t0 过滤（货币型 t1_tt 为 NULL，也走此分支）
      query = query.eq('t0', t0)
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
    // 基金规模区间（亿元）：服务端下推，避免前端只过滤首页
    if (scaleMin != null) query = query.gte('fund_scale', scaleMin)
    if (scaleMax != null) query = query.lte('fund_scale', scaleMax)
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

// ========== 基金分类（动态，来自 fund_scores 的 t0/t1_tt）==========
// 调用 Supabase RPC get_fund_categories()，返回：
//   { t0: [{t0, cnt}], t1: [{t0, t1_tt, cnt}] }
// 一级分类用 t0，二级分类用 t1_tt（货币型 t1_tt 为 NULL，前端单独处理）
export function fetchFundCategories() {
  return withCache('fundCategories', 86400000, fetchFundCategoriesImpl)
}

async function fetchFundCategoriesImpl() {
  if (supabase) {
    const { data, error } = await supabase.rpc('get_fund_categories')
    if (error) throw error
    return data
  }
  return { t0: [], t1: [] }
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
