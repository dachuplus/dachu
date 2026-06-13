#!/bin/bash
# allfund 一体化部署：构建 → EdgeOne 部署 → GitHub 推送
set -e

NODE=/Users/maoshanbo/.workbuddy/binaries/node/versions/22.12.0/bin/node
NPX=/Users/maoshanbo/.workbuddy/binaries/node/versions/22.12.0/bin/npx
TOKEN='Xsv2Fuvl8onurw1TguQ8/bpY3lNtUKiyJ8wqm9QOTaw='

cd /Users/maoshanbo/WorkBuddy/20260405093252/allfund

echo "=== 1/3 Building ==="
$NODE node_modules/.bin/vite build 2>&1 | tail -5

echo "=== 2/3 Deploying to EdgeOne ==="
cd dist && rm -f ../dist.zip && zip -qr ../dist.zip . && cd ..
$NPX edgeone pages deploy dist.zip -n allfund -t "$TOKEN" 2>&1

echo "=== 3/3 Pushing to GitHub ==="
git push origin main 2>&1

echo "=== Done ==="
