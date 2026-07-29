/**
 * EdgeOne Pages Function — 已发布文章列表边缘缓存代理
 * 路由：/api/articles  →  functions/api/articles.js
 *
 * 作用：首页 / 博客列表首屏从 EdgeOne 边缘节点就近返回已发布文章摘要，
 *       不再跨境直连 Supabase（新加坡），显著提速首屏。
 * 缓存：caches.default（原生 Cache API）+ Cache-Control（EdgeOne CDN 层亦缓存），
 *       列表 TTL 较短（60s），因为新增/修改文章后需较快生效。
 * 安全：anon key 读取，RLS 保证只返回 published 文章。
 */

const SUPABASE_URL = 'https://tqhtegazxykkqfcpejky.supabase.co'
const ANON_KEY = 'sb_publishable_iFtMcvav774gqF28gGYQVw_QMmuS-z3'
// 与前端 listArticles 的 FIELDS 保持一致（不含大字段 content，降低体积）
const FIELDS =
  'id,title,summary,status,published_at,updated_at,views,tags,cover_image,author_email'
const CACHE_TTL = 60 // 秒（列表变化较快，缓存短一些）

export async function onRequestGet(context) {
  const cache = caches.default
  const cacheKey = new Request(context.request.url)

  // 1. 命中边缘缓存 → 直接返回
  try {
    const cached = await cache.match(cacheKey)
    if (cached) {
      const body = await cached.text()
      return new Response(body, {
        status: 200,
        headers: {
          'Content-Type': 'application/json; charset=utf-8',
          'X-Cache': 'HIT',
        },
      })
    }
  } catch (e) {
    // 缓存异常 → 忽略，走回源
  }

  // 2. 回源 Supabase（anon key，受 RLS 限制只能读 published）
  const url =
    SUPABASE_URL +
    '/rest/v1/articles?select=' +
    encodeURIComponent(FIELDS) +
    '&status=eq.published&order=published_at.desc.nullslast&limit=200'
  let upstream
  try {
    upstream = await fetch(url, {
      headers: {
        apikey: ANON_KEY,
        Authorization: 'Bearer ' + ANON_KEY,
        Accept: 'application/json',
      },
    })
  } catch (e) {
    return new Response(JSON.stringify({ error: 'upstream error' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }

  if (!upstream.ok) {
    return new Response(JSON.stringify({ error: 'upstream error' }), {
      status: 502,
      headers: { 'Content-Type': 'application/json; charset=utf-8' },
    })
  }

  const rows = await upstream.json()
  const body = JSON.stringify(Array.isArray(rows) ? rows : [])

  const resp = new Response(body, {
    status: 200,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control':
        'public, s-maxage=' + CACHE_TTL + ', stale-while-revalidate=120',
      'X-Cache': 'MISS',
    },
  })

  // 3. 写入边缘缓存（后台异步，不阻塞响应）
  const putPromise = cache.put(cacheKey, resp.clone())
  if (typeof context.waitUntil === 'function') {
    context.waitUntil(putPromise)
  } else {
    putPromise.catch(() => {})
  }

  return resp
}
