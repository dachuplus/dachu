/**
 * Supabase Edge Function - 数据代理
 *
 * 在服务端抓取公开数据源，解析返回 JSON，解决前端 CORS 限制
 * - value500.com：HTML 页面解析 (bond/shibor/m2/cpi/ep/pe300)
 * - 蛋卷基金估值中心：JSON API 透传 (danjuan)
 *
 * 部署：supabase functions deploy value500
 * 调用：POST /functions/v1/value500 { "pages": ["bond","shibor","danjuan"] }
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const PAGE_MAP = {
  bond:    'http://www.value500.com/10Bond.html',
  shibor:  'http://www.value500.com/Shibor.asp',
  m2:      'http://www.value500.com/M1.asp',
  cpi:     'http://www.value500.com/CPI.asp',
  ep:      'http://www.value500.com/ep.asp',
  pe300:   'http://www.value500.com/000300SHPEPB.asp',
  danjuan: 'https://danjuanfunds.com/djapi/index_eva/dj'
}

// 蛋卷数据缓存（减少 API 压力）
const DANJUAN_CACHE_TTL = 6 * 60 * 60 * 1000 // 6小时
let danjuanCache = null as { data: any; ts: number } | null

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

// ========== 解析函数 ==========

function parseBondYield(html) {
  const S = '[\\s\\u3000]*'
  const match = html.match(new RegExp(
    "(\\d{4}年\\d{1,2}月\\d{1,2}日)" + S + "国债到期收益率" + S +
    "1年期[：:]([\\d.]+)％[；;][^]*?5年期[：:]([\\d.]+)％[；;][^]*?10年期[：:]([\\d.]+)％"
  ))
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  const y1 = parseFloat(match[2]) / 100
  const y5 = parseFloat(match[3]) / 100
  const y10 = parseFloat(match[4]) / 100
  return { code: 0, data: { date: match[1], yield1y: y1, yield5y: y5, yield10y: y10, spread: Math.round((y10 - y1) * 10000) / 100 } }
}

function parseShibor(html) {
  const match = html.match(/(\d{4}年\d{1,2}月\d{1,2}日)\s*O\/N[：:]([\d.]+)％\s*1W[：:]([\d.]+)％\s*1M[：:]([\d.]+)％\s*1Y[：:]([\d.]+)％/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  return { code: 0, data: { date: match[1], on: parseFloat(match[2]) / 100, w1: parseFloat(match[3]) / 100, m1: parseFloat(match[4]) / 100, y1: parseFloat(match[5]) / 100 } }
}

function parseM2(html) {
  const match = html.match(/(\d{4}年\d{1,2}月)\s*M1增速[：:]([\d.\-]+)％[；;]\s*M2增速[：:]([\d.\-]+)％/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  const m1yoy = parseFloat(match[2])
  const m2yoy = parseFloat(match[3])
  return { code: 0, data: { date: match[1], m1yoy, m2yoy, m1m2diff: Math.round((m1yoy - m2yoy) * 10) / 10 } }
}

function parseCPI(html) {
  const match = html.match(/(\d{4}年\d{1,2}月)\s*CPI同比[：:]([\d.\-]+)%/)
  if (!match) return { code: -1, data: null, msg: '解析失败' }
  return { code: 0, data: { date: match[1], cpi: parseFloat(match[2]) / 100 } }
}

function parsePE300(html) {
  const S = '[\\s\\u3000]*'
  const peMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300滚动市盈率[：:]([\\d.]+)"))
  const pePctMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市盈率百分位（近五年）[：:]([\\d.]+)%?\\s*'"))
  const pbMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市净率[：:]([\\d.]+)"))
  const pbPctMatch = html.match(new RegExp("text\\s*:\\s*'\\d{4}年\\d{1,2}月\\d{1,2}日" + S + "沪深300市净率百分位（近五年）[：:]([\\d.]+)%?\\s*'"))
  const dateMatch = html.match(new RegExp("(\\d{4}年\\d{1,2}月\\d{1,2}日)" + S + "沪深300滚动市盈率"))
  if (!peMatch) return { code: -1, data: null, msg: '解析失败' }
  return { code: 0, data: { date: dateMatch ? dateMatch[1] : '', pe: parseFloat(peMatch[1]), pePercentile: pePctMatch ? parseFloat(pePctMatch[1]) : null, pb: pbMatch ? parseFloat(pbMatch[1]) : null, pbPercentile: pbPctMatch ? parseFloat(pbPctMatch[1]) : null } }
}

function parseEP(html) {
  const dateMatch = html.match(/(\d{4}年\d{1,2}月\d{1,2}日)\s*上交所股债收益率比[：:]([\d.]+)/)
  const szMatch = html.match(/深交所股债收益率比[：:]([\d.]+)/)
  if (!dateMatch) return { code: -1, data: null, msg: '解析失败' }
  return { code: 0, data: { date: dateMatch[1], shRatio: parseFloat(dateMatch[2]), szRatio: szMatch ? parseFloat(szMatch[1]) : null } }
}

// ========== 蛋卷基金估值解析（JSON 透传 + 字段映射）==========
function parseDanjuan(jsonStr: string) {
  try {
    const json = JSON.parse(jsonStr)
    if (!json.data || !json.data.items) return { code: -1, data: null, msg: '蛋卷数据格式异常' }
    const items = json.data.items.map((item: any) => ({
      name:         item.name,
      code:         item.index_code,
      ttype:        item.ttype,
      pe:           item.pe > 0            ? item.pe           : null,
      pePercentile:  item.pe_percentile > 0 ? Math.round(item.pe_percentile * 10000) / 100 : null,
      pb:           item.pb > 0            ? item.pb           : null,
      pbPercentile: item.pb_percentile > 0 ? Math.round(item.pb_percentile * 10000) / 100 : null,
      dividendYield: item.yeild > 0          ? Math.round(item.yeild * 10000) / 100   : null,
      roe:          item.roe > 0           ? Math.round(item.roe * 10000) / 100    : null,
      peg:          item.peg > 0           ? item.peg          : null,
      evaType:      item.eva_type || '',
      date:          item.date || '',
    }))
    return { code: 0, data: items, total: items.length, source: 'danjuanfunds.com' }
  } catch (e) {
    return { code: -1, data: null, msg: '蛋卷 JSON 解析失败: ' + e.message }
  }
}

const PARSERS = {
  bond:   parseBondYield,
  shibor: parseShibor,
  m2:     parseM2,
  cpi:    parseCPI,
  pe300:  parsePE300,
  ep:     parseEP,
  danjuan: parseDanjuan,
}

serve(async (req) => {
  // Handle CORS preflight
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  try {
    const { pages = ['bond', 'shibor', 'm2', 'cpi', 'ep', 'pe300'] } = await req.json()

    // 并行抓取所有页面
    const results = {}
    const promises = pages.map(async (key) => {
      // --- 蛋卷估值：JSON API + 缓存 ---
      if (key === 'danjuan') {
        const now = Date.now()
        if (danjuanCache && (now - danjuanCache.ts) < DANJUAN_CACHE_TTL) {
          results[key] = { code: 0, data: danjuanCache.data, total: danjuanCache.data.length, source: 'danjuanfunds.com', cached: true }
          return
        }
        try {
          const res = await fetch(PAGE_MAP[key], { signal: AbortSignal.timeout(8000) })
          const jsonStr = await res.text()
          const parsed = parseDanjuan(jsonStr)
          if (parsed.code === 0 && parsed.data) {
            danjuanCache = { data: parsed.data, ts: now }
          }
          results[key] = parsed
        } catch (err) {
          // 有缓存时降级返回缓存
          if (danjuanCache) {
            results[key] = { code: 0, data: danjuanCache.data, total: danjuanCache.data.length, source: 'danjuanfunds.com', cached: true, warning: '使用缓存数据' }
          } else {
            results[key] = { code: -1, data: null, msg: err.message }
          }
        }
        return
      }

      // --- value500 / 其他 HTML 页面 ---
      const url = PAGE_MAP[key]
      const parser = PARSERS[key]
      if (!url || !parser) {
        results[key] = { code: -1, data: null, msg: '未知页面' }
        return
      }
      try {
        const res = await fetch(url, {
          headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
          signal: AbortSignal.timeout(8000)
        })
        const html = await res.text()
        results[key] = parser(html)
      } catch (err) {
        results[key] = { code: -1, data: null, msg: err.message }
      }
    })

    await Promise.all(promises)

    return new Response(JSON.stringify(results), {
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  } catch (err) {
    return new Response(JSON.stringify({ error: err.message }), {
      status: 500,
      headers: { ...corsHeaders, 'Content-Type': 'application/json' }
    })
  }
})
