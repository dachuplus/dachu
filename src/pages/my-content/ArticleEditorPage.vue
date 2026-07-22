<template>
  <div class="ed-page">
    <header class="ed-header">
      <h1 class="ed-title">{{ isEdit ? '编辑文章' : '写文章' }}</h1>
      <button class="ed-cancel" @click="goBack">取消</button>
    </header>

    <div v-if="!isOwner" class="ed-noauth">无访问权限</div>

    <template v-else>
      <div class="ed-disclaimer">
        合规提示：内容须为独立性研究，严禁出现「保本 / 稳赚 / 必涨 / 推荐买入 / 代客理财」等违规表述，违者将被系统拦截。
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
            <button class="ed-tool" @click="insertImage">插入图片</button>
            <input ref="fileInput" type="file" accept="image/*" style="display:none" @change="onFileChange" />
          </div>
          <textarea v-model="form.content" class="ed-textarea"
            placeholder="支持 Markdown：# 标题、**粗体**、*斜体*、`代码`、> 引用、- 列表、[链接](url)、![图片](url)"></textarea>
        </div>

        <div v-if="complianceHits.length" class="ed-compliance">
          ⚠ 合规拦截：检测到不合规表述 —— {{ complianceHits.join('、') }}。请修改后重试。
        </div>
        <div v-if="errorMsg" class="ed-error">{{ errorMsg }}</div>

        <div class="ed-actions">
          <button class="ed-btn ed-btn--draft" :disabled="saving" @click="onSave('draft')">保存草稿</button>
          <button class="ed-btn ed-btn--pub" :disabled="saving" @click="onSave('published')">
            {{ isEdit ? '更新发布' : '发布' }}
          </button>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import {
  getArticle, createArticle, updateArticle, uploadArticleImage, checkCompliance,
} from '../../api/articles'
import { toast } from '../../composables/useToast'

const { isOwner } = useAuth()
const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const fileInput = ref(null)
const lastUploadedUrl = ref('')
const complianceHits = ref([])
const errorMsg = ref('')
const saving = ref(false)
const form = ref({ title: '', summary: '', tagsRaw: '', cover_image: '', content: '' })

function goBack() {
  router.replace('/content')
}

async function load() {
  if (!isOwner.value) {
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

async function onSave(targetStatus) {
  complianceHits.value = []
  errorMsg.value = ''
  if (!form.value.title.trim()) {
    errorMsg.value = '请填写标题'
    return
  }
  if (!form.value.content.trim()) {
    errorMsg.value = '请填写正文'
    return
  }
  const hits = checkCompliance(form.value.title + ' ' + form.value.summary + ' ' + form.value.content)
  if (hits.length) {
    complianceHits.value = hits
    return
  }
  saving.value = true
  try {
    const payload = {
      title: form.value.title.trim(),
      summary: form.value.summary.trim(),
      content: form.value.content,
      cover_image: form.value.cover_image.trim() || null,
      tags: parseTags(form.value.tagsRaw),
      status: targetStatus,
    }
    if (isEdit.value) await updateArticle(route.params.id, payload)
    else await createArticle(payload)
    toast(targetStatus === 'published' ? '已发布' : '已保存草稿', 'success')
    router.replace('/content')
  } catch (err) {
    const msg = err.message || String(err)
    if (msg.indexOf('COMPLIANCE_VIOLATION') !== -1) {
      const m = msg.match(/COMPLIANCE_VIOLATION:\s*(.+)$/)
      complianceHits.value = m ? m[1].split('、') : ['不合规表述']
    } else {
      errorMsg.value = '保存失败：' + msg
    }
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ed-page {
  max-width: 720px;
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
.ed-toolbar { margin-bottom: 6px; }
.ed-tool {
  background: #f3f2f1;
  border: 1px solid #b1b4b6;
  color: #1d70b8;
  font-size: 13px;
  padding: 6px 12px;
  cursor: pointer;
}
.ed-tool:hover { background: #e8e8e8; }
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
</style>
