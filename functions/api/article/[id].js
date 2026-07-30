/**
 * EdgeOne Pages Function — 文章边缘缓存代理
 * 路由：/api/article/:id  →  functions/api/article/[id].js
 *
 * 作用：读者阅读「已发布」文章时，优先从 EdgeOne 边缘节点就近返回，
 *       避免浏览器跨境直连 Supabase（新加坡），显著提速首屏。
 * 缓存：caches.default（原生 Cache API，零控制台配置、无 1MB 限制），
 *       缓存 TTL = s-maxage=600s。
 * 安全：使用 anon key 读取，RLS 保证 anon 只能读到 published 文章；
 *       草稿/未发布文章上游返回空 → 本函数返 404，前端回退 Supabase（作者视图）。
 */

const SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
// anon key 本就是公开密钥（前端 bundle 内含），仅受 RLS 保护，可安全硬编码于边缘函数
const ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
const CACHE_TTL = 600 // 秒

export async function onRequestGet(context) {
  const { params, waitUntil } = context
  const id = params && params.id

  // 校验 id 为纯数字
  if (!id || !/^\d+$/.test(String(id))) {
    return new Response(JSON.stringify({ error: 'not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }

  // 用真实请求 URL 作为缓存键，便于 EdgeOne CDN 层也按 URL 缓存
  const cacheKey = new Request(context.request.url)
  const cache = caches.default

  // 1. 命中边缘缓存（缓存过期 caches 会抛 504，需 try/catch 兜底）
  try {
    const cached = await cache.match(cacheKey)
    if (cached) {
      const body = await cached.text()
      return new Response(body, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'Cache-Control': 'public, s-maxage=' + CACHE_TTL + ', stale-while-revalidate=300',
          'X-Cache': 'HIT',
        },
      })
    }
  } catch (e) {
    // 缓存未命中/过期/异常 → 忽略，走回源
  }

  // 2. 回源 Supabase（anon key，受 RLS 限制只能读 published）
  const url =
    SUPABASE_URL + '/rest/v1/articles?id=eq.' + encodeURIComponent(id) + '&select=*'
  let upstream
  const ac = new AbortController()
  const acTimer = setTimeout(() => ac.abort(), 8000) // 上游 8s 超时：避免函数长时间挂起，快速返 502 让前端回退
  try {
    upstream = await fetch(url, {
      headers: {
        apikey: ANON_KEY,
        Authorization: 'Bearer ' + ANON_KEY,
        Accept: 'application/json',
      },
      signal: ac.signal,
    })
  } catch (e) {
    // 边缘 → Supabase 失败（含超时）：返 502，前端会回退直连
    clearTimeout(acTimer)
    return new Response(JSON.stringify({ error: 'upstream error' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }
  clearTimeout(acTimer)

  if (!upstream.ok) {
    return new Response(JSON.stringify({ error: 'not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }

  const rows = await upstream.json()
  if (!Array.isArray(rows) || rows.length === 0) {
    // 未发布/不存在（RLS 已过滤掉草稿）→ 不缓存，返 404
    return new Response(JSON.stringify({ error: 'not found' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }

  const article = rows[0]
  const body = JSON.stringify(article)

  const resp = new Response(body, {
    status: 200,
      headers: {
        'Content-Type': 'application/json; charset=utf-8',
        'Cache-Control': 'public, s-maxage=' + CACHE_TTL + ', stale-while-revalidate=300',
        'X-Cache': 'MISS',
      },
  })

  // 3. 写入边缘缓存（后台异步，不阻塞响应）
  const putPromise = cache.put(cacheKey, resp.clone())
  if (typeof waitUntil === 'function') {
    waitUntil(putPromise)
  } else {
    putPromise.catch(() => {})
  }

  return resp
}
