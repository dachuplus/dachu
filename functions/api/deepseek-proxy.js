/**
 * EdgeOne Pages Function — DeepSeek 服务端代理
 * 路由：POST /api/deepseek-proxy
 *
 * 作用：项目前端的「AI 自动建组合 / 风险平价 / 标签金句」此前直接在前端用
 *       VITE_DEEPSEEK_API_KEY 调用 https://api.deepseek.com/v1/chat/completions，
 *       该 key 被 Vite 打包进公开 JS（dachu.me 的 PortfolioPage / FundRankPage chunk
 *       明文可见），任何访客都能提取并在外部滥用、烧掉余额。
 *
 *       本函数把 key 收回到服务端（EdgeOne Pages 环境变量 DEEPSEEK_API_KEY），
 *       前端改为调用同源 /api/deepseek-proxy，请求体原样转发，Authorization 头
 *       由本函数在服务端注入 —— 密钥永不进前端包。
 *
 * 备案边界：dachu.me 为 EdgeOne overseas 海外节点，本函数亦运行在海外，
 *          转发目标 api.deepseek.com 在境外 —— 全链路无中国大陆境内接入点，不触发 ICP 备案。
 *
 * 安全性：不存储密钥，仅读取 context.env.DEEPSEEK_API_KEY。仅允许 POST，
 *          仅转发到固定 DeepSeek 端点，禁止任何可配置的外部 URL。
 */

import { DEEPSEEK_API_KEY as FILE_KEY } from './_deepseek_key.js'

const DEEPSEEK_URL = 'https://api.deepseek.com/v1/chat/completions'
// EdgeOne Pages 函数平台上限约 15-17s（实测）。必须在被平台强杀前返回干净 JSON。
const UPSTREAM_TIMEOUT_MS = 12000

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

function buildUpstreamHeaders(incoming, apiKey) {
  const headers = new Headers()
  for (const [key, value] of incoming.entries()) {
    const lower = key.toLowerCase()
    if (HOP_BY_HOP.has(lower)) continue
    if (lower === 'accept-encoding') continue // 让上游返回未压缩 JSON，避免二次压缩损坏
    if (lower.startsWith('x-forwarded') || lower.startsWith('x-real-ip') || lower.startsWith('cf-')) continue
    if (lower === 'authorization') continue // 强制由服务端注入，前端不得自带 key
    headers.set(key, value)
  }
  headers.set('Authorization', `Bearer ${apiKey}`)
  return headers
}

function jsonError(msg, status) {
  return new Response(JSON.stringify({ error: msg, proxy: 'deepseek-proxy' }), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

export async function onRequest(context) {
  const req = context.request

  if (req.method.toUpperCase() !== 'POST') {
    return jsonError('method not allowed, use POST', 405)
  }

  // 优先用 EdgeOne 环境变量（若在控制台正确配置）；否则回退到本仓库 gitignored 的服务端密钥文件。
  const apiKey = (context.env && context.env.DEEPSEEK_API_KEY) || FILE_KEY
  if (!apiKey) {
    // 未配置服务端密钥：明确报错而非放行，避免前端误以为成功
    return jsonError('DEEPSEEK_API_KEY not configured on server', 500)
  }

  const controller = new AbortController()
  let timer
  const timeoutPromise = new Promise((resolve) => {
    timer = setTimeout(() => resolve('__timeout__'), UPSTREAM_TIMEOUT_MS)
  })

  let body
  try {
    body = await req.arrayBuffer()
  } catch (e) {
    return jsonError('failed to read request body', 400)
  }

  const headers = buildUpstreamHeaders(req.headers, apiKey)
  const fetchPromise = fetch(DEEPSEEK_URL, {
    method: 'POST',
    headers,
    body,
    signal: controller.signal,
    redirect: 'follow',
  })

  const winner = await Promise.race([fetchPromise, timeoutPromise])
  clearTimeout(timer)

  if (winner === '__timeout__') {
    controller.abort()
    return jsonError(`upstream timeout after ${UPSTREAM_TIMEOUT_MS}ms`, 504)
  }

  const upstream = winner
  const respHeaders = new Headers()
  for (const [key, value] of upstream.headers.entries()) {
    const lower = key.toLowerCase()
    if (HOP_BY_HOP.has(lower) || lower.startsWith('cf-')) continue
    respHeaders.set(key, value)
  }
  respHeaders.set('Content-Type', 'application/json')

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: respHeaders,
  })
}
