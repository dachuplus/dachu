<template>
  <div class="app-layout">
    <!-- PC 端顶部导航 -->
    <header class="govuk-header" v-if="!isMobile">
      <div class="govuk-header__container">
        <div class="govuk-header__logo">
          <router-link to="/" class="govuk-header__logotype-text" style="text-decoration:none;color:#fff">ALLFUND.CN</router-link>
        </div>
        <div class="govuk-header__content">
          <div class="govuk-header__auth">
            <!-- 已登录 -->
            <template v-if="isLoggedIn">
              <span class="auth-user-email">{{ user?.email }}</span>
              <button class="auth-btn auth-btn--logout" @click="handleLogout">退出</button>
            </template>
            <!-- 未登录 -->
            <button v-else class="auth-btn auth-btn--login" @click="showLogin">登录 / 注册</button>
          </div>
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
          这是 ALLFUND.CN 的测试版本 — 数据每日更新，如有问题请反馈。
        </span>
      </p>
    </div>

    <!-- 全局金刚区导航（所有页面可见） -->
    <nav class="quick-nav">
      <div class="quick-nav__inner">
        <router-link
          v-for="item in quickLinks"
          :key="item.path"
          :to="item.path"
          class="quick-nav__item"
          :class="{ 'quick-nav__item--active': route.path === item.path || route.path.startsWith(item.path + '/') }"
        >
          {{ item.label }}
        </router-link>
      </div>
    </nav>

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

    <!-- 全局通知与对话框 -->
    <Toast />
    <ConfirmDialog />
    <LoginDialog v-if="showLoginDialog" @close="showLoginDialog = false" @logged-in="onLoggedIn" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MobileTabBar from './components/MobileTabBar.vue'
import Toast from './components/Toast.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import LoginDialog from './components/LoginDialog.vue'
import { useAuth } from './composables/useAuth'

const route   = useRoute()
const router  = useRouter()
const { user, isLoggedIn, loading: authLoading, init, signOut, showLoginDialog, showLogin, hideLogin } = useAuth()

/* ---- 响应式断点 ---- */
const isMobile = ref(window.innerWidth < 769)
function onResize() {
  isMobile.value = window.innerWidth < 769
}
onMounted(() => {
  window.addEventListener('resize', onResize)
  init()  // 初始化全局 auth
})
onUnmounted(() => window.removeEventListener('resize', onResize))

/* ---- 认证 ---- */
async function handleLogout() {
  await signOut()
}

function onLoggedIn() {
  hideLogin()
}

/* ---- 全局金刚区 ---- */
const quickLinks = [
  { path: '/signal',           label: '指标信号' },
  { path: '/tools/fund-rank',  label: '靠谱指数' },
  { path: '/portfolio',        label: '基金组合' },
]

/* ---- Tab 数据（仅移动端 TabBar 使用）---- */
const tabs = [
  { key: 'home',      path: '/',                 label: '首页' },
  { key: 'signal',    path: '/signal',           label: '信号' },
  { key: 'fundrank',  path: '/tools/fund-rank',  label: '评分' },
  { key: 'portfolio', path: '/portfolio',        label: '组合' },
  { key: 'profile',   path: '/profile',          label: '我的' },
]

const pageTitle = computed(() => route.meta?.title || '投资助手')
const showBack  = computed(() => {
  const tabPaths = tabs.map(t => t.path)
  return !tabPaths.includes(route.path)
})
</script>

<style scoped>
/* ========== gov.uk 顶部导航 ========== */
.govuk-header {
  background: #1d70b8;
  border-bottom: 4px solid #003078;
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
  display: flex;
  justify-content: flex-end;
  align-items: center;
}
.govuk-header__auth {
  display: flex;
  align-items: center;
  gap: var(--space-sm);
}
.auth-user-email {
  color: #ffffff;
  font-size: 14px;
  font-weight: 400;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.auth-btn {
  background: transparent;
  border: 1px solid rgba(255,255,255,0.5);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  padding: 6px 14px;
  cursor: pointer;
  white-space: nowrap;
}
.auth-btn:hover {
  border-color: #ffffff;
  background: rgba(255,255,255,0.1);
}
.auth-btn--logout {
  border-color: rgba(255,255,255,0.3);
  font-weight: 400;
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

/* ========== 全局金刚区导航 ========== */
.quick-nav {
  max-width: 960px; margin: 0 auto; padding: 0 30px;
  background: #fff; border-bottom: 1px solid var(--border);
}
.quick-nav__inner { display: flex; gap: 0; justify-content: center; }
.quick-nav__item {
  display: block; padding: 12px 24px; font-size: 16px; font-weight: 700;
  color: var(--text-secondary); text-decoration: none;
  border-bottom: 4px solid transparent; transition: all 0.15s;
}
.quick-nav__item:hover { color: var(--brand); border-bottom-color: var(--brand); }
.quick-nav__item--active { color: var(--brand); border-bottom-color: var(--brand); }

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
