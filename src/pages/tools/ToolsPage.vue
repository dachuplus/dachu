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
/* ========== gov.uk 风格工具集合页 ========== */
.tool-grid { display: flex; flex-direction: column; gap: 0; border-top: 1px solid var(--border); }
.tool-item {
  display: block; padding: var(--space-md) 0;
  border-bottom: 1px solid var(--border);
  text-decoration: none; color: var(--text-primary);
  font-size: 19px; font-weight: 700;
}
.tool-item:hover { background: #f8f8f8; color: var(--text-primary); }
.coming-soon { color: var(--text-secondary); font-size: 16px; padding: var(--space-xl) 0; border-top: 1px solid var(--border); margin-top: var(--space-xl); }
</style>
