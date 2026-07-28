/**
 * 轻量、零依赖、防 XSS 的 Markdown 渲染器 + 合规词检测。
 *
 * 设计原则：
 *  1. 先整体 escapeHtml，再解析受控子集 → 用户无法注入原始 HTML / 脚本。
 *  2. 链接 / 图片 URL 经 sanitizeUrl 白名单校验，非法 URL 降级为 '#'。
 *  3. 仅支持安全子集（标题/粗体/斜体/行内代码/代码块/引用/列表/分隔线/链接/图片），
 *     不渲染原始 HTML，规避存储型 XSS。
 *
 * 合规：checkCompliance 复用与后端一致的禁语集合（前端预检，后端触发器为最终护栏）。
 */

// 与后端 guard_article_compliance 保持一致的禁语（含中英文）
export const FORBIDDEN_WORDS = [
  '保本', '稳赚', '必涨', '保证收益', '承诺收益', '推荐买入', '跟单',
  '代客理财', '零风险', '稳赚不赔', '高收益无风险', '内部消息', '包赚',
  'guaranteed', '保证盈利', '保底',
]

/** 合规预检：返回命中的禁语数组（空数组表示通过） */
export function checkCompliance(text) {
  const t = String(text || '')
  const hits = []
  for (const w of FORBIDDEN_WORDS) {
    if (t.indexOf(w) !== -1) hits.push(w)
  }
  return hits
}

/** HTML 转义 */
export function escapeHtml(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/**
 * URL 白名单：仅允许 http(s) / mailto / 相对路径 / 锚点 / 裸域名（补 https）。
 * 其余（如 javascript:、data:）一律降级为 '#'。
 */
export function sanitizeUrl(url) {
  const u = String(url || '').trim()
  if (!u) return '#'
  if (/^(https?:\/\/|mailto:|#|\/|\.\/|\.\.\/)/i.test(u)) return u
  if (/^[a-z0-9.-]+\.[a-z]{2,}(\/|$)/i.test(u)) return 'https://' + u // 裸域名补 https
  return '#'
}

/** 行内渲染（输入已为转义后文本） */
function renderInline(text) {
  // 1) 保护行内代码，避免其中内容被二次格式化
  const codes = []
  let s = text.replace(/`([^`]+)`/g, (m, c) => {
    codes.push(c)
    return '\u0000CODE' + (codes.length - 1) + '\u0000'
  })
  // 2) 图片（必须先于链接，避免被链接规则吞掉 '!'）
  s = s.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (m, alt, u) => {
    return '<img src="' + escapeHtml(sanitizeUrl(u)) + '" alt="' + alt + '" />'
  })
  // 3) 链接
  s = s.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (m, t, u) => {
    return '<a href="' + escapeHtml(sanitizeUrl(u)) + '" target="_blank" rel="noopener noreferrer">' + t + '</a>'
  })
  // 4) 粗体 / 斜体
  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  s = s.replace(/__([^_]+)__/g, '<strong>$1</strong>')
  s = s.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  s = s.replace(/(^|[^a-zA-Z0-9_])_([^_]+)_/g, '$1<em>$2</em>')
  // 5) 还原行内代码
  s = s.replace(/\u0000CODE(\d+)\u0000/g, (m, i) => '<code>' + codes[Number(i)] + '</code>')
  return s
}

/**
 * 渲染对齐容器内的内容（保留段落/列表/标题等块级结构）。
 * 输入为已 escapeHtml 的行数组（由 renderMarkdown 转入），不再二次转义。
 */
function renderAlignContent(lines) {
  // 注意：lines 已经由 renderMarkdown 统一 escapeHtml 过，此处不可再转义
  let html = ''
  let para = []
  let inList = null

  function flushPara() {
    if (para.length) {
      html += '<p>' + renderInline(para.join(' ')) + '</p>'
      para = []
    }
  }
  function closeList() {
    if (inList) { html += '</' + inList + '>'; inList = null }
  }

  for (const line of lines) {
    // 标题
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      flushPara(); closeList()
      html += '<h' + h[1].length + '>' + renderInline(h[2]) + '</h' + h[1].length + '>'
      continue
    }
    // 分隔线
    if (/^(\s*[-*_])\s*(\1\s*){2,}$/.test(line)) {
      flushPara(); closeList()
      html += '<hr />'
      continue
    }
    // 引用
    if (/^>\s?/.test(line)) {
      flushPara(); closeList()
      html += '<blockquote>' + renderInline(line.replace(/^>\s?/, '')) + '</blockquote>'
      continue
    }
    // 无序列表
    const ul = line.match(/^\s*[-*+]\s+(.*)$/)
    if (ul) {
      flushPara()
      if (inList !== 'ul') { closeList(); html += '<ul>'; inList = 'ul' }
      html += '<li>' + renderInline(ul[1]) + '</li>'
      continue
    }
    // 有序列表
    const ol = line.match(/^\s*\d+\.\s+(.*)$/)
    if (ol) {
      flushPara()
      if (inList !== 'ol') { closeList(); html += '<ol>'; inList = 'ol' }
      html += '<li>' + renderInline(ol[1]) + '</li>'
      continue
    }
    // 空行 → 段落分隔
    if (/^\s*$/.test(line)) {
      flushPara(); closeList()
      continue
    }
    // 普通行
    para.push(line)
  }

  flushPara()
  closeList()
  return html
}

/**
 * 渲染 Markdown 安全子集为 HTML 字符串。
 * 输入会先经 escapeHtml，因此用户无法注入 HTML / 脚本。
 */
export function renderMarkdown(md) {
  if (!md) return ''
  const escaped = escapeHtml(md)
  const lines = escaped.split(/\r?\n/)
  let html = ''
  let inList = null // 'ul' | 'ol'
  let inCode = false
  let codeBuf = []
  let para = []
  let inAlign = null // 'left' | 'center' | 'right' | 'justify'
  let alignBuf = []

  function flushPara() {
    if (para.length) {
      html += '<p>' + renderInline(para.join(' ')) + '</p>'
      para = []
    }
  }
  function closeList() {
    if (inList) {
      html += '</' + inList + '>'
      inList = null
    }
  }

  for (let n = 0; n < lines.length; n++) {
    const line = lines[n]

    // 代码围栏 ```
    if (/^```/.test(line)) {
      if (inCode) {
        html += '<pre><code>' + codeBuf.join('\n') + '</code></pre>'
        codeBuf = []
        inCode = false
      } else {
        flushPara()
        closeList()
        inCode = true
      }
      continue
    }
    if (inCode) {
      codeBuf.push(line)
      continue
    }

    // 对齐容器 :::left / :::center / :::right / :::justify ... :::（白名单，仅四类，防 XSS）
    const alignOpen = line.match(/^:::\s*(left|center|right|justify)\s*$/)
    if (alignOpen) {
      flushPara()
      closeList()
      inAlign = alignOpen[1]
      alignBuf = []
      continue
    }
    if (inAlign) {
      if (/^:::\s*$/.test(line)) {
        // 对齐容器内：保留段落/列表等结构，不拍平
        html += '<div class="align-' + inAlign + '">' + renderAlignContent(alignBuf) + '</div>'
        inAlign = null
        alignBuf = []
      } else {
        alignBuf.push(line)
      }
      continue
    }

    // 标题 # ~ ####
    const h = line.match(/^(#{1,4})\s+(.*)$/)
    if (h) {
      flushPara()
      closeList()
      const lvl = h[1].length
      html += '<h' + lvl + '>' + renderInline(h[2]) + '</h' + lvl + '>'
      continue
    }

    // 分隔线
    if (/^(\s*[-*_])\s*(\1\s*){2,}$/.test(line)) {
      flushPara()
      closeList()
      html += '<hr />'
      continue
    }

    // 引用
    if (/^>\s?/.test(line)) {
      flushPara()
      closeList()
      html += '<blockquote>' + renderInline(line.replace(/^>\s?/, '')) + '</blockquote>'
      continue
    }

    // 无序列表
    const ul = line.match(/^\s*[-*+]\s+(.*)$/)
    if (ul) {
      flushPara()
      if (inList !== 'ul') {
        closeList()
        html += '<ul>'
        inList = 'ul'
      }
      html += '<li>' + renderInline(ul[1]) + '</li>'
      continue
    }

    // 有序列表
    const ol = line.match(/^\s*\d+\.\s+(.*)$/)
    if (ol) {
      flushPara()
      if (inList !== 'ol') {
        closeList()
        html += '<ol>'
        inList = 'ol'
      }
      html += '<li>' + renderInline(ol[1]) + '</li>'
      continue
    }

    // 空行
    if (/^\s*$/.test(line)) {
      flushPara()
      closeList()
      continue
    }

    // 普通段落行
    para.push(line)
  }

  flushPara()
  closeList()
  if (inAlign) {
    html += '<div class="align-' + inAlign + '">' + renderAlignContent(alignBuf) + '</div>'
  }
  if (inCode) {
    html += '<pre><code>' + codeBuf.join('\n') + '</code></pre>'
  }
  return html
}
