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
  // 先清旧块（编辑场景）
  await supabase.from('article_chunks').delete().eq('article_id', articleId)
  for (let seq = 0; seq < total; seq++) {
    let lastErr = null
    for (let attempt = 1; attempt <= 3; attempt++) {
      const { error } = await supabase
        .from('article_chunks')
        .insert({ article_id: articleId, seq, part: parts[seq] })
      if (!error) {
        lastErr = null
        break
      }
      lastErr = error
      await new Promise((r) => setTimeout(r, 400 * attempt))
    }
    if (lastErr) throw new Error('分块上传失败（第 ' + (seq + 1) + '/' + total + ' 块）：' + (lastErr.message || lastErr))
    if (onProgress) onProgress(seq + 1, total)
  }
}

/** 新建文章（分块上传正文；前端已做合规预检，数据库触发器兜底） */
export async function createArticle(payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')
  // 1) 先插元数据行（content 暂空，状态 draft，避免空内容被发布）
  const meta = {
    author_email: email,
    title: payload.title,
    summary: payload.summary || null,
    content: '',
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: 'draft',
    published_at: null,
  }
  const { data, error } = await supabase.from('articles').insert(meta).select('id').single()
  if (error) throw error
  const id = data.id
  // 2) 分块上传正文
  await uploadChunks(id, payload.content, payload.onProgress)
  // 3) 服务端拼装
  const { error: ae } = await supabase.rpc('assemble_article_content', { p_article_id: id })
  if (ae) throw ae
  // 4) 需要发布则置为已发布
  if (payload.status === 'published') {
    const { error: pe } = await supabase
      .from('articles')
      .update({ status: 'published', published_at: new Date().toISOString() })
      .eq('id', id)
    if (pe) throw pe
  }
  return { id, ok: true }
}

/** 更新文章（分块上传正文；前端已做合规预检，数据库触发器兜底） */
export async function updateArticle(id, payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')
  const meta = {}
  if (payload.title !== undefined) meta.title = payload.title
  if (payload.summary !== undefined) meta.summary = payload.summary
  if (payload.cover_image !== undefined) meta.cover_image = payload.cover_image
  if (payload.tags !== undefined) meta.tags = payload.tags
  // 拼装完成前保持 draft，避免旧/空内容被发布
  meta.status = payload.status === 'published' ? 'draft' : (payload.status || 'draft')
  const { error } = await supabase.from('articles').update(meta).eq('id', Number(id))
  if (error) throw error
  // 分块上传正文
  await uploadChunks(Number(id), payload.content, payload.onProgress)
  // 服务端拼装
  const { error: ae } = await supabase.rpc('assemble_article_content', { p_article_id: Number(id) })
  if (ae) throw ae
  // 需要发布则置为已发布
  if (payload.status === 'published') {
    const { error: pe } = await supabase
      .from('articles')
      .update({ status: 'published', published_at: new Date().toISOString() })
      .eq('id', Number(id))
    if (pe) throw pe
  }
  return { ok: true }
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
