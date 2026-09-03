#!/usr/bin/env bash
#
# 部署 dachu 到 EdgeOne Pages（overseas 区，免 ICP 备案）。
#
# 关键修复：EdgeOne Pages Functions 必须同时满足两点才会被平台激活：
#   1) functions/ 目录被打入构建产物（dist/functions/...）
#   2) 构建产物根目录存在 package.json（告诉 CLI 这是含 Functions 的项目）
# 此前只拷贝了 functions/ 却漏了 package.json，导致 /api/* 一直落到 SPA 回退。
# 另：部署「文件夹」(./dist) 比 zip 更可靠地触发 Functions 构建。
#
set -euo pipefail

# 切到脚本所在目录的上一级（项目根 dachu/）
cd "$(dirname "$0")/.."

# 载入 .env.local 中的密钥（EDGEONE_PAGES_API_TOKEN 等）
if [ -f .env.local ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env.local
  set +a
fi

# 定位 edgeone CLI（沙箱未加入 PATH，使用受管 node 工作区中的副本）
NODE_BIN="$(command -v node || echo '/Users/maoshanbo/.workbuddy/binaries/node/versions/22.22.2/bin/node')"
EDGEONE_BIN="${EDGEONE_BIN:-$(find /Users/maoshanbo/.workbuddy/binaries/node/workspace/node_modules/edgeone -name edgeone.js -path '*edgeone-bin*' 2>/dev/null | head -1)}"
if [ -z "$EDGEONE_BIN" ]; then
  echo "未找到 edgeone CLI（bin），请确认已安装" >&2
  exit 1
fi

TOKEN="${EDGEONE_PAGES_API_TOKEN:-}"
# 若没有 token，则尝试使用已登录的 ~/.edgeone 会话（不带 -t）
USE_TOKEN_FLAG=""
if [ -n "$TOKEN" ]; then
  USE_TOKEN_FLAG="-t $TOKEN"
fi

echo "==> 1/4 构建前端 (vite build)"
npm run build

echo "==> 1.5/4 导出已发布文章静态列表 (public/articles-list.json)"
# 部署时把已发布文章烘焙成静态 JSON，CDN 毫秒级返回，绕开 EdgeOne→Supabase 偶发慢链。
# 失败不阻断部署（运行时仍有边缘函数兜底），但打印原因以便发现连接问题。
if /Users/maoshanbo/.workbuddy/binaries/python/envs/default/bin/python scripts/export_articles_list.py 2>&1; then
  echo "已更新 public/articles-list.json"
else
  echo "⚠️ 静态文章列表导出失败，继续部署（运行时仍有边缘函数兜底）"
fi

echo "==> 2/4 拷贝边缘函数 functions/ 到 dist/"
rm -rf dist/functions
cp -r functions dist/functions

echo "==> 3/4 写入 dist/package.json（激活 Pages Functions 必需）"
cat > dist/package.json <<'JSON'
{
  "name": "dachu-pages-functions",
  "version": "1.0.0",
  "private": true
}
JSON

echo "==> 3.5/4 同步数据下载中心 public/downloads/ → dist/downloads/"
# CI 评分流水线的 export_all_tables.py 会把最新 xlsx 写到 public/downloads/，
# 但 EdgeOne 实际部署的是 dist/，必须在此复制，否则下载中心永远停在旧版本（详见 2026-09-02 故障）。
if [ -d public/downloads ]; then
  rm -rf dist/downloads
  cp -r public/downloads dist/downloads
  echo "已同步 $(ls public/downloads | wc -l | tr -d ' ') 个下载文件到 dist/downloads/"
else
  echo "public/downloads/ 不存在，跳过（下载中心沿用既有文件）"
fi

echo "==> 3.6/4 同步文章静态列表 public/articles-list.json → dist/articles-list.json"
# Vite 不会自动 copy 根 public/ 中未被源码 import 的文件，必须手动复制
if [ -f public/articles-list.json ]; then
  cp public/articles-list.json dist/articles-list.json
  echo "已��步 articles-list.json"
else
  echo "public/articles-list.json 不存在，跳过（运行时走边缘函数兜底）"
fi

echo "==> 3.7/4 往 dist/index.html 注入版本探测 inline script（独立于 chunk，确保 reload 拉新 chunk）"
# 关键：把版本探测从 chunk（App.vue 的 onMounted）搬到 index.html 的 inline <script>，
# 这样即使浏览器在跑旧 chunk，**index.html 重新加载时也会先于任何 chunk 执行**，
# 检测到 hash 变化就 window.location.reload() → 浏览器强制拉新 chunk。
# 解决「旧 chunk 没有新版检测逻辑 → 永远不 reload → 永远不换 chunk」的死循环。
# 用同步 XMLHttpRequest（XHR synchronous）让 reload 命令在 chunk 加载前就发出。
/Users/maoshanbo/.workbuddy/binaries/python/versions/3.14.3/bin/python3 - <<'PY'
import re, sys
path = 'dist/index.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()
script = '<script>(function(){try{var K="dachu_app_version",x=new XMLHttpRequest();x.open("GET","/version.json?_="+Date.now(),false);x.send();if(x.status!==200)return;var d=JSON.parse(x.responseText);if(!d||!d.h)return;var s=localStorage.getItem(K);if(s&&s!==d.h){localStorage.setItem(K,d.h);window.location.reload();}else if(!s){localStorage.setItem(K,d.h);}}catch(e){}})();</script>'
# 在 <script type="module" crossorigin src="/assets/index- 之前插入
new_content, n = re.subn(
    r'(<script type="module"[^>]*src="/assets/index-[^"]+\.js")',
    script + r'\1',
    content,
    count=1,
)
if n == 0:
    print('⚠️ 未找到 <script type="module" 插入点，跳过 inline script 注入')
    sys.exit(1)
with open(path, 'w', encoding='utf-8') as f:
    f.write(new_content)
print(f'已注入版本探测 inline script (替换次数={n})')
PY

echo "==> 3.8/4 写入 dist/version.json（SPA 自动检测新版 → reload 拉新 chunk）"
# 提取本次构建主 chunk 的 hash，作为版本标识。从 dist/index.html 读取它真正引用的 chunk
# （而非 ls 第一个，因为 vite 可能生成多个 index-*.js，如 legacy / 动态 import 分片）。
# 浏览器加载 index.html 时（无论 chunk 是否已缓存），inline script 会 fetch 此 json 与
# localStorage 比对，hash 变了就 window.location.reload() 拉新 chunk。
MAIN_CHUNK=$(grep -oE '/assets/index-[a-zA-Z0-9_.-]+\.js' dist/index.html 2>/dev/null | head -1 | sed -E 's|.*/index-([^.]+)\.js$|\1|')
if [ -n "$MAIN_CHUNK" ]; then
  BUILD_TS=$(date +%s)
  printf '{"h":"%s","t":%s}\n' "$MAIN_CHUNK" "$BUILD_TS" > dist/version.json
  echo "已写入 version.json (hash=$MAIN_CHUNK, t=$BUILD_TS)"
else
  echo "⚠️ dist/index.html 中未找到 index-*.js，跳过 version.json"
fi

echo "==> 4/4 部署文件夹 ./dist 到 EdgeOne Pages (overseas)"
# 部署文件夹（而非 zip）更可靠地触发 Functions 构建；functions/ + package.json 同在 dist 根目录
"$NODE_BIN" "$EDGEONE_BIN" pages deploy ./dist -n dachu -a overseas $USE_TOKEN_FLAG

echo "==> 完成。正式访问 https://dachu.me"
