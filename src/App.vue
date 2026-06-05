<template>
  <div class="app-layout">
    <!-- 顶部导航栏 -->
    <header class="app-header">
      <div class="header-inner">
        <span class="header-back" v-if="showBack" @click="router.back()">←</span>
        <span class="header-title">{{ pageTitle }}</span>
        <span class="header-right"></span>
      </div>
    </header>

    <!-- 主内容区 -->
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['HomePage']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>

    <!-- 底部 TabBar -->
    <nav class="tab-bar">
      <router-link
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="tab-item"
        :class="{ active: currentTab === tab.key }"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </router-link>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'home',    path: '/',        icon: '📊', label: '首页'  },
  { key: 'config',  path: '/config',  icon: '⚖️', label: '配置'  },
  { key: 'tools',   path: '/tools',   icon: '🔧', label: '工具'  },
  { key: 'lab',     path: '/lab',     icon: '🧪', label: '实验室'},
  { key: 'profile', path: '/profile', icon: '👤', label: '我的'  },
]

const currentTab = computed(() => route.meta?.tab || 'home')
const pageTitle  = computed(() => route.meta?.title || '大厨仪表盘')
const showBack   = computed(() => {
  const tabPaths = tabs.map(t => t.path)
  return !tabPaths.includes(route.path)
})
</script>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  max-width: 480px;
  margin: 0 auto;
  background: var(--bg-primary);
}

.app-header {
  position: sticky;
  top: 0;
  z-index: 50;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border);
  height: var(--header-height);
}

.header-inner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 100%;
  padding: 0 16px;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-back {
  color: var(--text-secondary);
  cursor: pointer;
  font-size: 20px;
  padding: 4px 8px 4px 0;
}

.header-right {
  width: 32px;
}

.app-main {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
  padding-bottom: calc(var(--tab-height) + 12px);
}

/* TabBar */
.tab-bar {
  position: fixed;
  bottom: 0;
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-width: 480px;
  height: var(--tab-height);
  background: var(--bg-card);
  border-top: 1px solid var(--border);
  display: flex;
  z-index: 50;
}

.tab-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  text-decoration: none;
  color: var(--text-muted);
  transition: color 0.15s;
}

.tab-item.active {
  color: var(--accent-red);
}

.tab-icon {
  font-size: 20px;
  line-height: 1;
}

.tab-label {
  font-size: 10px;
  font-weight: 500;
}
</style>
