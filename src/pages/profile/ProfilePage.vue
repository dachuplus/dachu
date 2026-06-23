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
            <div class="user-meta">
              <span>注册：{{ profile?.created_at ? fmtDate(profile.created_at) : '--' }}</span>
              <span>登录次数：{{ profile?.login_count || 0 }}</span>
            </div>
          </div>
        </div>
        <button class="btn-signout" @click="handleSignOut">退出登录</button>
      </div>

      <!-- 未登录 -->
      <div v-else class="auth-section">
        <p class="auth-hint">登录后可使用组合管理、历史记录等功能</p>
        <button class="btn-primary govuk-button" @click="showLogin">登录 / 注册</button>
      </div>
    </div>

    <!-- 我的组合（已登录时显示） -->
    <div class="card" v-if="isLoggedIn">
      <div class="card-title">我的组合</div>
      <div v-if="portfolios.length === 0" class="empty-portfolio">
        <p>还没有组合，去 <router-link to="/tools/fund-rank">靠谱指数</router-link> 挑选基金添加到组合吧</p>
      </div>
      <div v-for="pf in portfolios" :key="pf.id" class="portfolio-card">
        <div class="pf-header">
          <span class="pf-name">{{ pf.name }}</span>
          <span class="pf-meta">{{ pf.portfolio_data?.length || 0 }} 只基金 · 更新于 {{ fmtDate(pf.updated_at) }}</span>
        </div>
        <div class="pf-funds" v-if="pf.portfolio_data?.length">
          <div v-for="item in pf.portfolio_data" :key="item.code" class="pf-fund-row">
            <span class="pf-fund-code">{{ item.code }}</span>
            <span class="pf-fund-name">{{ item.name }}</span>
            <button class="pf-remove" @click="removeFromPortfolio(pf.id, item.code)">移除</button>
          </div>
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
import { ref } from 'vue'
import { useAuth } from '../../composables/useAuth'
import { removeFundFromPortfolio } from '../../api/user-data'

const {
  user, loading: authLoading, isLoggedIn,
  portfolios, profile,
  signOut, refreshUserData, showLogin
} = useAuth()

const showDisclaimer = ref(false)

function fmtDate(ts) {
  if (!ts) return '--'
  const d = new Date(ts)
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' })
}

async function handleSignOut() {
  await signOut()
}

async function removeFromPortfolio(pfId, code) {
  await removeFundFromPortfolio(pfId, code)
  await refreshUserData()
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
.user-meta { font-size: 14px; color: var(--text-secondary); margin-top: 4px; display: flex; gap: var(--space-lg); }
.btn-signout {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  padding: var(--space-xs) var(--space-md); font-size: 14px; cursor: pointer;
}
.btn-signout:hover { background: #f3f2f1; }

/* 认证表单 */
.auth-hint { font-size: 16px; color: var(--text-secondary); margin-bottom: var(--space-md); }

/* 组合列表 */
.empty-portfolio { padding: var(--space-xl) 0; font-size: 16px; color: var(--text-secondary); text-align: center; }
.empty-portfolio a { color: var(--link); text-decoration: underline; }

.portfolio-card {
  border-top: 1px solid var(--border); padding: var(--space-md) 0;
}
.pf-header { margin-bottom: var(--space-sm); }
.pf-name { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.pf-meta { font-size: 14px; color: var(--text-secondary); margin-left: var(--space-md); }

.pf-funds { border-top: 1px solid #f3f2f1; padding-top: var(--space-sm); }
.pf-fund-row {
  display: flex; align-items: center; padding: var(--space-xs) 0;
  font-size: 14px;
}
.pf-fund-code { font-weight: 700; color: var(--text-secondary); width: 90px; font-family: monospace; }
.pf-fund-name { flex: 1; color: var(--text-primary); }
.pf-remove {
  background: none; border: none; color: #d4351c; font-size: 13px;
  cursor: pointer; padding: 2px 8px;
}
.pf-remove:hover { text-decoration: underline; }

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
