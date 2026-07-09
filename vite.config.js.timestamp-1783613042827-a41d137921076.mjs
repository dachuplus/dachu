// vite.config.js
import { defineConfig } from "file:///Users/maoshanbo/WorkBuddy/20260405093252/allfund/node_modules/vite/dist/node/index.js";
import vue from "file:///Users/maoshanbo/WorkBuddy/20260405093252/allfund/node_modules/@vitejs/plugin-vue/dist/index.mjs";
var vite_config_default = defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 解决 value500 和腾讯行情的 CORS 问题
    proxy: {
      "/api/v500": {
        target: "https://www.value500.com",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/v500/, "")
      },
      "/api/qt": {
        target: "https://qt.gtimg.cn",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/qt/, "")
      },
      // 蛋卷基金估值 API 代理（开发环境直连，避免 CORS）
      "/api/danjuan": {
        target: "https://danjuanfunds.com",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api\/danjuan/, "")
      }
    }
  },
  build: {
    outDir: "dist",
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes("node_modules/vue/") || id.includes("node_modules/@vue/") || id.includes("node_modules/vue-router/")) return "vendor";
          if (id.includes("node_modules/@supabase/")) return "supabase";
          if (id.includes("node_modules/echarts/")) return "echarts";
        }
      }
    }
  }
});
export {
  vite_config_default as default
};
//# sourceMappingURL=data:application/json;base64,ewogICJ2ZXJzaW9uIjogMywKICAic291cmNlcyI6IFsidml0ZS5jb25maWcuanMiXSwKICAic291cmNlc0NvbnRlbnQiOiBbImNvbnN0IF9fdml0ZV9pbmplY3RlZF9vcmlnaW5hbF9kaXJuYW1lID0gXCIvVXNlcnMvbWFvc2hhbmJvL1dvcmtCdWRkeS8yMDI2MDQwNTA5MzI1Mi9hbGxmdW5kXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ZpbGVuYW1lID0gXCIvVXNlcnMvbWFvc2hhbmJvL1dvcmtCdWRkeS8yMDI2MDQwNTA5MzI1Mi9hbGxmdW5kL3ZpdGUuY29uZmlnLmpzXCI7Y29uc3QgX192aXRlX2luamVjdGVkX29yaWdpbmFsX2ltcG9ydF9tZXRhX3VybCA9IFwiZmlsZTovLy9Vc2Vycy9tYW9zaGFuYm8vV29ya0J1ZGR5LzIwMjYwNDA1MDkzMjUyL2FsbGZ1bmQvdml0ZS5jb25maWcuanNcIjtpbXBvcnQgeyBkZWZpbmVDb25maWcgfSBmcm9tICd2aXRlJ1xuaW1wb3J0IHZ1ZSBmcm9tICdAdml0ZWpzL3BsdWdpbi12dWUnXG5cbmV4cG9ydCBkZWZhdWx0IGRlZmluZUNvbmZpZyh7XG4gIHBsdWdpbnM6IFt2dWUoKV0sXG4gIHNlcnZlcjoge1xuICAgIHBvcnQ6IDUxNzMsXG4gICAgLy8gXHU4OUUzXHU1MUIzIHZhbHVlNTAwIFx1NTQ4Q1x1ODE3RVx1OEJBRlx1ODg0Q1x1NjBDNVx1NzY4NCBDT1JTIFx1OTVFRVx1OTg5OFxuICAgIHByb3h5OiB7XG4gICAgICAnL2FwaS92NTAwJzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwczovL3d3dy52YWx1ZTUwMC5jb20nLFxuICAgICAgICBjaGFuZ2VPcmlnaW46IHRydWUsXG4gICAgICAgIHJld3JpdGU6IChwYXRoKSA9PiBwYXRoLnJlcGxhY2UoL15cXC9hcGlcXC92NTAwLywgJycpLFxuICAgICAgfSxcbiAgICAgICcvYXBpL3F0Jzoge1xuICAgICAgICB0YXJnZXQ6ICdodHRwczovL3F0Lmd0aW1nLmNuJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICByZXdyaXRlOiAocGF0aCkgPT4gcGF0aC5yZXBsYWNlKC9eXFwvYXBpXFwvcXQvLCAnJyksXG4gICAgICB9LFxuICAgICAgLy8gXHU4NkNCXHU1Mzc3XHU1N0ZBXHU5MUQxXHU0RjMwXHU1MDNDIEFQSSBcdTRFRTNcdTc0MDZcdUZGMDhcdTVGMDBcdTUzRDFcdTczQUZcdTU4ODNcdTc2RjRcdThGREVcdUZGMENcdTkwN0ZcdTUxNEQgQ09SU1x1RkYwOVxuICAgICAgJy9hcGkvZGFuanVhbic6IHtcbiAgICAgICAgdGFyZ2V0OiAnaHR0cHM6Ly9kYW5qdWFuZnVuZHMuY29tJyxcbiAgICAgICAgY2hhbmdlT3JpZ2luOiB0cnVlLFxuICAgICAgICByZXdyaXRlOiAocGF0aCkgPT4gcGF0aC5yZXBsYWNlKC9eXFwvYXBpXFwvZGFuanVhbi8sICcnKSxcbiAgICAgIH0sXG4gICAgfVxuICB9LFxuICBidWlsZDoge1xuICAgIG91dERpcjogJ2Rpc3QnLFxuICAgIHJvbGx1cE9wdGlvbnM6IHtcbiAgICAgIG91dHB1dDoge1xuICAgICAgICBtYW51YWxDaHVua3MoaWQpIHtcbiAgICAgICAgICBpZiAoaWQuaW5jbHVkZXMoJ25vZGVfbW9kdWxlcy92dWUvJykgfHwgaWQuaW5jbHVkZXMoJ25vZGVfbW9kdWxlcy9AdnVlLycpIHx8IGlkLmluY2x1ZGVzKCdub2RlX21vZHVsZXMvdnVlLXJvdXRlci8nKSkgcmV0dXJuICd2ZW5kb3InXG4gICAgICAgICAgaWYgKGlkLmluY2x1ZGVzKCdub2RlX21vZHVsZXMvQHN1cGFiYXNlLycpKSByZXR1cm4gJ3N1cGFiYXNlJ1xuICAgICAgICAgIGlmIChpZC5pbmNsdWRlcygnbm9kZV9tb2R1bGVzL2VjaGFydHMvJykpIHJldHVybiAnZWNoYXJ0cydcbiAgICAgICAgfVxuICAgICAgfVxuICAgIH1cbiAgfVxufSlcbiJdLAogICJtYXBwaW5ncyI6ICI7QUFBcVUsU0FBUyxvQkFBb0I7QUFDbFcsT0FBTyxTQUFTO0FBRWhCLElBQU8sc0JBQVEsYUFBYTtBQUFBLEVBQzFCLFNBQVMsQ0FBQyxJQUFJLENBQUM7QUFBQSxFQUNmLFFBQVE7QUFBQSxJQUNOLE1BQU07QUFBQTtBQUFBLElBRU4sT0FBTztBQUFBLE1BQ0wsYUFBYTtBQUFBLFFBQ1gsUUFBUTtBQUFBLFFBQ1IsY0FBYztBQUFBLFFBQ2QsU0FBUyxDQUFDLFNBQVMsS0FBSyxRQUFRLGdCQUFnQixFQUFFO0FBQUEsTUFDcEQ7QUFBQSxNQUNBLFdBQVc7QUFBQSxRQUNULFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFNBQVMsQ0FBQyxTQUFTLEtBQUssUUFBUSxjQUFjLEVBQUU7QUFBQSxNQUNsRDtBQUFBO0FBQUEsTUFFQSxnQkFBZ0I7QUFBQSxRQUNkLFFBQVE7QUFBQSxRQUNSLGNBQWM7QUFBQSxRQUNkLFNBQVMsQ0FBQyxTQUFTLEtBQUssUUFBUSxtQkFBbUIsRUFBRTtBQUFBLE1BQ3ZEO0FBQUEsSUFDRjtBQUFBLEVBQ0Y7QUFBQSxFQUNBLE9BQU87QUFBQSxJQUNMLFFBQVE7QUFBQSxJQUNSLGVBQWU7QUFBQSxNQUNiLFFBQVE7QUFBQSxRQUNOLGFBQWEsSUFBSTtBQUNmLGNBQUksR0FBRyxTQUFTLG1CQUFtQixLQUFLLEdBQUcsU0FBUyxvQkFBb0IsS0FBSyxHQUFHLFNBQVMsMEJBQTBCLEVBQUcsUUFBTztBQUM3SCxjQUFJLEdBQUcsU0FBUyx5QkFBeUIsRUFBRyxRQUFPO0FBQ25ELGNBQUksR0FBRyxTQUFTLHVCQUF1QixFQUFHLFFBQU87QUFBQSxRQUNuRDtBQUFBLE1BQ0Y7QUFBQSxJQUNGO0FBQUEsRUFDRjtBQUNGLENBQUM7IiwKICAibmFtZXMiOiBbXQp9Cg==
