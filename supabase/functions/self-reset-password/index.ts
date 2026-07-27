import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

function json(o: any, status = 200) {
  return new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json' } })
}

// 重置后的默认密码（与后台 admin-reset-password 保持一致）
const DEFAULT_PASSWORD = '123456'
// 主管理员邮箱（受保护，不允许公开自助重置）
const ADMIN_EMAIL = '57502460@qq.com'

// 手机号规范化：11 位大陆号补 +86；已带 + 的保留
function normalizePhone(v: string): string {
  v = (v || '').replace(/[\s-]/g, '')
  if (v.startsWith('+')) return v
  if (v.startsWith('86') && v.length === 13) return '+' + v
  if (/^1\d{10}$/.test(v)) return '+86' + v
  return v
}

// 将任意标识符（手机号/邮箱）解析为候选 auth 邮箱列表。
// 手机号走合成邮箱（新账号 @dachu.user，历史账号 @allfund.user），逐一匹配兼容。
function resolveCandidateEmails(identifier: string): string[] {
  const raw = (identifier || '').trim()
  const cleaned = raw.replace(/[\s-]/g, '')
  if (/^\+?1\d{10}$/.test(cleaned) || /^\+861\d{10}$/.test(cleaned)) {
    const phone = normalizePhone(raw).replace(/^\+/, '')
    return [`${phone}@dachu.user`, `${phone}@allfund.user`]
  }
  return [raw]
}

Deno.serve(async (req: Request) => {
  try {
    if (req.method !== 'POST') return json({ error: 'method not allowed' }, 405)

    const body = await req.json().catch(() => ({}))
    const identifier = (body.identifier || '').trim()
    if (!identifier) return json({ error: 'identifier required' }, 400)

    const emails = resolveCandidateEmails(identifier)
    if (emails.length === 0 || emails.some((e) => !e)) {
      return json({ error: 'invalid identifier' }, 400)
    }

    const admin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )

    // 拉取用户列表，按候选邮箱逐一匹配（兼容新/旧账号域名）
    const { data: list, error: le } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 })
    if (le) return json({ error: le.message }, 500)

    const users = list?.users || []
    let found: any = null
    for (const email of emails) {
      const u = users.find((x: any) => x.email === email)
      if (u) { found = u; break }
    }
    if (!found) return json({ error: 'account not found' }, 404)

    // 保护主管理员账号，避免被公开接口锁定
    if (found.email === ADMIN_EMAIL) {
      return json({ error: 'cannot reset this account' }, 400)
    }

    // 重置为默认密码 123456，并确认邮箱（避免登录后再次要求验证）
    const { error: pe } = await admin.auth.admin.updateUserById(found.id, {
      password: DEFAULT_PASSWORD,
      email_confirm: true,
    })
    if (pe) return json({ error: pe.message }, 500)

    return json({ ok: true, email: found.email, note: 'password has been reset to default 123456' })
  } catch (e) {
    return json({ error: String(e) }, 500)
  }
})
