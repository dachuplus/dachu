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
/* ========== gov.uk 风格"我的"页面 ========== */
.page-placeholder { padding-bottom: var(--space-2xl); }
.profile-items { display: flex; flex-direction: column; border-top: 1px solid var(--border); }
.profile-item {
  display: flex; justify-content: space-between;
  padding: var(--space-md) 0; border-bottom: 1px solid var(--border);
  cursor: pointer; font-size: 16px;
}
.profile-item:hover { background: #f8f8f8; }
.pi-label { font-size: 16px; color: var(--text-primary); font-weight: 700; }
.pi-arrow { color: var(--text-secondary); font-size: 19px; }
.disclaimer {
  font-size: 16px; color: var(--text-secondary); line-height: 1.8;
  padding: var(--space-xl) 0; border-top: 1px solid var(--border); margin-top: var(--space-xl);
}
</style>
