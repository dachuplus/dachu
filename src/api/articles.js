/**
 * 文章数据层（我的内容 / 类公众号）
 *
 * 封装文章 CRUD、作者、封面图上传、阅读量自增。
 * 发文合规前端预检复用 markdown.js 的 checkCompliance（与后端触发器双重保险）。
 *
 * 权限边界（后端 RLS 为准）：
 *  - 公开只读已发布文章；作者可读/写/删自己的全部（含草稿）。
 *  - 仅 article_authors 表中存在的邮箱可写（is_article_author()）。
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

/** 新建文章（含合规前端预检） */
export async function createArticle(payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')
  const hits = checkCompliance(
    (payload.title || '') + ' ' + (payload.summary || '') + ' ' + (payload.content || '')
  )
  if (hits.length) throw new Error('COMPLIANCE_VIOLATION: ' + hits.join('、'))
  const row = {
    author_email: email,
    title: payload.title,
    summary: payload.summary || null,
    content: payload.content,
    cover_image: payload.cover_image || null,
    tags: payload.tags || [],
    status: payload.status || 'draft',
    published_at: payload.status === 'published' ? new Date().toISOString() : null,
  }
  const { data, error } = await supabase.from('articles').insert(row).select().single()
  if (error) throw error
  return data
}

/** 更新文章（含合规前端预检） */
export async function updateArticle(id, payload) {
  const email = currentEmail()
  if (!email) throw new Error('请先登录')
  const hits = checkCompliance(
    (payload.title || '') + ' ' + (payload.summary || '') + ' ' + (payload.content || '')
  )
  if (hits.length) throw new Error('COMPLIANCE_VIOLATION: ' + hits.join('、'))
  const row = {}
  if (payload.title !== undefined) row.title = payload.title
  if (payload.summary !== undefined) row.summary = payload.summary
  if (payload.content !== undefined) row.content = payload.content
  if (payload.cover_image !== undefined) row.cover_image = payload.cover_image
  if (payload.tags !== undefined) row.tags = payload.tags
  if (payload.status !== undefined) {
    row.status = payload.status
    if (payload.status === 'published') row.published_at = new Date().toISOString()
  }
  const { data, error } = await supabase
    .from('articles')
    .update(row)
    .eq('id', Number(id))
    .select()
    .single()
  if (error) throw error
  return data
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
