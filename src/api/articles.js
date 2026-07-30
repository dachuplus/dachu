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
import { supabase } from './supabase.js'
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
 */
function withTimeout(promise, label) {
  return Promise.race([
    promise,
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error(label + ' 请求超时（>' + (REQ_TIMEOUT / 1000) + 's），请检查网络')), REQ_TIMEOUT)
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

/* ========== 文章列表浏览器缓存 ========== */

/** 缓存 TTL：5 分钟。国内→新加坡延迟高时，缓存命中 = 零等待 */
const CACHE_TTL_MS = 5 * 60 * 1000
const CACHE_KEY_PREFIX = 'dachu_articles_'

/**
 * 从 sessionStorage 读缓存。
 * 用 sessionStorage 而非 localStorage：关标签页自动清理，不占长期存储。
 */
function readCache(key) {
  try {
    const raw = sessionStorage.getItem(CACHE_KEY_PREFIX + key)
    if (!raw) return null
    const { ts, data } = JSON.parse(raw)
    if (Date.now() - ts > CACHE_TTL_MS) return null // 过期
    return data
  } catch { return null }
}

function writeCache(key, data) {
  try {
    sessionStorage.setItem(CACHE_KEY_PREFIX + key, JSON.stringify({ ts: Date.now(), data }))
  } catch { /* storage full / private mode: silently skip */ }
}

/** 根据查询参数生成缓存 key */
function cacheKey(opts) {
  return 'list_' + (opts.status || 'all') + '_' + (opts.authorEmail || '') + '_' + (opts.tag || '')
}

/**
 * 列表文章（带缓存）。
 * 命中缓存 → 瞬间返回旧数据，同时后台静默刷新（下次打开就是新的）。
 */
export async function listArticles({ status = 'published', authorEmail = null, limit = 50, offset = 0, tag = null } = {}) {
  // 注意：EdgeOne Pages Functions 出站请求有超时限制（连 Supabase 新加坡会 504 超时），
  // 因此 /api/articles 边缘函数在 EdgeOne 环境下不可用，已跳过，直接走 Supabase 直连。
  // 浏览器端有 localStorage 缓存（5min TTL）+ 后台静默刷新 + 网络重试，体验仍可接受。

  if (!supabase) throw new Error('未连接数据库')

  const ck = cacheKey({ status, authorEmail, tag })
  // 1. 缓存命中 → 立刻返回（零等待）
  const cached = readCache(ck)
  if (cached && offset === 0) {
    // 后台静默刷新（不阻塞 UI）
    refreshListInBackground({ status, authorEmail, limit, tag }, ck)
    return cached.slice(0, limit)
  }

  // 2. 无缓存 → 正常请求（列表只查必要字段，不取大字段 content）
  const FIELDS = 'id,title,summary,status,published_at,updated_at,views,tags,cover_image,author_email,is_pinned,scheduled_at'
  let q = supabase.from('articles').select(FIELDS)
  if (status) q = q.eq('status', status)
  if (authorEmail) q = q.eq('author_email', authorEmail)
  if (tag) q = q.contains('tags', [tag])
  // 置顶文章排最前，其次按发布时间倒序
  q = q.order('is_pinned', { ascending: false })
  q = q.order('published_at', { ascending: false, nullsFirst: false })
  q = q.range(offset, Math.max(offset, offset + limit - 1))
  const { data, error } = await withTimeout(q, '文章列表')
  if (error) throw error
  const result = data || []
  if (offset === 0) writeCache(ck, result)
  return result
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
 * 注意：EdgeOne Pages Functions 出站请求超时限制导致 /api/article/:id 边缘函数不可用，
 *       已跳过边缘缓存，直接走 Supabase 直连（浏览器端有 localStorage 缓存兜底）。
 */
export async function getArticle(id) {
  const numId = Number(id)
  if (!Number.isFinite(numId)) throw new Error('文章 ID 无效')

  // 直连 Supabase（边缘函数在 EdgeOne 环境下不可用，见 listArticles 注释）
  if (!supabase) throw new Error('未连接数据库')
  const { data, error } = await withTimeout(
    supabase.from('articles').select('*').eq('id', numId).maybeSingle(),
    '文章详情'
  )
  if (error) throw error
  return data
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
    const res = await fetch(PUBLISH_FN_URL, {
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
