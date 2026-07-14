#!/usr/bin/env bash
# run_etl_step.sh — 包装单个 ETL 步骤，记录运行日志到 public.etl_run_log 表。
#
# 用法:
#   bash scripts/run_etl_step.sh "<step_name>" "<command>"
#
# 行为:
#   1. 写入 running 状态，拿到日志行 id
#   2. 执行 <command>（实时输出到控制台，同时缓存用于提取行数）
#   3. 成功 -> success；失败 -> failed（附带末尾错误信息）
#   4. 若命令 stdout/stderr 中出现 "ROWS_AFFECTED=<n>" 则记录影响行数
set -uo pipefail

STEP="$1"
CMD="$2"

if [ -z "$STEP" ] || [ -z "$CMD" ]; then
  echo "用法: run_etl_step.sh <step_name> <command>" >&2
  exit 2
fi

# 定位仓库根目录（scripts/ 的上一级）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

PY="$(command -v python || command -v python3)"

# 1. 标记 running，捕获日志行 id
RUN_ID="$("$PY" scripts/log_etl_step.py --step "$STEP" --mark running 2>/dev/null)" || RUN_ID=""

# 2. 执行命令（实时输出 + 缓存到临时文件）
TMP="$(mktemp)"
eval "$CMD" 2>&1 | tee "$TMP"
RC=${PIPESTATUS[0]}
OUT="$(cat "$TMP")"

# 3. 提取影响行数（步骤可打印 ROWS_AFFECTED=<n> 上报准确行数）
ROWS="$(grep -oE 'ROWS_AFFECTED=[0-9]+' "$TMP" | tail -1 | cut -d= -f2)"
rm -f "$TMP"

# 4. 更新结果
if [ "$RC" -eq 0 ]; then
  "$PY" scripts/log_etl_step.py --step "$STEP" --mark success --id "$RUN_ID" ${ROWS:+--rows "$ROWS"} 2>/dev/null || true
else
  ERR="$(echo "$OUT" | tail -3 | tr '\n' ' ' | cut -c1-300)"
  "$PY" scripts/log_etl_step.py --step "$STEP" --mark failed --id "$RUN_ID" --error "$ERR" 2>/dev/null || true
fi

exit "$RC"
