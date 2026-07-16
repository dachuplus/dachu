<template>
  <div class="login-overlay" :class="{ 'login-overlay--wall': wall }" @click.self="!wall && $emit('close')">
    <div class="login-dialog" role="dialog" aria-modal="true" aria-label="登录注册">
      <button v-if="!wall" class="login-close" @click="$emit('close')" aria-label="关闭">&times;</button>

      <div class="login-title">登录 ALLFUND.CN</div>

      <!-- Tab 切换 -->
      <div class="login-tabs">
        <span class="login-tab" :class="{ active: mode === 'signin' }" @click="mode = 'signin'">登录</span>
        <span class="login-tab" :class="{ active: mode === 'signup' }" @click="mode = 'signup'">注册</span>
      </div>

      <!-- 账号类型切换：邮箱 / 手机号 -->
      <div class="login-acctype">
        <button type="button" class="acctype-btn" :class="{ active: accType === 'email' }" @click="accType = 'email'">邮箱</button>
        <button type="button" class="acctype-btn" :class="{ active: accType === 'phone' }" @click="accType = 'phone'">手机号</button>
      </div>

      <!-- 表单 -->
      <div class="login-form">
        <label class="login-label" :for="accType === 'email' ? 'login-email' : 'login-phone'">
          {{ accType === 'email' ? '邮箱地址' : '手机号' }}
        </label>
        <input
          :id="accType === 'email' ? 'login-email' : 'login-phone'"
          class="login-input"
          :type="accType === 'email' ? 'email' : 'tel'"
          v-model="account"
          :placeholder="accType === 'email' ? 'you@example.com' : '11 位手机号'"
          @keyup.enter="submit"
        />

        <label class="login-label" for="login-password">密码</label>
        <input
          id="login-password"
          class="login-input"
          type="password"
          v-model="password"
          placeholder="至少 6 位字符（注册时自设）"
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
import { useAuth } from '../composables/useAuth.js'

const props = defineProps({
  // wall=true 时作为登录墙：全屏、不可关闭、无关闭按钮
  wall: { type: Boolean, default: false },
})

const emit = defineEmits(['close', 'logged-in'])
const { markLogin } = useAuth()

const mode = ref('signin')      // 'signin' | 'signup'
const accType = ref('email')    // 'email' | 'phone'
const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')

// 手机号规范化：11 位大陆号补 +86；已带 + 的保留
function normalizePhone(v) {
  v = (v || '').replace(/[\s-]/g, '')
  if (v.startsWith('+')) return v
  if (v.startsWith('86') && v.length === 13) return '+' + v
  if (/^1\d{10}$/.test(v)) return '+86' + v
  return v
}

async function submit() {
  error.value = ''
  success.value = ''
  const isPhone = accType.value === 'phone'
  const identifier = isPhone ? normalizePhone(account.value) : (account.value || '').trim()

  if (!identifier || !password.value) {
    error.value = isPhone ? '请填写手机号和密码' : '请填写邮箱和密码'
    return
  }
  if (isPhone) {
    if (!/^\+861\d{10}$/.test(identifier)) {
      error.value = '请输入有效的 11 位手机号'
      return
    }
  } else {
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identifier)) {
      error.value = '邮箱格式不正确'
      return
    }
  }
  if (password.value.length < 6) {
    error.value = '密码长度至少 6 位'
    return
  }

  loading.value = true
  try {
    if (mode.value === 'signup') {
      const creds = isPhone
        ? { phone: identifier, password: password.value }
        : { email: identifier, password: password.value }
      const { data, error: err } = await supabase.auth.signUp(creds)
      if (err) { error.value = translateError(err.message); return }
      if (data?.user?.identities?.length === 0) {
        error.value = isPhone ? '该手机号已注册，请直接登录' : '该邮箱已注册，请直接登录'
        mode.value = 'signin'
        return
      }
      markLogin()
      if (data?.session) {
        toast('注册成功', 'success')
        emit('logged-in')
      } else {
        success.value = '注册成功！请直接登录。'
      }
    } else {
      const creds = isPhone
        ? { phone: identifier, password: password.value }
        : { email: identifier, password: password.value }
      const { error: err } = await supabase.auth.signInWithPassword(creds)
      if (err) { error.value = translateError(err.message); return }
      markLogin()
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
    'Invalid login credentials': '账号或密码错误',
    'Email not confirmed': '邮箱尚未确认，请直接尝试登录',
    'Phone not confirmed': '手机号尚未验证，请直接尝试登录',
    'User already registered': '该账号已注册，请直接登录',
    'Password should be at least 6 characters': '密码长度至少 6 位',
    'Unable to validate email address: invalid format': '邮箱格式不正确',
    'Unable to validate phone number: invalid format': '手机号格式不正确',
    'Phone auth is not enabled': '手机号注册未启用，请改用邮箱或联系管理员',
    'Signups not allowed for this method': '该注册方式未开启',
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
/* 登录墙模式：品牌蓝全屏背景，不可点击遮罩关闭 */
.login-overlay--wall {
  background: #1d70b8;
  z-index: 1000;
}
.login-overlay--wall .login-dialog {
  border-width: 4px;
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

/* 账号类型切换 */
.login-acctype {
  display: flex; gap: var(--space-sm); margin-bottom: var(--space-md);
}
.acctype-btn {
  flex: 1; padding: var(--space-xs) var(--space-sm);
  font-size: 15px; font-weight: 700; color: var(--text-secondary);
  background: #f3f3f3; border: 1px solid var(--border); cursor: pointer;
}
.acctype-btn.active {
  color: #ffffff; background: #1d70b8; border-color: #1d70b8;
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
