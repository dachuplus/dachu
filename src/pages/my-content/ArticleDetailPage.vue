<template>
  <div class="dp-page" v-if="article">
    <div class="dp-disclaimer">
      大厨先生-个人博客声明：本站所有内容仅代表作者个人研究观点，不构成任何投资建议，亦不构成金融产品营销。市场有风险，决策需谨慎。
    </div>
    <router-link to="/content" class="dp-back">← 返回博客列表</router-link>

    <article class="dp-article">
      <h1 class="dp-title">{{ article.title }}</h1>
      <div class="dp-meta">
        <span v-if="author">{{ author.author_name }}</span>
        <span v-else>编辑部</span>
        <span v-if="article.published_at">· {{ formatDate(article.published_at) }}</span>
        <span>· {{ article.views || 0 }} 浏览</span>
      </div>
      <div v-if="article.cover_image" class="dp-cover">
        <img :src="article.cover_image" :alt="article.title" />
      </div>
      <div class="dp-content" v-html="renderedContent"></div>
      <div v-if="article.tags && article.tags.length" class="dp-tags">
        <span v-for="t in article.tags" :key="t" class="dp-tag">{{ t }}</span>
      </div>
      <div class="dp-disclaimer dp-disclaimer--footer">
        风险提示：以上内容基于公开信息整理，仅供研究参考。投资有风险，过往业绩不代表未来表现，请独立判断并自担风险。
      </div>
    </article>
  </div>
  <div v-else-if="loading" class="dp-loading">加载中…</div>
  <div v-else class="dp-empty">文章不存在或尚未发布。</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getArticle, getAuthor, incrementViews } from '../../api/articles'
import { renderMarkdown } from '../../utils/markdown'

const route = useRoute()
const article = ref(null)
const author = ref(null)
const loading = ref(false)

const renderedContent = computed(() => renderMarkdown(article.value?.content || ''))

async function load() {
  loading.value = true
  try {
    const id = route.params.id
    const a = await getArticle(id)
    article.value = a || null
    if (a) {
      author.value = await getAuthor(a.author_email)
      if (a.status === 'published') incrementViews(id).catch(() => {})
    }
  } catch (e) {
    article.value = null
  } finally {
    loading.value = false
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
</script>

<style scoped>
.dp-page {
  max-width: 680px;
  margin: 0 auto;
  padding: var(--space-md);
}
.dp-disclaimer {
  background: #f3f2f1;
  border-left: 4px solid #b1b4b6;
  padding: 10px 12px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: var(--space-md);
}
.dp-disclaimer--footer {
  margin-top: var(--space-lg);
  border-left-color: #d4351c;
}
.dp-article {
  max-width: 680px;
  margin: 0 auto;
}
.dp-back {
  display: inline-block;
  color: #1d70b8;
  font-size: 14px;
  text-decoration: underline;
  margin-bottom: var(--space-md);
}
.dp-title {
  font-size: 26px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-sm);
  line-height: 1.35;
}
.dp-meta {
  font-size: 13px;
  color: var(--text-muted);
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: var(--space-md);
}
.dp-cover {
  margin-bottom: var(--space-md);
}
.dp-cover img {
  width: 100%;
  display: block;
}
.dp-content {
  font-size: 16px;
  line-height: 1.8;
  color: var(--text-primary);
  word-break: break-word;
}
.dp-content :deep(h1),
.dp-content :deep(h2),
.dp-content :deep(h3),
.dp-content :deep(h4) {
  color: var(--text-primary);
  margin: var(--space-lg) 0 var(--space-sm);
  line-height: 1.4;
}
.dp-content :deep(h1) { font-size: 22px; }
.dp-content :deep(h2) { font-size: 20px; }
.dp-content :deep(h3) { font-size: 18px; }
.dp-content :deep(p) { margin: 0 0 var(--space-md); }
.dp-content :deep(ul),
.dp-content :deep(ol) { padding-left: 24px; margin: 0 0 var(--space-md); }
.dp-content :deep(li) { margin-bottom: 6px; }
.dp-content :deep(a) { color: #1d70b8; }
.dp-content :deep(blockquote) {
  border-left: 4px solid #b1b4b6;
  margin: 0 0 var(--space-md);
  padding: 4px 14px;
  color: var(--text-secondary);
  background: #f3f2f1;
}
.dp-content :deep(code) {
  background: #f3f2f1;
  padding: 1px 5px;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 14px;
}
.dp-content :deep(pre) {
  background: #0b0c0c;
  color: #fff;
  padding: 12px 14px;
  overflow-x: auto;
  margin: 0 0 var(--space-md);
}
.dp-content :deep(pre code) {
  background: transparent;
  color: #fff;
  padding: 0;
}
.dp-content :deep(img) {
  max-width: 100%;
  display: block;
  margin: var(--space-md) 0;
}
.dp-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--border);
  margin: var(--space-lg) 0;
}
.dp-tags { margin-top: var(--space-lg); display: flex; gap: 8px; flex-wrap: wrap; }
.dp-tag {
  background: #f3f2f1;
  color: var(--text-secondary);
  padding: 2px 10px;
  font-size: 13px;
}
.dp-loading, .dp-empty {
  padding: 60px 0;
  text-align: center;
  color: var(--text-secondary);
}
</style>
