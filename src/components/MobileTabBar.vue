<template>
  <nav class="mobile-tab-bar">
    <router-link
      v-for="tab in tabs"
      :key="tab.path"
      :to="tab.path"
      class="tab-item"
      :class="{ active: currentTab === tab.key }"
    >
      <span class="tab-icon" v-html="tab.icon"></span>
      <span class="tab-label">{{ tab.label }}</span>
    </router-link>
  </nav>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

const tabs = [
  {
    key: 'home',
    path: '/',
    label: '总览',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>',
  },
  {
    key: 'config',
    path: '/config',
    label: '配置',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>',
  },
  {
    key: 'tools',
    path: '/tools',
    label: '工具',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>',
  },
  {
    key: 'lab',
    path: '/lab',
    label: '实验室',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 3H5a2 2 0 00-2 2v4a2 2 0 002 2h4a2 2 0 002-2V5a2 2 0 00-2-2z"/><path d="M19 3h-4a2 2 0 00-2 2v4a2 2 0 002 2h4a2 2 0 002-2V5a2 2 0 00-2-2z"/><path d="M9 21h-4a2 2 0 01-2-2v-4a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2z"/><path d="M19 21h-4a2 2 0 01-2-2v-4a2 2 0 012-2h4a2 2 0 012 2v4a2 2 0 01-2 2z"/></svg>',
  },
  {
    key: 'profile',
    path: '/profile',
    label: '我的',
    icon: '<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>',
  },
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
  background: var(--bg-card);
  border-top: 1px solid var(--border-light);
  display: flex;
  z-index: 50;
  /* 手机端左右留白 + 最大宽度居中 */
  padding: 0 calc((100vw - min(100vw, var(--max-width))) / 2);
}

/* PC 端隐藏 */
@media (min-width: 1024px) {
  .mobile-tab-bar { display: none !important; }
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
  -webkit-tap-highlight-color: transparent;
}
.tab-item.active {
  color: var(--brand);
}
.tab-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 20px;
}
.tab-icon :deep(svg) {
  width: 20px;
  height: 20px;
}
.tab-label {
  font-size: 10px;
  font-weight: 500;
  line-height: 1;
}
</style>
