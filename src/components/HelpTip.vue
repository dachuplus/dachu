<template>
  <span class="help-tip" @mouseenter="open = true" @mouseleave="open = false">
    <span class="help-tip__icon" @click.stop="toggle" @mouseenter="open = true">?</span>
    <span v-if="open" class="help-tip__pop" :class="{ 'help-tip__pop--right': align === 'right' }">
      <span v-if="title" class="help-tip__title">{{ title }}</span>
      <span class="help-tip__body">{{ text }}</span>
    </span>
  </span>
</template>

<script setup>
import { ref } from 'vue'
defineProps({
  title: { type: String, default: '' },
  text: { type: String, default: '' },
  align: { type: String, default: 'left' } // 'left' | 'right'
})
const open = ref(false)
function toggle() { open.value = !open.value }
</script>

<style scoped>
.help-tip {
  position: relative;
  display: inline-flex;
  align-items: center;
  vertical-align: middle;
}
.help-tip__icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 1px solid var(--text-secondary);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
  line-height: 1;
  cursor: help;
  flex: 0 0 auto;
  margin-left: 6px;
}
.help-tip__pop {
  position: absolute;
  top: 24px;
  left: 0;
  z-index: 80;
  width: 300px;
  max-width: 84vw;
  background: #fff;
  border: 1px solid #b1b4b6;
  border-radius: 4px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.15);
  padding: 12px 14px;
  text-align: left;
  white-space: pre-line;
  font-size: 13px;
  line-height: 1.65;
  color: var(--text-primary);
}
.help-tip__pop--right {
  left: auto;
  right: 0;
}
.help-tip__title {
  display: block;
  font-weight: 700;
  margin-bottom: 6px;
  color: var(--brand);
}
.help-tip__body {
  display: block;
}
</style>
