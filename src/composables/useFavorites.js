import { ref } from 'vue'

const STORAGE_KEY = 'af_favorites'

// 模块级单例：所有页面共享同一份收藏数据
function load() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (e) {
    return []
  }
}

const favorites = ref(load())

function persist() {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favorites.value))
  } catch (e) {
    // 存储不可用时静默失败，不影响内存中的状态
  }
}

export function isFav(c) {
  return favorites.value.some(f => f.c === c)
}

export function addFav(fund) {
  if (!fund || !fund.c) return
  if (isFav(fund.c)) return
  favorites.value = [...favorites.value, { c: fund.c, name: fund.name || '', t0: fund.t0 || '' }]
  persist()
}

export function removeFav(c) {
  favorites.value = favorites.value.filter(f => f.c !== c)
  persist()
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
  favorites.value = []
  persist()
}

export function useFavorites() {
  return { favorites, isFav, addFav, removeFav, toggleFav, clear }
}
