import { ref, readonly } from 'vue'

// 全局单例 — 所有页面共享同一个 toast/confirm 状态
const toasts = ref([])
const confirmState = ref({ show: false, title: '', message: '', resolve: null })

let nextId = 1

/**
 * 显示 toast 通知
 * @param {string} message - 通知内容
 * @param {'success'|'error'|'info'|'warning'} type - 类型
 * @param {number} duration - 自动消失时间(ms)，默认 4000
 */
export function toast(message, type = 'info', duration = 4000) {
  const id = nextId++
  toasts.value = [...toasts.value, { id, message, type }]
  setTimeout(() => {
    toasts.value = toasts.value.filter(t => t.id !== id)
  }, duration)
}

/**
 * 显示确认对话框，返回 Promise<boolean>
 * @param {string} title - 标题
 * @param {string} message - 提示信息
 * @returns {Promise<boolean>} - 用户选择确定返回 true，取消返回 false
 */
export function confirm(title, message) {
  return new Promise((resolve) => {
    confirmState.value = { show: true, title, message, resolve }
  })
}

/** 确认对话框内部：确定 */
export function confirmAccept() {
  confirmState.value.resolve?.(true)
  confirmState.value = { show: false, title: '', message: '', resolve: null }
}

/** 确认对话框内部：取消 */
export function confirmCancel() {
  confirmState.value.resolve?.(false)
  confirmState.value = { show: false, title: '', message: '', resolve: null }
}

/** 只读状态，供 Toast/ConfirmDialog 组件消费 */
export function useToast() {
  return {
    toasts: readonly(toasts),
    confirmState
  }
}
