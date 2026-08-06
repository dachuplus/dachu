<template>
  <div class="ed-page">
    <header class="ed-header">
      <h1 class="ed-title">{{ isEdit ? '编辑文章' : '写文章' }}</h1>
      <button class="ed-cancel" @click="goBack">取消</button>
    </header>

    <div v-if="!canManageContent" class="ed-noauth">无访问权限</div>

    <template v-else>
      <div class="ed-disclaimer">
        合规提示：内容须为独立性研究，建议避免「保本 / 稳赚 / 必涨 / 推荐买入 / 代客理财」等表述。
      </div>

      <div class="ed-form">
        <label class="ed-field">
          <span class="ed-label">标题 *</span>
          <input v-model="form.title" class="ed-input" maxlength="200" placeholder="文章标题" />
        </label>

        <label class="ed-field">
          <span class="ed-label">摘要</span>
          <input v-model="form.summary" class="ed-input" placeholder="一句话摘要（可选）" />
        </label>

        <label class="ed-field">
          <span class="ed-label">标签（逗号或空格分隔）</span>
          <input v-model="form.tagsRaw" class="ed-input" placeholder="如：基金研究, 方法论" />
        </label>

        <label class="ed-field">
          <span class="ed-label">封面图 URL</span>
          <div class="ed-cover-row">
            <input v-model="form.cover_image" class="ed-input" placeholder="https://..." />
            <button v-if="lastUploadedUrl" class="ed-useimg" @click="form.cover_image = lastUploadedUrl">用刚上传图片</button>
          </div>
        </label>

        <div class="ed-field">
          <span class="ed-label">正文（Markdown）*</span>
          <div class="ed-toolbar">
            <div class="ed-tool-group">
              <button class="ed-tool" type="button" title="粗体" @click="applyWrap('**','**','粗体文字')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 4h8a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/><path d="M6 12h9a4 4 0 0 1 4 4 4 4 0 0 1-4 4H6z"/></svg></button>
              <button class="ed-tool" type="button" title="斜体" @click="applyWrap('*','*','斜体文字')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="19" y1="4" x2="10" y2="4"/><line x1="14" y1="20" x2="5" y2="20"/><line x1="15" y1="4" x2="9" y2="20"/></svg></button>
              <button class="ed-tool" type="button" title="链接" @click="applyWrap('[', '](https://)', '链接文字')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg></button>
              <button class="ed-tool" type="button" title="图片" @click="insertImage"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg></button>
            </div>
            <div class="ed-tool-group">
              <button class="ed-tool" type="button" title="标题" @click="applyLinePrefix('## ')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h8"/><path d="M4 18V6"/><path d="M12 18V6"/><path d="M17 12a3 3 0 1 0 0-6v6z"/></svg></button>
              <button class="ed-tool" type="button" title="子标题" @click="applyLinePrefix('### ')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h8"/><path d="M4 18V6"/><path d="M12 18V6"/><path d="M17 13a2 2 0 1 0 0-4v4z"/></svg></button>
              <button class="ed-tool" type="button" title="引用" @click="applyLinePrefix('> ')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 21c3 0 7-1 7-8V5c0-1.25-.756-2.017-2-2H4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2 1 0 1 0 1 1v1c0 1-1 2-2 2s-1 .008-1 1.031V21z"/><path d="M15 21c3 0 7-1 7-8V5c0-1.25-.757-2.017-2-2h-4c-1.25 0-2 .75-2 1.972V11c0 1.25.75 2 2 2h.75c0 2.25.25 4-.75 4v3z"/></svg></button>
              <button class="ed-tool" type="button" title="无序列表" @click="applyLinePrefix('- ')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><circle cx="4" cy="6" r="1.5" fill="currentColor" stroke="none"/><circle cx="4" cy="12" r="1.5" fill="currentColor" stroke="none"/><circle cx="4" cy="18" r="1.5" fill="currentColor" stroke="none"/></svg></button>
              <button class="ed-tool" type="button" title="有序列表" @click="applyLinePrefix('1. ')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="10" y1="6" x2="21" y2="6"/><line x1="10" y1="12" x2="21" y2="12"/><line x1="10" y1="18" x2="21" y2="18"/><text x="3" y="7.5" font-size="8" fill="currentColor" stroke="none">1</text><text x="3" y="13.5" font-size="8" fill="currentColor" stroke="none">2</text><text x="3" y="19.5" font-size="8" fill="currentColor" stroke="none">3</text></svg></button>
              <button class="ed-tool" type="button" title="分割线" @click="applyBlock('---')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="3" y1="12" x2="21" y2="12"/></svg></button>
            </div>
            <div class="ed-tool-group">
              <span class="ed-tool-label">对齐</span>
              <button class="ed-tool" type="button" title="左对齐" @click="applyAlign('left')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="15" y2="12"/><line x1="3" y1="18" x2="18" y2="18"/></svg></button>
              <button class="ed-tool" type="button" title="居中" @click="applyAlign('center')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="6" y1="12" x2="18" y2="12"/><line x1="4" y1="18" x2="20" y2="18"/></svg></button>
              <button class="ed-tool" type="button" title="右对齐" @click="applyAlign('right')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="9" y1="12" x2="21" y2="12"/><line x1="6" y1="18" x2="21" y2="18"/></svg></button>
              <button class="ed-tool" type="button" title="两端对齐" @click="applyAlign('justify')"><svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg></button>
            </div>
            <div class="ed-tool-group ed-tool-group--mode">
              <button class="ed-tool ed-tool--mode" type="button" :class="{active: !previewMode}" @click="previewMode=false">编辑</button>
              <button class="ed-tool ed-tool--mode" type="button" :class="{active: previewMode}" @click="previewMode=true">预览</button>
            </div>
            <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileChange" />
          </div>

          <div class="ed-editor-wrap">
            <textarea v-show="!previewMode" ref="textarea" v-model="form.content" class="ed-textarea"
              placeholder="支持 Markdown：# 标题、**粗体**、*斜体*、`代码`、> 引用、- 列表、[链接](url)、![图片](url)；悬停图标查看功能。"></textarea>
            <div v-show="previewMode" class="ed-preview" v-html="renderedPreview"></div>
          </div>
          <p class="ed-hint">提示：选中文字后点工具栏图标可快速加粗 / 加链接 / 对齐；两端对齐适用于全文或大段文字。</p>
        </div>

        <div v-if="complianceHits.length" class="ed-compliance">
          ⚠ 合规拦截：检测到不合规表述 —— {{ complianceHits.join('、') }}。请修改后重试。
        </div>
        <div v-if="errorMsg" class="ed-error">{{ errorMsg }}</div>

        <div class="ed-schedule">
          <span class="ed-label">发布方式</span>
          <div class="ed-schedule-opts">
            <label class="ed-radio"><input type="radio" value="now" v-model="scheduleMode" /> 立即发布</label>
            <label class="ed-radio"><input type="radio" value="scheduled" v-model="scheduleMode" /> 定时发布</label>
          </div>
          <div v-if="scheduleMode === 'scheduled'" class="ed-schedule-when">
            <input type="datetime-local" v-model="scheduledAt" class="ed-input" />
            <p class="ed-hint">选择未来的日期与时间，到点后系统自动发布（精确到分钟）。</p>
          </div>
        </div>

        <!-- 公众号同步发布 -->
        <div class="ed-wechat">
          <label class="ed-wechat__toggle">
            <input type="checkbox" v-model="wechatEnabled" />
            <span class="ed-label">同步发布到微信公众号</span>
          </label>
          <template v-if="wechatEnabled">
            <div class="ed-ip-box">
              <span class="ed-label">服务器出口 IP（请加入公众号 IP 白名单）</span>
              <span v-if="detectingIp" class="ed-ip-value ed-ip-loading">检测中…</span>
              <span v-else-if="detectedIp" class="ed-ip-value">{{ detectedIp }} <button type="button" class="ed-ip-copy" @click="copyIp">复制</button></span>
              <span v-else class="ed-ip-value ed-ip-err">检测失败，请刷新重试</span>
            </div>
            <label class="ed-field">
              <span class="ed-label">公众号 AppID *</span>
              <input v-model="wechatAppId" class="ed-input" placeholder="wx 开头的 AppID" />
            </label>
            <label class="ed-field">
              <span class="ed-label">公众号 AppSecret *</span>
              <input v-model="wechatAppSecret" type="password" class="ed-input" placeholder="AppSecret（仅本次使用，不存储）" />
            </label>
            <p class="ed-hint">发布时服务器会自动检测出口 IP。如果提示 IP 白名单错误，请将显示的 IP 加入公众号后台「IP 白名单」后重试。</p>
          </template>
        </div>

        <!-- 微信发布结果 -->
        <div v-if="wechatResult" :class="['ed-wechat-result', wechatResult.success ? 'ed-wechat-result--ok' : 'ed-wechat-result--err']">
          {{ wechatResult.success ? '✅ ' + wechatResult.message : '❌ ' + wechatResult.error }}
        </div>

        <div class="ed-actions">
          <button class="ed-btn ed-btn--draft" :disabled="saving" @click="onSave('draft')">
            {{ saving && savingAction === 'draft' ? (uploadProgress ? '上传中 ' + Math.round(uploadProgress.done / uploadProgress.total * 100) + '%' : '保存中...') : '保存草稿' }}
          </button>
          <button class="ed-btn ed-btn--pub" :disabled="saving" @click="onSave('published')">
            {{ saving && savingAction === 'published' ? (uploadProgress ? '上传中 ' + Math.round(uploadProgress.done / uploadProgress.total * 100) + '%' : '发布中...') : (scheduleMode === 'scheduled' ? '定时发布' : (isEdit ? '更新发布' : '发布')) }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import {
  getArticle, createArticle, updateArticle, uploadArticleImage, checkCompliance,
} from '../../api/articles'
import { toast } from '../../composables/useToast'
import { renderMarkdown } from '../../utils/markdown'

const { isOwner } = useAuth()
const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)

// 可管理内容：仅管理员可写/编辑/发布（路由 ownerOnly 亦拦截非管理员）
const canManageContent = computed(() => isOwner.value)
const fileInput = ref(null)
const textarea = ref(null)
const previewMode = ref(false)
const renderedPreview = computed(() => renderMarkdown(form.value.content || ''))
const lastUploadedUrl = ref('')
const complianceHits = ref([])
const errorMsg = ref('')
const saving = ref(false)
const savingAction = ref(null) // 'draft' | 'published' | null
const uploadProgress = ref(null) // { done, total } 或 null
const form = ref({ title: '', summary: '', tagsRaw: '', cover_image: '', content: '' })
const scheduleMode = ref('now') // 'now' | 'scheduled'
const scheduledAt = ref('')    // datetime-local 字符串（本地时间）

// 公众号同步发布
const wechatEnabled = ref(false)
const wechatAppId = ref('')
const wechatAppSecret = ref('')
const wechatResult = ref(null)  // { success, message/error } | null
const wechatPublishing = ref(false)
const detectedIp = ref('')
const detectingIp = ref(false)

/** 检测 EdgeOne 函数当前出口 IP（用于填入微信白名单） */
async function detectEgressIp() {
  detectingIp.value = true
  detectedIp.value = ''
  try {
    const res = await fetch('/api/detect-ip')
    const data = await res.json()
    if (data.ip && data.ip !== 'unknown') {
      detectedIp.value = data.ip
    }
  } catch (_) {
    detectedIp.value = ''
  } finally {
    detectingIp.value = false
  }
}

/** 勾选/取消同步时触发 IP 检测 */
watch(wechatEnabled, (val) => {
  if (val) detectEgressIp()
})

/** 复制 IP 到剪贴板 */
async function copyIp() {
  try {
    await navigator.clipboard.writeText(detectedIp.value)
    toast('IP 已复制', 'success')
  } catch (_) {
    toast('复制失败，请手动选择', 'error')
  }
}

function goBack() {
  router.replace('/content')
}

/** 将 UTC ISO 时间转为本地 datetime-local 输入值（YYYY-MM-DDTHH:MM） */
function toLocalInput(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  if (isNaN(d.getTime())) return ''
  const local = new Date(d.getTime() - d.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 16)
}

async function load() {
  if (!canManageContent.value) {
    router.replace('/content')
    return
  }
  if (isEdit.value) {
    try {
      const a = await getArticle(route.params.id)
      if (!a) {
        toast('文章不存在', 'error')
        router.replace('/content')
        return
      }
      form.value = {
        title: a.title,
        summary: a.summary || '',
        tagsRaw: (a.tags || []).join(', '),
        cover_image: a.cover_image || '',
        content: a.content || '',
      }
      // 回填定时发布状态（仅当为定时草稿时）
      if (a.scheduled_at && a.status === 'draft') {
        scheduleMode.value = 'scheduled'
        scheduledAt.value = toLocalInput(a.scheduled_at)
      } else {
        scheduleMode.value = 'now'
        scheduledAt.value = ''
      }
    } catch (e) {
      toast('加载失败：' + (e.message || e), 'error')
    }
  }
}

function parseTags(raw) {
  return String(raw || '')
    .split(/[,，\s]+/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function onFileChange(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  try {
    const { url } = await uploadArticleImage(file)
    lastUploadedUrl.value = url
    form.value.content += `\n![${file.name}](${url})\n`
    toast('图片已上传并插入', 'success')
  } catch (err) {
    toast('上传失败：' + (err.message || err), 'error')
  }
  e.target.value = ''
}

function insertImage() {
  if (fileInput.value) fileInput.value.click()
}

// —— Markdown 格式工具栏：基于 textarea 选区插入语法 ——
function applyWrap(before, after, placeholder) {
  const ta = textarea.value
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const selected = form.value.content.substring(start, end) || placeholder
  form.value.content =
    form.value.content.substring(0, start) + before + selected + after + form.value.content.substring(end)
  const caret = start + before.length
  nextTick(() => {
    ta.focus()
    ta.selectionStart = caret
    ta.selectionEnd = caret + selected.length
  })
}

function applyLinePrefix(prefix) {
  const ta = textarea.value
  if (!ta) return
  const start = ta.selectionStart
  const val = form.value.content
  const lineStart = val.lastIndexOf('\n', start - 1) + 1
  form.value.content = val.substring(0, lineStart) + prefix + val.substring(lineStart)
  nextTick(() => {
    ta.focus()
    ta.selectionStart = ta.selectionEnd = start + prefix.length
  })
}

function applyBlock(text) {
  const ta = textarea.value
  if (!ta) return
  const start = ta.selectionStart
  const val = form.value.content
  const before = val.substring(0, start)
  const needsNlBefore = before && !before.endsWith('\n') ? '\n' : ''
  const snippet = needsNlBefore + text + '\n'
  form.value.content = before + snippet + val.substring(start)
  nextTick(() => {
    ta.focus()
    ta.selectionStart = ta.selectionEnd = start + snippet.length
  })
}

function applyAlign(align) {
  const ta = textarea.value
  if (!ta) return
  const start = ta.selectionStart
  const end = ta.selectionEnd
  const val = form.value.content
  const selected = val.substring(start, end) || '对齐的文字'
  const block = ':::' + align + '\n' + selected + '\n:::'
  const before = val.substring(0, start)
  const after = val.substring(end)
  const prefix = before && !before.endsWith('\n') ? '\n' : ''
  const suffix = after && !after.startsWith('\n') ? '\n' : ''
  const snippet = prefix + block + suffix
  form.value.content = before + snippet + after
  const caret = start + prefix.length + (':::' + align + '\n').length
  nextTick(() => {
    ta.focus()
    ta.selectionStart = ta.selectionEnd = caret
  })
}

async function onSave(targetStatus) {
  complianceHits.value = []
  errorMsg.value = ''
  if (!form.value.title.trim()) {
    errorMsg.value = '请填写标题'
    toast('请填写文章标题', 'error')
    return
  }
  if (!form.value.content.trim()) {
    errorMsg.value = '请填写正文'
    toast('请填写正文内容', 'error')
    return
  }
  const hits = checkCompliance(form.value.title + ' ' + form.value.summary + ' ' + form.value.content)
  if (hits.length) {
    // 仅提示，不拦截
    toast('提示：内容包含敏感词「' + hits.join('、') + '」，请确认无误后继续', 'warning')
  }
  // 定时发布校验：选中定时模式且点击发布时，时间必须晚于当前
  if (scheduleMode.value === 'scheduled' && targetStatus === 'published') {
    if (!scheduledAt.value) {
      errorMsg.value = '请选择定时发布的时间'
      toast('请选择定时发布的时间', 'error')
      return
    }
    const t = new Date(scheduledAt.value)
    if (isNaN(t.getTime()) || t.getTime() <= Date.now()) {
      errorMsg.value = '定时发布时间必须晚于当前时间'
      toast('定时发布时间必须晚于当前时间', 'error')
      return
    }
  }
  saving.value = true
  savingAction.value = targetStatus
  uploadProgress.value = null
  try {
    const payload = {
      title: form.value.title.trim(),
      summary: form.value.summary.trim(),
      content: form.value.content,
      cover_image: form.value.cover_image.trim() || null,
      tags: parseTags(form.value.tagsRaw),
      status: targetStatus,
      // 定时发布：仅在「定时模式 + 点击发布」时透传未来时间；其他情况清空定时
      scheduled_at: (scheduleMode.value === 'scheduled' && targetStatus === 'published')
        ? new Date(scheduledAt.value).toISOString()
        : null,
      // 分块上传进度回调
      onProgress: (done, total) => { uploadProgress.value = { done, total } },
      // 网络重试回调：单步失败自动重试时通知用户
      onRetry: (nextAttempt, maxAttempts) => {
        const msg = targetStatus === 'published' ? '发布' : '保存'
        toast(msg + ' 网络慢，正在自动重试 (' + nextAttempt + '/' + maxAttempts + ')…', 'info')
      },
    }
    // 分块上传：Edge Function 在新加坡执行，国内弱网给 180 秒
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 180000)
    let result
    if (isEdit.value) {
      result = await Promise.race([
        updateArticle(route.params.id, payload),
        new Promise((_, reject) =>
          controller.signal.addEventListener('abort', () => reject(new Error('请求超时，请检查网络后重试')))
        )
      ])
    } else {
      result = await Promise.race([
        createArticle(payload),
        new Promise((_, reject) =>
          controller.signal.addEventListener('abort', () => reject(new Error('请求超时，请检查网络后重试')))
        )
      ])
    }
    clearTimeout(timer)
    uploadProgress.value = null
    toast(result && result.scheduled ? '已设置定时发布' : (targetStatus === 'published' ? '已发布' : '已保存草稿'), 'success')

    // 公众号同步发布（仅在「已发布」状态且用户开启了微信同步时触发）
    if (targetStatus === 'published' && wechatEnabled.value && wechatAppId.value.trim() && wechatAppSecret.value.trim()) {
      await pushToWechat()
    }

    router.replace('/content')
  } catch (err) {
    uploadProgress.value = null
    const msg = err.message || String(err)
    if (msg.indexOf('COMPLIANCE_VIOLATION') !== -1) {
      const m = msg.match(/COMPLIANCE_VIOLATION:\s*(.+)$/)
      toast('提示：内容包含敏感词「' + (m ? m[1] : '不合规表述') + '」', 'warning')
    } else if (msg === '请求超时，请检查网络后重试' || msg.indexOf('abort') !== -1 || msg.indexOf('timeout') !== -1) {
      toast('发布超时，请检查网络连接后重试', 'error')
    } else {
      errorMsg.value = '保存失败：' + msg
      toast('保存失败：' + msg, 'error')
    }
  } finally {
    saving.value = false
    savingAction.value = null
  }
}

/**
 * Markdown → 微信公众号 HTML（简化版，与 functions/api/wechat-publish.js 保持一致）
 */
function mdToWechatHtml(md) {
  if (!md) return ''
  let html = md
    .replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
      '<pre style="background:#f5f5f5;padding:12px;border-radius:4px;overflow-x:auto;font-size:14px;line-height:1.6;"><code>' + code.trim().replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;') + '</code></pre>')
    .replace(/`([^`]+)`/g, '<code style="background:#f0f0f0;padding:2px 4px;border-radius:3px;font-size:14px;">$1</code>')
    .replace(/^#### (.+)$/gm, '<h4 style="font-size:16px;font-weight:bold;margin:16px 0 8px;">$1</h4>')
    .replace(/^### (.+)$/gm, '<h3 style="font-size:18px;font-weight:bold;margin:18px 0 8px;">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 style="font-size:20px;font-weight:bold;margin:20px 0 10px;">$1</h2>')
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
  if (!html.startsWith('<')) html = '<p style="margin:12px 0;font-size:15px;line-height:1.8;">' + html + '</p>'
  return html
}

/** 翻译微信错误码 */
function translateWechatErr(code, msg) {
  const map = {
    40013: 'AppID 不正确',
    40001: 'access_token 无效或过期',
    40125: 'AppSecret 不正确',
    40164: 'IP 不在白名单中（请将当前公网 IP 加入公众号后台 IP 白名单）',
    48001: '该账号未开通群发接口权限，需完成微信认证并开通「发布能力」',
    45009: '今日群发次数已达上限',
    45027: '草稿箱已达上限',
    50007: '图文消息内容不合法',
  }
  return map[code] || msg || '未知错误'
}

/** 推送文章到微信公众号 — 通过 EdgeOne 函数代理调用微信 API */
async function pushToWechat() {
  wechatResult.value = null
  wechatPublishing.value = true
  try {
    const res = await fetch('/api/wechat-publish', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        appid: wechatAppId.value.trim(),
        appsecret: wechatAppSecret.value.trim(),
        title: form.value.title.trim(),
        content: form.value.content,
        summary: form.value.summary.trim(),
        cover_image: form.value.cover_image.trim() || '',
        author: '大厨先生',
      }),
    })
    const data = await res.json()
    // 用函数返回的实际出口 IP 更新界面显示
    if (data.egress_ip) detectedIp.value = data.egress_ip

    if (data.success) {
      wechatResult.value = { success: true, message: data.message }
      toast('已同步推送到公众号', 'success')
    } else {
      let errMsg = data.error || '公众号发布失败'
      // IP 错误时确保界面上的 IP 是精确值
      if (data.egress_ip && errMsg.indexOf('IP') !== -1) {
        detectedIp.value = data.egress_ip
      }
      wechatResult.value = { success: false, error: errMsg }
      toast('公众号推送失败', 'error')
    }
  } catch (e) {
    const msg = e.message || String(e)
    wechatResult.value = { success: false, error: msg }
    toast('公众号推送失败：' + msg, 'error')
  } finally {
    wechatPublishing.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ed-page {
  max-width: 680px;
  margin: 0 auto;
  padding: var(--space-md);
}
.ed-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-md);
}
.ed-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.ed-cancel {
  background: none;
  border: 1px solid #b1b4b6;
  color: var(--text-secondary);
  font-size: 14px;
  padding: 6px 14px;
  cursor: pointer;
}
.ed-cancel:hover { border-color: #1d70b8; color: #1d70b8; }
.ed-noauth {
  padding: 60px 0;
  text-align: center;
  color: #d4351c;
  font-size: 18px;
  font-weight: 700;
}
.ed-disclaimer {
  background: #f3f2f1;
  border-left: 4px solid #b1b4b6;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-md);
}
.ed-form { display: flex; flex-direction: column; gap: var(--space-md); }
.ed-field { display: flex; flex-direction: column; gap: 6px; }
.ed-label { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.ed-input {
  border: 2px solid #b1b4b6;
  padding: 8px 10px;
  font-size: 15px;
  width: 100%;
  box-sizing: border-box;
}
.ed-input:focus { outline: 3px solid #ffdd00; border-color: #1d70b8; }
.ed-cover-row { display: flex; gap: 8px; align-items: center; }
.ed-cover-row .ed-input { flex: 1; }
.ed-useimg {
  flex: none;
  background: #f3f2f1;
  border: 1px solid #b1b4b6;
  color: #1d70b8;
  font-size: 13px;
  padding: 8px 10px;
  cursor: pointer;
  white-space: nowrap;
}
.ed-useimg:hover { background: #e8e8e8; }
.ed-toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
  align-items: center;
}
.ed-tool-group {
  display: flex;
  gap: 4px;
  align-items: center;
  padding-right: 6px;
  border-right: 1px solid #b1b4b6;
}
.ed-tool-group:last-child { border-right: none; }
.ed-tool-label {
  font-size: 12px;
  color: var(--text-secondary);
  font-weight: 700;
}
.ed-tool {
  background: #f3f2f1;
  border: 1px solid #b1b4b6;
  color: #1d70b8;
  font-size: 13px;
  padding: 6px 8px;
  cursor: pointer;
  white-space: nowrap;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 32px;
  height: 32px;
}
.ed-tool:hover { background: #e8e8e8; }
.ed-tool--mode.active { background: #1d70b8; color: #fff; border-color: #1d70b8; }
.ed-editor-wrap { position: relative; }
.ed-textarea {
  border: 2px solid #b1b4b6;
  padding: 10px;
  font-size: 15px;
  line-height: 1.7;
  width: 100%;
  min-height: 360px;
  box-sizing: border-box;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  resize: vertical;
}
.ed-textarea:focus { outline: 3px solid #ffdd00; border-color: #1d70b8; }
.ed-preview {
  border: 2px solid #b1b4b6;
  border-top: none;
  padding: 14px 16px;
  min-height: 360px;
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-primary);
  word-break: break-word;
  background: #fff;
}
.ed-hint { font-size: 12px; color: var(--text-muted); margin: 6px 0 0; }
.ed-ip-box { display: flex; flex-direction: column; gap: 4px; padding: 8px 10px; background: #fff; border: 2px solid #1d70b8; margin-bottom: 10px; }
.ed-ip-value { font-size: 14px; font-weight: 700; color: #1d70b8; font-family: monospace; display: flex; align-items: center; gap: 8px; }
.ed-ip-loading, .ed-ip-err { color: #505050; font-weight: 400; font-family: inherit; }
.ed-ip-copy { font-size: 12px; padding: 2px 8px; border: 1px solid #1d70b8; background: #1d70b8; color: #fff; cursor: pointer; }
.ed-ip-copy:hover { background: #0b4f8a; }
.ed-textarea {
  border: 2px solid #b1b4b6;
  padding: 10px;
  font-size: 15px;
  line-height: 1.7;
  width: 100%;
  min-height: 320px;
  box-sizing: border-box;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  resize: vertical;
}
.ed-textarea:focus { outline: 3px solid #ffdd00; border-color: #1d70b8; }
.ed-compliance {
  background: #fff;
  border: 2px solid #d4351c;
  border-left-width: 6px;
  padding: 10px 12px;
  color: #d4351c;
  font-size: 14px;
  font-weight: 700;
}
.ed-error {
  background: #fff;
  border: 2px solid #d4351c;
  border-left-width: 6px;
  padding: 10px 12px;
  color: #d4351c;
  font-size: 14px;
}
.ed-schedule { display: flex; flex-direction: column; gap: 8px; border: 1px solid #b1b4b6; padding: 12px; background: #f3f2f1; }
.ed-schedule-opts { display: flex; gap: 18px; }
.ed-radio { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 700; color: var(--text-primary); cursor: pointer; }
.ed-radio input { width: 16px; height: 16px; accent-color: #1d70b8; }
.ed-schedule-when { display: flex; flex-direction: column; gap: 4px; }
.ed-schedule-when .ed-input { max-width: 280px; }

/* 公众号同步发布 */
.ed-wechat { display: flex; flex-direction: column; gap: 10px; border: 1px solid #b1b4b6; padding: 12px; background: #f3f2f1; }
.ed-wechat__toggle { display: inline-flex; align-items: center; gap: 8px; cursor: pointer; font-size: 14px; font-weight: 700; color: var(--text-primary); }
.ed-wechat__toggle input[type="checkbox"] { width: 16px; height: 16px; accent-color: #1d70b8; cursor: pointer; }

/* 微信发布结果 */
.ed-wechat-result {
  padding: 10px 14px;
  font-size: 14px;
  font-weight: 700;
  border-left-width: 5px;
  border-left-style: solid;
}
.ed-wechat-result--ok {
  background: #f0f9f0;
  border-color: #00703c;
  color: #00703c;
}
.ed-wechat-result--err {
  background: #fff2f0;
  border-color: #d4351c;
  color: #d4351c;
}
.ed-actions { display: flex; gap: var(--space-sm); margin-top: var(--space-sm); }
.ed-btn {
  flex: 1;
  border: none;
  font-size: 16px;
  font-weight: 700;
  padding: 12px;
  cursor: pointer;
}
.ed-btn:disabled { opacity: 0.6; cursor: default; }
.ed-btn--draft { background: #f3f2f1; color: var(--text-secondary); border: 1px solid #b1b4b6; }
.ed-btn--draft:hover:not(:disabled) { background: #e8e8e8; }
.ed-btn--pub { background: #1d70b8; color: #fff; }
.ed-btn--pub:hover:not(:disabled) { background: #003078; }

/* 预览区 Markdown 渲染样式（与文章详情保持一致） */
.ed-preview :deep(h1),
.ed-preview :deep(h2),
.ed-preview :deep(h3),
.ed-preview :deep(h4) {
  color: var(--text-primary);
  margin: 18px 0 8px;
  line-height: 1.4;
}
.ed-preview :deep(h1) { font-size: 22px; }
.ed-preview :deep(h2) { font-size: 20px; }
.ed-preview :deep(h3) { font-size: 18px; }
.ed-preview :deep(p) { margin: 0 0 12px; }
.ed-preview :deep(ul),
.ed-preview :deep(ol) { padding-left: 24px; margin: 0 0 12px; }
.ed-preview :deep(li) { margin-bottom: 6px; }
.ed-preview :deep(a) { color: #1d70b8; }
.ed-preview :deep(blockquote) {
  border-left: 4px solid #b1b4b6;
  margin: 0 0 12px;
  padding: 4px 14px;
  color: var(--text-secondary);
  background: #f3f2f1;
}
.ed-preview :deep(code) {
  background: #f3f2f1;
  padding: 1px 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 14px;
}
.ed-preview :deep(pre) {
  background: #0b0c0c;
  color: #fff;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0 0 12px;
}
.ed-preview :deep(pre code) { background: transparent; color: #fff; padding: 0; }
.ed-preview :deep(img) { max-width: 100%; display: block; margin: 12px 0; }
.ed-preview :deep(hr) { border: none; border-top: 1px solid var(--border); margin: 24px 0; }
.ed-preview :deep(.align-left) { text-align: left; }
.ed-preview :deep(.align-center) { text-align: center; }
.ed-preview :deep(.align-right) { text-align: right; }
.ed-preview :deep(.align-justify) { text-align: justify; }
.ed-preview :deep(.align-center img) { margin-left: auto; margin-right: auto; }
.ed-preview :deep(.align-right img) { margin-left: auto; margin-right: 0; }
</style>
