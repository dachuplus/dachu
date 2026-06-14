<template>
  <svg
    class="svg-icon"
    :width="size"
    :height="size"
    :viewBox="viewBox"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
  >
    <!-- 指标信号 — 波形图 -->
    <template v-if="name === 'signal'">
      <rect x="4" y="14" width="4" height="8" rx="1" stroke="currentColor" stroke-width="2"/>
      <rect x="12" y="8" width="4" height="14" rx="1" stroke="currentColor" stroke-width="2"/>
      <rect x="20" y="2" width="4" height="20" rx="1" stroke="currentColor" stroke-width="2"/>
      <rect x="28" y="10" width="4" height="12" rx="1" stroke="currentColor" stroke-width="2"/>
    </template>

    <!-- 牛人组合 — 五角星 -->
    <template v-else-if="name === 'star'">
      <path d="M16 2L19.09 10.86L28 11.27L21 17.14L22.18 26L16 21.77L9.82 26L11 17.14L4 11.27L12.91 10.86L16 2Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </template>

    <!-- AI组合 — 芯片/大脑 -->
    <template v-else-if="name === 'ai'">
      <rect x="6" y="6" width="20" height="20" rx="4" stroke="currentColor" stroke-width="2"/>
      <rect x="10" y="10" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5"/>
      <rect x="17" y="10" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5"/>
      <rect x="10" y="17" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5"/>
      <rect x="17" y="17" width="5" height="5" rx="1" stroke="currentColor" stroke-width="1.5"/>
    </template>

    <!-- 靠谱指数 — 奖牌 -->
    <template v-else-if="name === 'medal'">
      <circle cx="16" cy="11" r="7" stroke="currentColor" stroke-width="2"/>
      <path d="M11 16L8 28L16 23L24 28L21 16" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </template>

    <!-- 基金组合 — 文件夹/组合 -->
    <template v-else-if="name === 'portfolio'">
      <rect x="3" y="6" width="11" height="10" rx="2" stroke="currentColor" stroke-width="2"/>
      <rect x="18" y="6" width="11" height="10" rx="2" stroke="currentColor" stroke-width="2"/>
      <rect x="3" y="21" width="11" height="10" rx="2" stroke="currentColor" stroke-width="2"/>
      <rect x="18" y="21" width="11" height="10" rx="2" stroke="currentColor" stroke-width="2"/>
    </template>

    <!-- 投顾产品 — 盾牌 -->
    <template v-else-if="name === 'shield'">
      <path d="M5 10L16 3L27 10V18C27 24 16 30 16 30C16 30 5 24 5 18V10Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      <path d="M12 16L15 19L20 13" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
    </template>

    <!-- 实验室 — 烧杯 -->
    <template v-else-if="name === 'lab'">
      <path d="M10 2H22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <path d="M12 2V12L4 28H28L20 12V2" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      <path d="M10 18H22" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 用户/我的 — 人物 -->
    <template v-else-if="name === 'user'">
      <circle cx="16" cy="10" r="5" stroke="currentColor" stroke-width="2"/>
      <path d="M4 28C4 22 8 18 16 18C24 18 28 22 28 28" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 工具 — 齿轮 -->
    <template v-else-if="name === 'gear'">
      <circle cx="16" cy="16" r="4" stroke="currentColor" stroke-width="2"/>
      <path d="M16 2V6M16 26V30M5.64 5.64L8.47 8.47M23.53 23.53L26.36 26.36M2 16H6M26 16H30M5.64 26.36L8.47 23.53M23.53 8.47L26.36 5.64" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 首页/总览 — 仪表盘 -->
    <template v-else-if="name === 'dashboard'">
      <path d="M4 20C4 13.37 9.37 8 16 8C22.63 8 28 13.37 28 20" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
      <path d="M4 20H8L11 14L15 22L18 10L22 18L25 13L28 20" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </template>

    <!-- 点赞 — 大拇指向上 -->
    <template v-else-if="name === 'thumbs-up'">
      <path d="M6 14H10V26H6V14Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      <path d="M10 14L14 6C14 5 15 4 17 4C17.5 4 18 4.5 18 5V10H25C26 10 27 11 27 12L24 23C24 24 23 25 22 25H10V14Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </template>

    <!-- 吐槽 — 大拇指向下 -->
    <template v-else-if="name === 'thumbs-down'">
      <path d="M6 18H10V6H6V18Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
      <path d="M10 18L14 26C14 27 15 28 17 28C17.5 28 18 27.5 18 27V22H25C26 22 27 21 27 20L24 9C24 8 23 7 22 7H10V18Z" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>
    </template>

    <!-- 添加/加号 — 圆形加号 -->
    <template v-else-if="name === 'plus-circle'">
      <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2"/>
      <path d="M16 8V24M8 16H24" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 搜索 — 放大镜 -->
    <template v-else-if="name === 'search'">
      <circle cx="14" cy="14" r="8" stroke="currentColor" stroke-width="2"/>
      <path d="M20 20L28 28" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 帮助 — 问号圆 -->
    <template v-else-if="name === 'help'">
      <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2"/>
      <path d="M14 14C14 12 16 10 16 10C18 10 19 11.5 19 13C19 15 16 16 16 16V18" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
      <circle cx="16" cy="23" r="1.5" fill="currentColor"/>
    </template>

    <!-- 对勾 -->
    <template v-else-if="name === 'check'">
      <path d="M6 16L13 23L26 8" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
    </template>

    <!-- 关闭 — X -->
    <template v-else-if="name === 'close'">
      <path d="M8 8L24 24M24 8L8 24" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
    </template>

    <!-- 默认 — 点 -->
    <template v-else>
      <circle cx="16" cy="16" r="6" stroke="currentColor" stroke-width="2"/>
    </template>
  </svg>
</template>

<script setup>
defineProps({
  name: { type: String, required: true },
  size: { type: [String, Number], default: 18 },
})
const viewBox = '0 0 32 32'
</script>

<style scoped>
.svg-icon {
  display: inline-block;
  vertical-align: middle;
  flex-shrink: 0;
}
</style>
