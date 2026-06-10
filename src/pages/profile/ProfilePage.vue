<template>
  <div class="page-placeholder">
    <!-- 用户信息 / 登录注册 -->
    <div class="card">
      <div class="card-title">我的</div>

      <!-- 已登录 -->
      <div v-if="isLoggedIn" class="auth-section">
        <div class="user-info">
          <div class="user-avatar">{{ (user?.email || '?')[0].toUpperCase() }}</div>
          <div class="user-detail">
            <div class="user-email">{{ user?.email || '--' }}</div>
            <div class="user-id">UID: {{ user?.id?.slice(0, 8) || '--' }}</div>
          </div>
        </div>
        <button class="btn-signout" @click="handleSignOut">退出登录</button>
      </div>

      <!-- 未登录 -->
      <div v-else class="auth-section">
        <div class="auth-tabs">
          <span class="auth-tab" :class="{ active: authMode === 'signin' }" @click="authMode = 'signin'">登录</span>
          <span class="auth-tab" :class="{ active: authMode === 'signup' }" @click="authMode = 'signup'">注册</span>
        </div>
        <div class="auth-form">
          <input
            class="govuk-input"
            type="email"
            v-model="authEmail"
            placeholder="邮箱地址"
            @keyup.enter="handleAuth"
          />
          <input
            class="govuk-input"
            type="password"
            v-model="authPassword"
            placeholder="密码（至少6位）"
            @keyup.enter="handleAuth"
          />
          <div class="auth-error" v-if="authError">{{ authError }}</div>
          <div class="auth-success" v-if="authSuccess">{{ authSuccess }}</div>
          <button class="btn-primary govuk-button" @click="handleAuth" :disabled="authLoading">
            {{ authLoading ? '处理中...' : (authMode === 'signin' ? '登录' : '注册') }}
          </button>
        </div>
      </div>
    </div>

    <!-- 功能入口 -->
    <div class="card">
      <div class="profile-items">
        <div class="profile-item" @click="showDisclaimer = !showDisclaimer">
          <span class="pi-label">免责声明</span>
          <span class="pi-arrow">{{ showDisclaimer ? '∨' : '›' }}</span>
        </div>
        <div class="disclaimer-content" v-if="showDisclaimer">
          <p>本工具展示数据仅供参考，不构成任何投资建议。</p>
          <p>投资有风险，决策需谨慎。</p>
          <p>数据来源：天天基金、value500.com、蛋卷基金、恒生聚源、Supabase</p>
        </div>
        <div class="profile-item">
          <span class="pi-label">数据来源</span>
          <span class="pi-arrow">›</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useAuth } from '../../composables/useAuth'

const {
  user, loading: authLoading, authError, isLoggedIn,
  signUp, signIn, signOut
} = useAuth()

const authMode = ref('signin')
const authEmail = ref('')
const authPassword = ref('')
const authSuccess = ref('')
const showDisclaimer = ref(false)

async function handleAuth() {
  authSuccess.value = ''
  if (!authEmail.value || !authPassword.value) {
    authError.value = '请填写邮箱和密码'
    return
  }
  if (authPassword.value.length < 6) {
    authError.value = '密码至少6位'
    return
  }
  if (authMode.value === 'signup') {
    const result = await signUp(authEmail.value, authPassword.value)
    if (result) {
      authSuccess.value = '注册成功！请检查邮箱确认链接。'
    }
  } else {
    await signIn(authEmail.value, authPassword.value)
  }
}

async function handleSignOut() {
  await signOut()
}
</script>

<style scoped>
/* ========== gov.uk 风格"我的"页面 ========== */
.page-placeholder { padding-bottom: var(--space-2xl); }

.card {
  background: #ffffff; border: 1px solid var(--border);
  padding: var(--space-lg); margin-bottom: var(--space-xl);
}
.card-title { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: var(--space-md); }

/* 用户信息 */
.auth-section { margin-top: var(--space-md); }
.user-info { display: flex; align-items: center; gap: var(--space-md); margin-bottom: var(--space-md); }
.user-avatar {
  width: 48px; height: 48px; background: #1d70b8; color: #fff;
  display: flex; align-items: center; justify-content: center;
  font-size: 24px; font-weight: 700;
}
.user-detail { flex: 1; }
.user-email { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.user-id { font-size: 14px; color: var(--text-secondary); }
.btn-signout {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md); font-size: 14px; cursor: pointer;
}
.btn-signout:hover { background: #f3f2f1; }

/* 认证表单 */
.auth-tabs { display: flex; gap: var(--space-lg); margin-bottom: var(--space-md); border-bottom: 2px solid var(--border); }
.auth-tab { font-size: 16px; font-weight: 700; color: var(--text-secondary); cursor: pointer; padding-bottom: var(--space-xs); border-bottom: 3px solid transparent; margin-bottom: -2px; }
.auth-tab.active { color: #1d70b8; border-bottom-color: #1d70b8; }
.auth-form { display: flex; flex-direction: column; gap: var(--space-sm); }
.auth-form .govuk-input { margin-bottom: 0; }
.auth-error { font-size: 14px; color: #d4351c; }
.auth-success { font-size: 14px; color: #00703c; }

/* 功能入口 */
.profile-items { display: flex; flex-direction: column; border-top: 1px solid var(--border); }
.profile-item {
  display: flex; justify-content: space-between;
  padding: var(--space-md) 0; border-bottom: 1px solid var(--border);
  cursor: pointer; font-size: 16px;
}
.profile-item:hover { background: #f8f8f8; }
.pi-label { font-size: 16px; color: var(--text-primary); font-weight: 700; }
.pi-arrow { color: var(--text-secondary); font-size: 19px; }
.disclaimer-content {
  font-size: 14px; color: var(--text-secondary); line-height: 1.8;
  padding: var(--space-md); border-bottom: 1px solid var(--border);
  background: #f8f8f8;
}
.disclaimer-content p { margin: 0 0 var(--space-xs); }
</style>
