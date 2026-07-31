/**
 * Supabase 客户端配置
 * 在 .env 文件中填写你的 Supabase Project URL 和 anon key
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

/**
 * 带超时的 fetch：Supabase 新加坡节点偶发延迟高（实测 auth 7~15s、REST 偶发超时），
 * 给每个请求套 45s 上限，超时即 Abort，避免前端无限"处理中…"。
 */
const FETCH_TIMEOUT_MS = 45000
const baseFetch = (typeof fetch !== 'undefined' ? fetch : (...a) => Promise.reject(new Error('no fetch')))
function timeoutFetch(input, init = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  const signal = init.signal || controller.signal
  return baseFetch(input, { ...init, signal }).finally(() => clearTimeout(timer))
}

export const supabase = SUPABASE_URL && SUPABASE_ANON_KEY
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { fetch: timeoutFetch },
    })
  : null

export const isSupabaseReady = () => !!supabase
