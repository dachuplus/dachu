<template>
  <div class="page-placeholder">
    <!-- 用户信息 / 登录注册 -->
    <div class="card">
      <div class="card-title">我的</div>

      <!-- 已登录 -->
      <div v-if="isLoggedIn" class="auth-section">
        <div class="user-info">
          <div class="user-avatar">{{ displayInitial }}</div>
          <div class="user-detail">
            <div class="user-email">{{ displayName }}</div>
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

    <!-- 我的关注（已登录时显示） -->
    <div class="card" v-if="isLoggedIn">
      <div class="card-title">我的关注</div>
      <div v-if="!favRows.length && !favLoading" class="empty-portfolio">
        <p>还没有关注基金，去 <router-link to="/tools/fund-rank">工具</router-link> 页添加关注吧</p>
      </div>
      <div v-else-if="favLoading" class="empty-portfolio"><p>加载中...</p></div>
      <div v-else class="fav-list">
        <div v-for="item in favRows" :key="item.c" class="fav-row">
          <div class="fav-main">
            <span class="fav-name">{{ item.name || '--' }}</span>
            <span class="fav-code">{{ item.c }}</span>
          </div>
          <div class="fav-score" v-if="item.k_all != null">{{ item.k_all.toFixed(1) }}</div>
          <div class="fav-return" :class="{ 'text-up': isUp(item.r1y), 'text-down': isDown(item.r1y) }">
            {{ formatReturn(item.r1y) }}
          </div>
          <button class="fav-remove" @click="onRemoveFav(item.c)">移除</button>
        </div>
      </div>
    </div>

    <!-- 我的组合（已登录时显示） -->
    <div class="card" v-if="isLoggedIn">
      <div class="card-title">我的组合</div>
      <div v-if="portfolios.length === 0" class="empty-portfolio">
        <p>还没有组合，去 <router-link to="/tools/fund-rank">工具</router-link> 挑选基金添加到组合吧</p>
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
          <p>数据来源：ALLFUND.CN</p>
        </div>
        <router-link v-if="isOwner" to="/data-center" class="profile-item">
          <span class="pi-label">下载数据 (数据中心)</span>
          <span class="pi-arrow">›</span>
        </router-link>
        <div class="profile-item">
          <span class="pi-label">数据来源</span>
          <span class="pi-arrow">›</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAuth } from '../../composables/useAuth'
import { useFavorites } from '../../composables/useFavorites'
import { removeFundFromPortfolio } from '../../api/user-data'
import { supabase } from '../../api/supabase'

const {
  user, loading: authLoading, isLoggedIn, isOwner,
  displayName, displayInitial,
  portfolios, profile,
  signOut, refreshUserData, showLogin
} = useAuth()

const { favorites, removeFav } = useFavorites()

const showDisclaimer = ref(false)

// 关注基金
const favRows = ref([])
const favLoading = ref(false)

function isUp(v) { return typeof v === 'number' && v > 0 }
function isDown(v) { return typeof v === 'number' && v < 0 }
function formatReturn(v) {
  if (typeof v !== 'number') return '--'
  return (v > 0 ? '+' : '') + v.toFixed(2) + '%'
}

async function fetchFavScores() {
  if (!favorites.value.length) { favRows.value = []; return }
  favLoading.value = true
  const codes = favorites.value.map(f => f.c)
  const base = favorites.value.map(f => ({ ...f, k_all: undefined, r1y: undefined }))
  try {
    const { data, error } = await supabase
      .from('fund_scores')
      .select('c,name,k_all,r1y')
      .in('c', codes)
    if (!error && data) {
      const byCode = Object.fromEntries(data.map(d => [d.c, d]))
      favRows.value = base.map(f => {
        const s = byCode[f.c]
        return s ? { ...f, name: s.name, k_all: s.k_all, r1y: s.r1y } : f
      })
    } else {
      favRows.value = base
    }
  } catch (e) {
    favRows.value = base
  }
  favLoading.value = false
}

function onRemoveFav(c) { removeFav(c) }

watch(favorites, fetchFavScores, { deep: true })

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

onMounted(fetchFavScores)
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

/* 关注基金 */
.fav-list { border-top: 1px solid var(--border); }
.fav-row {
  display: flex; align-items: center; gap: var(--space-md);
  padding: var(--space-sm) 0; border-bottom: 1px solid #f3f2f1;
}
.fav-row:last-child { border-bottom: none; }
.fav-main { flex: 1; min-width: 0; }
.fav-name { font-weight: 700; color: var(--text-primary); font-size: 15px; }
.fav-code { font-size: 13px; color: var(--text-secondary); font-family: monospace; margin-left: var(--space-sm); }
.fav-score { font-weight: 700; font-size: 16px; color: var(--text-primary); width: 48px; text-align: right; }
.fav-return { font-weight: 700; font-size: 14px; width: 72px; text-align: right; }
.fav-remove {
  background: none; border: 1px solid var(--border); color: var(--text-secondary);
  font-size: 13px; cursor: pointer; padding: 4px 10px;
}
.fav-remove:hover { color: #d4351c; border-color: #d4351c; }
.text-up { color: #d4351c; }
.text-down { color: #00703c; }
.profile-item {
  display: flex; justify-content: space-between;
  padding: var(--space-md) 0; border-bottom: 1px solid var(--border);
  cursor: pointer; font-size: 16px;
  text-decoration: none; color: inherit;
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
