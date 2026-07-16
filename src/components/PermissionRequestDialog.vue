<template>
  <div class="login-overlay" v-if="show">
    <div class="login-dialog" role="dialog" aria-modal="true" aria-label="申请权限">
      <div class="login-title">申请访问权限</div>
      <p class="perm-subtitle">请填写以下信息，管理员审核通过后将为您开通对应功能。</p>

      <!-- 提交成功态 -->
      <div class="perm-success" v-if="submitted">
        <div class="perm-success__icon" aria-hidden="true">✓</div>
        <div class="perm-success__title">权限申请已经提交</div>
        <p class="perm-success__desc">我们已收到您的访问权限申请，管理员审核通过后将为您开通对应功能，请耐心等待。</p>
        <button class="login-submit perm-success__close" type="button" @click="$emit('submitted'); $emit('close')">关闭</button>
      </div>

      <div class="login-form" v-else>
        <label class="login-label" for="perm-realName">真实姓名</label>
        <input
          id="perm-realName"
          class="login-input"
          type="text"
          v-model="realName"
          placeholder="请输入您的真实姓名"
          @keyup.enter="submit"
        />

        <label class="login-label" for="perm-phone">手机号</label>
        <input
          id="perm-phone"
          class="login-input"
          type="tel"
          v-model="phone"
          placeholder="11 位手机号（可带 +86）"
          @keyup.enter="submit"
        />

        <label class="login-label" for="perm-extra">补充信息</label>
        <textarea
          id="perm-extra"
          class="login-textarea"
          v-model="extra"
          rows="3"
          placeholder="如：您的使用场景、希望开通的功能等（选填）"
        ></textarea>

        <div class="login-error" v-if="error">{{ error }}</div>

        <div class="login-actions">
          <button class="login-cancel" type="button" @click="$emit('close')">取消</button>
          <button class="login-submit" type="button" :disabled="loading" @click="submit">
            {{ loading ? '提交中...' : '提交申请' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { usePermissionRequests } from '../composables/usePermissionRequests.js'

const props = defineProps({
  // 控制弹窗显示：true 时渲染遮罩与卡片
  show: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'submitted'])

const { submitRequest } = usePermissionRequests()

const realName = ref('')
const phone    = ref('')
const extra    = ref('')
const loading  = ref(false)
const error    = ref('')
const submitted = ref(false)

// 手机号校验：11 位大陆号，允许可选 +86 前缀
function isPhoneValid(v) {
  const s = (v || '').replace(/[\s-]/g, '')
  return /^(?:\+?86)?1\d{10}$/.test(s)
}

async function submit() {
  error.value = ''
  const name = (realName.value || '').trim()
  if (!name) {
    error.value = '请填写真实姓名'
    return
  }
  if (!isPhoneValid(phone.value)) {
    error.value = '请输入有效的 11 位手机号（可带 +86）'
    return
  }

  loading.value = true
  try {
    await submitRequest({ realName: name, phone: phone.value.trim(), extra: (extra.value || '').trim() })
    // 重置表单
    realName.value = ''
    phone.value = ''
    extra.value = ''
    // 进入提交成功态：弹窗内展示「权限申请已经提交」，由关闭按钮自行关闭
    submitted.value = true
  } catch (e) {
    error.value = e?.message || '提交失败，请稍后重试'
    console.error('[PermissionRequestDialog]', e)
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* 复用 LoginDialog 的 .login-overlay / .login-dialog 视觉风格（dark overlay + 白色卡片） */
.login-overlay {
  position: fixed; inset: 0; z-index: 1000;
  background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center;
}
.login-dialog {
  background: #ffffff;
  border: 2px solid #1d70b8;
  width: 440px; max-width: 90vw; max-height: 90vh; overflow-y: auto;
  padding: 30px;
  position: relative;
  border-radius: 0;
}
.login-title {
  font-size: 24px; font-weight: 700; color: #0b0c0c;
  margin-bottom: var(--space-sm);
}
.perm-subtitle {
  font-size: 15px; color: var(--text-secondary); line-height: 1.6;
  margin: 0 0 var(--space-lg);
}

/* 提交成功态 */
.perm-success {
  text-align: center;
  padding: var(--space-lg) 0 var(--space-sm);
}
.perm-success__icon {
  width: 56px; height: 56px; line-height: 56px;
  margin: 0 auto var(--space-md);
  border-radius: 50%;
  background: #00703c; color: #ffffff;
  font-size: 30px; font-weight: 700;
}
.perm-success__title {
  font-size: 22px; font-weight: 700; color: #00703c;
  margin-bottom: var(--space-sm);
}
.perm-success__desc {
  font-size: 15px; color: var(--text-secondary); line-height: 1.6;
  margin: 0 0 var(--space-lg);
}
.perm-success__close {
  width: 100%;
}

/* Form */
.login-form {
  display: flex; flex-direction: column; gap: var(--space-md);
}
.login-label {
  font-size: 16px; font-weight: 700; color: #0b0c0c;
  margin-bottom: -8px;
}
.login-input {
  padding: var(--space-sm); border: 1px solid var(--border);
  font-size: 16px; width: 100%; box-sizing: border-box;
  border-radius: 0;
}
.login-input:focus { outline: 2px solid #1d70b8; outline-offset: -1px; }
.login-textarea {
  padding: var(--space-sm); border: 1px solid var(--border);
  font-size: 16px; width: 100%; box-sizing: border-box;
  resize: vertical; font-family: inherit; line-height: 1.5;
  border-radius: 0;
}
.login-textarea:focus { outline: 2px solid #1d70b8; outline-offset: -1px; }

.login-error {
  font-size: 14px; color: #d4351c; font-weight: 700;
}

.login-actions {
  display: flex; gap: var(--space-sm); margin-top: var(--space-sm);
}
.login-submit {
  flex: 1;
  background: #1d70b8; color: #ffffff; border: none;
  padding: var(--space-sm) var(--space-md); font-size: 16px; font-weight: 700;
  cursor: pointer; border-radius: 0;
}
.login-submit:hover { background: #003078; }
.login-submit:disabled { opacity: 0.6; cursor: not-allowed; }
.login-cancel {
  flex: 1;
  background: #ffffff; color: #1d70b8; border: 1px solid #1d70b8;
  padding: var(--space-sm) var(--space-md); font-size: 16px; font-weight: 700;
  cursor: pointer; border-radius: 0;
}
.login-cancel:hover { background: #f3f3f3; }
</style>
