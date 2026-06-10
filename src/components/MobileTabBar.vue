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

const route = useRoute()

const tabs = [
  { key: 'home',    path: '/',        label: '总览'     },
  { key: 'signal',  path: '/signal',  label: '指标信号' },
  { key: 'tools',   path: '/tools',   label: '工具'     },
  { key: 'lab',     path: '/lab',     label: '实验室'   },
  { key: 'profile', path: '/profile', label: '我的'     },
]

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
