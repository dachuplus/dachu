/**
 * Supabase Edge Function - 宏观参考数据聚合代理（替代已失效的 value500.com）
 *
 * 聚合下列公开数据源，服务端抓取 + 单位换算 + 缓存，返回扁平 JSON：
 *   1. 国债收益率曲线（10Y + 10Y-2Y 利差）  → 东方财富数据中心 RPTA_WEB_TREASURYYIELD
 *   2. Shibor 隔夜(O/N)                     → 东方财富数据中心 RPT_IMP_INTRESTRATEN
 *   3. M2 同比                              → 东方财富数据中心 RPT_ECONOMY_CURRENCY_SUPPLY
 *   4. CPI 同比                             → 东方财富数据中心 RPT_ECONOMY_CPI
 *   5. PMI（制造业）                        → 东方财富数据中心 RPT_ECONOMY_PMI
 *   6. 沪深300 PE / 百分位                  → 蛋卷估值中心 djapi/index_eva/dj
 *
 * value500.com 已无法访问，本函数是信号页/组合页宏观基准的唯一数据来源。
 * 各源独立抓取，单源失败不影响其余（返回 null 字段，前端按空值优雅降级）。
 *
 * 部署：
 *   supabase functions deploy macro-data --no-verify-jwt
 * 调用（GET，免鉴权，CORS 已开放）：
 *   /functions/v1/macro-data
 */

import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'

const CACHE_TTL = 30 * 60 * 1000 // 30 分钟
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'

let cache: { body: string; ts: number } | null = null

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

// ===== 东财数据中心 GET 封装 =====
async function fetchEastmoney(url: string): Promise<any[]> {
  const res = await fetch(url, {
    headers: { 'User-Agent': UA, 'Referer': 'https://data.eastmoney.com/' },
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error('HTTP ' + res.status)
  const j = await res.json()
  if (!j?.result?.data) throw new Error('空数据')
  return j.result.data as any[]
}

// 1. 国债收益率（10Y + 10Y-2Y 利差），单位：百分数
async function getBond() {
  const url =
    'https://datacenter.eastmoney.com/api/data/get?type=RPTA_WEB_TREASURYYIELD&sty=ALL&st=SOLAR_DATE&sr=-1&p=1&ps=3&source=WEB&client=WEB'
  const rows = await fetchEastmoney(url)
  const row = rows[0] || {}
  return {
    date: row.SOLAR_DATE || '',
    // EMM00166466 = 10Y 收益率（百分数，约 1.68）→ 转小数 0.0168
    yield10y: typeof row.EMM00166466 === 'number' ? row.EMM00166466 / 100 : null,
    // EMM01276014 = 10Y-2Y 期限利差（百分点，约 0.45）→ 原值保留
    spread: typeof row.EMM01276014 === 'number' ? row.EMM01276014 : null,
  }
}

// 2. Shibor 隔夜(O/N)，单位：百分数 → 小数
async function getShibor() {
  const url =
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_IMP_INTRESTRATEN&columns=REPORT_DATE,REPORT_PERIOD,MARKET,IR_RATE&pageSize=10&sortColumns=REPORT_DATE&sortTypes=-1'
  const rows = await fetchEastmoney(url)
  const row = rows.find(
    (r) => r.MARKET === '上海银行同业拆借市场' && r.REPORT_PERIOD === '隔夜(O/N)'
  )
  if (!row) throw new Error('未找到 Shibor 隔夜')
  return {
    date: row.REPORT_DATE || '',
    on: typeof row.IR_RATE === 'number' ? row.IR_RATE / 100 : null,
  }
}

// 3. M2 同比（百分数，约 4）→ 原值保留
async function getM2() {
  const url =
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_CURRENCY_SUPPLY&columns=REPORT_DATE,CURRENCY_SAME&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1'
  const rows = await fetchEastmoney(url)
  const row = rows[0] || {}
  return {
    date: row.REPORT_DATE || '',
    m2yoy: typeof row.CURRENCY_SAME === 'number' ? row.CURRENCY_SAME : null,
  }
}

// 4. CPI 同比（百分数，约 0.5）→ 转小数 0.005
async function getCpi() {
  const url =
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_CPI&columns=REPORT_DATE,NATIONAL_SAME&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1'
  const rows = await fetchEastmoney(url)
  const row = rows[0] || {}
  return {
    date: row.REPORT_DATE || '',
    cpi: typeof row.NATIONAL_SAME === 'number' ? row.NATIONAL_SAME / 100 : null,
  }
}

// 5. PMI（制造业，约 49.2）→ 原值保留
async function getPmi() {
  const url =
    'https://datacenter-web.eastmoney.com/api/data/v1/get?reportName=RPT_ECONOMY_PMI&columns=REPORT_DATE,MAKE_INDEX&pageSize=1&sortColumns=REPORT_DATE&sortTypes=-1'
  const rows = await fetchEastmoney(url)
  const row = rows[0] || {}
  return {
    date: row.REPORT_DATE || '',
    pmi: typeof row.MAKE_INDEX === 'number' ? row.MAKE_INDEX : null,
  }
}

// 6. 沪深300 估值（蛋卷），百分位小数 → 百分数
async function getPe300() {
  const res = await fetch('https://danjuanfunds.com/djapi/index_eva/dj', {
    headers: { 'User-Agent': UA },
    signal: AbortSignal.timeout(8000),
  })
  if (!res.ok) throw new Error('蛋卷 HTTP ' + res.status)
  const j = await res.json()
  const items: any[] = j?.data?.items || []
  const hs = items.find((it) => it.index_code === 'SH000300') ||
    items.find((it) => (it.name || '').includes('沪深300'))
  if (!hs) throw new Error('蛋卷无沪深300')
  return {
    date: hs.date || '',
    pe: typeof hs.pe === 'number' ? hs.pe : null,
    pePercentile: typeof hs.pe_percentile === 'number'
      ? Math.round(hs.pe_percentile * 10000) / 100
      : null,
    pb: typeof hs.pb === 'number' ? hs.pb : null,
  }
}

// ===== 聚合（各源独立，单源失败降级为空） =====
async function collect() {
  const [bond, shibor, m2, cpi, pmi, pe300] = await Promise.allSettled([
    getBond(),
    getShibor(),
    getM2(),
    getCpi(),
    getPmi(),
    getPe300(),
  ])
  const pick = (r: PromiseSettledResult<any>, fb: any) =>
    r.status === 'fulfilled' ? r.value : fb

  return {
    bond: pick(bond, { date: '', yield10y: null, spread: null }),
    shibor: pick(shibor, { date: '', on: null }),
    m2: pick(m2, { date: '', m2yoy: null }),
    cpi: pick(cpi, { date: '', cpi: null }),
    pmi: pick(pmi, { date: '', pmi: null }),
    pe300: pick(pe300, { date: '', pe: null, pePercentile: null, pb: null }),
  }
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }
  try {
    const now = Date.now()
    // 命中缓存：直接返回聚合结果
    if (cache && now - cache.ts < CACHE_TTL) {
      return new Response(cache.body, {
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }

    const data = await collect()
    const body = JSON.stringify(data)
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
