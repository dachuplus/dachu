/**
 * Supabase Edge Function - 小程序权限墙后端
 *
 * 为 allfund 小程序提供「权限墙」服务端能力：
 *  - GET  ：携带用户会话令牌（Authorization: Bearer <user_access_token>）查询该用户权限摘要
 *  - POST ：已登录用户提交权限申请（写入 permission_requests）
 *
 * 设计要点（对齐网页版 useAuth.js 权限模型）：
 *  - 仅用 service_role 直连 rest，不依赖前端 RLS 猜测，避免小程序端权限误判。
 *  - 用户身份由传入的 JWT 经 /auth/v1/user 解析出 email（与 wechat-login 合成邮箱一致）。
 *
 * 部署：supabase functions deploy mp-permissions --project-ref tqhtegazxykkqfcpejky
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
}

// Supabase 标准密钥由部署平台自动注入
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || ''
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || ''

// 主管理员邮箱（与网页版 ADMIN_EMAIL 一致）
const ADMIN_EMAIL = '57502460@qq.com'

function json(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

/** 从 Authorization: Bearer <token> 取出 JWT，并解析出用户 email */
async function resolveEmailFromToken(authHeader: string | null): Promise<string> {
  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    throw new Error('未携带会话令牌')
  }
  const token = authHeader.slice(7).trim()
  const res = await fetch(`${SUPABASE_URL}/auth/v1/user`, {
    headers: {
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${token}`,
    },
  })
  if (!res.ok) throw new Error('会话令牌无效或已过期')
  const u = await res.json().catch(() => ({}))
  if (!u || !u.email) throw new Error('无法解析用户身份')
  return u.email as string
}

/** service_role 直连 PostgREST 查询 */
async function restGet(
  table: string,
  query: Record<string, string>
): Promise<any[]> {
  const qs = new URLSearchParams(query).toString()
  const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}?${qs}`, {
    headers: {
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${SERVICE_ROLE}`,
    },
  })
  if (!res.ok) return []
  const d = await res.json().catch(() => [])
  return Array.isArray(d) ? d : []
}

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })
  if (!SUPABASE_URL || !SERVICE_ROLE) {
    return json({ error: '服务端未配置 Supabase 密钥' }, 500)
  }

  try {
    const auth = req.headers.get('authorization') || req.headers.get('Authorization')
    const email = await resolveEmailFromToken(auth)

    if (req.method === 'GET') {
      const perm = await restGet('user_permissions', {
        select: 'is_admin,enabled_features',
        user_email: `eq.${email}`,
        limit: '1',
      })
      const blocked = await restGet('blocked_users', {
        select: 'user_email',
        user_email: `eq.${email}`,
        limit: '1',
      })
      const reqs = await restGet('permission_requests', {
        select: 'status,real_name,phone,extra,created_at',
        user_email: `eq.${email}`,
        limit: '1',
      })

      const p = perm[0]
      const isAdmin = email === ADMIN_EMAIL || !!p?.is_admin
      const enabledFeatures: string[] = Array.isArray(p?.enabled_features)
        ? p.enabled_features
        : []
      const hasAccess = isAdmin || enabledFeatures.length > 0
      const isBlocked = blocked.length > 0
      const r0 = reqs[0]
      const isRejected = !!r0 && r0.status === 'rejected'
      const isPending = !!r0 && r0.status === 'pending'
      const requested = reqs.length > 0

      return json({
        email,
        hasAccess,
        isAdmin,
        enabledFeatures,
        blocked: isBlocked,
        rejected: isRejected,
        pending: isPending,
        requested,
      })
    }

    if (req.method === 'POST') {
      const body = await req.json().catch(() => ({} as any))
      const realName = String(body.realName || body.real_name || '').trim()
      const phone = String(body.phone || '').trim()
      const extra = String(body.extra || body.note || '').trim()

      const res = await fetch(`${SUPABASE_URL}/rest/v1/permission_requests?on_conflict=user_email`, {
        method: 'POST',
        headers: {
          apikey: SERVICE_ROLE,
          Authorization: `Bearer ${SERVICE_ROLE}`,
          'Content-Type': 'application/json',
          Prefer: 'resolution=merge-duplicates,return=representation',
        },
        body: JSON.stringify({
          user_email: email,
          real_name: realName,
          phone,
          extra,
          status: 'pending',
        }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        return json({ error: err?.message || '提交申请失败' }, 400)
      }
      return json({ ok: true, status: 'pending' })
    }

    return json({ error: '不支持的请求方法' }, 405)
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    const status = /令牌|身份/.test(msg) ? 401 : 400
    return json({ error: msg }, status)
  }
})
