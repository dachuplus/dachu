// 用户数据 API —— 注册/登录/组合信息持久化
import { supabase } from './supabase'

// ========== 用户 Profile ==========

/**
 * 创建/更新用户 profile（注册/登录时调用）
 */
export async function upsertUserProfile(user) {
  if (!user?.id) return null
  const { data, error } = await supabase
    .from('user_profiles')
    .upsert({
      user_id: user.id,
      email: user.email,
      last_login_at: new Date().toISOString(),
    }, { onConflict: 'user_id' })

  if (error) {
    console.error('[user-data] upsertUserProfile error:', error)
    return null
  }
  return data
}

/**
 * 增加登录次数
 */
export async function incrementLoginCount(userId) {
  const { error } = await supabase.rpc('increment_login_count', { uid: userId })
  if (error) {
    // RPC 可能不存在，用 update 兜底
    const { data: existing } = await supabase
      .from('user_profiles')
      .select('login_count')
      .eq('user_id', userId)
      .single()

    const count = (existing?.login_count || 0) + 1
    await supabase
      .from('user_profiles')
      .update({ login_count: count, last_login_at: new Date().toISOString() })
      .eq('user_id', userId)
  }
}

/**
 * 获取当前用户的 profile
 */
export async function getMyProfile() {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return null

  const { data } = await supabase
    .from('user_profiles')
    .select('*')
    .eq('user_id', user.id)
    .single()

  return data
}

// ========== 用户组合 ==========

/**
 * 获取当前用户的组合列表
 */
export async function getMyPortfolios() {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return []

  const { data, error } = await supabase
    .from('user_portfolios')
    .select('*')
    .eq('user_id', user.id)
    .order('updated_at', { ascending: false })

  if (error) {
    console.error('[user-data] getMyPortfolios error:', error)
    return []
  }
  return data || []
}

/**
 * 添加基金到默认组合
 */
export async function addFundToPortfolio(code, name) {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) {
    // 未登录：回退到 localStorage
    return addToLocalPortfolio(code, name)
  }

  // 先查是否已有组合
  let { data: portfolios } = await supabase
    .from('user_portfolios')
    .select('*')
    .eq('user_id', user.id)
    .order('created_at', { ascending: true })
    .limit(1)

  if (!portfolios || portfolios.length === 0) {
    // 没有组合：创建新组合
    const { error: insertErr } = await supabase
      .from('user_portfolios')
      .insert({
        user_id: user.id,
        name: '我的组合',
        portfolio_data: [{ code, name, weight: 0, addedAt: new Date().toISOString() }],
      })
    if (insertErr) {
      console.error('[user-data] create portfolio error:', insertErr)
      return { success: false, error: insertErr.message }
    }
    return { success: true, message: `已将 ${name} 添加到新组合` }
  }

  // 已有组合：追加
  const portfolio = portfolios[0]
  const items = portfolio.portfolio_data || []
  if (items.find(i => i.code === code)) {
    return { success: false, message: `${name} 已在组合中` }
  }
  items.push({ code, name, weight: 0, addedAt: new Date().toISOString() })

  const { error: updateErr } = await supabase
    .from('user_portfolios')
    .update({
      portfolio_data: items,
      updated_at: new Date().toISOString()
    })
    .eq('id', portfolio.id)

  if (updateErr) {
    console.error('[user-data] update portfolio error:', updateErr)
    return { success: false, error: updateErr.message }
  }
  return { success: true, message: `已将 ${name} 添加到组合` }
}

/**
 * 从组合中移除基金
 */
export async function removeFundFromPortfolio(portfolioId, code) {
  const { data: portfolio } = await supabase
    .from('user_portfolios')
    .select('portfolio_data')
    .eq('id', portfolioId)
    .single()

  if (!portfolio) return { success: false }

  const items = (portfolio.portfolio_data || []).filter(i => i.code !== code)
  await supabase
    .from('user_portfolios')
    .update({ portfolio_data: items, updated_at: new Date().toISOString() })
    .eq('id', portfolioId)

  return { success: true }
}

/**
 * 更新组合中基金的权重
 */
export async function updateFundWeight(portfolioId, code, weight) {
  const { data: portfolio } = await supabase
    .from('user_portfolios')
    .select('portfolio_data')
    .eq('id', portfolioId)
    .single()

  if (!portfolio) return { success: false }

  const items = (portfolio.portfolio_data || []).map(i =>
    i.code === code ? { ...i, weight } : i
  )
  await supabase
    .from('user_portfolios')
    .update({ portfolio_data: items, updated_at: new Date().toISOString() })
    .eq('id', portfolioId)

  return { success: true }
}

// ========== localStorage 兜底（未登录时使用） ==========

function addToLocalPortfolio(code, name) {
  try {
    const raw = localStorage.getItem('allfund_portfolio') || '[]'
    const portfolio = JSON.parse(raw)
    if (portfolio.find(p => p.code === code)) {
      return { success: false, message: `${name} 已在组合中` }
    }
    portfolio.push({ code, name, weight: 0, addedAt: new Date().toISOString() })
    localStorage.setItem('allfund_portfolio', JSON.stringify(portfolio))
    return { success: true, message: `已将 ${name} 添加到本地组合` }
  } catch (e) {
    return { success: false, error: e.message }
  }
}

/**
 * 创建完整组合（AI 组合"添加到自建组合"使用）
 */
export async function createPortfolio(name, portfolioData) {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return { success: false, error: '请先登录' }

  const { data, error } = await supabase
    .from('user_portfolios')
    .insert({
      user_id: user.id,
      name,
      portfolio_data: portfolioData,
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    })
    .select()
    .single()

  if (error) {
    console.error('[user-data] createPortfolio error:', error)
    return { success: false, error: error.message }
  }
  return { success: true, data }
}

/**
 * 删除组合
 */
export async function deletePortfolio(portfolioId) {
  const { data: { user } } = await supabase.auth.getUser()
  if (!user) return { success: false, error: '未登录' }

  const { error } = await supabase
    .from('user_portfolios')
    .delete()
    .eq('id', portfolioId)
    .eq('user_id', user.id)

  if (error) {
    console.error('[user-data] deletePortfolio error:', error)
    return { success: false, error: error.message }
  }
  return { success: true }
}

export function getLocalPortfolio() {
  try {
    const raw = localStorage.getItem('allfund_portfolio') || '[]'
    return JSON.parse(raw)
  } catch { return [] }
}
