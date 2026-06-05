<template>
  <div class="page-placeholder">
    <div class="card">
      <div class="card-title">我的</div>
      <div class="profile-items">
        <div class="profile-item">
          <span class="pi-label">免责声明</span>
          <span class="pi-arrow">›</span>
        </div>
        <div class="profile-item">
          <span class="pi-label">数据来源</span>
          <span class="pi-arrow">›</span>
        </div>
      </div>
    </div>
    <div class="disclaimer">
      <p>本工具展示数据仅供参考，不构成任何投资建议。</p>
      <p>投资有风险，决策需谨慎。</p>
    </div>
  </div>
</template>
<script setup></script>
<style scoped>
.profile-items { display: flex; flex-direction: column; }
.profile-item { display: flex; justify-content: space-between; padding: 14px 0; border-bottom: 1px solid var(--border); cursor: pointer; }
.profile-item:last-child { border-bottom: none; }
.pi-label { font-size: 14px; color: var(--text-primary); }
.pi-arrow { color: var(--text-muted); }
.disclaimer { font-size: 12px; color: var(--text-muted); line-height: 1.8; padding: 0 4px; }
</style>
