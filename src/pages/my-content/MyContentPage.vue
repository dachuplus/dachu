<template>
  <div class="content-page">
    <!-- 二级分类导航：博客 / 影视 / 美食 / 游戏，右侧放「写文章」按钮 -->
    <div class="cp-tabs">
      <div class="cp-tab-list">
        <div
          v-for="c in categories"
          :key="c.key"
          class="cp-tab"
          :class="{ active: category === c.key }"
          @click="setCategory(c.key)"
        >{{ c.label }}</div>
      </div>
      <router-link v-if="canManageContent && category === 'blog'" to="/content/editor" class="cp-new-btn">+ 写文章</router-link>
    </div>

    <!-- 游戏二级 Tab：扫雷 / 2048（由信号页迁入） -->
    <div v-if="category === 'game'" class="cp-games">
      <GamesPanel />
    </div>

    <!-- 影视二级 Tab：影视观看榜（9+1电视剧评分框架）+ 个人工具 -->
    <div v-else-if="category === 'film'">
      <RankBoard
        title="影视观看榜"
        intro="精选影视作品，按「9+1 电视剧评分框架」评分：好老板 · 好故事 · 好团队 · 好演员 · 好制作 · 好宣发 · 好风口 · 好票房 · 好口碑，外加「好创新」。点击任意条目可展开十项明细。"
        :items="FILM_RANK"
        :dims="FILM_DIMS"
        cat-label="体裁"
        framework-name="9+1 电视剧评分框架"
        framework-note="九个基础维度各 1-10 分、合计 90 分；「好创新」为加分项，最高 +10 分，总分上限 100 分。"
      />
      <div class="cp-subblock">
        <h3 class="cp-subblock-title">个人工具</h3>
        <MediaTools />
      </div>
    </div>

    <!-- 美食二级 Tab：下辖两个三级 Tab —— 大厨榜-上海 / 必吃榜-上海（2017-2025） -->
    <div v-else-if="category === 'food'">
      <div class="cp-subtabs">
        <div
          v-for="t in foodTabs"
          :key="t.key"
          class="cp-subtab"
          :class="{ active: foodTab === t.key }"
          @click="foodTab = t.key"
        >{{ t.label }}<span class="cp-subtab-count">（{{ t.count }}）</span></div>
      </div>

      <!-- 三级 Tab ①：中国大厨榜 · 上海（9+1美食评分框架） -->
      <template v-if="foodTab === 'chef'">
        <RankBoard
          title="中国大厨榜 · 上海"
          :intro="`${CHEF_BOARD.length} 家上海餐厅，按「9+1 美食评分框架」评分：好老板 · 好理念 · 好团队 · 好厨师 · 好食材 · 好环境 · 好地段 · 好营收 · 好口碑，外加「好创新」。点击任意条目可展开十项明细。`"
          :items="CHEF_BOARD"
          :dims="CHEF_DIMS"
          cat-label="菜系"
          framework-name="9+1 美食评分框架"
          framework-note="九个基础维度各 1-10 分、合计 90 分；「好创新」为加分项，最高 +10 分，总分上限 100 分。"
        />
        <p class="cp-caveat">
          评分口径：本榜为「编辑综合评分」，由统一评分标准生成，非官方数据、也非实测结果。
          店名与所在区取自公开榜单（大众点评必吃榜 2017-2025 等，仅收录公开可溯源的门店）；
          人均消费无法逐年核实，统一留空显示 <code>--</code>，不做估算；
          菜系仅取来源明确标注者，其余归入「其他」，未作推断。
        </p>
      </template>

      <!-- 三级 Tab ②：大众点评必吃榜 · 上海历年（2017-2025） -->
      <MustEatBoard
        v-else
        title="大众点评必吃榜 · 上海历年"
        intro="收录大众点评「必吃榜」自 2017 年首发以来上海历年上榜餐厅，可按年份浏览，也可按餐厅聚合查看累计上榜次数与年份轨迹。数据为公开信息整理，逐年来源与覆盖度见页面底部说明。"
        :items="MUST_EAT_SHANGHAI"
        :sources="MUST_EAT_SOURCES"
      />
    </div>

    <!-- 博客：文章列表 -->
    <template v-else>
    <div v-if="canManageContent" class="cp-viewswitch">
      <button :class="{ active: view === 'published' }" @click="setView('published')">已发布</button>
      <button :class="{ active: view === 'mine' }" @click="setView('mine')">我的全部（含草稿）</button>
    </div>

    <div v-if="loading && !articles.length" class="cp-loading">
      <div>加载中…</div>
      <div v-if="slowHint" class="cp-loading-hint">网络较慢，正在重试中…</div>
    </div>
    <div v-else-if="loadError" class="cp-error">
      <p class="cp-error-msg">{{ loadError }}</p>
      <button class="cp-retry-btn" @click="load">重新加载</button>
    </div>
    <div v-else-if="articles.length === 0" class="cp-empty">
      {{ isOwner && view === 'mine' ? '还没有文章，点击右上角「写文章」开始吧。' : '暂无已发布内容。' }}
    </div>

    <ul v-else class="cp-list">
      <li v-for="a in articles" :key="a.id" class="cp-card">
        <router-link :to="`/content/${a.id}`" class="cp-card-link">
          <div v-if="a.cover_image" class="cp-cover" :style="{ backgroundImage: 'url(' + a.cover_image + ')' }"></div>
          <div class="cp-card-body">
            <div class="cp-card-top">
              <span class="cp-cat-badge">{{ catLabel(a.category) }}</span>
              <span v-if="a.scheduled_at && new Date(a.scheduled_at).getTime() > Date.now()" class="cp-badge cp-badge--sched">定时 · {{ formatDateTime(a.scheduled_at) }}</span>
              <span v-else-if="a.status === 'draft'" class="cp-badge cp-badge--draft">草稿</span>
              <span v-else class="cp-badge cp-badge--pub">已发布</span>
              <h2 class="cp-card-title">{{ a.title }}</h2>
            </div>
            <p v-if="a.summary" class="cp-card-summary">{{ a.summary }}</p>
            <div class="cp-card-meta">
              <span>{{ formatDate(a.published_at || a.updated_at) }}</span>
              <span class="cp-dot">·</span>
              <span>{{ a.views || 0 }} 浏览</span>
              <span v-if="a.is_pinned" class="cp-pinned">置顶</span>
              <span v-for="t in (a.tags || [])" :key="t" class="cp-tag">{{ t }}</span>
            </div>
          </div>
        </router-link>
        <div v-if="canManageContent" class="cp-card-actions">
          <router-link :to="`/content/editor/${a.id}`" class="cp-link-edit">编辑</router-link>
          <button class="cp-link-pin" @click="onTogglePin(a)">{{ a.is_pinned ? '取消置顶' : '置顶' }}</button>
          <button class="cp-link-del" @click="onDelete(a)">删除</button>
        </div>
      </li>
    </ul>
    </template>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import GamesPanel from '../../components/games/GamesPanel.vue'
import MediaTools from '../../components/MediaTools.vue'
import RankBoard from '../../components/rank/RankBoard.vue'
import MustEatBoard from '../../components/rank/MustEatBoard.vue'
import { FILM_RANK, FILM_DIMS } from '../../data/filmRank.js'
import { SH_RESTAURANTS, CHEF_DIMS } from '../../data/shRestaurants.js'
import { SH_RESTAURANTS_EXTRA } from '../../data/shRestaurantsExtra.js'
import { MUST_EAT_SHANGHAI, MUST_EAT_SOURCES } from '../../data/mustEatShanghai.js'
import { listArticles, deleteArticle, setArticlePinned, NETWORK_SLOW_MSG, isNetworkError } from '../../api/articles'
import { confirm, toast } from '../../composables/useToast'

/**
 * 中国大厨榜：原始 100 家（品牌级精选）+ 扩展集（公开榜单可溯源门店，编辑综合评分）。
 * 扩展集与主表已做品牌级去重，不会出现同一品牌两行。
 */
const CHEF_BOARD = [...SH_RESTAURANTS, ...SH_RESTAURANTS_EXTRA]

/**
 * 美食二级 Tab 下的三级 Tab：大厨榜-上海 / 必吃榜-上海（2017-2025）。
 * 家数取实际渲染的条目数，避免写死数字与实际数据脱节。
 */
const foodTab = ref('chef')
const foodTabs = computed(() => [
  { key: 'chef', label: '大厨榜-上海', count: `${CHEF_BOARD.length} 家` },
  { key: 'musteat', label: '必吃榜-上海', count: '2017-2025' },
])

const { isOwner, user } = useAuth()
const route = useRoute()
const articles = ref([])
const loading = ref(false)
const loadError = ref('')
const slowHint = ref(false)  // 加载超过 5s 时给出"网络较慢"提示
let slowTimer = null
const view = ref('published')

// 二级分类导航：博客 / 影视 / 美食 / 游戏（默认「博客」）
const category = ref('blog')
const categories = [
  { key: 'blog', label: '博客' },
  { key: 'film', label: '影视' },
  { key: 'food', label: '美食' },
  { key: 'game', label: '游戏' },
]
/** 分类 key → 中文标签（缺省回退「博客」） */
function catLabel(c) {
  const m = categories.find((x) => x.key === c)
  return m ? m.label : '博客'
}
/** 切换分类并重新加载列表 */
function setCategory(c) {
  if (category.value === c) return
  category.value = c
  load()
}

// 可管理内容：仅管理员可写/编辑/删除
const canManageContent = computed(() => isOwner.value)

async function load() {
  // 游戏 Tab 展示小游戏，不需要拉取文章列表
  if (category.value === 'game') {
    articles.value = []
    loadError.value = ''
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  slowHint.value = false
  // 5s 后仍未结束 → 提示"网络较慢"，避免用户以为页面卡死
  clearTimeout(slowTimer)
  slowTimer = setTimeout(() => {
    if (loading.value) slowHint.value = true
  }, 5000)
  // 分类过滤：当前选中分类（博客/影视/美食/游戏）
  const cat = category.value
  try {
    if (canManageContent.value && view.value === 'mine') {
      const email = user.value?.email
      // 「我的全部」仅显示草稿/定时文章，已发布的不在此显示
      articles.value = await listArticles({ status: 'draft', authorEmail: email, limit: 200, category: cat })
    } else {
      articles.value = await listArticles({ status: 'published', limit: 200, category: cat })
    }
  } catch (e) {
    const msg = (e && e.message) || String(e)
    // 瞬时网络故障（504/超时/断网等）→ 统一提示
    if (msg === NETWORK_SLOW_MSG || isNetworkError(e)) {
      loadError.value = '网络速度慢，请稍后再试。'
    } else if (msg.indexOf('未登录') !== -1) {
      loadError.value = '登录已过期，请刷新页面重新登录。'
    } else {
      loadError.value = '加载失败：' + msg
    }
  } finally {
    loading.value = false
    slowHint.value = false
    clearTimeout(slowTimer)
  }
}

onBeforeUnmount(() => clearTimeout(slowTimer))

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

async function onTogglePin(a) {
  const target = !a.is_pinned
  try {
    await setArticlePinned(a.id, target)
    // 本地立即生效：更新标记并重排，避免等待缓存刷新
    const list = articles.value.map((x) =>
      x.id === a.id ? { ...x, is_pinned: target } : x
    )
    list.sort(
      (x, y) =>
        (y.is_pinned ? 1 : 0) - (x.is_pinned ? 1 : 0) ||
        new Date(y.published_at || 0) - new Date(x.published_at || 0)
    )
    articles.value = list
    toast(target ? '已置顶' : '已取消置顶', 'success')
  } catch (e) {
    toast('操作失败：' + (e.message || e), 'error')
  }
}

function formatDate(s) {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d.getTime())) return ''
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`
}

function formatDateTime(s) {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d.getTime())) return ''
  const p = (x) => String(x).padStart(2, '0')
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}`
}

onMounted(load)
// 从编辑页返回列表时刷新
watch(() => route.fullPath, () => {
  if (route.path === '/content') load()
})
</script>

<style scoped>
.content-page {
  max-width: 680px;
  margin: 0 auto;
  padding: var(--space-md);
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
.cp-tabs {
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 2px solid var(--border);
  margin-bottom: var(--space-md);
}
.cp-tab-list { display: flex; }
.cp-games { margin-top: var(--space-sm); }
.cp-subblock { margin-top: 28px; border-top: 1px solid var(--border); padding-top: 18px; }
.cp-subblock-title { font-size: 18px; font-weight: 700; color: var(--text-primary); margin: 0 0 12px; }
/* 三级 Tab：比二级 Tab 更轻（字号小一档、下划线更细），窄屏可横向滑动 */
.cp-subtabs {
  display: flex;
  border-bottom: 2px solid var(--border);
  margin-bottom: var(--space-md);
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  scrollbar-width: none;
}
.cp-subtabs::-webkit-scrollbar { display: none; }
.cp-subtab {
  flex: none;
  white-space: nowrap;
  padding: 8px 14px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: color 0.15s, border-color 0.15s;
}
.cp-subtab:hover { color: var(--text-primary); }
.cp-subtab.active {
  color: #1d70b8;
  border-bottom-color: #1d70b8;
}
.cp-subtab-count {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-muted);
}
.cp-subtab.active .cp-subtab-count { color: #1d70b8; }
.cp-caveat {
  margin: 14px 0 0;
  padding: 12px 14px;
  border-left: 4px solid var(--brand);
  background: var(--bg-body);
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
.cp-caveat code { background: none; padding: 0 2px; font-size: 13px; }
.cp-placeholder {
  padding: 40px 0;
  text-align: center;
  color: var(--text-secondary);
  font-size: 15px;
}
.cp-tab {
  padding: 8px 18px;
  font-size: 19px;
  font-weight: 700;
  color: var(--text-secondary);
  cursor: pointer;
  border-bottom: 4px solid transparent;
  margin-bottom: -2px;
  transition: all 0.15s;
}
.cp-tab:hover { color: var(--text-primary); }
.cp-tab.active {
  color: #1d70b8;
  border-bottom-color: #1d70b8;
}
.cp-cat-badge {
  background: #1d70b8;
  color: #fff;
  font-size: 12px;
  font-weight: 700;
  padding: 1px 8px;
  white-space: nowrap;
}
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
.cp-loading-hint {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
  opacity: 0.7;
}
.cp-error {
  padding: 40px 20px;
  text-align: center;
}
.cp-error-msg {
  color: #d4351c;
  font-size: 15px;
  margin: 0 0 16px;
  line-height: 1.6;
}
.cp-retry-btn {
  background: #1d70b8;
  color: #fff;
  border: none;
  font-size: 15px;
  font-weight: 700;
  padding: 10px 24px;
  cursor: pointer;
}
.cp-retry-btn:hover { background: #003078; }
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
.cp-pinned {
  background: #1d70b8;
  color: #fff;
  padding: 1px 8px;
  font-size: 12px;
  font-weight: 700;
}
.cp-link-pin {
  background: transparent;
  border: none;
  color: #1d70b8;
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  padding: 0;
}
.cp-link-pin:hover { text-decoration: underline; }
.cp-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 1px 8px;
}
.cp-badge--draft { background: #fff; color: #b1b4b6; border: 1px solid #b1b4b6; }
.cp-badge--pub { background: #1d70b8; color: #fff; }
.cp-badge--sched { background: #ffdd00; color: #0b0c0c; border: 1px solid #ffdd00; }
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
