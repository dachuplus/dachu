/**
 * 文章数据层（我的内容 / 类公众号）
 *
 * 封装文章 CRUD、作者、封面图上传、阅读量自增。
 * 发文合规：前端预检（ArticleEditorPage 调 checkCompliance）+ 数据库触发器 guard_article_compliance 兜底。
 *
 * 权限边界（后端 RLS 为准）：
 *  - 公开只读已发布文章；作者可读/写/删自己的全部（含草稿）。
 *  - article_authors 白名单中的邮箱，或被授予「内容」权限的用户（has_content_permission()）可写。
 */
import { supabase, rewriteSupabaseUrl } from './supabase.js'
import { useAuth } from '../composables/useAuth.js'

/** 当前登录邮箱（发文 author_email 必须与此一致） */
function currentEmail() {
  try {
    return useAuth().user.value?.email || null
  } catch (e) {
    return null
  }
}

import { checkCompliance } from '../utils/markdown.js'
export { checkCompliance }

/* ========== 网络超时工具 ========== */

/** 单次 supabase 调用超时（毫秒）。国内→新加坡偶尔延迟高，给 60s 足够覆盖极端弱网 */
const REQ_TIMEOUT = 60000

/**
 * 给任意 Promise 加超时。
 * 超时后原 Promise 不会被取消（浏览器限制），但调用方会立刻拿到错误继续走重试/报错逻辑。
 * @param {number} [timeoutMs] 覆盖默认超时（默认 REQ_TIMEOUT=60s）
 */
function withTimeout(promise, label, timeoutMs) {
  const ms = timeoutMs || REQ_TIMEOUT
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(label + ' 请求超时（>' + (ms / 1000) + 's），请检查网络')), ms)
    )
  ])
}

/**
 * 网络抖动自动重试：超时/网络错误时按指数退避重试最多 maxAttempts 次。
 * 业务错误（如 RLS 拒绝、合规拦截）立即抛出，不重试。
 * @param {() => Promise<any>} fn 实际执行函数（每次都重新调用，避免重发幂等性问题需自行处理）
 * @param {number} maxAttempts 总尝试次数（含首次）
 * @param {(attempt:number, err:Error) => void} onRetry 重试时的回调（用于显示「重试中」提示）
 */
async function withRetry(fn, maxAttempts, onRetry) {
  let lastErr
  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn()
    } catch (e) {
      lastErr = e
      const msg = (e && e.message) || String(e)
      // 只对网络类错误重试：超时/连接失败/5xx；业务错误（合规、RLS、参数错）立刻抛
      const isNetErr = msg.indexOf('请求超时') !== -1
        || msg.indexOf('Failed to fetch') !== -1
        || msg.indexOf('NetworkError') !== -1
        || msg.indexOf('网络') !== -1
        || msg.indexOf('aborted') !== -1
      if (!isNetErr || attempt >= maxAttempts) throw e
      const delay = 800 * attempt // 0.8s, 1.6s, 2.4s ...
      if (onRetry) onRetry(attempt + 1, maxAttempts, e)
      await new Promise((r) => setTimeout(r, delay))
    }
  }
  throw lastErr
}

/* ========== 瞬时网络故障统一提示 ========== */

/** 504/超时/断网等瞬时网络故障的统一友好提示语 */
export const NETWORK_SLOW_MSG = '网络速度慢，请稍后再试。'

/**
 * 判断错误是否为瞬时网络类故障（边缘函数 502/504、请求超时、断网等）。
 * 命中后统一提示「网络速度慢，请稍后再试。」。
 */
export function isNetworkError(e) {
  const msg = (e && (e.message || (e.error && e.error.message))) || String(e || '')
  return (
    msg.indexOf('504') !== -1 ||
    msg.indexOf('502') !== -1 ||
    msg.indexOf('超时') !== -1 ||
    msg.indexOf('timeout') !== -1 ||
    msg.indexOf('Failed to fetch') !== -1 ||
    msg.indexOf('NetworkError') !== -1 ||
    msg.indexOf('网络') !== -1 ||
    msg.indexOf('aborted') !== -1 ||
    msg.indexOf('edge-timeout') !== -1
  )
}

/* ========== 文章列表浏览器缓存 ========== */

/** 缓存 TTL：5 分钟。Supabase（新加坡）偶发延迟高时，缓存命中 = 零等待 */
const CACHE_TTL_MS = 5 * 60 * 1000
const CACHE_KEY_PREFIX = 'dachu_articles_'

/**
 * 从 localStorage 读缓存。
 * 用 localStorage 而非 sessionStorage：关闭标签页后仍保留，半小时内重访秒开。
 */
function readCache(key) {
  try {
    const raw = localStorage.getItem(CACHE_KEY_PREFIX + key)
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > CACHE_TTL_MS) { // 过期则清理
      localStorage.removeItem(CACHE_KEY_PREFIX + key)
      return null
    }
    return data
  } catch { return null }
}

function writeCache(key, data) {
  try {
    localStorage.setItem(CACHE_KEY_PREFIX + key, JSON.stringify({ ts: Date.now(), data }))
  } catch { /* storage full / private mode: silently skip */ }
}

/** 根据查询参数生成缓存 key */
function cacheKey(opts) {
  return 'list_' + (opts.status || 'all') + '_' + (opts.authorEmail || '') + '_' + (opts.tag || '')
}

/**
 * 列表文章（带缓存）。
 * 命中缓存 → 瞬间返回旧数据，同时后台静默刷新（下次打开就是新的）。
 *
 * 提速链路（按优先级）：
 *  1) localStorage 缓存（5 分钟内）
 *  2) /articles-list.json（部署时预生成的静态 JSON，EdgeOne CDN 毫秒级返回）
 *     → 拿到后立刻显示 + 触发后台静默刷新（保证下次或换设备后也是新的）
 *  3) /api/articles（同域边缘函数，15s 超时）→ 边缘偶尔抽风时回退
 *  4) 直连 Supabase（15s 超时兜底，迫使慢路径快速失败而非白屏60s+）
 */
export async function listArticles({ status = 'published', authorEmail = null, limit = 50, offset = 0, tag = null } = {}) {
  const ck = cacheKey({ status, authorEmail, tag })

  // ===== 1. localStorage 缓存命中（最快） =====
  const cached = readCache(ck)
  if (cached && offset === 0) {
    // 后台静默刷新（不阻塞 UI）
    refreshListInBackground({ status, authorEmail, limit, tag }, ck)
    return cached.slice(0, limit)
  }

  // ===== 2. 已发布全量列表：部署时预生成的静态 JSON（毫秒级 CDN 返回） =====
  //    仅对公开首屏（status=published + 无作者/标签过滤）启用。EdgeOne→Supabase 链路偶发 10-16s
  //    慢速时，这个静态文件是用户的救命稻草 —— 部署一次（CI 每日 21:30 或手动）即生效。
  if (status === 'published' && !authorEmail && !tag && offset === 0) {
    try {
      const staticRes = await fetch('/articles-list.json?t=' + Date.now(), {
        headers: { Accept: 'application/json' },
      })
      if (staticRes.ok) {
        const payload = await staticRes.json()
        if (payload && Array.isArray(payload.articles) && payload.articles.length) {
          writeCache(ck, payload.articles)
          // 后台静默刷新（让本地缓存与服务端/边缘函数/Supabase 一致，对未发布新文章也能尽快同步）
          refreshListInBackground({ status, authorEmail, limit, tag }, ck)
          return payload.articles.slice(0, limit)
        }
      }
      // 静态文件不存在/格式异常 → 走边缘函数
    } catch (e) {
      // 静态文件失败（极少，CDN 不可达）→ 走边缘函数
    }

    // ===== 3. 同域边缘函数（EdgeOne 境外节点就近回源，15s 内超时即走兜底） =====
    try {
      const res = await Promise.race([
        fetch('/api/articles', { headers: { Accept: 'application/json' } }),
        new Promise((_, rej) => setTimeout(() => rej(new Error('edge-timeout')), 12000)),
      ])
      if (res.ok) {
        const data = await res.json()
        if (Array.isArray(data) && data.length) {
          if (offset === 0) writeCache(ck, data)
          return data.slice(0, limit)
        }
      }
      // 502 / 空数组 → 走下方直连兜底
    } catch (e) {
      // 边缘超时或异常 → 忽略，走兜底
    }
  }

  // ===== 4. 兜底：直连 Supabase（列表只查必要字段，不取大字段 content）。
  //    单独 15s 超时：边缘已挂 12s 后，兜底再等 60s 用户体感极差，15s 总 ≤ 27s 即报错。 =====
  if (!supabase) throw new Error('未连接数据库')

  const FIELDS = 'id,title,summary,status,published_at,updated_at,views,tags,cover_image,author_email,is_pinned,scheduled_at'
  let q = supabase.from('articles').select(FIELDS)
  if (status) q = q.eq('status', status)
  if (authorEmail) q = q.eq('author_email', authorEmail)
  if (tag) q = q.contains('tags', [tag])
  // 置顶文章排最前，其次按发布时间倒序
  q = q.order('is_pinned', { ascending: false })
  q = q.order('published_at', { ascending: false, nullsFirst: false })
  q = q.range(offset, Math.max(offset, offset + limit - 1))
  try {
    const { data, error } = await withTimeout(q, '文章列表', 15000)
    if (error) throw error
    const result = data || []
    if (offset === 0) writeCache(ck, result)
    return result
  } catch (e) {
    // 瞬时网络故障（504/超时/断网）→ 统一友好提示
    if (isNetworkError(e)) throw new Error(NETWORK_SLOW_MSG)
    throw e
  }
}

/** 后台静默刷新：失败时静默忽略，不弹错误 */
async function refreshListInBackground(opts, ck) {
  try {
    const FIELDS = 'id,title,summary,status,published_at,updated_at,views,tags,cover_image,author_email,is_pinned,scheduled_at'
    let q = supabase.from('articles').select(FIELDS)
    if (opts.status) q = q.eq('status', opts.status)
    if (opts.authorEmail) q = q.eq('author_email', opts.authorEmail)
    if (opts.tag) q = q.contains('tags', [opts.tag])
    // 置顶文章排最前，其次按发布时间倒序
    q = q.order('is_pinned', { ascending: false })
    q = q.order('published_at', { ascending: false, nullsFirst: false })
    q = q.range(0, Math.max(0, (opts.limit || 50) - 1))
    const { data, error } = await withTimeout(q, '文章列表(后台刷新)')
    if (!error && data) writeCache(ck, data)
  } catch { /* 静默：缓存仍有效，下次再试 */ }
}

/**
 * 取单篇文章。
 * 提速优化：已发布文章优先走同域边缘缓存接口 /api/article/:id（EdgeOne 境外节点就近返回，免跨境直连新加坡）。
 * 兜底：边缘 2.5s 内未响应/返 404（未发布/草稿）→ 回退直连 Supabase，保证作者可读自己草稿。
 */
export async function getArticle(id) {
  const numId = Number(id)
  if (!Number.isFinite(numId)) throw new Error('文章 ID 无效')

  // 1. 优先走边缘缓存接口（5s 超时，避免偶发慢回源拖白屏）
  try {
    const res = await Promise.race([
      fetch(`/api/article/${numId}`, { headers: { Accept: 'application/json' } }),
      new Promise((_, rej) => setTimeout(() => rej(new Error('edge-timeout')), 5000)),
    ])
    if (res.ok) {
      const data = await res.json()
      if (data && data.id === numId) return data
    }
    // 404 / 非预期 → 走下方直连兜底
  } catch (e) {
    // 边缘超时或异常 → 忽略，走兜底
  }

  // 2. 兜底：直连 Supabase
  if (!supabase) throw new Error('未连接数据库')
  try {
    const { data, error } = await withTimeout(
      supabase.from('articles').select('*').eq('id', numId).maybeSingle(),
      '文章详情'
    )
    if (error) throw error
    return data
  } catch (e) {
    // 瞬时网络故障（504/超时/断网）→ 统一友好提示
    if (isNetworkError(e)) throw new Error(NETWORK_SLOW_MSG)
    throw e
  }
}

/** 取作者信息（公开） */
export async function getAuthor(email) {
  if (!supabase || !email) return null
  const { data, error } = await withTimeout(
    supabase.from('article_authors').select('*').eq('email', email).maybeSingle(),
    '作者信息'
  )
  if (error) throw error
  return data
}

/** 取全部作者（公开） */
export async function listAuthors() {
  if (!supabase) return []
  const { data, error } = await withTimeout(
    supabase.from('article_authors').select('*'),
    '作者列表'
  )
  if (error) throw error
  return data || []
}

/**
 * 分块上传：把长文切成小块逐块传到 Supabase（新加坡节点），
 * 避免单次大请求在弱网/高延迟链路上超时或失败。
 * 每块插入 article_chunks，最后由 assemble_article_content() 合并回 articles.content。
 */

/** 每块字符数（中文约 3 字节/字 → 约 3KB/块，足够小且可靠） */
const CHUNK_SIZE = 1000

function splitChunks(text) {
  const out = []
  const s = text || ''
  for (let i = 0; i < s.length; i += CHUNK_SIZE) {
    out.push(s.slice(i, i + CHUNK_SIZE))
  }
  if (out.length === 0) out.push('') // 至少一块，保证能拼出空内容
  return out
}

/** 逐块上传，带进度回调与单块失败重试 */
async function uploadChunks(articleId, content, onProgress) {
  const parts = splitChunks(content)
  const total = parts.length
  // 先清旧块（编辑场景）——带超时
  await withTimeout(
    supabase.from('article_chunks').delete().eq('article_id', articleId),
    '清理旧分块'
  )
  for (let seq = 0; seq < total; seq++) {
    let lastErr = null
    for (let attempt = 1; attempt <= 3; attempt++) {
      try {
        const { error } = await withTimeout(
          supabase.from('article_chunks').insert({ article_id: articleId, seq, part: parts[seq] }),
          '上传第' + (seq + 1) + '块'
        )
        if (!error) {
          lastErr = null
          break
        }
        lastErr = error
      } catch (e) {
        // 超时报错也计入重试
        lastErr = e
      }
      await new Promise((r) => setTimeout(r, 400 * attempt))
    }
    if (lastErr) throw new Error('分块上传失败（第 ' + (seq + 1) + '/' + total + ' 块）：' + (lastErr.message || lastErr))
    if (onProgress) onProgress(seq + 1, total)
  }
}

/* ========== Edge Function 代理写入 ========== */

/**
 * 文章发布 Edge Function 端点。
 * 浏览器只需一次 HTTP 调用，函数在服务端完成：建文章→分块→拼装→发布。
 * 解决国内直连新加坡 PostgREST 超时问题。
 */
const PUBLISH_FN_URL = 'https://tqhtegazxykkqfcpejky.supabase.co/functions/v1/publish-article'

/**
 * 压缩请求体（gzip）。中文文本压缩率 60-70%，大幅缩短国内→海外上传时间。
 * 返回 { body: Blob, contentEncoding: string } 或原始 JSON 字符串（降级）。
 */
async function compressBody(obj) {
  const json = JSON.stringify(obj)
  // 小于 512B 不值得压缩（gzip 头本身 ~20B）
  if (json.length < 512) return { body: json, encoding: null }
  try {
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(json))
        controller.close()
      }
    })
    const compressed = stream.pipeThrough(new CompressionStream('gzip'))
    const blob = await new Response(compressed).blob()
    return { body: blob, encoding: 'gzip' }
  } catch (e) {
    // 浏览器不支持 CompressionStream 时降级为明文
    return { body: json, encoding: null }
  }
}

/** 从 Supabase 内部存储同步读取 access_token（零网络开销）
 *
 * supabase-js v2 用 auth.storageKey 作为 localStorage key（如 sb-xxx-auth-token），
 * 值为 JSON { current: { access_token, ... }, expires_at }。
 * 直接从 supabase.auth.storage 读取，不依赖硬编码 key 名。
 */
function getAccessToken() {
  try {
    const raw = supabase.auth.storage.getItem(supabase.auth.storageKey)
    if (!raw) return null
    const data = JSON.parse(raw)
    return data?.current?.access_token || data?.access_token || null
  } catch { return null }
}

/** 调用 publish-article Edge Function（带超时保护 + gzip 压缩） */
async function callPublishFn(payload) {
  // 关键修复：从 localStorage 同步读取 token（零网络）
  // 上次用 supabase.auth.session 是 undefined（v2 无此属性），
  // 导致每次都降级到 getSession() 网络请求→国内→新加坡超时→卡死"发布中..."
  let accessToken = getAccessToken()
  if (!accessToken) {
    // 内存无 token 时才降级走网络（带超时保护）
    const { data: { session: netSession } } = await withTimeout(
      supabase.auth.getSession(),
      '获取登录状态'
    )
    if (!netSession?.access_token) throw new Error('未登录，请刷新页面重新登录')
    accessToken = netSession.access_token
  }
  const { body, encoding } = await compressBody(payload)
  // Edge Function 内部做 4-5 次 DB 操作，给 120 秒总超时（压缩后应远快于此）
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 120000)
  try {
    const headers = {
      'Authorization': `Bearer ${accessToken}`,
    }
    if (encoding) {
      headers['Content-Encoding'] = encoding
    } else {
      headers['Content-Type'] = 'application/json'
    }
    const res = await fetch(rewriteSupabaseUrl(PUBLISH_FN_URL), {
      method: 'POST',
      headers,
      body,
      signal: controller.signal,
    })
    const result = await res.json()
    if (!res.ok || !result.ok) {
      throw new Error(result.error || '发布失败（HTTP ' + res.status + '）')
    }
    return result
  } finally {
    clearTimeout(timer)
  }
}

/** 新建文章（通过 Edge Function 代理，一次请求完成全流程） */
export async function createArticle(payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')

  // 前端合规提示（仅提示，不拦截；DB 触发器仍会记录但不再 RAISE）
  const v = checkCompliance(`${payload.title} ${payload.summary || ''} ${payload.content}`)
  // 不再 throw，命中时由调用方决定是否提示

  // 注意：Edge Function 内部一次性完成全部 DB 操作，不报告中间进度
  // onProgress 不在此处调用，按钮保持"发布中…"状态直到返回

  return callPublishFn({
    title: payload.title,
    summary: payload.summary || '',
    content: payload.content,
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: payload.status || 'draft',
    scheduled_at: payload.scheduled_at || null,
  })
}

/** 更新文章（通过 Edge Function 代理） */
export async function updateArticle(id, payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')

  // Edge Function 一次性完成，不报告中间进度
  return callPublishFn({
    article_id: Number(id),
    title: payload.title,
    summary: payload.summary || '',
    content: payload.content,
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: payload.status || 'draft',
    scheduled_at: payload.scheduled_at || null,
  })
}

/** 删除文章（作者本人，RLS 兜底） */
export async function deleteArticle(id) {
  if (!supabase) throw new Error('未连接数据库')
  const { error } = await supabase.from('articles').delete().eq('id', Number(id))
  if (error) throw error
}

/** 置顶 / 取消置顶文章（管理员，RLS 兜底：has_content_permission 允许） */
export async function setArticlePinned(id, pinned) {
  if (!supabase) throw new Error('未连接数据库')
  const { error } = await supabase
    .from('articles')
    .update({ is_pinned: !!pinned })
    .eq('id', Number(id))
  if (error) throw error
}

/** 阅读量自增（仅统计已发布；公开可调用） */
export async function incrementViews(id) {
  if (!supabase) throw new Error('未连接数据库')
  const { error } = await supabase.rpc('increment_article_views', { p_article_id: Number(id) })
  if (error) throw error
}

/**
 * 上传文章配图到 article-images 存储桶（仅作者可写，RLS 兜底）。
 * @returns {Promise<{path:string, url:string}>}
 */
export async function uploadArticleImage(file) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')
  if (!supabase) throw new Error('未连接数据库')
  const rawExt = (file.name.split('.').pop() || 'png').toLowerCase().replace(/[^a-z0-9]/g, '')
  const ext = ['png', 'jpg', 'jpeg', 'webp', 'gif'].includes(rawExt) ? rawExt : 'png'
  const safeName = Date.now() + '-' + Math.random().toString(36).slice(2, 8) + '.' + ext
  const path = email + '/' + safeName
  const { error } = await supabase.storage.from('article-images').upload(path, file, { upsert: false })
  if (error) throw error
  const { data } = supabase.storage.from('article-images').getPublicUrl(path)
  return { path, url: data.publicUrl }
}

/** 删除已上传的配图 */
export async function deleteArticleImage(path) {
  if (!supabase || !path) return
  const { error } = await supabase.storage.from('article-images').remove([path])
  if (error) throw error
}
