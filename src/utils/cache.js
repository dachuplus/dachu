/**
 * 带 TTL 的内存请求缓存（单例）
 * 用于去重高频请求、降低 Supabase / 第三方 API 压力。
 * 同时合并「同一时刻的并发请求」（缓存的是 Promise，未完成的请求会被复用）。
 */
const store = new Map()

/**
 * @param {string} key 缓存键
 * @param {number} ttl 毫秒，默认 60000（60s）
 * @param {Function} fn 返回 Promise 的工厂函数
 * @returns {Promise}
 */
export function withCache(key, ttl = 60000, fn) {
  const hit = store.get(key)
  if (hit && Date.now() <= hit.exp) return hit.value
  const p = Promise.resolve().then(fn)
  store.set(key, { value: p, exp: Date.now() + ttl })
  // 请求失败时立即失效，下次调用可重试
  p.catch(() => store.delete(key))
  return p
}

// 仅供测试 / 手动清理使用
export function clearCache() {
  store.clear()
}
