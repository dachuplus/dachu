#!/bin/bash
# allfund 一体化部署：构建 → EdgeOne 部署 → GitHub 推送（通过 REST API 绕过 git 协议）
# 用法: bash deploy_and_push.sh "commit message"
# 环境变量: EDGEONE_TOKEN, GITHUB_TOKEN
set -e

NODE=/Users/maoshanbo/.workbuddy/binaries/node/versions/22.12.0/bin/node
NPX=/Users/maoshanbo/.workbuddy/binaries/node/versions/22.12.0/bin/npx
PYTHON=/Users/maoshanbo/.workbuddy/binaries/python/versions/3.13.12/bin/python3

# 读取 .env.local 中的 token
ENV_FILE="$(cd "$(dirname "$0")/.." && pwd)/.env.local"
if [ -f "$ENV_FILE" ]; then
  export $(grep -E '^(EDGEONE_TOKEN|GITHUB_TOKEN)=' "$ENV_FILE" | xargs)
fi

# 检查环境变量
if [ -z "$EDGEONE_TOKEN" ]; then
  echo "❌ 未找到 EDGEONE_TOKEN（请在 .env.local 中设置）"
  exit 1
fi
if [ -z "$GITHUB_TOKEN" ]; then
  echo "❌ 未找到 GITHUB_TOKEN（请在 .env.local 中设置）"
  exit 1
fi

CD "$(cd "$(dirname "$0")/.." && pwd)"

MSG="${1:-chore: auto deploy $(date '+%Y-%m-%d %H:%M')}"

echo "=== 0/3 Committing local changes ==="
git add -A
git diff --cached --quiet || git commit -m "$MSG"
echo "  ✓ 本地 commit 完成"

echo "=== 1/3 Building ==="
$NODE node_modules/.bin/vite build 2>&1 | tail -5

echo "=== 2/3 Deploying to EdgeOne ==="
cd dist && rm -f ../dist.zip && zip -qr ../dist.zip . && cd ..
$NPX edgeone pages deploy dist.zip -n allfund -t "$EDGEONE_TOKEN" 2>&1

echo "=== 3/3 Pushing to GitHub (via REST API) ==="
GITHUB_TOKEN="$GITHUB_TOKEN" $PYTHON scripts/allfund_push_via_api.py "$MSG"

echo "=== Done ==="
