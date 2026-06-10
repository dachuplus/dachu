import { createApp } from 'vue'
import router from './router/index.js'
import './style.css'
import App from './App.vue'

const app = createApp(App)
app.use(router)

// 全局错误捕获 — 调试用
app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', err)
  const el = document.getElementById('app')
  if (el && !el.querySelector('.vue-error-box')) {
    const box = document.createElement('div')
    box.className = 'vue-error-box'
    box.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:99999;background:#fff3f3;color:#c00;padding:16px;font-size:13px;line-height:1.6;border-bottom:2px solid red;'
    box.innerHTML = '<b>Vue 运行时错误：</b><br>' +
      (err.message || err) +
      '<br><small>来源: ' + (info || '') + '</small>'
    el.prepend(box)
  }
}

app.mount('#app')
