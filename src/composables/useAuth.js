/**
 * useAuth.js — Supabase Auth 单例 + 功能权限
 *
 * 全局唯一 auth 状态，App.vue 初始化后所有组件共享同一状态。
 *
 * 权限模型：
 *  - 未登录：看不到任何内容（App.vue 登录墙拦截）
 *  - 管理员（ADMIN_EMAIL）：看到全部功能
 *  - 其他已登录用户：按 user_permissions.enabled_features 显示对应功能；
 *    若未开通任何功能，则显示「陌生人，无访问权限」
 *
 * 注册/登录由 LoginDialog.vue（wall 模式）统一处理，本模块提供状态读取与退出。
 */
import { ref, computed } from 'vue'
import { supabase } from '../api/supabase'
import { toast } from './useToast.js'
import { upsertUserProfile, getMyPortfolios } from '../api/user-data'

// 会话最长有效期：1 周（用户要求从默认 30 天缩短）
const SESSION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000
const LS_LOGIN_AT = 'allfund_auth_login_at'

// 数据中心（数据下载 / 用户权限管理）唯一授权管理员账户
export const ADMIN_EMAIL = '57502460@qq.com'

// 可授予用户的功能清单（数据中心「用户权限管理」勾选用）
export const FEATURES = [
  { key: 'fund-rank', label: '靠谱指数', desc: '靠谱指数评分、基金详情、基金对比' },
  { key: 'signal',    label: '指标信号', desc: '宏观信号、股债性价比、风格因子、行业估值' },
  { key: 'portfolio', label: '智能组合', desc: '自建组合、AI 组合、组合回测' },
]

// ---- 全局单例状态 ----
const user = ref(null)
const loading = ref(false)
const portfolios = ref([])
const profile = ref(null)
const showLoginDialog = ref(false)

// 功能权限状态（来自 user_permissions 表；管理员邮箱兜底全开）
const permissions = ref({ is_admin: false, enabled_features: [] })
const permissionsReady = ref(false)

// 账号是否被封禁（命中 blocked_users 表时为 true，App 显示封禁屏）
const blocked = ref(false)

// 权限申请是否被驳回（命中 permission_requests.status='rejected' 时为 true，App 显示驳回屏）
const rejected = ref(false)

// 是否已初始化（App.vue 调用 init 后为 true）
let _initDone = false

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)

  /** 是否为管理员（硬编码管理员邮箱 或 数据库中标记为管理员） */
  const isAdmin = computed(() =>
    !!user.value && (user.value.email === ADMIN_EMAIL || permissions.value.is_admin)
  )

  /** 是否为数据中心授权账户（= 管理员，仅其可访问数据中心与权限管理） */
  const isOwner = computed(() => user.value?.email === ADMIN_EMAIL)

  /** 已开通的功能 key 列表 */
  const enabledFeatures = computed(() => permissions.value.enabled_features || [])

  /** 是否已开通任意功能（管理员恒为 true） */
  const hasAnyAccess = computed(() => isAdmin.value || (permissions.value.enabled_features || []).length > 0)

  /** 陌生人：已登录但既不是管理员、也未开通任何功能 → 显示「无访问权限」 */
  const isStranger = computed(() =>
    !!user.value && !isAdmin.value && (permissions.value.enabled_features || []).length === 0
  )

  /** 当前用户是否拥有某功能权限 */
  function hasFeature(key) {
    if (!user.value) return false
    if (user.value.email === ADMIN_EMAIL) return true
    if (permissions.value.is_admin) return true
    const f = permissions.value.enabled_features || []
    return f.includes('all') || f.includes(key)
  }

  /** 初始化：App.vue 挂载时调用，恢复 session 并监听状态变更 */
  async function init() {
    if (_initDone) return
    _initDone = true
    loading.value = true
    try {
      const { data } = await supabase.auth.getSession()
      const u = data?.session?.user || null
      user.value = u
      if (u) {
        if (checkSessionExpiry()) {
          // 已超 1 周，内部已强制登出
        } else {
          await loadPermissions(u.email)
          await refreshUserData()
          if (await checkBlocked()) {
            // 命中封禁名单：强制登出，保持 blocked=true 以展示封禁屏
            await signOut()
            blocked.value = true
          }
        }
      } else {
        permissionsReady.value = true
      }
    } catch (e) {
      console.error('[auth] init session error:', e)
      permissionsReady.value = true
    } finally {
      loading.value = false
    }
    // 监听全局状态变更
    supabase.auth.onAuthStateChange(async (event, session) => {
      const newUser = session?.user || null
      // 真正的登录（非 token 刷新）才重置 1 周会话计时
      if (event === 'SIGNED_IN') {
        localStorage.setItem(LS_LOGIN_AT, String(Date.now()))
      }
      user.value = newUser
      if (newUser) {
        await loadPermissions(newUser.email)
        await refreshUserData()
        if (await checkBlocked()) {
          await signOut()
          blocked.value = true
        }
      } else {
        localStorage.removeItem(LS_LOGIN_AT)
        portfolios.value = []
        profile.value = null
        permissions.value = { is_admin: false, enabled_features: [] }
        permissionsReady.value = true
        // 注意：blocked 不在此重置，封禁屏在登出后仍需保留，直至整页刷新
      }
    })
  }

  /** 加载当前用户的功能权限（管理员邮箱兜底全开，DB 不存在时也不报错） */
  async function loadPermissions(email) {
    permissionsReady.value = false
    rejected.value = false
    if (!email) {
      permissions.value = { is_admin: false, enabled_features: [] }
      permissionsReady.value = true
      return
    }
    const isAdminEmail = email === ADMIN_EMAIL
    try {
      const { data, error } = await supabase
        .from('user_permissions')
        .select('is_admin, enabled_features')
        .eq('user_email', email)
        .maybeSingle()
      if (data) {
        permissions.value = {
          is_admin: !!data.is_admin,
          enabled_features: Array.isArray(data.enabled_features) ? data.enabled_features : [],
        }
      } else {
        // 无记录：管理员兜底全开，普通用户无权限
        permissions.value = { is_admin: isAdminEmail, enabled_features: isAdminEmail ? ['all'] : [] }
      }
    } catch (e) {
      console.error('[auth] loadPermissions error:', e)
      permissions.value = { is_admin: isAdminEmail, enabled_features: isAdminEmail ? ['all'] : [] }
    } finally {
      permissionsReady.value = true
    }
    // 注意：rejected 检查放在 finally 之后，即便权限加载失败也独立判断
    await checkRejected(email)
  }

  /** 检查当前登录用户的权限申请是否被驳回（读取 permission_requests，命中 status='rejected' 则置 rejected=true） */
  async function checkRejected(email) {
    if (!email) { rejected.value = false; return }
    try {
      const { data, error } = await supabase
        .from('permission_requests')
        .select('user_email')
        .eq('user_email', email)
        .eq('status', 'rejected')
        .maybeSingle()
      const isRejected = !!data && !error
      rejected.value = isRejected
    } catch (e) {
      rejected.value = false
    }
  }

  /** 保存某用户的权限（仅管理员调用，依赖 RLS 策略：`auth.email() = '57502460@qq.com'`） */
  async function savePermissions(email, payload) {
    if (!supabase) throw new Error('未连接数据库')
    const { error } = await supabase
      .from('user_permissions')
      .upsert({
        user_email: email,
        is_admin: !!payload.is_admin,
        enabled_features: payload.enabled_features || [],
        granted_by: user.value?.email || null,
        updated_at: new Date().toISOString(),
      }, { onConflict: 'user_email' })
    if (error) throw error
  }

  /** 删除某用户的权限记录（仅管理员调用） */
  async function deletePermissions(email) {
    if (!supabase) throw new Error('未连接数据库')
    const { error } = await supabase
      .from('user_permissions')
      .delete()
      .eq('user_email', email)
    if (error) throw error
  }

  /** 检查当前登录用户是否被封禁（读取 blocked_users，命中则置 blocked=true） */
  async function checkBlocked() {
    const u = user.value
    if (!u || !u.email) { blocked.value = false; return false }
    try {
      const { data, error } = await supabase
        .from('blocked_users')
        .select('user_email')
        .eq('user_email', u.email)
        .maybeSingle()
      const isBlocked = !!data && !error
      blocked.value = isBlocked
      return isBlocked
    } catch (e) {
      blocked.value = false
      return false
    }
  }

  /** 封禁某用户（仅管理员调用，依赖 RLS：`auth.email() = '57502460@qq.com'`） */
  async function blockUser(email) {
    if (!supabase) throw new Error('未连接数据库')
    const { error } = await supabase
      .from('blocked_users')
      .upsert({
        user_email: email,
        blocked_by: user.value?.email || null,
        blocked_at: new Date().toISOString(),
      }, { onConflict: 'user_email' })
    if (error) throw error
  }

  /** 解除封禁（仅管理员调用） */
  async function unblockUser(email) {
    if (!supabase) throw new Error('未连接数据库')
    const { error } = await supabase
      .from('blocked_users')
      .delete()
      .eq('user_email', email)
    if (error) throw error
  }

  /** 刷新用户数据（组合 + profile），可由外部触发 */
  async function refreshUserData() {
    const u = user.value
    if (!u) return
    try {
      await upsertUserProfile(u)
      portfolios.value = await getMyPortfolios()
    } catch (e) {
      console.error('[auth] refreshUserData error:', e)
    }
  }

  /** 显示名：优先邮箱，其次手机号，兼容两种注册方式 */
  const displayName = computed(() => {
    const u = user.value
    if (!u) return ''
    return u.email || u.phone || '用户'
  })
  const displayInitial = computed(() => {
    const n = displayName.value
    return n ? n[0].toUpperCase() : '?'
  })

  /** 记录本次登录起始时间（用于 1 周会话过期强制登出） */
  function markLogin() {
    localStorage.setItem(LS_LOGIN_AT, String(Date.now()))
  }

  /** 检查会话是否已超过 1 周，超过则强制登出。返回 true 表示已过期登出 */
  function checkSessionExpiry() {
    const at = Number(localStorage.getItem(LS_LOGIN_AT) || '0')
    if (at && Date.now() - at > SESSION_MAX_AGE_MS) {
      signOut()
      toast('登录已过期（超过 7 天），请重新登录', 'info')
      return true
    }
    return false
  }

  /** 退出登录 */
  async function signOut() {
    try {
      await supabase.auth.signOut()
    } catch (e) {
      console.error('[auth] signOut error:', e)
    }
    user.value = null
    portfolios.value = []
    profile.value = null
    permissions.value = { is_admin: false, enabled_features: [] }
    permissionsReady.value = true
    rejected.value = false
  }

  /** 打开登录弹窗（全局触发） */
  function showLogin() { showLoginDialog.value = true }
  function hideLogin() { showLoginDialog.value = false }

  return {
    user, loading, isLoggedIn, isAdmin, isOwner, isStranger, hasAnyAccess, enabledFeatures, permissionsReady, blocked, rejected,
    displayName, displayInitial, portfolios, profile,
    init, signOut, refreshUserData, loadPermissions, savePermissions, deletePermissions, hasFeature,
    checkBlocked, blockUser, unblockUser,
    showLoginDialog, showLogin, hideLogin, markLogin,
  }
}
