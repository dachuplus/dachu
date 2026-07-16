import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

function json(o: any, status = 200) {
  return new Response(JSON.stringify(o), { status, headers: { 'Content-Type': 'application/json' } })
}

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
    if (userData.user.email !== '57502460@qq.com') return json({ error: 'forbidden' }, 403)

    const body = await req.json().catch(() => ({}))
    const email = body.email
    if (!email) return json({ error: 'email required' }, 400)

    const admin = createClient(
      Deno.env.get('SUPABASE_URL')!,
      Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!
    )
    const { data: list } = await admin.auth.admin.listUsers({ page: 1, perPage: 1000 })
    const found = (list?.users || []).find((u: any) => u.email === email)
    if (!found) return json({ error: 'user not found' }, 404)

    const { error: de } = await admin.auth.admin.deleteUser(found.id)
    if (de) return json({ error: de.message }, 500)

    return json({ ok: true, deleted: email })
  } catch (e) {
    return json({ error: String(e) }, 500)
  }
})
