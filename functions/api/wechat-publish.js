/**
 * EdgeOne Pages Function — 微信公众号同步发布代理
 * 路由：POST /api/wechat-publish
 *
 * 安全说明：AppSecret 仅在此函数内使用，不落库、不返回前端。
 * 流程：检测出口IP → 获取 access_token → 创建草稿 → 发布 → 返回结果（含实际出口IP）。
 *
 * 微信 API 文档：
 *   - 获取 token: GET https://api.weixin.qq.com/cgi-bin/token
 *   - 新建草稿: POST https://api.weixin.qq.com/cgi-bin/draft/add
 *   - 发布:     POST https://api.weixin.qq.com/cgi-bin/freepublish/submit
 */

const WECHAT_API_BASE = 'https://api.weixin.qq.com'

/**
 * 检测当前函数的出口公网 IP（与后续微信 API 调用使用同一连接）
 */
async function detectEgressIP() {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 5000)
    const res = await fetch('https://ipinfo.io/json', {
      signal: controller.signal,
      headers: { 'Accept': 'application/json' },
    })
    clearTimeout(timer)
    const data = await res.json()
    return data.ip || null
  } catch (_) {
    // 备用：用 ifconfig.me
    try {
      const res = await fetch('https://ifconfig.me', { signal: AbortSignal.timeout(3000) })
      return await res.text()
    } catch (__) {
      return null
    }
  }
}

/**
 * 将 Markdown 正文转为微信公众号支持的 HTML（简化版）。
 */
function markdownToWechatHtml(md) {
  if (!md) return ''
  let html = md
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      '<pre style="background:#f5f5f5;padding:12px;border-radius:4px;overflow-x:auto;font-size:14px;line-height:1.6;"><code>' + escapeHtml(code.trim()) + '</code></pre>'
    )
    .replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;font-size:14px;">$1</code>')
    .replace(/^#### (.+)$/gm, '<h4 style="font-size:16px;font-weight:bold;margin:16px 0 8px;">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:18px;font-weight:bold;margin:18px 0 8px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:20px;font-weight:bold;margin:20px 0 10px;">$2</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size:22px;font-weight:bold;margin:22px 0 10px;">$1</h1>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#1d70b8;text-decoration:none;">$1</a>')
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;display:block;" />')
    .replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:4px solid #b1b4b6;padding:8px 14px;color:#505050;margin:8px 0;">$1</blockquote>')
    .replace(/^- (.+)$/gm, '<li style="margin:4px 0;list-style:disc inside;">$1</li>')
    .replace(/^\d+\. (.+)$/gm, '<li style="margin:4px 0;list-style:decimal inside;">$1</li>')
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;" />')
    .replace(/\n\n+/g, '</p><p style="margin:12px 0;font-size:15px;line-height:1.8;">')
    .replace(/\n/g, '<br />')

  if (!html.startsWith('<')) {
    html = '<p style="margin:12px 0;font-size:15px;line-height:1.8;">' + html + '</p>'
  }
  return html
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

/** 获取微信 access_token */
async function getAccessToken(appId, appSecret) {
  const url = `${WECHAT_API_BASE}/cgi-bin/token?grant_type=client_credential&appid=${encodeURIComponent(appId)}&secret=${encodeURIComponent(appSecret)}`
  const res = await fetch(url, { method: 'GET' })
  const data = await res.json()
  if (data.errcode && data.errcode !== 0) {
    throw new Error(`[ ${data.errcode} ] ${data.errmsg || '未知错误'}`)
  }
  if (!data.access_token) throw new Error('未返回 access_token')
  return data.access_token
}

/** 创建草稿并返回 media_id */
async function createDraft(accessToken, title, content, summary, coverImage, author) {
  const articles = [{
    title,
    author: author || '',
    digest: summary || '',
    content,
    thumb_media_id: '',
    need_open_comment: 0,
    only_fans_can_comment: 0,
  }]
  const res = await fetch(`${WECHAT_API_BASE}/cgi-bin/draft/add?access_token=${accessToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ articles }),
  })
  const data = await res.json()
  if (data.errcode && data.errcode !== 0) {
    throw new Error(`[ ${data.errcode} ] ${data.errmsg || '未知错误'}`)
  }
  return data.media_id
}

/** 发布草稿 */
async function publishDraft(accessToken, mediaId) {
  const res = await fetch(`${WECHAT_API_BASE}/cgi-bin/freepublish/submit?access_token=${accessToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_id: mediaId }),
  })
  const data = await res.json()
  if (data.errcode && data.errcode !== 0) {
    throw new Error(`[ ${data.errcode} ] ${data.errmsg || '未知错误'}`)
  }
  return data
}

export async function onRequestPost(context) {
  // 先检测出口 IP（在微信调用之前，确保同一连接上下文）
  const egressIP = await detectEgressIP()

  try {
    const body = await context.request.json()
    const { appid, appsecret, title, content, summary, cover_image, author } = body

    if (!appid || !appsecret) {
      return jsonResp({ success: false, error: '缺少 AppID 或 AppSecret', egress_ip: egressIP }, 400)
    }
    if (!title || !content) {
      return jsonResp({ success: false, error: '缺少标题或正文', egress_ip: egressIP }, 400)
    }

    // 1. Markdown → 公众号 HTML
    const htmlContent = markdownToWechatHtml(content)

    // 2. 获取 access_token
    const token = await getAccessToken(appid, appsecret)

    // 3. 创建草稿
    const mediaId = await createDraft(token, title, htmlContent, summary, cover_image, author)

    // 4. 发布
    const publishResult = await publishDraft(token, mediaId)

    return jsonResp({
      success: true,
      publish_result: publishResult,
      media_id: mediaId,
      message: `已成功推送到公众号（publish_id: ${publishResult.publish_id}）`,
      egress_ip: egressIP,
    })

  } catch (err) {
    let errorMsg = err.message || String(err)
    // 常见错误码友好提示（保留原始错误码便于排查）
    if (errorMsg.indexOf('40164') !== -1) {
      errorMsg = `IP 白名单校验失败（40164）。本次请求出口 IP：${egressIP || '未知'}。请将此 IP 加入公众号「设置与开发→基本配置→IP白名单」后立即重试。`
    } else if (errorMsg.indexOf('40013') !== -1) {
      errorMsg = 'AppID 不正确（40013），请检查后重试。'
    } else if (errorMsg.indexOf('40125') !== -1) {
      errorMsg = 'AppSecret 不正确（40125），请检查后重试。'
    } else if (errorMsg.indexOf('48001') !== -1) {
      errorMsg = '该账号未开通群发权限（48001）。个人未认证号可能不支持接口群发，建议改为仅创建草稿、手动去公众号后台发布。'
    } else if (errorMsg.indexOf('40001') !== -1) {
      errorMsg = 'access_token 无效或过期（40001），请稍后重试。'
    }

    return jsonResp({
      success: false,
      error: errorMsg,
      egress_ip: egressIP,
    }, 500)
  }
}

function jsonResp(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}
