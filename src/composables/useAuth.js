/**
 * useAuth.js — Supabase Auth 单例
 *
 * 全局唯一 auth 状态，App.vue 初始化后所有组件共享同一状态。
 * 注册/登录由 LoginDialog.vue 统一处理，本模块提供状态读取和退出。
 */
import { ref, computed } from 'vue'
import { supabase } from '../api/supabase'
import { toast } from './useToast.js'
import { upsertUserProfile, getMyPortfolios } from '../api/user-data'

// 会话最长有效期：1 周（用户要求从默认 30 天缩短）
const SESSION_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000
const LS_LOGIN_AT = 'allfund_auth_login_at'

// ---- 全局单例状态 ----
const user = ref(null)
const loading = ref(false)
const portfolios = ref([])
const profile = ref(null)
const showLoginDialog = ref(false)

// 是否已初始化（App.vue 调用 init 后为 true）
let _initDone = false

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)

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
          await refreshUserData()
        }
      }
    } catch (e) {
      console.error('[auth] init session error:', e)
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
        await refreshUserData()
      } else {
        localStorage.removeItem(LS_LOGIN_AT)
        portfolios.value = []
        profile.value = null
      }
    })
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
  }

  /** 打开登录弹窗（全局触发） */
  function showLogin() { showLoginDialog.value = true }
  function hideLogin() { showLoginDialog.value = false }

  return { user, loading, isLoggedIn, displayName, displayInitial, portfolios, profile, init, signOut, refreshUserData, showLoginDialog, showLogin, hideLogin, markLogin }
}
