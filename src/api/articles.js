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

/**
 * 列表文章。
 * @param {object} opts
 *  - status: 'published' | 'draft' | null(全部)
 *  - authorEmail: 指定作者（null 表示不按作者过滤）
 *  - tag: 按标签筛选（可选）
 *  - limit / offset: 分页
 */
export async function listArticles({ status = 'published', authorEmail = null, limit = 50, offset = 0, tag = null } = {}) {
  if (!supabase) throw new Error('未连接数据库')
  let q = supabase.from('articles').select('*')
  if (status) q = q.eq('status', status)
  if (authorEmail) q = q.eq('author_email', authorEmail)
  if (tag) q = q.contains('tags', [tag])
  q = q.order('published_at', { ascending: false, nullsFirst: false })
  q = q.range(offset, Math.max(offset, offset + limit - 1))
  const { data, error } = await q
  if (error) throw error
  return data || []
}

/** 取单篇文章（已发布所有人可读；草稿仅作者可读，越权返回 null） */
export async function getArticle(id) {
  if (!supabase) throw new Error('未连接数据库')
  const { data, error } = await supabase
    .from('articles')
    .select('*')
    .eq('id', Number(id))
    .maybeSingle()
  if (error) throw error
  return data
}

/** 取作者信息（公开） */
export async function getAuthor(email) {
  if (!supabase || !email) return null
  const { data, error } = await supabase
    .from('article_authors')
    .select('*')
    .eq('email', email)
    .maybeSingle()
  if (error) throw error
  return data
}

/** 取全部作者（公开） */
export async function listAuthors() {
  if (!supabase) return []
  const { data, error } = await supabase.from('article_authors').select('*')
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

/** 调用 publish-article Edge Function */
async function callPublishFn(body) {
  const { data: { session } } = await supabase.auth.getSession()
  if (!session?.access_token) throw new Error('未登录')
  const res = await fetch(PUBLISH_FN_URL, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${session.access_token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })
  const result = await res.json()
  if (!res.ok || !result.ok) {
    throw new Error(result.error || '发布失败（HTTP ' + res.status + '）')
  }
  return result
}

/** 新建文章（通过 Edge Function 代理，一次请求完成全流程） */
export async function createArticle(payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')

  // 前端合规预检（checkCompliance 返回数组，空数组=通过）
  const v = checkCompliance(`${payload.title} ${payload.summary || ''} ${payload.content}`)
  if (v.length > 0) throw new Error(`内容包含不合规表述「${v.join('、')}」`)

  // 模拟进度反馈（Edge Function 内部一次性完成，无法报告中间状态）
  if (payload.onProgress) payload.onProgress(1, 1)

  return callPublishFn({
    title: payload.title,
    summary: payload.summary || '',
    content: payload.content,
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: payload.status || 'draft',
  })
}

/** 更新文章（通过 Edge Function 代理） */
export async function updateArticle(id, payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')

  if (payload.onProgress) payload.onProgress(1, 1)

  return callPublishFn({
    article_id: Number(id),
    title: payload.title,
    summary: payload.summary || '',
    content: payload.content,
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: payload.status || 'draft',
  })
}

/** 删除文章（作者本人，RLS 兜底） */
export async function deleteArticle(id) {
  if (!supabase) throw new Error('未连接数据库')
  const { error } = await supabase.from('articles').delete().eq('id', Number(id))
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
