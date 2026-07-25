<template>
  <div class="login-overlay" :class="{ 'login-overlay--wall': wall }" @click.self="!wall && $emit('close')">
    <div class="login-dialog" role="dialog" aria-modal="true" aria-label="登录注册">
      <button v-if="!wall" class="login-close" @click="$emit('close')" aria-label="关闭">&times;</button>

      <div class="login-title">登录</div>

      <!-- Tab 切换 -->
      <div class="login-tabs">
        <span class="login-tab" :class="{ active: mode === 'signin' || mode === 'reset' }" @click="mode = 'signin'">登录</span>
        <span class="login-tab" :class="{ active: mode === 'signup' }" @click="mode = 'signup'; accType = 'phone'">注册（手机号）</span>
      </div>

      <!-- 账号类型切换：仅登录时可选邮箱/手机号；注册仅限手机号 -->
      <div class="login-acctype" v-if="mode === 'signin'">
        <button type="button" class="acctype-btn" :class="{ active: accType === 'email' }" @click="accType = 'email'">邮箱</button>
        <button type="button" class="acctype-btn" :class="{ active: accType === 'phone' }" @click="accType = 'phone'">手机号</button>
      </div>
      <p class="login-hint" v-else>新用户请使用手机号注册，自主设定密码（无需短信验证码），注册后申请访问权限。</p>

      <!-- 表单 -->
      <div class="login-form">
        <!-- 重置密码模式 -->
        <template v-if="mode === 'reset'">
          <p class="login-hint">输入注册时使用的邮箱或手机号，我们将发送密码重置链接到您的邮箱。</p>

          <div class="login-acctype">
            <button type="button" class="acctype-btn" :class="{ active: accType === 'email' }" @click="accType = 'email'">邮箱</button>
            <button type="button" class="acctype-btn" :class="{ active: accType === 'phone' }" @click="accType = 'phone'">手机号</button>
          </div>

          <label class="login-label" :for="accType === 'email' ? 'reset-email' : 'reset-phone'">
            {{ accType === 'email' ? '邮箱地址' : '手机号' }}
          </label>
          <input
            :id="accType === 'email' ? 'reset-email' : 'reset-phone'"
            class="login-input"
            :type="accType === 'email' ? 'email' : 'tel'"
            v-model="account"
            :placeholder="accType === 'email' ? 'you@example.com' : '11 位手机号'"
            @keyup.enter="sendReset"
          />

          <div class="login-error" v-if="error">{{ error }}</div>
          <div class="login-success" v-if="success">{{ success }}</div>

          <button class="login-submit" :disabled="loading" @click="sendReset">
            {{ loading ? '发送中...' : '发送重置链接' }}
          </button>

          <button class="login-link-btn" type="button" @click="backToSignin">← 返回登录</button>
        </template>

        <!-- 登录 / 注册模式 -->
        <template v-else>
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

        <!-- 忘记密码：仅登录模式显示 -->
        <button
          v-if="mode === 'signin'"
          class="login-forgot"
          type="button"
          @click="startReset"
        >忘记密码？</button>

        <button class="login-submit" :disabled="loading" @click="submit">
          {{ loading ? '处理中...' : (mode === 'signup' ? '注册' : '登录') }}
        </button>

        <div class="login-divider"><span>或</span></div>
        <button class="login-wechat" type="button" @click="startWechatLogin" :disabled="wxLoading">
          <span class="login-wechat__icon">微</span>{{ wxLoading ? '跳转中...' : '微信扫码登录' }}
        </button>
        </template>
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

const mode = ref('signin')      // 'signin' | 'signup' | 'reset'
const accType = ref('email')    // 'email' | 'phone'
const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref('')
const wxLoading = ref(false)

// 手机号规范化：11 位大陆号补 +86；已带 + 的保留
function normalizePhone(v) {
  v = (v || '').replace(/[\s-]/g, '')
  if (v.startsWith('+')) return v
  if (v.startsWith('86') && v.length === 13) return '+' + v
  if (/^1\d{10}$/.test(v)) return '+86' + v
  return v
}

// 手机号 → 确定性合成邮箱（Supabase 手机号注册未开启，且需短信OTP，
// 故以合成邮箱承载「手机号+密码」身份，复用既有的邮件自动确认与邮箱权限体系）。
// 新账号使用 @dachu.user；历史账号为 @allfund.user，登录时按候选顺序逐一尝试以保证兼容。
function phoneCandidates(phone) {
  const p = normalizePhone(phone).replace(/^\+/, '')
  return [`${p}@dachu.user`, `${p}@allfund.user`]
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
      if (isPhone) {
        // 历史账号可能落在 @allfund.user，先逐一尝试验证是否已注册
        let existing = false
        for (const email of phoneCandidates(identifier)) {
          const { error: e2 } = await supabase.auth.signInWithPassword({ email, password: password.value })
          if (!e2) { existing = true; break }
        }
        if (existing) {
          error.value = '该手机号已注册，请直接登录'
          mode.value = 'signin'
          return
        }
        const { data, error: err } = await supabase.auth.signUp({ email: phoneCandidates(identifier)[0], password: password.value })
        if (err) { error.value = translateError(err.message); return }
        if (data?.user?.identities?.length === 0) {
          error.value = '该手机号已注册，请直接登录'
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
        const creds = { email: identifier, password: password.value }
        const { data, error: err } = await supabase.auth.signUp(creds)
        if (err) { error.value = translateError(err.message); return }
        if (data?.user?.identities?.length === 0) {
          error.value = '该邮箱已注册，请直接登录'
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
      }
    } else {
      if (isPhone) {
        // 新账号 @dachu.user，历史账号 @allfund.user，按候选顺序逐一登录
        let ok = false
        for (const email of phoneCandidates(identifier)) {
          const { error: err } = await supabase.auth.signInWithPassword({ email, password: password.value })
          if (!err) { ok = true; break }
        }
        if (!ok) { error.value = '账号或密码错误'; return }
      } else {
        const { error: err } = await supabase.auth.signInWithPassword({ email: identifier, password: password.value })
        if (err) { error.value = translateError(err.message); return }
      }
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

// 微信网页扫码登录：跳转微信开放平台扫码页，回调 /wechat-callback 完成会话签发
function startWechatLogin() {
  const appid = import.meta.env.VITE_WECHAT_WEB_APPID
  if (!appid) {
    toast('微信登录暂未开放', 'info')
    return
  }
  wxLoading.value = true
  const redirect = encodeURIComponent(location.origin + '/wechat-callback')
  const state = Math.random().toString(36).slice(2)
  try { localStorage.setItem('wx_login_state', state) } catch (e) {}
  const url = `https://open.weixin.qq.com/connect/qrconnect?appid=${appid}&redirect_uri=${redirect}&response_type=code&scope=snsapi_login&state=${state}#wechat_redirect`
  location.href = url
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

// ── 重置密码 ──
function startReset() {
  mode.value = 'reset'
  error.value = ''
  success.value = ''
  account.value = ''
}

function backToSignin() {
  mode.value = 'signin'
  error.value = ''
  success.value = ''
}

async function sendReset() {
  error.value = ''
  success.value = ''
  const isPhone = accType.value === 'phone'
  const identifier = isPhone ? normalizePhone(account.value) : (account.value || '').trim()

  if (!identifier) {
    error.value = isPhone ? '请填写手机号' : '请填写邮箱'
    return
  }
  if (isPhone && !/^\+861\d{10}$/.test(identifier)) {
    error.value = '请输入有效的 11 位手机号'
    return
  }
  if (!isPhone && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(identifier)) {
    error.value = '邮箱格式不正确'
    return
  }

  loading.value = true
  try {
    const email = isPhone ? emailForPhone(identifier) : identifier
    const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + '/wechat-callback', // 复用已有回调页处理 token
    })
    if (err) {
      // 用户不存在时也返回友好提示（不泄露用户是否存在）
      error.value = translateError(err.message)
      return
    }
    success.value = '重置链接已发送到您的邮箱，请查收并按提示设置新密码。'
  } catch (e) {
    error.value = '网络错误，请稍后重试'
    console.error('[LoginDialog reset]', e)
  } finally {
    loading.value = false
  }
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

/* 忘记密码链接 */
.login-forgot {
  align-self: flex-end;
  background: none; border: none; font-size: 14px; color: #1d70b8;
  cursor: pointer; padding: 2px 4px; text-decoration: underline;
}
.login-forgot:hover { color: #003078; }

/* 返回按钮 */
.login-link-btn {
  align-self: center;
  background: none; border: 1px solid var(--border); font-size: 14px;
  color: var(--text-secondary); cursor: pointer; padding: var(--space-xs) var(--space-md);
  margin-top: var(--space-sm);
}
.login-link-btn:hover { color: #1d70b8; border-color: #1d70b8; }

/* 微信扫码登录分隔与按钮 */
.login-divider {
  display: flex; align-items: center; text-align: center;
  color: var(--text-secondary); font-size: 13px; margin: 2px 0;
}
.login-divider::before, .login-divider::after {
  content: ''; flex: 1; border-top: 1px solid var(--border);
}
.login-divider span { padding: 0 var(--space-sm); }
.login-wechat {
  display: flex; align-items: center; justify-content: center; gap: var(--space-sm);
  width: 100%; padding: var(--space-sm) var(--space-md);
  font-size: 16px; font-weight: 700; color: #ffffff;
  background: #07c160; border: none; cursor: pointer;
}
.login-wechat:hover { background: #06ad56; }
.login-wechat:disabled { opacity: 0.6; cursor: not-allowed; }
.login-wechat__icon {
  display: inline-flex; align-items: center; justify-content: center;
  width: 22px; height: 22px; border-radius: 50%;
  background: #ffffff; color: #07c160; font-size: 13px; font-weight: 700;
}

.login-hint {
  font-size: 14px; color: var(--text-secondary); margin: 0 0 var(--space-md);
  background: #f3f3f3; border-left: 4px solid #1d70b8; padding: var(--space-sm) var(--space-md);
}
</style>
