/**
 * EdgeOne Pages Function — 微信公众号同步发布代理
 * 路由：POST /api/wechat-publish  →  functions/api/wechat-publish.js
 *
 * 安全说明：AppSecret 仅在此函数内使用，不落库、不返回前端。
 * 流程：接收文章数据 + 凭证 → 获取 access_token → 创建草稿 → 发布 → 返回结果。
 *
 * 微信 API 文档：
 *   - 获取 token: GET https://api.weixin.qq.com/cgi-bin/token
 *   - 新建草稿: POST https://api.weixin.qq.com/cgi-bin/draft/add
 *   - 发布:     POST https://api.weixin.qq.com/cgi-bin/freepublish/submit
 */

const WECHAT_API_BASE = 'https://api.weixin.qq.com'

/**
 * 将 Markdown 正文转为微信公众号支持的 HTML（简化版）。
 * 公众号正文接受 HTML，这里做基础转换：标题、粗体、斜体、链接、图片、列表、引用、代码块。
 */
function markdownToWechatHtml(md) {
  if (!md) return ''
  let html = md
    // 代码块（``` ... ```）
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
      return '<pre style="background:#f5f5f5;padding:12px;border-radius:4px;overflow-x:auto;font-size:14px;line-height:1.6;"><code>' + escapeHtml(code.trim()) + '</code></pre>'
    })
    // 行内代码
    .replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;font-size:14px;">$1</code>')
    // 标题
    .replace(/^#### (.+)$/gm, '<h4 style="font-size:16px;font-weight:bold;margin:16px 0 8px;">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:18px;font-weight:bold;margin:18px 0 8px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:20px;font-weight:bold;margin:20px 0 10px;">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 style="font-size:22px;font-weight:bold;margin:22px 0 10px;">$1</h1>')
    // 粗体 + 斜体
    .replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // 链接
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" style="color:#1d70b8;text-decoration:none;">$1</a>')
    // 图片
    .replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" style="max-width:100%;display:block;" />')
    // 引用
    .replace(/^&gt; (.+)$/gm, '<blockquote style="border-left:4px solid #b1b4b6;padding:8px 14px;color:#505050;margin:8px 0;">$1</blockquote>')
    // 无序列表
    .replace(/^- (.+)$/gm, '<li style="margin:4px 0;list-style:disc inside;">$1</li>')
    // 有序列表
    .replace(/^\d+\. (.+)$/gm, '<li style="margin:4px 0;list-style:decimal inside;">$1</li>')
    // 分割线
    .replace(/^---$/gm, '<hr style="border:none;border-top:1px solid #ddd;margin:16px 0;" />')
    // 段落（连续文本）
    .replace(/\n\n+/g, '</p><p style="margin:12px 0;font-size:15px;line-height:1.8;">')
    .replace(/\n/g, '<br />')

  // 包裹在段落标签中
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
    throw new Error(`获取 access_token 失败: [${data.errcode}] ${data.errmsg || '未知错误'}`)
  }
  if (!data.access_token) {
    throw new Error('获取 access_token 失败: 未返回 token')
  }
  return data.access_token
}

/** 创建草稿并返回 media_id */
async function createDraft(accessToken, title, content, summary, coverImage, author) {
  const articles = [{
    title: title,
    author: author || '',
    digest: summary || '',
    content: content,
    thumb_media_id: '', // 可选，留空则使用默认头像
    need_open_comment: 0, // 不开启评论
    only_fans_can_comment: 0,
  }]

  const res = await fetch(`${WECHAT_API_BASE}/cgi-bin/draft/add?access_token=${accessToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ articles }),
  })
  const data = await res.json()
  if (data.errcode && data.errcode !== 0) {
    throw new Error(`创建草稿失败: [${data.errcode}] ${data.errmsg || '未知错误'}`)
  }
  return data.media_id
}

/** 发布草稿（已群发） */
async function publishDraft(accessToken, mediaId) {
  const res = await fetch(`${WECHAT_API_BASE}/cgi-bin/freepublish/submit?access_token=${accessToken}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ media_id: mediaId }),
  })
  const data = await res.json()
  if (data.errcode && data.errcode !== 0) {
    throw new Error(`发布失败: [${data.errcode}] ${data.errmsg || '未知错误'}`)
  }
  return data
}

export async function onRequestPost(context) {
  try {
    const body = await context.request.json()

    const { appid, appsecret, title, content, summary, cover_image, author } = body

    if (!appid || !appsecret) {
      return new Response(JSON.stringify({ success: false, error: '缺少 AppID 或 AppSecret' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    if (!title || !content) {
      return new Response(JSON.stringify({ success: false, error: '缺少标题或正文' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })
    }

    // 1. Markdown → 公众号 HTML
    const htmlContent = markdownToWechatHtml(content)

    // 2. 获取 access_token
    const token = await getAccessToken(appid, appsecret)

    // 3. 创建草稿
    const mediaId = await createDraft(token, title, htmlContent, summary, cover_image, author)

    // 4. 发布
    const publishResult = await publishDraft(token, mediaId)

    return new Response(JSON.stringify({
      success: true,
      publish_result: publishResult,
      media_id: mediaId,
      message: `已成功推送到公众号（publish_id: ${publishResult.publish_id}）`,
    }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })

  } catch (err) {
    const errorMsg = err.message || String(err)
    return new Response(JSON.stringify({
      success: false,
      error: errorMsg,
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
