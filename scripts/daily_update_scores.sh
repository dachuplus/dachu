#!/bin/bash
# ============================================================
# 靠谱指数每日自动更新脚本
# 1. 从 Supabase 拉取全量基金数据
# 2. 重新计算 k0w-k5 各周期靠谱分 (收益50%+回撤25%+夏普25%)
# 3. 计算 k_all (v7加权综合分) 和 score_grade
# 4. 更新 fund_scores_meta
# 5. 写日志到 logs/ 目录
# ============================================================
set -e

PROJECT_DIR="/Users/maoshanbo/WorkBuddy/20260405093252/allfund"
cd "$PROJECT_DIR"

# 创建日志目录
mkdir -p logs

LOG_FILE="logs/daily_update_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "========================================"
echo "靠谱指数 Supabase 每日更新"
echo "开始时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

# 加载环境变量
if [ -f .env.local ]; then
  export SUPABASE_MGMT_TOKEN=$(grep SUPABASE_PAT .env.local | cut -d'=' -f2)
  echo "SUPABASE_MGMT_TOKEN: ${SUPABASE_MGMT_TOKEN:0:10}..."
else
  echo "ERROR: .env.local not found"
  exit 1
fi

# Python 环境
PYTHON=/Users/maoshanbo/.workbuddy/binaries/python/envs/default/bin/python
if [ ! -f "$PYTHON" ]; then
  echo "Python venv not found, creating..."
  /Users/maoshanbo/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m venv /Users/maoshanbo/.workbuddy/binaries/python/envs/default
  /Users/maoshanbo/.workbuddy/binaries/python/envs/default/bin/pip install requests -q
fi

# ============================================================
echo ""
echo "[Step 1/2] 重新计算各周期靠谱分 (k0w-k5)..."
echo "========================================"

$PYTHON scripts/recalc_all_scores.py

echo ""
echo "[Step 2/2] 计算 k_all 综合分 + score_grade..."
echo "========================================"

$PYTHON scripts/compute_k_all.py

echo ""
echo "========================================"
echo "更新完成: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"
