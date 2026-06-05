import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 解决 value500 和腾讯行情的 CORS 问题
    proxy: {
      '/api/v500': {
        target: 'https://www.value500.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v500/, ''),
      },
      '/api/qt': {
        target: 'https://qt.gtimg.cn',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/qt/, ''),
      },
      // 蛋卷基金估值 API 代理（开发环境直连，避免 CORS）
      '/api/danjuan': {
        target: 'https://danjuanfunds.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/danjuan/, ''),
      },
    }
  },
  build: {
    outDir: 'dist',
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/vue/') || id.includes('node_modules/@vue/') || id.includes('node_modules/vue-router/')) return 'vendor'
          if (id.includes('node_modules/@supabase/')) return 'supabase'
          if (id.includes('node_modules/echarts/')) return 'echarts'
        }
      }
    }
  }
})
