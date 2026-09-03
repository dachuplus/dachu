<template>
  <div class="app-root">
    <!-- 公开路由（如微信扫码回调）：无需登录，仅渲染路由内容 -->
    <div v-if="route.meta?.public" class="public-route">
      <router-view />
    </div>

    <!-- 账号被封禁 -->
    <div v-if="blocked" class="stranger-screen">
      <div class="stranger-card">
        <div class="stranger-brand">大厨先生</div>
        <div class="stranger-title">账号已被封禁</div>
        <p class="stranger-desc">您的账号已被管理员封禁，无法访问本站。如需恢复访问，请联系管理员。</p>
        <div class="stranger-actions">
          <button class="stranger-logout" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </div>

    <!-- 未登录：全屏登录墙（公开内容/回调路由除外，放行以渲染应用）；
         login-wall 功能开关关闭时，所有人可直接浏览（不弹墙） -->
    <LoginDialog v-else-if="!authLoading && !isLoggedIn && !isPublicContentRoute && featureEnabled('login-wall')" :wall="true" @logged-in="onLoggedIn" />

    <!-- 已登录但权限申请被驳回：驳回提示（优先于陌生人提示） -->
    <div v-else-if="!authLoading && isLoggedIn && rejected" class="stranger-screen">
      <div class="stranger-card">
        <div class="stranger-brand">大厨先生</div>
        <div class="stranger-title">申请已被驳回</div>
        <p class="stranger-desc">抱歉，您提交的访问权限申请未通过审核。如有疑问可联系管理员，或点击「重新申请」补充信息再次提交。</p>
        <div class="stranger-actions">
          <button class="stranger-request" @click="showRequestDialog = true">重新申请</button>
          <button class="stranger-logout" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </div>

    <!-- 已登录但无权限：陌生人提示 -->
    <div v-else-if="!authLoading && isLoggedIn && isStranger" class="stranger-screen">
      <div class="stranger-card">
        <div class="stranger-brand">大厨先生</div>
        <div class="stranger-title">暂无访问权限</div>
        <p class="stranger-desc">抱歉，您的账户尚未开通 大厨先生 的访问权限。如需使用，请点击「申请权限」填写信息，管理员审核通过后将为您开通对应功能。</p>
        <div class="stranger-actions">
          <button class="stranger-request" @click="showRequestDialog = true">申请权限</button>
          <button class="stranger-logout" @click="handleLogout">退出登录</button>
        </div>
      </div>
    </div>

    <!-- 已登录且有权限：完整应用 -->
    <div v-else class="app-layout">
    <!-- PC 端顶部导航 -->
    <header class="govuk-header" v-if="!isMobile">
      <div class="govuk-header__container">
        <div class="govuk-header__logo">
          <router-link to="/" class="govuk-header__logotype-text" style="text-decoration:none;color:#fff">靠谱指数-评分工具</router-link>
        </div>
        <div class="govuk-header__content">
          <div class="govuk-header__auth">
            <!-- 已登录 -->
            <template v-if="isLoggedIn">
              <router-link to="/profile" class="auth-user-email">个人中心</router-link>
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

    <!-- 全局金刚区导航（所有页面可见） -->
    <nav class="quick-nav">
      <div class="quick-nav__inner">
        <router-link
          v-for="item in visibleQuickLinks"
          :key="item.path"
          :to="item.path"
          class="quick-nav__item"
          :class="{ 'quick-nav__item--active': route.path === item.path || route.path.startsWith(item.path + '/') }"
        >
          {{ item.label }}
        </router-link>
        <router-link
          v-if="isOwner"
          to="/data-center"
          class="quick-nav__item quick-nav__item--download"
          :class="{ 'quick-nav__item--active': route.path === '/data-center' }"
          title="数据中心：查看并下载全部数据表"
        >
          管理
        </router-link>
      </div>
    </nav>

    <!-- 主内容区 -->
    <main class="app-main" :class="{ 'pc-main': !isMobile }">
      <div v-if="!routeAllowed" class="no-feature-access">
        <p class="no-feature-access__title">无访问权限</p>
        <p class="no-feature-access__desc">您暂无「{{ currentFeatureLabel }}」功能的访问权限。</p>
        <button class="no-feature-access__btn" @click="handleRequestAccess">申请访问权限</button>
      </div>
      <router-view v-else v-slot="{ Component }">
        <keep-alive :include="['FundRankPage']">
          <component :is="Component" />
        </keep-alive>
      </router-view>

      <!-- 全站免责声明（合规：个人观点，不构成投资建议） -->
      <footer class="site-disclaimer">
        个人观点，仅供参考，不构成任何投资建议或金融产品营销。市场有风险，投资需谨慎。
      </footer>

      <!-- 底部访客计数条（对齐 1400px 内容列，gov.uk 风格） -->
      <footer v-if="visitorCount !== null" class="site-visitor-bar">
        <span class="site-visitor-bar__text">你是第 <strong>{{ visitorCount }}</strong> 位访客</span>
      </footer>
    </main>

    <!-- 移动端底部 TabBar -->
    <MobileTabBar v-if="isMobile" />

    <!-- 全局通知与对话框 -->
    <Toast />
    <ConfirmDialog />

    <!-- 登录弹窗（非墙模式：公开路由中点击「登录/注册」触发）。
         不再被 !authLoading 守卫：用户已主动表达登录意愿，不应被 init 卡死阻塞。 -->
    <LoginDialog v-if="!isLoggedIn && showLoginDialogValue" @logged-in="onLoggedIn" @close="hideLogin" />
    </div>

    <!-- 申请权限弹窗：独立于各分支，任何登录状态下均可弹出 -->
    <PermissionRequestDialog :show="showRequestDialog" @close="showRequestDialog = false" @submitted="onRequestSubmitted" />
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import MobileTabBar from './components/MobileTabBar.vue'
import Toast from './components/Toast.vue'
import ConfirmDialog from './components/ConfirmDialog.vue'
import LoginDialog from './components/LoginDialog.vue'
import PermissionRequestDialog from './components/PermissionRequestDialog.vue'
import { useAuth, FEATURES } from './composables/useAuth'
import { useFeatureFlags } from './composables/useFeatureFlags'
import { supabase } from './api/supabase'

const route   = useRoute()
const router  = useRouter()
const { user, isLoggedIn, isAdmin, isOwner, isStranger, blocked, rejected, loading: authLoading, hasFeature, displayName, init, signOut, showLoginDialog, showLogin, hideLogin, checkRejected } = useAuth()
const showLoginDialogValue = showLoginDialog  // 模板中用于 v-if 控制弹窗显隐
const { featureEnabled, loadFeatureFlags } = useFeatureFlags()

/* 公开内容路由（微信回调等）：未登录也可访问，登录墙对其放行。
 * 注意：当 login-wall 权限墙开启时，仅 meta.public 的回调路由放行，
 *       博客（content）路由不再视为公开——必须登录才能看。 */
const isPublicContentRoute = computed(() => {
  // 兜底：路由尚未解析完成（首屏第一帧）时，先视为公开路由，
  // 避免 route.meta 为空导致 isPublicContentRoute 误判为 false、登录墙闪现一帧。
  if (!route.matched || route.matched.length === 0) return true
  // 回调类路由（微信扫码、OAuth 等）始终放行，否则无法完成登录流程
  if (route.meta?.public) return true
  // 权限墙关闭时：博客作为公开内容放行；权限墙开启时：博客也需登录
  if (route.meta?.feature === 'content' && featureEnabled('content') && !featureEnabled('login-wall')) return true
  return false
})

/* ---- 响应式断点 ---- */
const isMobile = ref(window.innerWidth < 769)
function onResize() {
  isMobile.value = window.innerWidth < 769
}
onMounted(async () => {
  window.addEventListener('resize', onResize)
  await init()        // 初始化全局 auth（恢复 session 后再上报，确保能拿到登录邮箱）
  loadFeatureFlags()  // 加载功能开放开关（失败回退默认，不阻塞页面）
  logVisitor()        // 上报本次访问（IP / 邮箱 / 地区 / 页面）
  loadVisitorCount()  // 拉取累计访客数（写入 visitor_logs 的总条数）
})

/* ---- 累计访客数（用于底部「你是第 N 位访客」）---- */
const visitorCount = ref(null)
async function loadVisitorCount() {
  if (!supabase) return
  try {
    // 经 SECURITY DEFINER 函数取累计数（visitor_logs 已启用 RLS，anon 不可直接读行，
    // 仅可执行该函数拿到一个数字，既满足计数又不泄露任何访客记录）
    const { data, error } = await supabase.rpc('get_visitor_count')
    const n = typeof data === 'number' ? data : parseInt(data, 10)
    if (!error && Number.isFinite(n)) visitorCount.value = n
  } catch (e) {
    // 查询失败静默处理，不展示计数即可
  }
}
onUnmounted(() => window.removeEventListener('resize', onResize))

/* ---- 访客访问记录上报（写入 visitor_logs 表）---- */
async function logVisitor() {
  if (!supabase) return
  const pagePath = route.path || (typeof window !== 'undefined' ? window.location.pathname : '/')

  // 用户身份：去个人化——不再写入明文邮箱或匿名追踪 ID，仅区分「已登录 / 匿名」
  const email = user.value?.email ? 'authenticated' : 'anonymous'

  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : null

  // 异步获取 IP + 地区（免费服务，可能不可达，失败不阻塞页面）
  let ip = null
  let region = ''
  try {
    const ipRes = await fetch('https://api.ipify.org?format=json')
    const ipData = await ipRes.json()
    ip = ipData.ip || null
    try {
      const geoRes = await fetch(`http://ip-api.com/json/${ip}?lang=zh-CN`)
      const geo = await geoRes.json()
      region = `${geo.regionName || ''}${geo.city ? ' ' + geo.city : ''}`.trim()
    } catch (e) {
      region = ''   // ip-api 不可达时地区留空，正常写入
    }
  } catch (e) {
    ip = null
  }

  try {
    await supabase.from('visitor_logs').insert({
      ip_address: ip,
      email,
      region,
      page_path: pagePath,
      user_agent: userAgent,
    })
  } catch (e) {
    // 上报失败静默处理，绝不阻塞页面
    console.error('[visitor_logs] 上报失败', e)
  }
}

/* ---- 认证 ---- */
async function handleLogout() {
  // 乐观更新：先清本地状态，避免 signOut 网络请求卡住时界面无反应
  user.value = null
  // 异步调用 signOut（不 await），即使网络超时也不影响登出体验
  supabase.auth.signOut().catch((e) => console.error('[auth] signOut error:', e))
  // 跳转首页（当前页可能是 ownerOnly 页面，登出后无权访问）
  router.push('/')
}

function onLoggedIn() {
  hideLogin()
}

/* ---- 权限申请弹窗 ---- */
const showRequestDialog = ref(false)
function onRequestSubmitted() {
  showRequestDialog.value = false
  // 重新申请后清掉「已被驳回」状态，避免仍卡在驳回屏
  checkRejected(user.value?.email)
}

/** 「无访问权限」卡片 → 点击「申请访问权限」：
 *  未登录 → 先弹登录框；已登录 → 直接弹权限申请表单 */
function handleRequestAccess() {
  if (!isLoggedIn.value) {
    showLogin()
  } else {
    showRequestDialog.value = true
  }
}

/* ---- 全局金刚区 ---- */
const quickLinks = [
  { path: '/content',          label: '博客', feature: 'content' },
  { path: '/signal',           label: '信号', feature: 'signal' },
  { path: '/tools/fund-rank',  label: '选基', feature: 'fund-rank' },
  { path: '/portfolio',        label: '组合', feature: 'portfolio' },
]
// 按全局开关过滤可见的金刚区入口（全部展示，权限由路由级 routeAllowed 拦截）
const visibleQuickLinks = computed(() =>
  quickLinks.filter(item => {
    const f = item.feature
    if (!f) return true                    // 无功能标签的入口始终可见
    return featureEnabled(f)               // 全局开关开着就显示，权限由路由守卫控制
  })
)

/* ---- 当前路由的功能权限拦截（未授权功能显示「无访问权限」） ---- */
const routeAllowed = computed(() => {
  // ownerOnly 路由：仅管理员可进；管理员始终可进，不受功能开关影响（避免把自己锁在门外）
  if (route.meta?.ownerOnly) return isOwner.value
  const feat = route.meta?.feature
  if (feat && !featureEnabled(feat)) return false  // 全局关闭的功能：任何登录用户都无权限
  if (isAdmin.value) return true
  if (!feat) return true
  if (feat === 'content') return true              // 内容公开可读
  return hasFeature(feat)
})
const currentFeatureLabel = computed(() => {
  if (route.meta?.ownerOnly) return '管理/编辑'
  const feat = route.meta?.feature
  const f = FEATURES.find(x => x.key === feat)
  return f ? f.label : ''
})

/* ---- Tab 数据（仅移动端 TabBar 使用）---- */
const tabs = [
  { key: 'home',      path: '/',                 label: '首页',  feature: null },
  { key: 'content',   path: '/content',          label: '博客',  feature: 'content' },
  { key: 'signal',    path: '/signal',           label: '信号',  feature: 'signal' },
  { key: 'fundrank',  path: '/tools/fund-rank',  label: '选基',  feature: 'fund-rank' },
  { key: 'portfolio', path: '/portfolio',        label: '组合',  feature: 'portfolio' },
  { key: 'profile',   path: '/profile',          label: '我的',  feature: null },
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
  width: 100%;
}
.govuk-header__container {
  max-width: 1400px;
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
  text-decoration: none;
  cursor: pointer;
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
  max-width: 1400px;
  margin: 0 auto;
  padding: var(--space-sm) 15px;
  border-bottom: 1px solid var(--border);
  background: #ffffff;
  width: 100%;
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
  max-width: 1400px; margin: 0 auto; padding: 0 30px;
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
.quick-nav__item--download {
  color: var(--text-secondary);
  border-bottom-color: transparent;
  cursor: pointer;
}
.quick-nav__item--download:hover {
  color: #0b5c8a;
  border-bottom-color: #0b5c8a;
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
  padding: var(--space-xl) 30px;
  padding-bottom: var(--space-2xl);
  max-width: 1400px;
  margin: 0 auto;
  width: 100%;
}
/* pc-main 模式下抵消 app-main 的基础水平 padding，确保与 header 对齐 */
.app-main.pc-main {
  padding-left: 0;
  padding-right: 0;
}

/* ========== 全站免责声明 ========== */
.site-disclaimer {
  margin-top: var(--space-xl);
  padding: 12px 16px;
  border-top: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  background: #f3f2f1;
  text-align: center;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-secondary);
}

/* ========== 底部访客计数条 ========== */
.site-visitor-bar {
  margin-top: var(--space-xl);
  padding-top: var(--space-md);
  border-top: 1px solid var(--border);
  text-align: center;
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
}
.site-visitor-bar__text strong {
  color: var(--brand);
  font-weight: 700;
}
@media (max-width: 768px) {
  .mobile-header { display: flex; }
}

/* ========== 登录墙 / 陌生人 / 无功能权限 ========== */
.app-root { min-height: 100vh; }

/* 公开路由（微信回调等）：极简容器，仅承载回调页 */
.public-route { min-height: 100vh; }

.stranger-screen {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #1d70b8;
  padding: var(--space-md);
}
.stranger-card {
  background: #ffffff;
  border: 4px solid #003078;
  max-width: 480px; width: 100%;
  padding: 40px 32px;
  text-align: center;
}
.stranger-brand {
  font-size: 20px; font-weight: 700; color: #1d70b8;
  margin-bottom: var(--space-lg); letter-spacing: 0.5px;
}
.stranger-title {
  font-size: 28px; font-weight: 700; color: #d4351c;
  margin-bottom: var(--space-md);
}
.stranger-desc {
  font-size: 16px; color: var(--text-secondary); line-height: 1.6;
  margin-bottom: var(--space-lg);
}
.stranger-logout {
  background: #1d70b8; color: #ffffff; border: none;
  padding: 10px 28px; font-size: 16px; font-weight: 700; cursor: pointer;
}
.stranger-logout:hover { background: #003078; }

.stranger-actions {
  display: flex; gap: var(--space-sm); justify-content: center; flex-wrap: wrap;
}
.stranger-request {
  background: #ffffff; color: #1d70b8; border: 1px solid #1d70b8;
  padding: 10px 28px; font-size: 16px; font-weight: 700; cursor: pointer;
}
.stranger-request:hover { background: #f3f3f3; }

.no-feature-access {
  max-width: 600px; margin: 60px auto; padding: 40px;
  text-align: center;
  background: #ffffff; border: 2px solid var(--border); border-left: 6px solid #d4351c;
}
.no-feature-access__title {
  font-size: 24px; font-weight: 700; color: #d4351c; margin: 0 0 var(--space-md);
}
.no-feature-access__desc {
  font-size: 16px; color: var(--text-secondary); margin: 0;
}
.no-feature-access__btn {
  display: inline-block; margin-top: var(--space-md);
  padding: 10px 24px; font-size: 16px; font-weight: 700;
  color: #fff; background: #1d70b8; border: none; cursor: pointer;
}
.no-feature-access__btn:hover { background: #003078; }
</style>
