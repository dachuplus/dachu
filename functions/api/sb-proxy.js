/**
 * EdgeOne Pages Function — Supabase 同域代理
 * 路由：/api/sb-proxy?path=<目标路径及查询参数>
 *
 * 作用：前端把对 *.supabase.co 的请求改写为同源 /api/sb-proxy?path=...，
 *       由本函数转发到 Supabase 新加坡节点（经 EdgeOne 优化骨干网），
 *       绕开浏览器跨境直连的不稳定，提升登录 / 查库速度。
 *
 * 备案边界：dachu.me 为 EdgeOne overseas 海外节点，本函数亦运行在海外，
 *          转发目标 Supabase 新加坡同样在境外 —— 全链路无中国大陆境内接入点，不触发 ICP 备案。
 *
 * 安全性：不存储任何密钥。前端请求自带的 apikey / Authorization 头原样透传。
 *        仅允许转发到本项目固定 Supabase 域名的相对路径，禁止绝对 URL / 跨域转发。
 */

const SUPABASE_BASE = 'https://tqhtegazxykkqfcpejky.supabase.co'
// EdgeOne Pages 函数平台上限约 15-17s（实测）。我们必须在被平台强杀前返回自己的 502 JSON，
// 否则 supabase-js 拿到 HTML 无法解析 → error.message 空 → UI 看不到真实错误。
// 因此用 Promise.race 形式：超时立即拒绝、不等底层 fetch 收尾；并随即 abort 底层 fetch 以释放资源。
// 同时不允许任何重试 —— 一次慢就是真慢，重试只会把总耗时推到 30s+，必触发平台强杀。
const UPSTREAM_TIMEOUT_MS = 8000
const RETRY_ON_NETWORK_ERROR = 0

// 不应转发给上游的逐跳（hop-by-hop）及代理相关头
const HOP_BY_HOP = new Set([
  'host',
  'connection',
  'keep-alive',
  'transfer-encoding',
  'upgrade',
  'proxy-authorization',
  'proxy-connection',
  'content-length', // 交给 fetch 按实际 body 重新计算
  'te',
  'trailer',
])

function buildUpstreamHeaders(incoming) {
  const headers = new Headers()
  for (const [key, value] of incoming.entries()) {
    const lower = key.toLowerCase()
    if (HOP_BY_HOP.has(lower)) continue
    // 去掉 accept-encoding：让上游返回未压缩 JSON，避免经 EdgeOne 二次压缩导致正文损坏
    if (lower === 'accept-encoding') continue
    // 去掉浏览器 / 边缘网关注入的转发类伪头，避免干扰上游
    if (lower.startsWith('x-forwarded') || lower.startsWith('x-real-ip') || lower.startsWith('cf-')) continue
    headers.set(key, value)
  }
  return headers
}

async function proxyOnce(targetUrl, method, headers, body) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), UPSTREAM_TIMEOUT_MS)
  try {
    return await fetch(targetUrl, {
      method,
      headers,
      body: method === 'GET' || method === 'HEAD' ? undefined : body,
      signal: controller.signal,
      redirect: 'follow',
    })
  } finally {
    clearTimeout(timer)
  }
}

function buildResponse(upstream) {
  // 过滤响应中的 hop-by-hop 头，避免下游浏览器误用
  const respHeaders = new Headers()
  for (const [key, value] of upstream.headers.entries()) {
    const lower = key.toLowerCase()
    if (HOP_BY_HOP.has(lower)) continue
    if (lower.startsWith('cf-')) continue
    respHeaders.set(key, value)
  }
  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  })
}

function jsonError(msg, status) {
  return new Response(JSON.stringify({ error: msg, proxy: 'sb-proxy' }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export async function onRequest(context) {
  const req = context.request
  const url = new URL(req.url)
  const targetPath = url.searchParams.get('path')

  if (!targetPath) {
    return jsonError('missing path query param', 400)
  }

  // 防目录穿越 / 越权：仅允许转发到本项目 Supabase 的相对路径
  if (
    targetPath.startsWith('http://') ||
    targetPath.startsWith('https://') ||
    targetPath.startsWith('//') ||
    targetPath.startsWith('../')
  ) {
    return jsonError('absolute or relative traversal url not allowed', 400)
  }

  const targetUrl = SUPABASE_BASE + (targetPath.startsWith('/') ? targetPath : '/' + targetPath)
  const method = req.method.toUpperCase()
  const headers = buildUpstreamHeaders(req.headers)

  // 读取 body（仅一次），重试时复用同一份 ArrayBuffer
  let body = undefined
  if (method !== 'GET' && method !== 'HEAD') {
    body = await req.arrayBuffer()
  }

  let lastErr = null
  for (let attempt = 0; attempt <= RETRY_ON_NETWORK_ERROR; attempt++) {
    try {
      const upstream = await proxyOnce(targetUrl, method, headers, body)
      return buildResponse(upstream)
    } catch (err) {
      lastErr = err
      // 仅在网络层错误（超时 / 连接失败）时重试；4xx/5xx 不会进入这里
      if (attempt < RETRY_ON_NETWORK_ERROR) {
        await new Promise((r) => setTimeout(r, 300))
        continue
      }
    }
  }

  const msg =
    lastErr && lastErr.name === 'AbortError'
      ? `upstream timeout after ${UPSTREAM_TIMEOUT_MS}ms`
      : (lastErr && lastErr.message) || 'upstream fetch failed'
  return jsonError(msg, 502)
}
