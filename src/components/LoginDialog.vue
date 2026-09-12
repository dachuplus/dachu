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
          <template v-if="loading">{{ loadingText }}</template>
          <template v-else>{{ mode === 'signup' ? '注册' : '登录' }}</template>
        </button>

        <!-- 自动重试期间显示取消按钮：用户不必等满 13s -->
        <button v-if="loading && retryCount > 0" class="login-link-btn" type="button" @click="stopAutoRetry">
          中断重试
        </button>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { supabase, rewriteSupabaseUrl, getSupabaseAnonKey } from '../api/supabase'
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
const loadingText = ref('处理中...')
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
  loadingText.value = '验证中...'
  retryCount.value = 0
  cancelAutoRetry.value = false
  stopAutoRetry() // 确保之前的 timer 已清
  try {
    if (mode.value === 'signup') {
      if (isPhone) {
        // 历史账号可能落在 @allfund.user，先逐一尝试验证是否已注册
        let existing = false
        for (const email of phoneCandidates(identifier)) {
          const { error: e2 } = await withAuthTimeout(supabase.auth.signInWithPassword({ email, password: password.value }))
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
        let lastErr = null
        let ok = false
        for (const email of phoneCandidates(identifier)) {
          const err = await authLoginViaEdgeFunction(email, password.value)
          if (!err) { ok = true; break }
          lastErr = err
          // 业务错误（密码错等）不再尝试下一个候选
          if (!isRetryableError(err)) break
        }
        if (!ok) {
          error.value = translateError(
            lastErr ? (typeof lastErr.message === 'string' ? lastErr.message : '') : '',
            lastErr
          )
          return
        }
      } else {
        const err = await authLoginViaEdgeFunction(identifier, password.value)
        if (err) {
          const errMsg = (err && typeof err.message === 'string' && err.message.trim()) ? err.message.trim() : ''
          console.error('[LoginDialog] auth-login error:', JSON.stringify(err), '| extracted msg:', errMsg)
          error.value = translateError(errMsg, err)
          return
        }
      }
      markLogin()
      loadingText.value = '加载权限中...'
      toast('登录成功', 'success')
      emit('logged-in')
    }
  } catch (e) {
    // 超时（AbortError）/网络错 → 友好提示，避免无限"处理中…"
    const msg = (e && e.message) ? String(e.message) : String(e || '')
    console.error('[LoginDialog] 登录异常:', { name: e?.name, message: e?.message, code: e?.code, string: String(e) })
    if (msg.indexOf('aborted') !== -1 || msg.indexOf('timeout') !== -1) {
      error.value = '登录服务响应慢（服务器限速中），请等待 30 秒后重试'
    } else if (msg.indexOf('Failed to fetch') !== -1 || msg.indexOf('NetworkError') !== -1 || msg.indexOf('网络') !== -1) {
      error.value = '网络连接失败，请检查网络后重试'
    } else if (!msg || msg.length < 2) {
      error.value = '登录失败，请稍后重试'
    } else {
      error.value = '登录出错：' + msg
    }
  } finally {
    stopAutoRetry()
    loading.value = false
    loadingText.value = '处理中...'
    retryCount.value = 0
  }
}

// 微信网页扫码登录：已移除（2026-09-04）。如未来要重新接入，恢复下面代码并新建 /wechat-callback 路由。
// function startWechatLogin() { ... }

// 给 Supabase Auth 请求加 60s 超时兜底：避免异常时前端无限"处理中…"
function withAuthTimeout(promise, ms = 60000) {
  return Promise.race([
    promise,
    new Promise((_, reject) => setTimeout(() => reject(new Error('登录服务响应超时 (timeout)')), ms)),
  ])
}

/**
 * 错误分类：判定是否为「网络/超时/服务级」(可重试) vs 「账号密码问题」(不可重试)。
 * supabase-js v2 把 5xx 包成 AuthRetryableFetchError 且 body.message 解析为字面 "{}"，
 * 不能用 err.message 判 timeout/gateway，必须看 err.name 和 err.status。
 */
function isRetryableError(err) {
  if (!err) return false
  const name = err.name || ''
  if (name === 'AuthRetryableFetchError') return true
  if (name === 'AbortError') return true
  if (typeof err.status === 'number' && err.status >= 500) return true
  const msg = (typeof err.message === 'string' ? err.message : '').toLowerCase()
  if (msg.indexOf('timeout') !== -1) return true
  if (msg.indexOf('aborted') !== -1) return true
  if (msg.indexOf('failed to fetch') !== -1) return true
  if (msg.indexOf('networkerror') !== -1) return true
  if (msg.indexOf('fetch failed') !== -1) return true
  return false
}

/**
 * 走 supabase/functions/auth-login（在 Supabase 自身网络内调 auth，绕开 sb-proxy→supabase.co
 * 的 504 卡死）。fetch URL 仍经 sb-proxy 转发（浏览器到 supabase.co 在国内被 GFW 拦）。
 *
 * 返回值统一为 `err` 形状（与 supabase-js 兼容）：成功 = null，失败 = { name, message, status }。
 */
async function authLoginViaEdgeFunction(email, password) {
  const t0 = Date.now()
  const target = 'https://tqhtegazxykkqfcpejky.supabase.co/functions/v1/auth-login'
  const url = rewriteSupabaseUrl(target)
  const apikey = getSupabaseAnonKey()
  const headers = { 'Content-Type': 'application/json' }
  if (apikey) {
    headers['apikey'] = apikey
    headers['Authorization'] = `Bearer ${apikey}`
  }
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), 60000)
  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers,
      body: JSON.stringify({ email, password }),
      signal: controller.signal,
    })
  } catch (e) {
    clearTimeout(timer)
    return {
      name: 'AuthRetryableFetchError',
      message: (e && e.message) ? String(e.message) : 'fetch failed',
      status: 0,
    }
  }
  clearTimeout(timer)
  const dt = Date.now() - t0
  let body = null
  try { body = await resp.json() } catch (_) { /* 非 JSON */ }
  if (resp.ok && body && body.access_token) {
    // 成功：以 supabase-js v2 期望的 session 结构（session 对象本身，顶层直接带
    // access_token / refresh_token / expires_at / user）写入 storage，让 supabase.auth.getSession()
    // 能读到。注意：v2 的 _isValidSession 要求顶层直接有这三个字段，旧的 v1 嵌套
    // { currentSession, currentUser } 结构会被判为无效并丢弃 → 刚登录状态立即失效、登录墙反复弹出。
    // 不能用 supabase.auth.setSession()：它内部会再向 supabase.co 发 _getUser 请求（被 GFW 拦），
    // 而本 edge function 已返回完整 user，故直接本地写入并手动触发 SIGNED_IN 同步全局状态。
    try {
      const session = {
        access_token: body.access_token,
        refresh_token: body.refresh_token,
        token_type: body.token_type || 'bearer',
        expires_in: body.expires_in || 3600,
        expires_at: body.expires_at || Math.floor(Date.now() / 1000) + (body.expires_in || 3600),
        user: body.user,
      }
      const storageKey = supabase && supabase.auth && supabase.auth.storageKey
      if (storageKey && supabase.auth.storage) {
        supabase.auth.storage.setItem(storageKey, JSON.stringify(session))
      }
      if (supabase && supabase.auth && typeof supabase.auth._notifyAllSubscribers === 'function') {
        supabase.auth._notifyAllSubscribers('SIGNED_IN', session)
      }
    } catch (e) {
      console.warn('[LoginDialog] 写入 supabase session 失败，但 token 已获取:', e)
    }
    return null
  }
  // 失败：把后端 body 包装成与 supabase-js 兼容的 error
  const errBody = (body && body.error) || body || {}
  return {
    name: errBody.name || (resp.status >= 500 ? 'AuthRetryableFetchError' : 'AuthApiError'),
    message: (typeof errBody.message === 'string' ? errBody.message : '') || `HTTP ${resp.status}`,
    status: errBody.status || resp.status,
    code: errBody.code,
  }
}

/** 用户点击「中断自动重试」按钮 — 标记状态，等候中的 wait() 会立即返回 */
const retryCount = ref(0)
const cancelAutoRetry = ref(false)
let autoRetryTimer = null
function stopAutoRetry() {
  cancelAutoRetry.value = true
  if (autoRetryTimer) {
    clearTimeout(autoRetryTimer)
    autoRetryTimer = null
  }
}

function translateError(msg, errObj) {
  // 服务级错误（5xx/timeout/gateway/AuthRetryableFetchError）→ 不是账号密码问题
  if (errObj) {
    const name = errObj.name || ''
    const status = errObj.status
    if (name === 'AuthRetryableFetchError' || (typeof status === 'number' && status >= 500)) {
      return '登录服务暂时不可用，请稍后重试'
    }
  }
  const s = (typeof msg === 'string' ? msg : '').trim()
  if (!s) return '登录失败，请检查账号密码或稍后重试'
  if (/timeout|gateway|unavailable|service unavailable|网关|超时/i.test(s)) return '登录服务暂时不可用，请稍后重试'
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
  return map[s] || s
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
    const email = isPhone ? phoneCandidates(identifier)[0] : identifier
    const { error: err } = await supabase.auth.resetPasswordForEmail(email, {
      redirectTo: window.location.origin + '/',
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
