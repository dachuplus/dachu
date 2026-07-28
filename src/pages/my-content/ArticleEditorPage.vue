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

        <div class="ed-actions">
          <button class="ed-btn ed-btn--draft" :disabled="saving" @click="onSave('draft')">
            {{ saving && savingAction === 'draft' ? (uploadProgress ? '上传中 ' + Math.round(uploadProgress.done / uploadProgress.total * 100) + '%' : '保存中...') : '保存草稿' }}
          </button>
          <button class="ed-btn ed-btn--pub" :disabled="saving" @click="onSave('published')">
            {{ saving && savingAction === 'published' ? (uploadProgress ? '上传中 ' + Math.round(uploadProgress.done / uploadProgress.total * 100) + '%' : '发布中...') : (isEdit ? '更新发布' : '发布') }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
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

function goBack() {
  router.replace('/content')
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
    toast(targetStatus === 'published' ? '已发布' : '已保存草稿', 'success')
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
