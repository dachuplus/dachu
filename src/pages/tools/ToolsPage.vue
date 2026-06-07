<template>
  <div class="page-placeholder">
    <div class="card">
      <div class="card-title">工具集合</div>
      <div class="tool-grid">
        <router-link to="/tools/tougu"       class="tool-item">🎓 投顾产品精选</router-link>
        <router-link to="/tools/fund-rank"   class="tool-item">🏅 靠谱基金指数</router-link>
        <router-link to="/tools/industry-rank" class="tool-item">📊 指数估值</router-link>
      </div>
    </div>
    <div class="card">
      <div class="card-title">更多功能</div>
      <div class="coming-soon">指数工具 / 大V榜单 / 基金组合等功能开发中...</div>
    </div>
  </div>
</template>
<script setup></script>
<style scoped>
.tool-grid { display: flex; flex-direction: column; gap: 8px; }
.tool-item { display: block; padding: 12px; background: var(--bg-hover); border-radius: 8px; text-decoration: none; color: var(--text-primary); font-size: 14px; border: 1px solid var(--border); }
.tool-item:hover { border-color: var(--color-up); }
.coming-soon { color: var(--text-muted); font-size: 13px; padding: 12px 0; }
</style>
