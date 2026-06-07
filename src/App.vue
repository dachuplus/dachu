<template>
  <div class="app-layout">
    <!-- PC 端顶部导航 -->
    <header class="app-header" v-if="!isMobile">
      <div class="header-inner">
        <span class="header-title">{{ pageTitle }}</span>
        <nav class="header-nav">
          <router-link
            v-for="tab in tabs"
            :key="tab.path"
            :to="tab.path"
            class="nav-link"
            :class="{ active: currentTab === tab.key }"
          >{{ tab.label }}</router-link>
        </nav>
        <span class="header-right"></span>
      </div>
    </header>

    <!-- 移动端返回/标题（非 Tab 页显示） -->
    <header class="app-header mobile-header" v-if="isMobile && showBack">
      <div class="header-inner">
        <span class="header-back" @click="router.back()">←</span>
        <span class="header-title">{{ pageTitle }}</span>
        <span class="header-right"></span>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="app-main" :class="{ 'pc-main': !isMobile }">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['HomePage']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>

    <!-- 移动端底部 TabBar -->
    <MobileTabBar v-if="isMobile" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MobileTabBar from './components/MobileTabBar.vue'

const route   = useRoute()
const router  = useRouter()

/* ---- 响应式断点 ---- */
const isMobile = ref(window.innerWidth < 1024)
function onResize() {
  isMobile.value = window.innerWidth < 1024
}
onMounted(() => window.addEventListener('resize', onResize))
onUnmounted(() => window.removeEventListener('resize', onResize))

/* ---- Tab 数据 ---- */
const tabs = [
  { key: 'home',    path: '/',       label: '总览'   },
  { key: 'config',  path: '/config', label: '配置'   },
  { key: 'tools',   path: '/tools',  label: '工具'   },
  { key: 'lab',     path: '/lab',    label: '实验室' },
  { key: 'profile', path: '/profile', label: '我的'   },
]

const currentTab = computed(() => route.meta?.tab || 'home')
const pageTitle  = computed(() => route.meta?.title || '投资助手')
const showBack   = computed(() => {
  const tabPaths = tabs.map(t => t.path)
  return !tabPaths.includes(route.path)
})
</script>

<style scoped>
/* ---- 布局容器 ---- */
.app-layout {
  min-height: 100vh;
  background: var(--bg-body);
  max-width: var(--max-width);
  margin: 0 auto;
}

/* ---- PC 顶部导航 ---- */
.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
  height: var(--header-height);
  box-shadow: var(--shadow-sm);
}
.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 20px;
  max-width: var(--pc-max-width);
  margin: 0 auto;
}
.header-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-primary);
}
.header-back {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 20px;
  padding: 4px 8px 4px 0;
}
.header-right { width: 32px; }

/* PC 导航链接 */
.header-nav {
  display: flex;
  gap: 4px;
}
.nav-link {
  padding: 6px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-secondary);
  text-decoration: none;
  transition: all 0.15s;
}
.nav-link:hover {
  background: var(--bg-brand-light);
  color: var(--brand);
}
.nav-link.active {
  background: var(--bg-brand-light);
  color: var(--brand);
}

/* 移动端标题栏（子页面返回用） */
.mobile-header {
  display: none;
}
@media (max-width: 1023px) {
  .mobile-header { display: block; }
}

/* ---- 主内容区 ---- */
.app-main {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-md);
  padding-bottom: calc(var(--tab-height) + var(--space-md));
}
.pc-main {
  padding: 20px;
  padding-bottom: 20px;
  max-width: var(--pc-max-width);
  margin: 0 auto;
  width: 100%;
}

/* ---- PC 端隐藏移动端标题栏 ---- */
@media (min-width: 1024px) {
  .app-main {
    padding-bottom: 20px;
  }
}
</style>
