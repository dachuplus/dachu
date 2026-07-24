import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

function json(o: any, status = 200) {
  return new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json' } })
}

// 主管理员邮箱（与网页版 ADMIN_EMAIL 一致）
const ADMIN_EMAIL = '57502460@qq.com'
// 重置后的默认密码
const DEFAULT_PASSWORD = '123456'

Deno.serve(async (req: Request) => {
  try {
    const authHeader = req.headers.get('Authorization') || ''
    const supabase = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_ANON_KEY')!,
      { global: { headers: { Authorization: authHeader } } }
    )
    const { data: userData, error: ue } = await supabase.auth.getUser()
    if (ue || !userData.user) return json({ error: 'unauthorized' }, 401)

    const callerEmail = userData.user.email || ''

    // 管理员校验：主管理员邮箱 或 数据库 user_permissions.is_admin（service_role 直读，绕过 RLS）
    const admin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )
    let isAdmin = callerEmail === ADMIN_EMAIL
    if (!isAdmin) {
      const { data: perm } = await admin
        .from('user_permissions')
        .select('is_admin')
        .eq('user_email', callerEmail)
        .maybeSingle()
      isAdmin = !!perm?.is_admin
    }
    if (!isAdmin) return json({ error: 'forbidden' }, 403)

    const body = await req.json().catch(() => ({}))
    const email = body.email
    if (!email) return json({ error: 'email required' }, 400)
    // 不允许重置主管理员自身密码（防止误锁主账号）
    if (email === ADMIN_EMAIL) return json({ error: 'cannot reset main admin password here' }, 400)

    const { data: list } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 })
    const found = (list?.users || []).find((u: any) => u.email === email)
    if (!found) return json({ error: 'user not found' }, 404)

    // 清除旧密码并重置为默认密码 123456，同时确认邮箱（避免登录后要求重新验证）
    const { error: pe } = await admin.auth.admin.updateUserById(found.id, {
      password: DEFAULT_PASSWORD,
      email_confirm: true,
    })
    if (pe) return json({ error: pe.message }, 500)

    return json({ ok: true, email, note: 'password has been reset to default 123456' })
  } catch (e) {
    return json({ error: String(e) }, 500)
  }
})
