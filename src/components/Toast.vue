<template>
  <Teleport to="body">
    <transition-group name="toast" tag="div" class="toast-container">
      <div
        v-for="t in toasts"
        :key="t.id"
        class="toast-item"
        :class="'toast--' + t.type"
      >
        <span class="toast__icon">{{ icons[t.type] }}</span>
        <span class="toast__message">{{ t.message }}</span>
      </div>
    </transition-group>
  </Teleport>
</template>

<script setup>
import { computed } from 'vue'
import { useToast } from '../composables/useToast.js'

const { toasts } = useToast()

const icons = { success: '\u2713', error: '\u2717', info: '\u24D8', warning: '\u26A0' }
</script>

<style scoped>
.toast-container {
  position: fixed;
  bottom: 80px;
  right: 20px;
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: 8px;
  pointer-events: none;
}

.toast-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px 16px;
  background: #ffffff;
  border-left: 4px solid;
  border: 1px solid #b1b4b6;
  font-size: 16px;
  line-height: 1.4;
  color: #0b0c0c;
  pointer-events: auto;
  max-width: 360px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.08);
}

.toast--success { border-left-color: #00703c; }
.toast--error   { border-left-color: #d4351c; }
.toast--info    { border-left-color: #1d70b8; }
.toast--warning { border-left-color: #f47738; }

.toast__icon {
  font-size: 18px;
  flex-shrink: 0;
  line-height: 1.3;
}
.toast--success .toast__icon { color: #00703c; }
.toast--error   .toast__icon { color: #d4351c; }
.toast--info    .toast__icon { color: #1d70b8; }
.toast--warning .toast__icon { color: #f47738; }

.toast__message {
  flex: 1;
  word-break: break-word;
}

/* transition */
.toast-enter-active, .toast-leave-active {
  transition: all 0.3s ease;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(40px);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(40px);
}

/* 移动端 */
@media (max-width: 768px) {
  .toast-container {
    left: 15px;
    right: 15px;
    bottom: 80px;
  }
  .toast-item {
    max-width: none;
  }
}
</style>
