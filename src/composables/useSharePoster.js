import QRCode from 'qrcode'

/**
 * useSharePoster —— 分享海报公共 composable
 * --------------------------------------------------
 * 统一的「品牌蓝头图 + 自由内容区 + 底部二维码」海报生成与保存逻辑，
 * 供各页面（AI 大 PK、基金详情、组合等）复用，避免每页重复 canvas / 二维码代码。
 *
 * 设计原则：
 *  - 本 composable 不持有任何组件级 ref，纯工具函数，可在任意 .vue 中调用。
 *  - 内容区由调用方通过 drawContent 回调自由绘制，回调收到 (ctx, geom) 并返回绘制结束的 y 坐标。
 *  - 生成的永远是 PNG dataURL，由调用方决定如何展示（弹窗 <img> / 保存本地）。
 *
 * 用法：
 *   const { generatePoster, savePoster } = useSharePoster()
 *   const url = await generatePoster({
 *     title: 'AI 大 PK · 收益 PK',
 *     drawContent: async (ctx, { W, pad, y, truncateText, wrapText, roundRect, loadImage }) => {
 *        // 在头图下方自由绘制，返回绘制结束的 y 坐标
 *        ctx.fillStyle = '#1a1a1a'
 *        ctx.font = 'bold 22px sans-serif'
 *        ctx.fillText('hello', pad, y)
 *        return y + 40
 *     },
 *   })
 *   savePoster(url, 'my-share.png')
 */

export function useSharePoster() {
  const W = 750
  const pad = 30
  const headerH = 150
  const qrSize = 170
  const sourceLineH = 40
  const scale = 2

  /** 截断文本（超宽加省略号） */
  function truncateText(ctx, text, maxWidth) {
    if (!text) return ''
    if (ctx.measureText(text).width <= maxWidth) return text
    let t = text
    while (t.length > 1 && ctx.measureText(t + '…').width > maxWidth) t = t.slice(0, -1)
    return t + '…'
  }

  /** 按字符自动换行，返回行数组 */
  function wrapText(ctx, text, maxWidth) {
    if (!text) return []
    const lines = []
    let current = ''
    for (const ch of String(text)) {
      const test = current + ch
      if (ctx.measureText(test).width <= maxWidth) current = test
      else { if (current) lines.push(current); current = ch }
    }
    if (current) lines.push(current)
    return lines
  }

  /** 圆角矩形路径（绘制前需自行 fill/stroke） */
  function roundRect(ctx, x, y, w, h, r) {
    ctx.beginPath()
    ctx.moveTo(x + r, y)
    ctx.arcTo(x + w, y, x + w, y + h, r)
    ctx.arcTo(x + w, y + h, x, y + h, r)
    ctx.arcTo(x, y + h, x, y, r)
    ctx.arcTo(x, y, x + w, y, r)
    ctx.closePath()
  }

  /** 加载图片（dataURL / src）为 Image 对象，失败返回 null */
  function loadImage(src) {
    return new Promise((resolve) => {
      const img = new Image()
      img.onload = () => resolve(img)
      img.onerror = () => resolve(null)
      img.src = src
    })
  }

  /** 顶部品牌蓝条（每个海报通用） */
  function drawHeader(ctx, title) {
    ctx.fillStyle = '#1d70b8'
    ctx.fillRect(0, 0, W, headerH)
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'left'
    ctx.font = 'bold 38px sans-serif'
    ctx.fillText('ALLFUND.CN', pad, 34)
    ctx.font = '24px sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.fillText(title, pad, 86)
  }

  /**
   * 生成海报，返回 PNG dataURL
   * @param {Object}   opts
   * @param {string}   opts.title        头图副标题（如 "AI 大 PK · 收益 PK"）
   * @param {Function} [opts.drawContent] 内容绘制回调 (ctx, geom) => number|Promise<number>
   *                                       geom = { W, pad, headerH, y, truncateText, wrapText, roundRect, loadImage }
   *                                       回调需返回绘制结束的 y 坐标
   * @param {string}   [opts.qrText]       二维码内容（默认官网 https://www.allfund.cn）
   * @param {string}   [opts.qrCaption]    二维码上方说明
   * @param {string}   [opts.qrSubCaption] 二维码下方说明
   * @returns {Promise<string>} PNG dataURL
   */
  async function generatePoster(opts = {}) {
    const {
      title = '',
      drawContent = null,
      qrText = 'https://www.allfund.cn',
      qrCaption = '微信扫一扫 · 访问 www.allfund.cn',
      qrSubCaption = '识别二维码，查看靠谱指数与 AI 大 PK',
    } = opts

    const canvas = document.createElement('canvas')
    canvas.width = W * scale
    canvas.height = 6000 * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.textBaseline = 'top'
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, W, 6000)

    drawHeader(ctx, title)

    let usedY = headerH
    if (typeof drawContent === 'function') {
      const geom = { W, pad, headerH, y: headerH + 24, truncateText, wrapText, roundRect, loadImage }
      const r = await drawContent(ctx, geom)
      if (typeof r === 'number') usedY = r
    }

    // 二维码 + 说明
    const qrY = usedY + 16
    const qrCanvas = document.createElement('canvas')
    await QRCode.toCanvas(qrCanvas, qrText, {
      width: qrSize * scale, margin: 1, color: { dark: '#000000', light: '#ffffff' },
    })
    ctx.drawImage(qrCanvas, (W - qrSize) / 2, qrY, qrSize, qrSize)
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1d70b8'; ctx.font = 'bold 24px sans-serif'
    ctx.fillText(qrCaption, W / 2, qrY + qrSize + 14)
    ctx.fillStyle = '#999999'; ctx.font = '16px sans-serif'
    ctx.fillText(qrSubCaption, W / 2, qrY + qrSize + 44)

    const totalH = qrY + qrSize + sourceLineH
    // 裁剪到实际使用高度
    const finalCanvas = document.createElement('canvas')
    finalCanvas.width = W * scale
    finalCanvas.height = totalH * scale
    const fctx = finalCanvas.getContext('2d')
    fctx.drawImage(canvas, 0, 0, W * scale, totalH * scale, 0, 0, W * scale, totalH * scale)
    return finalCanvas.toDataURL('image/png')
  }

  /** 保存 PNG dataURL 到本地（触发浏览器下载） */
  function savePoster(dataUrl, filename = 'allfund-share.png') {
    if (!dataUrl) return
    const a = document.createElement('a')
    a.href = dataUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
  }

  return { generatePoster, savePoster, truncateText, wrapText, roundRect, loadImage }
}
