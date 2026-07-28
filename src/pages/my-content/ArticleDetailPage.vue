<template>
  <div class="dp-layout" v-if="article">
    <!-- 左侧文章列表 -->
    <aside class="dp-sidebar">
      <h3 class="dp-sidebar-title">文章列表</h3>
      <ul v-if="articleList.length" class="dp-sidebar-list">
        <li v-for="a in articleList" :key="a.id"
            :class="['dp-sidebar-item', { active: Number(a.id) === Number(route.params.id) }]">
          <router-link :to="`/content/${a.id}`" class="dp-sidebar-link">
            <span class="dp-sidebar-title-text">{{ a.title }}</span>
            <span class="dp-sidebar-date">{{ formatDate(a.published_at || a.updated_at) }}</span>
          </router-link>
        </li>
      </ul>
      <div v-else class="dp-sidebar-empty">暂无文章</div>
    </aside>

    <!-- 右侧正文 -->
    <main class="dp-main">
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
      </article>
    </main>
  </div>
  <div v-else-if="loading" class="dp-loading">加载中…</div>
  <div v-else class="dp-empty">文章不存在或尚未发布。</div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { getArticle, getAuthor, incrementViews, listArticles } from '../../api/articles'
import { renderMarkdown } from '../../utils/markdown'

const route = useRoute()
const article = ref(null)
const author = ref(null)
const loading = ref(false)
const articleList = ref([])

const renderedContent = computed(() => renderMarkdown(article.value?.content || ''))

async function load() {
  loading.value = true
  try {
    const id = route.params.id
    // 并行加载文章详情和侧边栏列表
    const [a, list] = await Promise.all([
      getArticle(id),
      listArticles({ status: 'published', limit: 200 }).catch(() => [])
    ])
    article.value = a || null
    articleList.value = list || []
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
.dp-layout {
  display: flex;
  gap: var(--space-lg);
  padding: var(--space-md);
  align-items: flex-start;
  max-width: 960px;
  margin: 0 auto;
}

/* 左侧边栏 */
.dp-sidebar {
  flex: none;
  width: 220px;
  position: sticky;
  top: var(--space-md);
}
.dp-sidebar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--space-sm);
  padding-bottom: var(--space-xs);
  border-bottom: 2px solid #1d70b8;
}
.dp-sidebar-list {
  list-style: none;
  margin: 0;
  padding: 0;
}
.dp-sidebar-item {
  border-left: 3px solid transparent;
  transition: border-color 0.15s, background 0.15s;
}
.dp-sidebar-item.active {
  border-left-color: #1d70b8;
  background: #f3f2f1;
}
.dp-sidebar-link {
  display: block;
  padding: 8px 10px;
  text-decoration: none;
  color: inherit;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.dp-sidebar-item.active .dp-sidebar-link {
  color: var(--text-primary);
  font-weight: 600;
}
.dp-sidebar-link:hover {
  background: #f9f9f9;
}
.dp-sidebar-title-text {
  font-size: 14px;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: #1d70b8;
}
.dp-sidebar-item.active .dp-sidebar-title-text {
  color: var(--text-primary);
}
.dp-sidebar-date {
  font-size: 12px;
  color: var(--text-muted);
}
.dp-sidebar-empty {
  padding: var(--space-md) 0;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 右侧正文 */
.dp-main {
  flex: 1;
  min-width: 0;
  max-width: 680px;
}
.dp-article {
  /* 由 dp-main 控制宽度 */
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
.dp-content :deep(.align-left) { text-align: left; }
.dp-content :deep(.align-center) { text-align: center; }
.dp-content :deep(.align-right) { text-align: right; }
.dp-content :deep(.align-justify) { text-align: justify; }
.dp-content :deep(.align-center img) { margin-left: auto; margin-right: auto; }
.dp-content :deep(.align-right img) { margin-left: auto; margin-right: 0; }
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

/* 移动端：侧边栏隐藏，正文全宽 */
@media (max-width: 768px) {
  .dp-layout {
    flex-direction: column;
    padding: var(--space-md);
  }
  .dp-sidebar {
    display: none;
  }
  .dp-main {
    max-width: 100%;
  }
}
</style>
