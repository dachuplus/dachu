<template>
  <div class="content-page">
    <header class="cp-header">
      <div class="cp-head-main">
        <h1 class="cp-title">内容</h1>
        <p class="cp-subtitle">独立性研究 · 仅代表个人观点，不构成投资建议或金融产品营销</p>
      </div>
      <router-link v-if="isOwner" to="/content/editor" class="cp-new-btn">+ 写文章</router-link>
    </header>

    <div v-if="isOwner" class="cp-viewswitch">
      <button :class="{ active: view === 'published' }" @click="setView('published')">已发布</button>
      <button :class="{ active: view === 'mine' }" @click="setView('mine')">我的全部（含草稿）</button>
    </div>

    <div v-if="loading" class="cp-loading">加载中…</div>
    <div v-else-if="articles.length === 0" class="cp-empty">
      {{ isOwner && view === 'mine' ? '还没有文章，点击右上角「写文章」开始吧。' : '暂无已发布内容。' }}
    </div>

    <ul v-else class="cp-list">
      <li v-for="a in articles" :key="a.id" class="cp-card">
        <router-link :to="`/content/${a.id}`" class="cp-card-link">
          <div v-if="a.cover_image" class="cp-cover" :style="{ backgroundImage: 'url(' + a.cover_image + ')' }"></div>
          <div class="cp-card-body">
            <div class="cp-card-top">
              <span v-if="a.status === 'draft'" class="cp-badge cp-badge--draft">草稿</span>
              <span v-else class="cp-badge cp-badge--pub">已发布</span>
              <h2 class="cp-card-title">{{ a.title }}</h2>
            </div>
            <p v-if="a.summary" class="cp-card-summary">{{ a.summary }}</p>
            <div class="cp-card-meta">
              <span>{{ formatDate(a.published_at || a.updated_at) }}</span>
              <span class="cp-dot">·</span>
              <span>{{ a.views || 0 }} 浏览</span>
              <span v-for="t in (a.tags || [])" :key="t" class="cp-tag">{{ t }}</span>
            </div>
          </div>
        </router-link>
        <div v-if="isOwner" class="cp-card-actions">
          <router-link :to="`/content/editor/${a.id}`" class="cp-link-edit">编辑</router-link>
          <button class="cp-link-del" @click="onDelete(a)">删除</button>
        </div>
      </li>
    </ul>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { listArticles, deleteArticle } from '../../api/articles'
import { confirm, toast } from '../../composables/useToast'

const { isOwner, user } = useAuth()
const route = useRoute()
const articles = ref([])
const loading = ref(false)
const view = ref('published')

async function load() {
  loading.value = true
  try {
    if (isOwner.value && view.value === 'mine') {
      const email = user.value?.email
      articles.value = await listArticles({ status: null, authorEmail: email, limit: 200 })
    } else {
      articles.value = await listArticles({ status: 'published', limit: 200 })
    }
  } catch (e) {
    toast('加载失败：' + (e.message || e), 'error')
  } finally {
    loading.value = false
  }
}

function setView(v) {
  view.value = v
  load()
}

async function onDelete(a) {
  const ok = await confirm('删除文章', `确定删除《${a.title}》吗？此操作不可恢复。`)
  if (!ok) return
  try {
    await deleteArticle(a.id)
    toast('已删除', 'success')
    await load()
  } catch (e) {
    toast('删除失败：' + (e.message || e), 'error')
  }
}

function formatDate(s) {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d.getTime())) return ''
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

onMounted(load)
// 从编辑页返回列表时刷新
watch(() => route.fullPath, () => {
  if (route.path === '/content') load()
})
</script>

<style scoped>
.content-page {
  max-width: 720px;
  margin: 0 auto;
  padding: var(--space-md);
}
.cp-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-md);
  margin-bottom: var(--space-lg);
}
.cp-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}
.cp-subtitle {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.5;
}
.cp-new-btn {
  flex: none;
  background: #1d70b8;
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  padding: 8px 14px;
  text-decoration: none;
  white-space: nowrap;
}
.cp-new-btn:hover { background: #003078; }
.cp-viewswitch {
  display: flex;
  gap: 0;
  border-bottom: 2px solid var(--border);
  margin-bottom: var(--space-md);
}
.cp-viewswitch button {
  background: transparent;
  border: none;
  padding: 10px 16px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 4px solid transparent;
  margin-bottom: -2px;
}
.cp-viewswitch button.active {
  color: #1d70b8;
  border-bottom-color: #1d70b8;
}
.cp-loading, .cp-empty {
  padding: 40px 0;
  text-align: center;
  color: var(--text-secondary);
  font-size: 15px;
}
.cp-list { list-style: none; margin: 0; padding: 0; }
.cp-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 6px solid #1d70b8;
  margin-bottom: var(--space-md);
}
.cp-card-link {
  display: flex;
  text-decoration: none;
  color: inherit;
  padding: var(--space-md);
  gap: var(--space-md);
}
.cp-cover {
  flex: none;
  width: 96px;
  height: 72px;
  background-size: cover;
  background-position: center;
  background-color: #f3f2f1;
}
.cp-card-body { flex: 1; min-width: 0; }
.cp-card-top { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; flex-wrap: wrap; }
.cp-card-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}
.cp-card-summary {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 8px;
  line-height: 1.5;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.cp-card-meta {
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  gap: 6px;
  align-items: center;
  flex-wrap: wrap;
}
.cp-dot { color: var(--text-muted); }
.cp-tag {
  background: #f3f2f1;
  color: var(--text-secondary);
  padding: 1px 8px;
  font-size: 12px;
}
.cp-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 1px 8px;
}
.cp-badge--draft { background: #fff; color: #b1b4b6; border: 1px solid #b1b4b6; }
.cp-badge--pub { background: #1d70b8; color: #fff; }
.cp-card-actions {
  display: flex;
  gap: var(--space-md);
  padding: 0 var(--space-md) var(--space-md);
}
.cp-link-edit {
  color: #1d70b8;
  font-size: 14px;
  font-weight: 700;
  text-decoration: underline;
}
.cp-link-del {
  background: none;
  border: none;
  color: #d4351c;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
  text-decoration: underline;
}
</style>
