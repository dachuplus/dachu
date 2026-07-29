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

echo "==> 4/4 部署文件夹 ./dist 到 EdgeOne Pages (overseas)"
# 部署文件夹（而非 zip）更可靠地触发 Functions 构建；functions/ + package.json 同在 dist 根目录
"$NODE_BIN" "$EDGEONE_BIN" pages deploy ./dist -n dachu -a overseas $USE_TOKEN_FLAG

echo "==> 完成。正式访问 https://dachu.me"
