<template>
  <div class="login-overlay" @click.self="$emit('close')">
    <div class="login-dialog" role="dialog" aria-modal="true" aria-label="登录注册">
      <button class="login-close" @click="$emit('close')" aria-label="关闭">&times;</button>

      <div class="login-title">登录 ALLFUND.CN</div>

      <!-- Tab 切换 -->
      <div class="login-tabs">
        <span class="login-tab" :class="{ active: mode === 'signin' }" @click="mode = 'signin'">登录</span>
        <span class="login-tab" :class="{ active: mode === 'signup' }" @click="mode = 'signup'">注册</span>
      </div>

      <!-- 表单 -->
      <div class="login-form">
        <label class="login-label" for="login-email">邮箱地址</label>
        <input
          id="login-email"
          class="login-input"
          type="email"
          v-model="email"
          placeholder="you@example.com"
          @keyup.enter="submit"
        />

        <label class="login-label" for="login-password">密码</label>
        <input
          id="login-password"
          class="login-input"
          type="password"
          v-model="password"
          placeholder="至少 6 位字符"
          @keyup.enter="submit"
        />

        <div class="login-error" v-if="error">{{ error }}</div>
        <div class="login-success" v-if="success">{{ success }}</div>

        <button class="login-submit" :disabled="loading" @click="submit">
          {{ loading ? '处理中...' : (mode === 'signup' ? '注册' : '登录') }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { supabase } from '../api/supabase'
import { toast } from '../composables/useToast.js'

const emit = defineEmits(['close', 'logged-in'])

const mode = ref('signin')
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

async function submit() {
  error.value = ''
  success.value = ''

  if (!email.value || !password.value) {
    error.value = '请填写邮箱和密码'
    return
  }
  if (password.value.length < 6) {
    error.value = '密码长度至少 6 位'
    return
  }

  loading.value = true

  try {
    if (mode.value === 'signup') {
      const { data, error: err } = await supabase.auth.signUp({
        email: email.value,
        password: password.value,
      })
      if (err) {
        error.value = translateError(err.message)
        return
      }
      if (data?.user?.identities?.length === 0) {
        error.value = '该邮箱已注册，请直接登录'
        mode.value = 'signin'
        return
      }
      // 如果邮箱确认开启，提示用户检查邮箱；否则自动已登录
      if (data?.session) {
        toast('注册成功', 'success')
        emit('logged-in')
      } else {
        success.value = '注册成功！请检查邮箱中的确认链接，点击后即可登录。'
      }
    } else {
      const { error: err } = await supabase.auth.signInWithPassword({
        email: email.value,
        password: password.value,
      })
      if (err) {
        error.value = translateError(err.message)
        return
      }
      toast('登录成功', 'success')
      emit('logged-in')
    }
  } catch (e) {
    error.value = '网络错误，请稍后重试'
    console.error('[LoginDialog]', e)
  } finally {
    loading.value = false
  }
}

function translateError(msg) {
  if (!msg) return '未知错误'
  const map = {
    'Invalid login credentials': '邮箱或密码错误',
    'Email not confirmed': '邮箱尚未确认，请检查邮箱中的确认链接',
    'User already registered': '该邮箱已注册，请直接登录',
    'Password should be at least 6 characters': '密码长度至少 6 位',
    'Unable to validate email address: invalid format': '邮箱格式不正确',
  }
  return map[msg] || msg
}
</script>

<style scoped>
.login-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0, 0, 0, 0.4);
  display: flex; align-items: center; justify-content: center;
}
.login-dialog {
  background: #ffffff;
  border: 2px solid #1d70b8;
  width: 400px; max-width: 90vw; max-height: 90vh; overflow-y: auto;
  padding: 30px;
  position: relative;
}
.login-close {
  position: absolute; top: 8px; right: 12px;
  background: none; border: none; font-size: 24px; color: var(--text-secondary);
  cursor: pointer; padding: 4px 8px; line-height: 1;
}
.login-close:hover { color: var(--text-primary); }
.login-title {
  font-size: 24px; font-weight: 700; color: var(--text-primary);
  margin-bottom: var(--space-lg);
}

/* Tabs */
.login-tabs {
  display: flex; gap: var(--space-lg); margin-bottom: var(--space-lg);
  border-bottom: 2px solid var(--border);
}
.login-tab {
  font-size: 16px; font-weight: 700; color: var(--text-secondary);
  cursor: pointer; padding-bottom: var(--space-xs);
  border-bottom: 3px solid transparent; margin-bottom: -2px;
}
.login-tab.active {
  color: #1d70b8; border-bottom-color: #1d70b8;
}

/* Form */
.login-form {
  display: flex; flex-direction: column; gap: var(--space-md);
}
.login-label {
  font-size: 16px; font-weight: 700; color: var(--text-primary);
  margin-bottom: -8px;
}
.login-input {
  padding: var(--space-sm); border: 1px solid var(--border);
  font-size: 16px; width: 100%; box-sizing: border-box;
}
.login-input:focus { outline: 2px solid #1d70b8; outline-offset: -1px; }

.login-error {
  font-size: 14px; color: #d4351c; font-weight: 700;
}
.login-success {
  font-size: 14px; color: #00703c;
  background: #f0faf3; padding: var(--space-sm); border-left: 4px solid #00703c;
}

.login-submit {
  background: #1d70b8; color: #ffffff; border: none;
  padding: var(--space-sm) var(--space-md); font-size: 16px; font-weight: 700;
  cursor: pointer;
}
.login-submit:hover { background: #003078; }
.login-submit:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
