import { ref, watch } from 'vue'
import { useAuth } from './useAuth.js'

const LOCAL_KEY = 'af_favorites'

// 模块级单例：所有页面共享同一份收藏数据
// 登录用户：云端 user_favorites 表；未登录：localStorage 降级
const favorites = ref([])
let loadedFor = null // 已为哪个 user_email 加载（null = 本地游客态）

function loadLocal() {
  try {
    const raw = localStorage.getItem(LOCAL_KEY)
    favorites.value = raw ? (Array.isArray(JSON.parse(raw)) ? JSON.parse(raw) : []) : []
  } catch (e) {
    favorites.value = []
  }
  loadedFor = null
}

function saveLocal() {
  try {
    localStorage.setItem(LOCAL_KEY, JSON.stringify(favorites.value))
  } catch (e) {
    // 存储不可用时静默失败
  }
}

async function loadRemote(userEmail) {
  try {
    const { supabase } = await import('../api/supabase.js')
    const { data, error } = await supabase
      .from('user_favorites')
      .select('fund_code, fund_name, created_at')
      .eq('user_email', userEmail)
      .order('created_at', { ascending: false })
    if (error) throw error
    favorites.value = (data || []).map(r => ({ c: r.fund_code, name: r.fund_name || '', t0: '' }))
    loadedFor = userEmail
  } catch (e) {
    // 远端失败：若尚未加载过则回落本地，标记已尝试避免反复请求
    if (loadedFor === null) loadLocal()
    loadedFor = userEmail
  }
}

async function writeRemote(userEmail, op, payload) {
  try {
    const { supabase } = await import('../api/supabase.js')
    if (op === 'insert') {
      await supabase.from('user_favorites').upsert(
        { user_email: userEmail, fund_code: payload.c, fund_name: payload.name || '' },
        { onConflict: 'user_email,fund_code' }
      )
    } else if (op === 'delete') {
      await supabase.from('user_favorites')
        .delete()
        .eq('user_email', userEmail)
        .eq('fund_code', payload.c)
    }
  } catch (e) {
    // 远端失败不回滚内存态，下次进入可重新同步
  }
}

// 模块加载即建立登录状态同步（无需页面显式调用）
const { user, isLoggedIn } = useAuth()
watch(
  [isLoggedIn, () => user.value?.email],
  async ([logged, email]) => {
    if (logged && email) {
      if (loadedFor !== email) await loadRemote(email)
    } else if (loadedFor !== null) {
      favorites.value = []
      loadLocal()
    }
  },
  { immediate: true }
)

export function isFav(c) {
  return favorites.value.some(f => f.c === c)
}

export function addFav(fund) {
  if (!fund || !fund.c) return
  if (isFav(fund.c)) return
  const item = { c: fund.c, name: fund.name || fund.n || '', t0: fund.t0 || '' }
  favorites.value = [...favorites.value, item]
  const { user: u, isLoggedIn: lg } = useAuth()
  if (lg.value && u.value?.email) {
    writeRemote(u.value.email, 'insert', item)
  } else {
    saveLocal()
  }
}

export function removeFav(c) {
  if (!c) return
  favorites.value = favorites.value.filter(f => f.c !== c)
  const { user: u, isLoggedIn: lg } = useAuth()
  if (lg.value && u.value?.email) {
    writeRemote(u.value.email, 'delete', { c })
  } else {
    saveLocal()
  }
}

export function toggleFav(fund) {
  if (!fund || !fund.c) return
  if (isFav(fund.c)) {
    removeFav(fund.c)
  } else {
    addFav(fund)
  }
}

export function clear() {
  const list = favorites.value
  favorites.value = []
  const { user: u, isLoggedIn: lg } = useAuth()
  if (lg.value && u.value?.email) {
    list.forEach(f => writeRemote(u.value.email, 'delete', { c: f.c }))
  } else {
    saveLocal()
  }
}

export function useFavorites() {
  return { favorites, isFav, addFav, removeFav, toggleFav, clear }
}
