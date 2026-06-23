/**
 * useAuth.js — Supabase Auth 单例
 *
 * 全局唯一 auth 状态，App.vue 初始化后所有组件共享同一状态。
 * 注册/登录由 LoginDialog.vue 统一处理，本模块提供状态读取和退出。
 */
import { ref, computed } from 'vue'
import { supabase } from '../api/supabase'
import { upsertUserProfile, getMyPortfolios } from '../api/user-data'

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
      if (u) await refreshUserData()
    } catch (e) {
      console.error('[auth] init session error:', e)
    } finally {
      loading.value = false
    }
    // 监听全局状态变更
    supabase.auth.onAuthStateChange(async (_event, session) => {
      const newUser = session?.user || null
      const wasLoggedIn = !!user.value
      user.value = newUser
      if (newUser) {
        await refreshUserData()
      } else {
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

  return { user, loading, isLoggedIn, portfolios, profile, init, signOut, refreshUserData, showLoginDialog, showLogin, hideLogin }
}
