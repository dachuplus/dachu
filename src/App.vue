<template>
  <div class="app-layout">
    <!-- PC 端 gov.uk 黑色顶部导航 -->
    <header class="govuk-header" v-if="!isMobile">
      <div class="govuk-header__container">
        <div class="govuk-header__logo">
          <span class="govuk-header__logotype-text">allfund.cn</span>
        </div>
        <div class="govuk-header__content">
          <nav class="govuk-header__navigation">
            <ul class="govuk-header__navigation-list">
              <li
                v-for="tab in tabs"
                :key="tab.path"
                class="govuk-header__navigation-item"
                :class="{ 'govuk-header__navigation-item--active': currentTab === tab.key }"
              >
                <router-link :to="tab.path" class="govuk-header__link">
                  {{ tab.label }}
                </router-link>
              </li>
            </ul>
          </nav>
        </div>
      </div>
    </header>

    <!-- 移动端返回/标题 -->
    <header class="mobile-header" v-if="isMobile && showBack">
      <button class="mobile-header__back" @click="router.back()" aria-label="返回">
        ← 返回
      </button>
      <span class="mobile-header__title">{{ pageTitle }}</span>
      <span class="mobile-header__spacer"></span>
    </header>

    <!-- Phase banner -->
    <div class="govuk-phase-banner" v-if="!isMobile">
      <p class="govuk-phase-banner__content">
        <strong class="govuk-tag govuk-phase-banner__tag">BETA</strong>
        <span class="govuk-phase-banner__text">
          这是 allfund.cn 的测试版本 — 数据每日更新，如有问题请反馈。
        </span>
      </p>
    </div>

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
const isMobile = ref(window.innerWidth < 769)
function onResize() {
  isMobile.value = window.innerWidth < 769
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
/* ========== gov.uk 顶部导航 ========== */
.govuk-header {
  background: #0b0c0c;
  border-bottom: 10px solid #1d70b8;
  color: #ffffff;
  font-size: 16px;
  line-height: 1.25;
}
.govuk-header__container {
  max-width: 960px;
  margin: 0 auto;
  padding: 0 15px;
  display: flex;
  align-items: center;
  height: 60px;
}
@media (min-width: 769px) {
  .govuk-header__container { padding: 0 30px; }
}

/* Logo */
.govuk-header__logo {
  margin-right: 30px;
}
.govuk-header__logotype-text {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.5px;
}

/* 导航区 */
.govuk-header__content {
  flex: 1;
}
.govuk-header__navigation {
  display: flex;
  justify-content: flex-end;
}
.govuk-header__navigation-list {
  list-style: none;
  display: flex;
  gap: 0;
  margin: 0;
  padding: 0;
}
.govuk-header__navigation-item {
  margin: 0;
  padding: 0;
}
.govuk-header__link {
  display: block;
  padding: 8px 16px;
  color: #ffffff;
  font-size: 16px;
  font-weight: 700;
  text-decoration: none;
  border-bottom: 4px solid transparent;
  transition: border-color 0.15s;
}
.govuk-header__link:hover {
  border-bottom-color: #ffffff;
  text-decoration: none;
}
.govuk-header__navigation-item--active .govuk-header__link {
  border-bottom-color: #1d70b8;
}

/* ========== Phase banner ========== */
.govuk-phase-banner {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--space-sm) 15px;
  border-bottom: 1px solid var(--border);
  background: #ffffff;
}
@media (min-width: 769px) {
  .govuk-phase-banner { padding: var(--space-sm) 30px; }
}
.govuk-phase-banner__content {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}
.govuk-phase-banner__tag {
  background: #1d70b8;
  color: #ffffff;
  font-size: 14px;
  padding: 2px 8px 1px;
}
.govuk-phase-banner__text {
  line-height: 1.25;
}

/* ========== 移动端标题栏 ========== */
.mobile-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: var(--header-height);
  padding: 0 var(--space-md);
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 50;
}
.mobile-header__back {
  color: var(--link);
  font-size: 16px;
  font-weight: 400;
  padding: 4px 0;
  text-decoration: underline;
}
.mobile-header__title {
  font-size: 19px;
  font-weight: 700;
  color: var(--text-primary);
}
.mobile-header__spacer { width: 48px; }

/* ========== 主内容区 ========== */
.app-layout {
  min-height: 100vh;
  background: var(--bg-body);
}
.app-main {
  flex: 1;
  padding: var(--space-md);
  padding-bottom: calc(var(--tab-height) + var(--space-md));
}
.pc-main {
  padding: var(--space-xl) 15px;
  padding-bottom: var(--space-2xl);
  max-width: 960px;
  margin: 0 auto;
  width: 100%;
}
@media (min-width: 769px) {
  .pc-main {
    padding: var(--space-xl) 30px;
  }
}
@media (max-width: 768px) {
  .mobile-header { display: flex; }
}
</style>
