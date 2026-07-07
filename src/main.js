import { createApp } from 'vue'
import router from './router/index.js'
import './style.css'
import App from './App.vue'

const app = createApp(App)
app.use(router)

// 全局错误捕获
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err, info)
  const el = document.getElementById('app')
  if (!el) return

  const isProd = import.meta.env.PROD
  if (isProd) {
    // 生产环境：仅显示友好提示，不暴露内部错误细节
    if (!el.querySelector('.vue-error-box')) {
      const box = document.createElement('div')
      box.className = 'vue-error-box'
      box.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#f3f2f1;color:#0b0c0c;padding:12px 16px;font-size:14px;border-top:3px solid #1d70b8;text-align:center;cursor:pointer;box-shadow:0 -2px 8px rgba(0,0,0,0.1);'
      box.textContent = '页面出现了一点小问题，点击此处刷新 ↻'
      box.onclick = () => location.reload()
      el.appendChild(box)
    }
  } else {
    // 开发环境：显示详细错误（调试用）
    if (!el.querySelector('.vue-error-box')) {
      const box = document.createElement('div')
      box.className = 'vue-error-box'
      box.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;background:#fff3f3;color:#c00;padding:16px;font-size:13px;line-height:1.6;border-bottom:2px solid red;'
      box.innerHTML = '<b>Vue 运行时错误：</b><br>' +
        (err.message || err) +
        '<br><small>来源: ' + (info || '') + '</small>'
      el.prepend(box)
    }
  }
}

// 全局未捕获错误兜底（网络/脚本异常不暴露细节）
window.addEventListener('error', (e) => {
  console.error('[Global Error]', e.message)
})
window.addEventListener('unhandledrejection', (e) => {
  console.error('[Unhandled Rejection]', e.reason)
})

app.mount('#app')
