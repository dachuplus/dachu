/**
 * Supabase Edge Function - 微信登录代理
 *
 * 解决前端无法直接持有微信 AppSecret 的问题：所有涉及 AppSecret 的调用（code→openid）
 * 均在此服务端完成，再调用 Supabase Admin API 创建/查找用户，并通过密码授权签发会话令牌。
 *
 * 路由：
 *  - { type: 'mp',  code }  → 微信小程序 wx.login() 拿到的 code，走 jscode2session
 *  - { type: 'web', code }  → 网页扫码回调拿到的 code，走 oauth2/access_token
 *
 * 身份体系：沿用既有「合成邮箱」约定，微信登录用户邮箱为 wx_<suffix>@allfund.wechat
 *   （有 unionid 时用 u_<unionid>，否则用 <type>_<openid>），密码由 openid+PEPPER 确定性派生，
 *   因此可重复登录并复用同一账号，且不依赖任何明文存储的密码。
 *
 * 部署：supabase functions deploy wechat-login --project-ref tqhtegazxykkqfcpejky
 *       supabase secrets set WECHAT_MP_APPID=wxac87803bace3ad2d WECHAT_MP_APPSECRET=xxx \
 *                          WECHAT_WEB_APPID=xxx WECHAT_WEB_APPSECRET=xxx WECHAT_PEPPER=xxx
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

// Supabase 标准密钥由部署平台自动注入
const SUPABASE_URL = Deno.env.get('SUPABASE_URL') || ''
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY') || ''
const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') || ''

// 微信相关密钥（由 supabase secrets set 注入）
const MP_APPID = Deno.env.get('WECHAT_MP_APPID') || ''
const MP_SECRET = Deno.env.get('WECHAT_MP_APPSECRET') || ''
const WEB_APPID = Deno.env.get('WECHAT_WEB_APPID') || ''
const WEB_SECRET = Deno.env.get('WECHAT_WEB_APPSECRET') || ''
const PEPPER = Deno.env.get('WECHAT_PEPPER') || ''

function json(body: any, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

async function sha256Hex(s: string): Promise<string> {
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(s))
  return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('')
}

/** 用 code 换取微信 openid（+ unionid 若有） */
async function exchangeOpenid(
  type: string,
  code: string
): Promise<{ openid: string; unionid?: string }> {
  let url: string
  if (type === 'mp') {
    if (!MP_APPID || !MP_SECRET) throw new Error('小程序微信登录未配置（缺少 AppSecret）')
    url =
      `https://api.weixin.qq.com/sns/jscode2session?appid=${MP_APPID}` +
      `&secret=${MP_SECRET}&js_code=${code}&grant_type=authorization_code`
  } else if (type === 'web') {
    if (!WEB_APPID || !WEB_SECRET) throw new Error('网页微信登录未配置（缺少 AppSecret）')
    url =
      `https://api.weixin.qq.com/sns/oauth2/access_token?appid=${WEB_APPID}` +
      `&secret=${WEB_SECRET}&code=${code}&grant_type=authorization_code`
  } else {
    throw new Error('未知的登录类型')
  }
  const res = await fetch(url)
  const d = await res.json()
  if (d && d.errcode) {
    throw new Error(`微信接口错误 ${d.errcode}: ${d.errmsg || ''}`)
  }
  if (!d || !d.openid) throw new Error('无法获取微信 openid')
  return { openid: d.openid, unionid: d.unionid }
}

/** 检查用户是否存在（Admin API 列表过滤） */
async function findUserByEmail(email: string): Promise<boolean> {
  const filter = `email.eq."${email}"`
  const url = `${SUPABASE_URL}/auth/v1/admin/users?per_page=1&filter=${encodeURIComponent(filter)}`
  const res = await fetch(url, {
    headers: { apikey: SERVICE_ROLE, Authorization: `Bearer ${SERVICE_ROLE}` },
  })
  if (!res.ok) return false
  const data = await res.json().catch(() => ({ users: [] }))
  const users = Array.isArray(data?.users) ? data.users : []
  return users.length > 0
}

/** 创建微信登录用户（Admin API），邮箱已确认 */
async function createUser(email: string, password: string, type: string): Promise<void> {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      apikey: SERVICE_ROLE,
      Authorization: `Bearer ${SERVICE_ROLE}`,
    },
    body: JSON.stringify({
      email,
      password,
      email_confirm: true,
      user_metadata: { provider: 'wechat', wx_type: type },
    }),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({}))
    // 已存在则可忽略（并发创建）
    if (err?.message && /already exists/i.test(err.message)) return
    throw new Error(err?.message || '创建微信用户失败')
  }
}

/** 密码授权签发会话令牌（使用 anon key，避免暴露 service_role） */
async function signInWithPassword(
  email: string,
  password: string
): Promise<{ access_token: string; refresh_token: string; expires_in: number }> {
  const res = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      apikey: SUPABASE_ANON_KEY,
      Authorization: `Bearer ${SUPABASE_ANON_KEY}`,
    },
    body: JSON.stringify({ email, password }),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) {
    throw new Error(data?.error_description || data?.error || '微信登录签发会话失败')
  }
  if (!data.access_token || !data.refresh_token) {
    throw new Error('微信登录签发会话返回异常')
  }
  return {
    access_token: data.access_token,
    refresh_token: data.refresh_token,
    expires_in: data.expires_in || 3600,
  }
}

serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response('ok', { headers: corsHeaders })
  if (req.method !== 'POST') return json({ error: '仅支持 POST' }, 405)

  try {
    if (!SUPABASE_URL || !SERVICE_ROLE) {
      return json({ error: '服务端未配置 Supabase 密钥' }, 500)
    }
    const { type, code } = await req.json().catch(() => ({}) as any)
    if (!type || !code) return json({ error: '缺少参数 type / code' }, 400)

    const { openid, unionid } = await exchangeOpenid(type, code)
    const suffix = unionid ? `u_${unionid}` : `${type}_${openid}`
    const email = `wx_${suffix}@allfund.wechat`
    const password = 'wx' + (await sha256Hex(openid + ':' + (PEPPER || 'allfund')))
    if (password.length < 6) throw new Error('派生密码长度不足')

    const exists = await findUserByEmail(email)
    if (!exists) await createUser(email, password, type)

    const session = await signInWithPassword(email, password)
    return json({
      access_token: session.access_token,
      refresh_token: session.refresh_token,
      expires_in: session.expires_in,
      email,
    })
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e)
    return json({ error: msg }, 400)
  }
})
