const fs = require('fs')
const { createClient } = require('/Users/maoshanbo/WorkBuddy/20260405093252/allfund/node_modules/@supabase/supabase-js/dist/index.cjs')

const env = {}
for (const raw of fs.readFileSync('/Users/maoshanbo/WorkBuddy/20260405093252/allfund/.env.local', 'utf8').split('\n')) {
  const s = raw.replace(/\r$/, '').trim()
  if (s.includes('=') && !s.startsWith('#')) {
    const i = s.indexOf('=')
    env[s.slice(0, i).trim()] = s.slice(i + 1).trim()
  }
}
const URL = (env.VITE_SUPABASE_URL || '').replace(/\s/g, '')
const ANON = (env.VITE_SUPABASE_ANON_KEY || '').replace(/\s/g, '')
console.log('URL quoted=', JSON.stringify(URL), 'len=', URL.length)
console.log('ANON len=', ANON.length)

;(async () => {
  let sb
  try {
    sb = createClient(URL, ANON)
  } catch (e) {
    console.log('createClient threw:', e.message)
    return
  }
  try {
    const { data, error } = await sb.from('fund_scores_meta')
      .select('nav_date,total_count,scored_count,tsq,update_time')
      .order('tsq', { ascending: false }).limit(1).single()
    console.log('PRIMARY error=', error && error.message)
    console.log('PRIMARY data=', JSON.stringify(data))
  } catch (e) {
    console.log('PRIMARY threw:', e.message)
  }
  try {
    const { data, error } = await sb.from('fund_scores_meta')
      .select('nav_date,tsq,update_time').limit(1)
    console.log('PRIMARY(no single) error=', error && error.message, 'rows=', data && data.length)
  } catch (e) {
    console.log('PRIMARY2 threw:', e.message)
  }
})()
