/**
 * 数据中心私有下载
 * ------------------------------------------------------------------
 * 所有导出的 xlsx / json 都存放在 Supabase Storage 的**私有桶** downloads 中，
 * 只有「已登录 且 具备管理员权限」的账户可以读取
 * （RLS 策略见 scripts/sql/downloads_bucket_private.sql）。
 *
 * 为什么不用「直链 + <a download>」：
 *   直链 = 匿名可下载，这正是本次要修掉的漏洞。
 * 为什么不直接把浏览器跳到 Supabase 签名 URL：
 *   国内直连 *.supabase.co 不稳定，全站 Supabase 流量都走同源 /api/sb-proxy
 *   （见 src/api/supabase.js 的 rewriteToProxy）。
 * 因此这里采用「带会话 JWT 的分片 Range 请求」经同源代理取回字节流：
 *   分片 2 MB，既避开 EdgeOne 函数约 5 MB 的请求体上限与 15~17 s 平台强杀，
 *   也让大文件（当前最大 7.6 MB）下载更稳，并能回报进度。
 */
import { supabase, getSupabaseAnonKey, rewriteSupabaseUrl } from './supabase'

const CHUNK_SIZE = 2 * 1024 * 1024
const XLSX_MIME = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

function objectUrl(name) {
  const base = (import.meta.env.VITE_SUPABASE_URL || '').replace(/\/$/, '')
  return rewriteSupabaseUrl(`${base}/storage/v1/object/downloads/${encodeURIComponent(name)}`)
}

async function sessionToken() {
  if (!supabase) throw new Error('登录服务未就绪')
  const { data } = await supabase.auth.getSession()
  const token = data && data.session && data.session.access_token
  if (!token) throw new Error('未登录，无法下载')
  return token
}

/**
 * 取回私有桶里的文件，返回 Blob。
 * @param {string} name 对象名，如 `fund_scores.xlsx`
 * @param {(ratio:number)=>void} [onProgress] 进度回调，0~1
 */
export async function fetchPrivateFile(name, onProgress) {
  const token = await sessionToken()
  const anon = getSupabaseAnonKey()
  const url = objectUrl(name)

  const get = (range) => {
    const headers = { apikey: anon, Authorization: 'Bearer ' + token }
    if (range) headers.Range = range
    return fetch(url, { headers })
  }

  const resp = await get('bytes=0-' + (CHUNK_SIZE - 1))
  if (!resp.ok) {
    let detail = ''
    try {
      const j = await resp.json()
      detail = j.error || j.message || ''
    } catch (_) {
      /* 非 JSON 响应，忽略 */
    }
    if (resp.status === 400 && /NoSuchKey|not_found/i.test(detail)) {
      throw new Error('该文件暂未生成')
    }
    if (resp.status === 400 || resp.status === 401 || resp.status === 403) {
      throw new Error('当前账户没有下载权限（需管理员权限）')
    }
    throw new Error('下载失败（HTTP ' + resp.status + '）' + (detail ? '：' + detail : ''))
  }

  const parts = []
  const total = (() => {
    if (resp.status !== 206) return null
    const m = /\/(\d+)\s*$/.exec(resp.headers.get('Content-Range') || '')
    return m ? parseInt(m[1], 10) : null
  })()

  let buf = await resp.arrayBuffer()
  parts.push(buf)
  let received = buf.byteLength
  if (onProgress && total) onProgress(received / total)

  while (total && received < total) {
    const end = Math.min(received + CHUNK_SIZE - 1, total - 1)
    const r = await get('bytes=' + received + '-' + end)
    if (!r.ok) throw new Error('下载中断（HTTP ' + r.status + '）')
    buf = await r.arrayBuffer()
    if (!buf.byteLength) break
    parts.push(buf)
    received += buf.byteLength
    if (onProgress) onProgress(Math.min(received / total, 1))
  }

  if (onProgress) onProgress(1)
  return new Blob(parts, { type: XLSX_MIME })
}

/** 触发浏览器另存为 */
export function saveBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(url), 4000)
}
