/**
 * api/user-data.js — 用户组合数据持久化（localStorage）
 *
 * 无 Supabase Auth 依赖，用户通过手机号标识。
 * 组合数据存储在 localStorage 中。
 */

const STORAGE_PREFIX = 'allfund_portfolios_'

/** 获取当前用户的手机号（从 useAuth 获取或缓存） */
function getPhone() {
  try {
    const auth = localStorage.getItem('allfund_auth')
    if (auth) return JSON.parse(auth).phone || 'anonymous'
  } catch {}
  return 'anonymous'
}

/** 获取用户的 key */
function getKey() {
  return STORAGE_PREFIX + getPhone()
}

/** 获取我的组合列表 */
export async function getMyPortfolios() {
  const key = getKey()
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : []
  } catch {
    return []
  }
}

/** 保存组合 */
export async function savePortfolio(portfolio) {
  const portfolios = await getMyPortfolios()
  const idx = portfolios.findIndex(p => p.id === portfolio.id)
  if (idx >= 0) {
    portfolios[idx] = { ...portfolios[idx], ...portfolio }
  } else {
    portfolios.push({ id: Date.now().toString(36), funds: [], ...portfolio })
  }
  localStorage.setItem(getKey(), JSON.stringify(portfolios))
  return portfolios
}

/** 更新组合 */
export async function updatePortfolio(portfolioId, updates) {
  const portfolios = await getMyPortfolios()
  const idx = portfolios.findIndex(p => p.id === portfolioId)
  if (idx >= 0) {
    portfolios[idx] = { ...portfolios[idx], ...updates }
    localStorage.setItem(getKey(), JSON.stringify(portfolios))
  }
  return portfolios
}

/** 删除组合 */
export async function deletePortfolio(portfolioId) {
  const portfolios = (await getMyPortfolios()).filter(p => p.id !== portfolioId)
  localStorage.setItem(getKey(), JSON.stringify(portfolios))
  return portfolios
}

/** 向组合中添加基金 */
export async function addFundToPortfolio(portfolioId, fund) {
  const portfolios = await getMyPortfolios()
  const portfolio = portfolios.find(p => p.id === portfolioId)
  if (portfolio) {
    portfolio.funds = portfolio.funds || []
    if (!portfolio.funds.some(f => f.c === fund.c)) {
      portfolio.funds.push(fund)
    }
    localStorage.setItem(getKey(), JSON.stringify(portfolios))
  }
  return portfolios
}
