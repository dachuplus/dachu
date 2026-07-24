<template>
  <div class="wechat-cb">
    <div class="wechat-cb__card">
      <div class="wechat-cb__brand">大厨先生</div>
      <div class="wechat-cb__title">{{ statusText }}</div>
      <div class="wechat-cb__spinner" v-if="loading"></div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuth } from '../../composables/useAuth'
import { toast } from '../../composables/useToast'

const route = useRoute()
const router = useRouter()
const { wechatLogin } = useAuth()

const statusText = ref('微信登录处理中...')
const loading = ref(true)

onMounted(async () => {
  const code = route.query.code
  const state = route.query.state
  let savedState = ''
  try { savedState = localStorage.getItem('wx_login_state') || '' } catch (e) {}

  if (!code) {
    statusText.value = '登录失败：缺少授权码'
    loading.value = false
    return
  }
  if (state && savedState && state !== savedState) {
    statusText.value = '登录失败：状态校验不通过'
    loading.value = false
    return
  }

  try {
    await wechatLogin('web', code)
    try { localStorage.removeItem('wx_login_state') } catch (e) {}
    statusText.value = '登录成功，正在跳转...'
    setTimeout(() => router.replace('/'), 600)
  } catch (e) {
    statusText.value = '微信登录失败：' + (e?.message || e)
    loading.value = false
  }
})
</script>

<style scoped>
.wechat-cb {
  min-height: 100vh;
  display: flex; align-items: center; justify-content: center;
  background: #1d70b8;
  padding: 16px;
}
.wechat-cb__card {
  background: #ffffff;
  border: 4px solid #003078;
  max-width: 420px; width: 100%;
  padding: 40px 32px;
  text-align: center;
}
.wechat-cb__brand {
  font-size: 20px; font-weight: 700; color: #1d70b8;
  margin-bottom: 24px; letter-spacing: 0.5px;
}
.wechat-cb__title {
  font-size: 18px; font-weight: 700; color: #0b0c0c; line-height: 1.6;
}
.wechat-cb__spinner {
  width: 28px; height: 28px; margin: 20px auto 0;
  border: 4px solid #b1b4b6; border-top-color: #1d70b8;
  border-radius: 50%;
  animation: wechat-spin 0.8s linear infinite;
}
@keyframes wechat-spin { to { transform: rotate(360deg); } }
</style>
