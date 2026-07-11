<template>
  <div class="hot-tags-section">
    <!-- Tab 切换：热门基金（行业）/ 热门基金（概念） -->
    <div class="tags-header">
      <span class="tags-title">热门基金</span>
      <div class="tabs">
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'concept' }"
          @click="activeTab = 'concept'"
        >概念</button>
        <button
          class="tab-btn"
          :class="{ active: activeTab === 'industry' }"
          @click="activeTab = 'industry'"
        >行业</button>
      </div>
    </div>

    <!-- 标签网格 -->
    <div class="tags-grid" v-if="displayTags.length > 0">
      <div
        v-for="tag in displayTags"
        :key="tag.name"
        class="tag-cell"
        :style="{ background: tagColor(tag.return_pct) }"
        @click="openTagDetail(tag)"
      >
        <span class="tag-name">{{ tag.name }}</span>
        <span class="tag-return" v-if="tag.return_pct != null">{{ fmtPct(tag.return_pct) }}</span>
      </div>
    </div>

    <!-- 加载中 -->
    <div class="tags-loading" v-if="loading && displayTags.length === 0">标签加载中...</div>

    <!-- 标签详情弹窗：关联基金列表 -->
    <Teleport to="body">
      <template v-if="selectedTag">
        <div class="mask" @click="selectedTag = null"></div>
        <div class="tag-detail-panel">
          <div class="detail-header">
            <span class="detail-title">
              {{ selectedTag.name }}
              <span class="detail-type-badge" :class="selectedTag.tag_type">{{ selectedTag.tag_type === 'concept' ? '概念' : '行业' }}</span>
              <span class="detail-return" v-if="selectedTag.return_pct != null">{{ fmtPct(selectedTag.return_pct) }}</span>
            </span>
            <div class="detail-header-actions">
              <button
                class="detail-share"
                v-if="tagFunds.length > 0"
                :disabled="shareGenerating"
                @click="generateShareImage"
                title="生成分享图片"
              >分享</button>
              <span class="detail-close" @click="selectedTag = null">&#x2715;</span>
            </div>
          </div>
          <div class="detail-body">
            <!-- 关联基金列表（前3只） -->
            <div class="funds-loading" v-if="tagFundsLoading">加载中...</div>
            <template v-else-if="tagFunds.length > 0">
              <div class="funds-count">相关基金 TOP {{ tagFunds.length }}</div>
              <div class="fund-tag-list">
                <div
                  v-for="f in tagFunds"
                  :key="f.c"
                  class="fund-tag-item"
                >
                  <div class="ft-main">
                    <div class="ft-line1">
                      <a class="ft-code" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.c }}</a>
                      <a class="ft-name" :href="eastMoneyUrl(f.c)" target="_blank">{{ f.n || ('基金' + f.c) }}</a>
                    </div>
                    <div class="ft-line2">
                      <span class="ft-manager">经理：{{ f.fund_manager || '—' }}</span>
                    </div>
                  </div>
                  <div class="ft-right">
                    <span class="ft-ret-label">近1年收益</span>
                    <span class="ft-ret" :style="{ color: retColor(f.r1y) }" v-if="f.r1y != null">{{ fmtRetPlain(f.r1y) }}%</span>
                    <span class="ft-ret" v-else>—</span>
                  </div>
                </div>
              </div>
            </template>
            <div class="funds-empty" v-else>
              <p>暂无关联基金数据</p>
              <p class="funds-empty-hint">可前往<a :href="eastmoneyTopicUrl(selectedTag.name)" target="_blank">天天基金</a>查看完整列表</p>
            </div>
            <!-- 数据来源 -->
            <div class="data-source-line">
              数据来源：ALLFUND.CN &nbsp;|&nbsp; 截止时间：{{ fundMetaUpdateTime || '—' }}
            </div>
          </div>
        </div>
      </template>
    </Teleport>

    <!-- 分享图片预览弹窗 -->
    <Teleport to="body">
      <template v-if="shareImage">
        <div class="mask" @click="shareImage = null"></div>
        <div class="share-panel">
          <div class="share-header">
            <span class="share-title">分享到朋友圈</span>
            <span class="detail-close" @click="shareImage = null">&#x2715;</span>
          </div>
          <div class="share-body">
            <img class="share-img" :src="shareImage" alt="分享图" />
            <p class="share-hint">长按图片可保存到相册，或分享到朋友圈</p>
            <button class="share-save-btn" @click="saveShareImage">保存图片</button>
          </div>
        </div>
      </template>
    </Teleport>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import QRCode from 'qrcode'
import { fetchFundTags, fetchFundMeta } from '../api/data.js'
import { fmtRetPlain } from '../utils/format.js'

const props = defineProps({
  /** 最大展示行数，默认显示全部 */
  maxRows: { type: Number, default: 0 },
})

// ========== 状态 ==========
const activeTab = ref('concept') // 'concept' | 'industry'
const allTags = ref([]) // [{ name, tag_type, return_pct, sort_order }]
const loading = ref(false)
const selectedTag = ref(null) // 当前选中的标签
const tagFunds = ref([]) // 标签关联的基金列表（前3只）
const tagFundsLoading = ref(false)
const shareImage = ref(null) // 生成的分享图 dataURL
const shareGenerating = ref(false)
const fundMetaUpdateTime = ref('') // fund_scores 更新时间

// ========== 计算属性 ==========
const displayTags = computed(() => {
  const filtered = allTags.value.filter(t => t.tag_type === activeTab.value)
  if (props.maxRows > 0) {
    return filtered.slice(0, props.maxRows * 8) // 每行8个
  }
  return filtered
})

// ========== 方法 ==========
async function loadTags() {
  loading.value = true
  try {
    const data = await fetchFundTags()
    if (Array.isArray(data)) {
      allTags.value = data
    }
  } catch (e) {
    console.error('[HotTags] load error', e)
  } finally {
    loading.value = false
  }
}

function openTagDetail(tag) {
  selectedTag.value = tag
  tagFunds.value = []
  loadTagFunds(tag)
  // 获取 fund_scores 更新时间
  fetchFundMeta().then(m => {
    if (m?.tsq) {
      try {
        const d = new Date(m.tsq)
        fundMetaUpdateTime.value = d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
      } catch { fundMetaUpdateTime.value = '' }
    }
  })
}

/** 从 fund_tag_funds 表查询标签关联基金（东财 ZTJJ 真实映射），再补充 fund_scores 的经理字段 */
async function loadTagFunds(tag) {
  tagFundsLoading.value = true
  try {
    const { supabase } = await import('../api/supabase.js')
    if (!supabase) { tagFundsLoading.value = false; return }

    // 1) 从 fund_tag_funds 获取东财 ZTJJ 接口映射的基金列表
    const { data: mappings, error: err1 } = await supabase
      .from('fund_tag_funds')
      .select('fund_code,fund_name,fund_type,syl_1n')
      .eq('tag_name', tag.name)
      .order('sort_order', { ascending: true })
    .limit(5)

    // 无数据时直接显示空状态，不做任何兜底
    if (err1 || !mappings || mappings.length === 0) {
      tagFunds.value = []
      return
    }

    // 2) 用基金代码从 fund_scores 补充经理信息
    const codes = mappings.map(m => m.fund_code).filter(Boolean)
    const { data: scores } = await supabase
      .from('fund_scores')
      .select('c,n,fund_manager,r1y,k1')
      .in('c', codes)

    const scoreMap = {}
    if (scores) {
      for (const s of scores) { scoreMap[s.c] = s }
    }

    // 3) 合并：用 fund_scores 的 r1y（近1年收益，来自CI计算），缺失时用东财 syl_1n
    tagFunds.value = mappings.map(m => {
      const sc = scoreMap[m.fund_code] || {}
      return {
        c: m.fund_code,
        n: m.fund_name,  // 直接使用东财官方名称
        t0: sc.t0,
        t1: sc.t1,
        t1_tt: sc.t1_tt,
        k1: sc.k1,
        r1y: sc.r1y ?? m.syl_1n,  // fund_scores优先，否则用东财近1年收益
        fund_manager: sc.fund_manager || '',
        _ftype: m.fund_type,
      }
    })
  } catch (e) {
    console.error('[HotTags] loadTagFunds error', e)
  } finally {
    tagFundsLoading.value = false
  }
}

/** 颜色映射：根据收益率返回红粉渐变色 */
function tagColor(ret) {
  if (ret == null) return '#e8e8e8'
  const r = parseFloat(ret)
  if (isNaN(r)) return '#e8e8e8'
  const v = Math.min(Math.max(r, 0), 600)
  let ratio = v / 600
  const r_val = Math.round(255 - ratio * 60)
  const g_val = Math.round(224 - ratio * 200)
  const b_val = Math.round(224 - ratio * 210)
  return `rgb(${r_val},${g_val},${b_val})`
}

function fmtPct(v) {
  if (v == null) return ''
  const n = parseFloat(v)
  if (isNaN(n)) return ''
  return n.toFixed(2) + '%'
}

function retColor(v) {
  if (v == null) return 'var(--text-secondary)'
  const n = parseFloat(v)
  if (isNaN(n) || n === 0) return 'var(--text-secondary)'
  return n > 0 ? '#d4351c' : '#00703c'
}

function eastMoneyUrl(code) {
  if (!code) return '#'
  const pureCode = code.replace(/\.of$/i, '').replace(/\.OF$/, '')
  return `https://fund.eastmoney.com/${pureCode}.html`
}

function eastmoneyTopicUrl(topicName) {
  return `https://fund.eastmoney.com/ztjj/#!syl/Y/curr/zf-${encodeURIComponent(topicName)}/fst/DESC`
}

/** 截断文本（canvas 绘制用） */
function truncateText(ctx, text, maxWidth) {
  if (!text) return ''
  if (ctx.measureText(text).width <= maxWidth) return text
  let t = text
  while (t.length > 1 && ctx.measureText(t + '…').width > maxWidth) {
    t = t.slice(0, -1)
  }
  return t + '…'
}

/** 文字自动换行（canvas 用） */
function wrapText(ctx, text, maxWidth) {
  if (!text) return []
  const lines = []
  let current = ''
  for (const ch of text) {
    const test = current + ch
    if (ctx.measureText(test).width <= maxWidth) {
      current = test
    } else {
      if (current) lines.push(current)
      current = ch
    }
  }
  if (current) lines.push(current)
  return lines
}

/** 调用 DeepSeek 生成标签相关金句 */
async function generateTagline(tagName, avgReturn, isPositive, funds) {
  const apiKey = import.meta.env.VITE_DEEPSEEK_API_KEY || ''
  if (!apiKey) return ''

  // 构建基金表现摘要
  const topFund = funds.length > 0 ? funds[0] : null
  const fundSummary = funds.slice(0, 3).map(f => {
    const ret = f.r1y != null ? (f.r1y >= 0 ? '+' : '') + f.r1y.toFixed(2) + '%' : '—'
    return `${f.n || f.c}(${ret})`
  }).join('、')

  const direction = isPositive ? '大涨' : '下跌'
  const toneInstruction = isPositive
    ? '写一句正向的、张扬的、充满斗志和激情的金句，让读者看了热血沸腾想立刻买入或持有'
    : '写一句鼓励的、温暖的、给人坚持力量的金句，让读者在亏损中不放弃、相信长期价值'

  const prompt = `你是一个有感染力的基金投资博主。请根据以下信息，${toneInstruction}。

要求：
- 金句必须与标签「${tagName}」强相关，体现该赛道的行业特征
- ${isPositive ? '要体现涨幅的亮眼程度，用数字增强冲击力' : '要体现当前困难是暂时的，该赛道长期逻辑未变'}
- 一句话，不超过30个字
- 不要用emoji，不要引号，直接输出金句正文

标签：${tagName}
板块方向：${direction}
平均近1年收益：${avgReturn != null ? (avgReturn >= 0 ? '+' : '') + avgReturn.toFixed(2) + '%' : '—'}
代表性基金：${fundSummary || '无'}`

  const response = await fetch('https://api.deepseek.com/v1/chat/completions', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${apiKey}` },
    body: JSON.stringify({
      model: 'deepseek-chat',
      messages: [
        { role: 'system', content: '你是擅长写短小有力投资金句的高手。只输出金句正文，不要任何解释、前缀、后缀。' },
        { role: 'user', content: prompt }
      ],
      temperature: 0.85,
      max_tokens: 100
    })
  })
  if (!response.ok) return ''
  const result = await response.json()
  let content = result.choices?.[0]?.message?.content || ''
  // 清理可能的引号和换行
  content = content.replace(/^["'「『]|["'」』]$/g, '').replace(/\n/g, ' ').trim()
  return content.slice(0, 60) // 安全截断
}

/** 生成分享图片：含标签 + 基金 + 金句 + 二维码 */
async function generateShareImage() {
  if (shareGenerating.value) return
  shareGenerating.value = true
  try {
    const scale = 2
    const W = 750
    const pad = 30
    const headerH = 150
    const titleGap = 110
    const fundH = 150
    const fundGap = 16
    const qrSize = 190
    const qrBottomGap = 70

    const list = tagFunds.value
    // 计算平均收益用于判断涨跌方向
    const avgReturn = list.length > 0
      ? list.reduce((s, f) => s + (f.r1y ?? 0), 0) / list.length
      : 0
    const isPositive = avgReturn >= 0

    // 获取金句（DeepSeek）
    let tagline = ''
    try {
      tagline = await generateTagline(selectedTag.value.name, avgReturn, isPositive, list)
    } catch { /* 静默失败，不显示金句 */ }

    // 获取更新时间
    let updateTimeStr = ''
    try {
      const meta = await fetchFundMeta()
      if (meta?.tsq) {
        const d = new Date(meta.tsq)
        updateTimeStr = d.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
      }
    } catch { /* ignore */ }

    let H = headerH + titleGap + 20
    H += list.length * (fundH + fundGap)
    H += 30 // 与金句间距
    if (tagline) H += 50 // 金句高度
    H += 20 // 金句与二维码间距
    const qrY = H
    H += qrSize + qrBottomGap
    H += 30 // 来源行高度

    const canvas = document.createElement('canvas')
    canvas.width = W * scale
    canvas.height = H * scale
    const ctx = canvas.getContext('2d')
    ctx.scale(scale, scale)
    ctx.textBaseline = 'top'

    // 背景
    ctx.fillStyle = '#ffffff'
    ctx.fillRect(0, 0, W, H)

    // 顶部品牌蓝条
    ctx.fillStyle = '#1d70b8'
    ctx.fillRect(0, 0, W, headerH)
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'left'
    ctx.font = 'bold 38px sans-serif'
    ctx.fillText('ALLFUND.CN', pad, 34)
    ctx.font = '24px sans-serif'
    ctx.fillStyle = 'rgba(255,255,255,0.92)'
    ctx.fillText('靠谱指数 · 热门基金', pad, 86)

    // 标签标题
    let y = headerH + 30
    ctx.textAlign = 'left'
    ctx.fillStyle = '#1a1a1a'
    ctx.font = 'bold 40px sans-serif'
    ctx.fillText(truncateText(ctx, selectedTag.value.name, W - pad * 2 - 160), pad, y)
    // 标签类型徽标
    const badgeText = selectedTag.value.tag_type === 'concept' ? '概念' : '行业'
    ctx.font = 'bold 22px sans-serif'
    const bw = ctx.measureText(badgeText).width + 24
    ctx.fillStyle = badgeText === '概念' ? '#d4351c' : '#1d70b8'
    roundRect(ctx, W - pad - bw, y + 6, bw, 36, 6)
    ctx.fill()
    ctx.fillStyle = '#ffffff'
    ctx.textAlign = 'center'
    ctx.fillText(badgeText, W - pad - bw / 2, y + 13)
    // 标签收益率
    ctx.textAlign = 'left'
    ctx.fillStyle = '#d4351c'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText('板块收益 ' + fmtPct(selectedTag.value.return_pct), pad, y + 56)

    // 基金卡片
    y = headerH + titleGap
    for (const f of list) {
      // 卡片底
      ctx.fillStyle = '#f6f8fb'
      roundRect(ctx, pad, y, W - pad * 2, fundH, 12)
      ctx.fill()
      ctx.strokeStyle = '#e3e8ef'
      ctx.lineWidth = 1
      roundRect(ctx, pad + 0.5, y + 0.5, W - pad * 2 - 1, fundH - 1, 12)
      ctx.stroke()

      const innerX = pad + 20
      // 代码
      ctx.textAlign = 'left'
      ctx.fillStyle = '#1d70b8'
      ctx.font = 'bold 22px sans-serif'
      ctx.fillText(f.c || '', innerX, y + 18)
      // 名称
      ctx.fillStyle = '#1a1a1a'
      ctx.font = 'bold 26px sans-serif'
      ctx.fillText(truncateText(ctx, f.n || ('基金' + f.c), W - pad * 2 - 40 - 150), innerX, y + 50)
      // 经理
      ctx.fillStyle = '#666666'
      ctx.font = '19px sans-serif'
      ctx.fillText('经理：' + (f.fund_manager || '—'), innerX, y + 92)

      // 区间收益（右侧）
      ctx.textAlign = 'right'
      const r1y = f.r1y
      ctx.fillStyle = (r1y == null || r1y >= 0) ? '#d4351c' : '#00703c'
      ctx.font = 'bold 32px sans-serif'
      const retStr = r1y == null ? '—' : (r1y >= 0 ? '+' : '') + r1y.toFixed(2) + '%'
      ctx.fillText(retStr, W - pad - 20, y + 44)
      ctx.fillStyle = '#999999'
      ctx.font = '17px sans-serif'
      ctx.fillText('近1年收益', W - pad - 20, y + 92)

      y += fundH + fundGap
    }

    // 金句（DeepSeek 生成，在二维码上方）
    if (tagline) {
      ctx.textAlign = 'center'
      ctx.fillStyle = isPositive ? '#d4351c' : '#1d70b8'
      ctx.font = 'bold 24px sans-serif'
      // 自动换行：金句较长时分行
      const maxTaglineW = W - pad * 2
      const lines = wrapText(ctx, tagline, maxTaglineW)
      let lineY = qrY - lines.length * 32 - 10
      for (const line of lines) {
        ctx.fillText(line, W / 2, lineY)
        lineY += 30
      }
    }

    // 二维码
    const qrCanvas = document.createElement('canvas')
    await QRCode.toCanvas(qrCanvas, 'https://www.allfund.cn', {
      width: qrSize * scale,
      margin: 1,
      color: { dark: '#000000', light: '#ffffff' },
    })
    ctx.drawImage(qrCanvas, (W - qrSize) / 2, qrY, qrSize, qrSize)
    // 二维码说明
    ctx.textAlign = 'center'
    ctx.fillStyle = '#1d70b8'
    ctx.font = 'bold 26px sans-serif'
    ctx.fillText('微信扫一扫 · 访问 www.allfund.cn', W / 2, qrY + qrSize + 18)
    ctx.fillStyle = '#999999'
    ctx.font = '18px sans-serif'
    ctx.fillText('识别二维码，查看靠谱指数与更多热门基金', W / 2, qrY + qrSize + 52)

    // 来源信息
    if (updateTimeStr) {
      ctx.fillStyle = '#bbbbbb'
      ctx.font = '15px sans-serif'
      ctx.fillText('来源：ALLFUND.CN  |  ' + updateTimeStr, W / 2, qrY + qrSize + 80)
    } else {
      ctx.fillStyle = '#bbbbbb'
      ctx.font = '15px sans-serif'
      ctx.fillText('来源：ALLFUND.CN', W / 2, qrY + qrSize + 80)
    }

    shareImage.value = canvas.toDataURL('image/png')
  } catch (e) {
    console.error('[HotTags] generateShareImage error', e)
    alert('生成分享图片失败，请重试')
  } finally {
    shareGenerating.value = false
  }
}

/** 圆角矩形路径 */
function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

/** 保存分享图片 */
function saveShareImage() {
  if (!shareImage.value) return
  const a = document.createElement('a')
  a.href = shareImage.value
  const safeName = (selectedTag.value?.name || 'fund') + '-allfund.png'
  a.download = safeName
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

// ========== 生命周期 ==========
onMounted(() => {
  loadTags()
})

defineExpose({ refresh: loadTags })
</script>

<style scoped>
.hot-tags-section {
  background: #ffffff;
  border-bottom: 1px solid var(--border);
}

/* 头部 */
.tags-header {
  display: flex;
  align-items: center;
  padding: var(--space-sm) var(--space-md);
  gap: var(--space-md);
}
.tags-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  flex-shrink: 0;
}
.tabs {
  display: flex;
  gap: 0;
}
.tab-btn {
  padding: 4px 14px;
  font-size: 14px;
  color: var(--link);
  cursor: pointer;
  border: 1px solid var(--border);
  background: #fff;
  text-decoration: none;
  transition: all 0.15s;
}
.tab-btn:hover { border-color: #1d70b8; }
.tab-btn.active {
  color: #fff;
  background: #1d70b8;
  border-color: #1d70b8;
  font-weight: 700;
}

/* 标签网格：8列布局 */
.tags-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  gap: 2px;
  padding: var(--space-sm) var(--space-md) var(--space-md);
}
@media (max-width: 767px) {
  .tags-grid {
    grid-template-columns: repeat(4, 1fr);
    gap: 3px;
  }
}

.tag-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 8px 4px;
  min-height: 52px;
  cursor: pointer;
  transition: opacity 0.15s, transform 0.1s;
  border-radius: 2px;
  text-align: center;
}
.tag-cell:hover {
  opacity: 0.85;
  transform: scale(1.03);
}
.tag-cell:active {
  transform: scale(0.97);
}
.tag-name {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  line-height: 1.2;
  word-break: keep-all;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
.tag-return {
  font-size: 11px;
  color: rgba(255,255,255,0.9);
  margin-top: 2px;
  font-weight: 500;
  font-variant-numeric: tabular-nums;
}

.tags-loading {
  text-align: center;
  padding: var(--space-md);
  font-size: 14px;
  color: var(--text-secondary);
}

/* ===== 标签详情弹窗（垂直居中，保证完整展示） ===== */
.tag-detail-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 560px;
  max-height: 88vh;
  background: #ffffff;
  border: 1px solid var(--border);
  overflow: hidden;
  display: flex;
  flex-direction: column;
  z-index: 101;
}
.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-md) var(--space-lg);
  border-bottom: 2px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.detail-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.detail-type-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 3px;
  color: #fff;
  flex-shrink: 0;
}
.detail-type-badge.concept { background: #d4351c; }
.detail-type-badge.industry { background: #1d70b8; }
.detail-return {
  font-size: 16px;
  font-weight: 700;
  color: #d4351c;
  flex-shrink: 0;
}
.detail-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  flex-shrink: 0;
}
.detail-share {
  font-size: 13px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: none;
  border-radius: 2px;
  padding: 5px 14px;
  cursor: pointer;
}
.detail-share:disabled {
  opacity: 0.6;
  cursor: default;
}
.detail-close {
  font-size: 24px;
  color: var(--text-primary);
  cursor: pointer;
  padding: 4px;
  line-height: 1;
  flex-shrink: 0;
}
.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md) var(--space-lg);
}
.funds-count {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: var(--space-sm);
}
.fund-tag-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}
.fund-tag-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-sm);
  padding: 10px 0;
  border-bottom: 1px solid #f0f0f0;
}
.fund-tag-item:last-child { border-bottom: none; }
.ft-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.ft-line1 {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  min-width: 0;
}
.ft-code {
  font-size: 12px;
  font-weight: 700;
  font-family: monospace;
  color: var(--text-primary);
  text-decoration: none;
  flex-shrink: 0;
}
.ft-code:hover { color: var(--link); text-decoration: underline; }
.ft-name {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-decoration: none;
  flex: 1;
  min-width: 0;
}
.ft-name:hover { color: var(--link); text-decoration: underline; }
.ft-line2 {
  display: flex;
  align-items: center;
}
.ft-manager {
  font-size: 13px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.ft-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  min-width: 88px;
}
.ft-ret-label {
  font-size: 11px;
  color: var(--text-secondary);
  margin-bottom: 2px;
}
.ft-ret {
  font-size: 18px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.funds-loading, .funds-empty {
  text-align: center;
  padding: var(--space-xl) 0;
  color: var(--text-secondary);
  font-size: 15px;
}
.funds-empty p { margin: var(--space-xs) 0; }
.funds-empty-hint { font-size: 13px; }
.funds-empty a { color: var(--link); text-decoration: underline; }
.data-source-line {
  font-size: 11px;
  color: var(--text-secondary);
  text-align: center;
  padding-top: var(--space-sm);
  margin-top: var(--space-xs);
  border-top: 1px solid #f0f0f0;
}

.mask { position: fixed; inset: 0; background: rgba(29,112,184,0.6); z-index: 100; }

/* ===== 分享图片预览弹窗 ===== */
.share-panel {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: calc(100% - 32px);
  max-width: 420px;
  background: #ffffff;
  border: 1px solid var(--border);
  z-index: 102;
  display: flex;
  flex-direction: column;
  max-height: 92vh;
}
.share-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-sm) var(--space-lg);
  border-bottom: 1px solid var(--border);
  background: #f3f2f1;
  flex-shrink: 0;
}
.share-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.share-body {
  padding: var(--space-md);
  overflow-y: auto;
  text-align: center;
}
.share-img {
  width: 100%;
  height: auto;
  border: 1px solid #eee;
  display: block;
}
.share-hint {
  font-size: 13px;
  color: var(--text-secondary);
  margin: var(--space-sm) 0;
}
.share-save-btn {
  display: block;
  width: 100%;
  padding: 10px;
  font-size: 15px;
  font-weight: 700;
  color: #fff;
  background: #1d70b8;
  border: none;
  border-radius: 2px;
  cursor: pointer;
}
</style>
