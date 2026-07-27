/**
 * Supabase Edge Function - 文章发布代理
 *
 * 解决国内浏览器直连新加坡 PostgREST 超时的问题：
 * 浏览器只需一次 HTTP 调用到此函数，函数在服务端（同数据中心）完成全部 DB 操作。
 *
 * 流程：收参数 → 建文章行 → 分块写正文 → 拼装 → 置发布状态 → 返回 ID
 * 认证：从 Authorization header 提取 JWT，用 getUser() 验证身份并取 email。
 * 写库：使用 service_role key（跳过 RLS 评估，更快）。
 *
 * 部署：supabase functions deploy publish-article --project-ref tqhtegazxykkqfcpejky
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || ''
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || ''

/** 合规关键词（与触发器 guard_article_compliance 保持一致） */
const FORBIDDEN = [
  '保本','稳赚','必涨','保证收益','承诺收益','推荐买入','跟单',
  '代客理财','零风险','稳赚不赔','高收益无风险','内部消息','包赚',
  'guaranteed','保证盈利','保底'
]

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

function checkCompliance(text: string): string | null {
  const lower = text.toLowerCase()
  for (const w of FORBIDDEN) {
    if (lower.includes(w.toLowerCase())) return w
  }
  return null
}

/** 将正文按 ~1000 字分块 */
function splitChunks(content: string): string[] {
  const chunks: string[] = []
  const CHUNK_SIZE = 1000
  let i = 0
  while (i < content.length) {
    chunks.push(content.slice(i, i + CHUNK_SIZE))
    i += CHUNK_SIZE
  }
  return chunks
}

serve(async (req) => {
  // CORS preflight
  if (req.method === 'OPTIONS') return new Response(null, { headers: corsHeaders })

  try {
    const { data: { user }, error: authErr } = await (
      await fetch(`${SUPABASE_URL}/auth/v1/user`, {
        method: 'GET',
        headers: { Authorization: req.headers.get('Authorization') || '' },
      })
    ).json()

    if (authErr || !user?.email) {
      return json({ error: '未登录或会话已过期' }, 401)
    }

    const body = await req.json()
    const { title, summary, content, cover_image, tags, status, article_id } = body

    // 基本校验
    if (!title?.trim()) return json({ error: '标题不能为空' }, 400)
    if (!content) return json({ error: '正文不能为空' }, 400)

    // 合规检查
    const violation = checkCompliance(`${title} ${summary || ''} ${content}`)
    if (violation) {
      return json({ error: `内容包含不合规表述「${violation}」，请修改后重试` }, 400)
    }

    const srHeader = `Bearer ${SERVICE_ROLE}`
    const authorEmail = user.email
    const isUpdate = !!article_id
    let id: number

    if (isUpdate) {
      // 更新：先清空 content（拼装时会重写）
      const updRes = await fetch(
        `${SUPABASE_URL}/rest/v1/articles?id=eq.${article_id}&author_email=eq.${encodeURIComponent(authorEmail)}`,
        {
          method: 'PATCH',
          headers: { ...corsHeaders, Authorization: srHeader, 'Content-Type': 'application/json', Prefer: 'return=representation' },
          body: JSON.stringify({
            title: title.trim(),
            summary: summary?.trim() || '',
            cover_image: cover_image?.trim() || null,
            tags: tags || [],
            updated_at: new Date().toISOString(),
            content: '', // 清空，后续由 chunk 拼装写入
          }),
        }
      )
      if (!updRes.ok) {
        const err = await updRes.json().catch(() => ({}))
        return json({ error: '更新文章失败', detail: err }, updRes.status)
      }
      const [row] = await updRes.json()
      id = row.id
    } else {
      // 新建
      const insRes = await fetch(`${SUPABASE_URL}/rest/v1/articles`, {
        method: 'POST',
        headers: { ...corsHeaders, Authorization: srHeader, 'Content-Type': 'application/json', Prefer: 'return=representation' },
        body: JSON.stringify({
          title: title.trim(),
          summary: summary?.trim() || '',
          content: '', // 先空，chunk 拼装后填入
          cover_image: cover_image?.trim() || null,
          tags: tags || [],
          author_email: authorEmail,
          status: 'draft',
        }),
      })
      if (!insRes.ok) {
        const err = await insRes.json().catch(() => ({}))
        return json({ error: '创建文章失败', detail: err }, insRes.status)
      }
      const [row] = await insRes.json()
      id = row.id
    }

    // 分块插入正文
    const parts = splitChunks(content)
    if (parts.length > 0) {
      // 先清旧块
      await fetch(
        `${SUPABASE_URL}/rest/v1/article_chunks?article_id=eq.${id}`,
        { method: 'DELETE', headers: { ...corsHeaders, Authorization: srHeader } }
      )
      // 批量插入新块
      const chunkRows = parts.map((part, seq) => ({ article_id: id, seq, part }))
      const chRes = await fetch(`${SUPABASE_URL}/rest/v1/article_chunks`, {
        method: 'POST',
        headers: { ...corsHeaders, Authorization: srHeader, 'Content-Type': 'application/json', Prefer: 'resolution=merge-duplicates' },
        body: JSON.stringify(chunkRows),
      })
      if (!chRes.ok) {
        // 清理孤儿文章
        await fetch(`${SUPABASE_URL}/rest/v1/articles?id=eq.${id}`, { method: 'DELETE', headers: { ...corsHeaders, Authorization: srHeader } })
        return json({ error: '分块上传正文失败' }, 500)
      }
    }

    // 服务端拼装
    const asmRes = await fetch(`${SUPABASE_URL}/rest/v1/rpc/assemble_article_content`, {
      method: 'POST',
      headers: { ...corsHeaders, Authorization: srHeader, 'Content-Type': 'application/json' },
      body: JSON.stringify({ p_article_id: id }),
    })
    if (!asmRes.ok) {
      const asmErr = await asmRes.json().catch(() => ({}))
      return json({ error: '拼装正文失败', detail: asmErr }, 500)
    }

    // 需要发布则置为已发布
    if (status === 'published') {
      const pubRes = await fetch(
        `${SUPABASE_URL}/rest/v1/articles?id=eq.${id}`,
        {
          method: 'PATCH',
          headers: { ...corsHeaders, Authorization: srHeader, 'Content-Type': 'application/json' },
          body: JSON.stringify({ status: 'published', published_at: new Date().toISOString() }),
        }
      )
      if (!pubRes.ok) {
        return json({ error: '发布状态更新失败（文章已保存为草稿）' }, 500)
      }
    }

    return json({ id, ok: true, message: isUpdate ? '已更新' : (status === 'published' ? '已发布' : '草稿已保存') })

  } catch (e: any) {
    console.error('publish-article error:', e)
    return json({ error: e.message || '服务器内部错误' }, 500)
  }
})
