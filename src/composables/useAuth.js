/**
 * useAuth.js — Supabase Auth 组合式函数
 */

import { ref, computed, onMounted } from 'vue'
import { supabase } from '../api/supabase'

const user = ref(null)
const loading = ref(true)
const authError = ref('')

export function useAuth() {
  const isLoggedIn = computed(() => !!user.value)

  onMounted(async () => {
    try {
      const { data } = await supabase.auth.getSession()
      user.value = data?.session?.user || null
    } catch (e) {
      console.error('Auth session check failed', e)
    } finally {
      loading.value = false
    }
    // 监听状态变化
    supabase.auth.onAuthStateChange((_event, session) => {
      user.value = session?.user || null
    })
  })

  async function signUp(email, password) {
    authError.value = ''
    const { data, error } = await supabase.auth.signUp({ email, password })
    if (error) {
      authError.value = error.message
      return null
    }
    return data
  }

  async function signIn(email, password) {
    authError.value = ''
    const { data, error } = await supabase.auth.signInWithPassword({ email, password })
    if (error) {
      authError.value = error.message
      return null
    }
    return data
  }

  async function signOut() {
    authError.value = ''
    const { error } = await supabase.auth.signOut()
    if (error) authError.value = error.message
    user.value = null
  }

  return {
    user, loading, authError, isLoggedIn,
    signUp, signIn, signOut
  }
}
