/**
 * EdgeOne Pages Function — 检测当前出口公网 IP
 * 路由：GET /api/detect-ip → functions/api/detect-ip.js
 *
 * 用途：发布前检测 EdgeOne 函数的出站 IP，方便用户填入微信白名单。
 * 注意：EdgeOne 出口 IP 是动态共享池，每次请求可能不同。
 */
export async function onRequest(context) {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    const res = await fetch('https://ipinfo.io/json', {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
    })
    clearTimeout(timer)
    const data = await res.json()
    return new Response(JSON.stringify({
      ip: data.ip,
      city: data.city,
      region: data.region,
      country: data.country,
      org: data.org,
      ts: new Date().toISOString(),
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  } catch (e) {
    return new Response(JSON.stringify({ error: String(e) }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
