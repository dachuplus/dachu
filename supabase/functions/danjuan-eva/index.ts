/**
 * Supabase Edge Function - 蛋卷指数估值代理（独立，不依赖 value500）
 *
 * 行业估值数据源：蛋卷估值中心 JSON API
 *   https://danjuanfunds.com/djapi/index_eva/dj
 * 一次返回全部 63 个指数的 PE/PB/股息率/ROE 及历史百分位（蛋卷已算好，无需本地计算）。
 *
 * 该端点仅做“服务端代理抓取 + 缓存”，把蛋卷原始 JSON 透传回前端，
 * 由前端 fetchDanjuanEva() 统一解析。不落库、不解析 value500.com（该站已无法访问）。
 *
 * 部署：
 *   supabase functions deploy danjuan-eva --no-verify-jwt
 * 调用（GET）：
 *   /functions/v1/danjuan-eva
 * 返回：蛋卷原始 JSON { data: { items: [...] }, result_code }
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const DANJUAN_URL = 'https://danjuanfunds.com/djapi/index_eva/dj'
const CACHE_TTL = 6 * 60 * 60 * 1000 // 6 小时

let cache: { body: string; ts: number } | null = null

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const now = Date.now()
    // 命中缓存：直接返回蛋卷原始 JSON
    if (cache && now - cache.ts < CACHE_TTL) {
      return new Response(cache.body, {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }

    const res = await fetch(DANJUAN_URL, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
      signal: AbortSignal.timeout(8000),
    })
    if (!res.ok) throw new Error('蛋卷 HTTP ' + res.status)
    const body = await res.text()
    // 轻量校验：必须是合法 JSON，避免缓存异常响应
    JSON.parse(body)
    cache = { body, ts: now }

    return new Response(body, {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  } catch (err) {
    // 抓取失败但有缓存：降级返回上次成功结果
    if (cache) {
      return new Response(cache.body, {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }
    return new Response(JSON.stringify({ error: String(err?.message || err) }), {
      status: 502,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' },
    })
  }
})
