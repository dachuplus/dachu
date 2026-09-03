/**
 * Supabase 客户端配置
 * 在 .env 文件中填写你的 Supabase Project URL 和 anon key
 */
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = import.meta.env.VITE_SUPABASE_URL || ''
const SUPABASE_ANON_KEY = import.meta.env.VITE_SUPABASE_ANON_KEY || ''

/**
 * 带超时的 fetch：Supabase 新加坡节点偶发延迟高（实测 auth 冷启动 7~20s、REST 偶发超时），
 * 给每个请求套 45s 上限，超时即 Abort，避免前端无限"处理中…"。
 *
 * 关键兼容点：supabase-js v2 内部会给 fetch 传入自己的 AbortSignal（用于其自身的取消/重试逻辑）。
 * 绝不能把它的 signal 直接透传给 fetch —— 会导致 supabase 内部响应解析异常（返回空 error {}、耗时翻倍）。
 * 正确做法：始终用我们自己的 controller.signal 调 fetch，并把 supabase 的 signal 关联过来
 * （它一 abort 我们也 abort），这样既保留超时保护，又不破坏 supabase 内部流程。
 */
const FETCH_TIMEOUT_MS = 45000
const baseFetch = (typeof fetch !== 'undefined' ? fetch : (...a) => Promise.reject(new Error('no fetch')))

/**
 * 同域代理改写：把对本项目 Supabase 域名（*.supabase.co）的 fetch 重写为同源
 * /api/sb-proxy?path=<原路径+查询>，由 EdgeOne 海外节点函数转发到 Supabase 新加坡，
 * 绕开浏览器跨境直连的不稳定。其余域名（如实时宏观数据 macro-data 函数、第三方源）不改写。
 *
 * 用 query 携带目标路径，避免多级路由匹配问题；path 值整体 encodeURIComponent。
 *
 * **例外 (2026-09-03)**：/auth/v1/* 认证端点不走 sb-proxy，改走浏览器直连 Supabase。
 * 原因: EdgeOne overseas 节点出口 (美西洛杉矶) → Supabase 新加坡 的横跨太平洋
 * 骨干网当前频繁超时 (HTTP 504 @ ≥15s)，认证请求 100% 失败。认证体积最小、延迟最敏感，
 * 让浏览器从国内直连 Supabase（跳过 EdgeOne 中转），反而更稳更快。
 * 其他端点 (PostgREST / storage / edge function) 仍走 sb-proxy，沿用优化链路。
 */
const SUPABASE_HOST = 'tqhtegazxykkqfcpejky.supabase.co'
const PROXY_BASE = 'https://dachu.me/api/sb-proxy'
// 开关：true=auth 端点不绕道 sb-proxy，让浏览器从国内直接 POST 到 Supabase
const AUTH_DIRECT_BYPASS = true

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
  // Auth 端点直连（绕开当前已断的 EdgeOne overseas → Supabase 链路）
  if (AUTH_DIRECT_BYPASS && u.pathname.startsWith('/auth/v1/')) return input
  const targetPath = u.pathname + u.search
  return `${PROXY_BASE}?path=${encodeURIComponent(targetPath)}`
}

/**
 * 供直接 fetch Supabase 端点（如各 Edge Function）的前端代码复用，
 * 把 *.supabase.co URL 改写成同源 /api/sb-proxy?path=...，统一走优化链路。
 *
 * 注意：/auth/v1/* 由 rewriteToProxy 内部直接放行（同源直连 Supabase），调用方无需特殊处理。
 */
export const rewriteSupabaseUrl = rewriteToProxy

function timeoutFetch(input, init = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), FETCH_TIMEOUT_MS)
  // 若 supabase 自带 signal，把它和我们的 controller 关联：它取消时我们也取消
  if (init.signal && typeof init.signal.addEventListener === 'function') {
    init.signal.addEventListener('abort', () => controller.abort())
  }
  // 始终用我们自己的 signal 调底层 fetch（绝不用 supabase 的 signal 直接透传）
  const rewritten = rewriteToProxy(input)
  return baseFetch(rewritten, { ...init, signal: controller.signal }).finally(() => clearTimeout(timer))
}

export const supabase = SUPABASE_URL && SUPABASE_ANON_KEY
  ? createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { fetch: timeoutFetch },
    })
  : null

export const isSupabaseReady = () => !!supabase
