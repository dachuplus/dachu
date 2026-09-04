/**
 * Supabase 客户端配置
 * 在 .env 文件中填写你的 Supabase Project URL 和 anon key
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

/**
 * 带超时的 fetch：给每个请求套 60s 上限，超时即 Abort，避免前端无限"处理中…"。
 *
 * 关键兼容点：supabase-js v2 内部会给 fetch 传入自己的 AbortSignal（用于其自身的取消/重试逻辑）。
 * 绝不能把它的 signal 直接透传给 fetch —— 会导致 supabase 内部响应解析异常（返回空 error {}、耗时翻倍）。
 * 正确做法：始终用我们自己的 controller.signal 调 fetch，并把 supabase 的 signal 关联过来
 * （它一 abort 我们也 abort），这样既保留超时保护，又不破坏 supabase 内部流程。
 *
 * 所有 Supabase 请求统一走同域 sb-proxy（/api/sb-proxy），由 EdgeOne 海外节点转发到 Supabase 新加坡。
 *
 * 唯独认证端点 (/auth/v1/*) 走【浏览器直连 supabase.co】，不走 sb-proxy：
 * EdgeOne 函数出口是数据中心 IP，Supabase 对 token 端点限流，走代理会返回 HTML 504，
 * supabase-js 解析失败 → 登录只显示泛化「登录失败」、掩盖真实的「账号或密码错误」。
 * 浏览器是住宅 IP，直连 supabase.co 不被限流，能拿到真实 JSON 错误。其余端点继续走 sb-proxy。
 */
const FETCH_TIMEOUT_MS = 60000
const baseFetch = (typeof fetch !== 'undefined' ? fetch : (...a) => Promise.reject(new Error('no fetch')))

/**
 * 同域代理改写：把对本项目 Supabase 域名（*.supabase.co）的 fetch 重写为同源
 * /api/sb-proxy?path=<原路径+查询>，由 EdgeOne 海外节点函数转发到 Supabase 新加坡，
 * 绕开浏览器跨境直连的不稳定。其余域名（如实时宏观数据 macro-data 函数、第三方源）不改写。
 *
 * 用 query 携带目标路径，避免多级路由匹配问题；path 值整体 encodeURIComponent。
 */
const SUPABASE_HOST = 'tqhtegazxykkqfcpejky.supabase.co'
const PROXY_BASE = 'https://dachu.me/api/sb-proxy'

function rewriteToProxy(input) {
  let str
  if (typeof input === 'string') str = input
  else if (input && typeof input.url === 'string') str = input.url
  else return input
  if (str.indexOf(SUPABASE_HOST) === -1) return input
  let u
  try {
    u = new URL(str)
  } catch (_) {
    return input
  }
  const targetPath = u.pathname + u.search
  return `${PROXY_BASE}?path=${encodeURIComponent(targetPath)}`
}

/**
 * 供直接 fetch Supabase 端点（如各 Edge Function）的前端代码复用，
 * 把 *.supabase.co URL 改写成同源 /api/sb-proxy?path=...。
 */
export const rewriteSupabaseUrl = rewriteToProxy

/**
 * 解析 fetch 入参为最终 URL 字符串（统一处理 string / Request）。
 */
function urlString(input) {
  if (typeof input === 'string') return input
  if (input && typeof input.url === 'string') return input.url
  return ''
}

function timeoutFetch(input, init = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  // 若 supabase 自带 signal，把它和我们的 controller 关联：它取消时我们也取消
  if (init.signal && typeof init.signal.addEventListener === 'function') {
    init.signal.addEventListener('abort', () => controller.abort())
  }
  const opts = { ...init, signal: controller.signal }
  // 认证端点 (/auth/v1/*) 走浏览器直连 supabase.co，绕过 sb-proxy：
  // 避免 EdgeOne 数据中心出口 IP 被 Supabase 限流导致 HTML 504、掩盖真实登录错误。
  const raw = urlString(input)
  if (raw && raw.indexOf('/auth/v1/') !== -1 && raw.indexOf(SUPABASE_HOST) !== -1) {
    return baseFetch(raw, opts).finally(() => clearTimeout(timer))
  }
  // 其余端点统一走同域 sb-proxy 单路。
  const rewritten = rewriteToProxy(input)
  return baseFetch(rewritten, opts).finally(() => clearTimeout(timer))
}

export const supabase = SUPABASE_URL && SUPABASE_ANON_KEY
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { fetch: timeoutFetch },
    })
  : null

export const isSupabaseReady = () => !!supabase
