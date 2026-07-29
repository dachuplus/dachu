<template>
  <nav class="mobile-tab-bar">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="tab-item"
      :class="{ active: currentTab === tab.key }"
    >
      <span class="tab-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAuth } from '../composables/useAuth'
import { useFeatureFlags } from '../composables/useFeatureFlags'

const route = useRoute()
const { isAdmin, hasFeature } = useAuth()
const { featureEnabled } = useFeatureFlags()

const allTabs = [
  { key: 'home',    path: '/',                 label: '首页',     feature: 'content' },
  { key: 'signal',  path: '/signal',           label: '信号',     feature: 'signal' },
  { key: 'fundrank',path: '/tools/fund-rank',  label: '工具',     feature: 'fund-rank' },
  { key: 'portfolio',path:'/portfolio',        label: '组合',     feature: 'portfolio' },
  { key: 'content',  path: '/content',          label: '内容',     feature: 'content' },
  { key: 'profile', path: '/profile',          label: '我的',     feature: null },
]
// 按功能开放状态 + 用户权限过滤可见 Tab
// 内容公开可读（任何用户可见）；其余功能按权限；全局关闭则隐藏入口
const tabs = computed(() => allTabs.filter(t => {
  const f = t.feature
  if (!f) return true                    // 无功能标签（首页/我的）始终可见
  if (!featureEnabled(f)) return false   // 全局关闭则隐藏入口
  if (f === 'content') return true       // 内容公开可读，任何用户都可见
  return isAdmin.value || hasFeature(f)  // 其余按用户权限
}))

const currentTab = computed(() => route.meta?.tab || 'home')
</script>

<style scoped>
.mobile-tab-bar {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: var(--tab-height);
  background: #1d70b8;
  border-top: 2px solid #003078;
  display: flex;
  z-index: 50;
}

/* PC 端隐藏 */
@media (min-width: 769px) {
  .mobile-tab-bar { display: none !important; }
}

.tab-item {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: #b1b4b6;
  font-size: 14px;
  font-weight: 700;
  transition: color 0.15s;
  -webkit-tap-highlight-color: transparent;
  border-top: 4px solid transparent;
}
.tab-item.active {
  color: #ffffff;
  border-top-color: #1d70b8;
}
.tab-item:hover {
  color: #ffffff;
  text-decoration: none;
}
.tab-label {
  line-height: 1;
}
</style>
