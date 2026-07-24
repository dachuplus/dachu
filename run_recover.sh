#!/bin/bash
# allfund fund_manager recovery + redeploy runner
set -u
DIR=$HOME/WorkBuddy/20260405093252/dachu
PY=$HOME/.workbuddy/binaries/python/envs/default/bin/python
NPX=$HOME/.workbuddy/binaries/node/versions/22.12.0/bin/npx
# 密钥从 gitignored 的 .env.local 读取，禁止硬编码（避免被 GitHub push protection 拦截 & 泄露）
if [ -f "$DIR/.env.local" ]; then
  MGMT=$(grep -E '^SUPABASE_PAT=' "$DIR/.env.local" | head -1 | cut -d= -f2)
  ANON=$(grep -E '^VITE_SUPABASE_ANON_KEY=' "$DIR/.env.local" | head -1 | cut -d= -f2)
  GH=$(grep -E '^GITHUB_TOKEN=' "$DIR/.env.local" | head -1 | cut -d= -f2)
else
  echo "⚠️ 未找到 $DIR/.env.local，无法读取密钥" >&2
  exit 1
fi
LOG=$DIR/recover.log
SUMMARY=$DIR/recover_summary.txt
: > "$SUMMARY"

# tee all output to log + capture
exec > >(tee -a "$LOG") 2>&1

log(){ echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }
echo "=== RECOVER START $(date) ==="

# ---- STEP 1: push script fixes ----
log "=== STEP1 push fixes ==="
cd "$DIR"
COMMIT1=$(GITHUB_TOKEN=$GH $PY scripts/allfund_push_via_api.py "fix: robust fund_manager pipeline (snapshot-restore before TRUNCATE + incremental fetch + jbgk priority + fund_combined col)" 2>&1 | tee /tmp/step1.txt | grep -oE "新 commit: [a-f0-9]{8}" | head -1 | awk '{print $3}')
echo "STEP1_COMMIT=$COMMIT1" >> "$SUMMARY"

# ---- STEP 2: compile ----
log "=== STEP2 compile ==="
if $PY -m py_compile scripts/repopulate_managers.py; then
  echo "STEP2=COMPILE_OK" >> "$SUMMARY"
  log "COMPILE_OK"
else
  echo "STEP2=COMPILE_FAIL" >> "$SUMMARY"
  log "COMPILE_FAIL"
fi

# ---- STEP 3: backfill (long, resumable) ----
log "=== STEP3 backfill ==="
BACKFILL_DONE=0
for i in 1 2 3 4 5 6; do
  log "--- repopulate attempt $i ---"
  SUPABASE_MGMT_TOKEN=$MGMT PYTHONPATH=scripts $PY scripts/repopulate_managers.py 2>&1 | tee -a "$LOG"
  if grep -q "基金经理回填完成" "$LOG"; then
    BACKFILL_DONE=1
    log "BACKFILL_DONE on attempt $i"
    break
  fi
  log "attempt $i did not finish; resuming"
done
echo "STEP3_BACKFILL_DONE=$BACKFILL_DONE" >> "$SUMMARY"

# ---- STEP 4: sync fund_combined ----
log "=== STEP4 sync fund_combined ==="
if SUPABASE_MGMT_TOKEN=$MGMT $PY scripts/sync_fund_combined_scores.py 2>&1 | tee -a "$LOG"; then
  echo "STEP4=OK" >> "$SUMMARY"
else
  echo "STEP4=FAIL" >> "$SUMMARY"
fi

# ---- STEP 5: counts ----
log "=== STEP5 counts ==="
echo "--- fund_scores non-null managers ---"
FS=$(curl -s -D - -o /dev/null "https://tqhtegazxykkqfcpejky.supabase.co/rest/v1/fund_scores?select=c&fund_manager=not.is.null" -H "apikey: $ANON" -H "Prefer: count=exact" | grep -i content-range | tr -d '\r')
log "fund_scores content-range: $FS"
echo "STEP5_FUND_SCORES=$FS" >> "$SUMMARY"
echo "--- fund_combined non-null managers ---"
FC=$(curl -s -D - -o /dev/null "https://tqhtegazxykkqfcpejky.supabase.co/rest/v1/fund_combined?select=c&fund_manager=not.is.null" -H "apikey: $ANON" -H "Prefer: count=exact" | grep -i content-range | tr -d '\r')
log "fund_combined content-range: $FC"
echo "STEP5_FUND_COMBINED=$FC" >> "$SUMMARY"
echo "--- 020039 ---"
R39=$(curl -s "https://tqhtegazxykkqfcpejky.supabase.co/rest/v1/fund_combined?c=eq.020039&select=c,fund_manager" -H "apikey: $ANON")
log "020039: $R39"
echo "STEP5_020039=$R39" >> "$SUMMARY"

# ---- STEP 6: export xlsx ----
log "=== STEP6 export ==="
$PY -m pip install openpyxl >/dev/null 2>&1 || true
BEFORE=$(ls -la public/downloads/fund_scores.xlsx public/downloads/fund_combined.xlsx 2>/dev/null | awk '{print $5, $9}')
if $PY scripts/export_all_tables.py 2>&1 | tee -a "$LOG"; then
  AFTER=$(ls -la public/downloads/fund_scores.xlsx public/downloads/fund_combined.xlsx 2>/dev/null | awk '{print $5, $9}')
  echo "STEP6=OK" >> "$SUMMARY"
  log "export OK"
  log "before: $BEFORE"
  log "after:  $AFTER"
  echo "STEP6_BEFORE=$BEFORE" >> "$SUMMARY"
  echo "STEP6_AFTER=$AFTER" >> "$SUMMARY"
else
  echo "STEP6=FAIL" >> "$SUMMARY"
  log "export FAIL"
fi

# ---- STEP 7: vite build ----
log "=== STEP7 build ==="
if $NPX vite build 2>&1 | tee -a "$LOG"; then
  echo "STEP7=BUILT" >> "$SUMMARY"
  log "BUILD OK"
else
  echo "STEP7=FAIL" >> "$SUMMARY"
  log "BUILD FAIL"
fi

# ---- STEP 8: deploy EdgeOne ----
log "=== STEP8 deploy ==="
rm -f dist.zip && cd dist && zip -r ../dist.zip . >/dev/null 2>&1 && cd ..
TOKEN=$(grep -E "EDGEONE_PAGES_TOKEN|EDGEONE_PAGES_API_TOKEN" .env.local | head -1 | cut -d= -f2)
DEPLOY_OUT=$($NPX edgeone pages deploy dist.zip -n dachu -t "$TOKEN" 2>&1 | tee -a "$LOG" | grep -iE "https?://|preview|deploy|success|error" | head -5)
echo "STEP8_DEPLOY=$DEPLOY_OUT" >> "$SUMMARY"
log "DEPLOY: $DEPLOY_OUT"

# ---- STEP 9: final push ----
log "=== STEP9 final push ==="
COMMIT2=$(cd "$DIR" && GITHUB_TOKEN=$GH $PY scripts/allfund_push_via_api.py "chore: regenerate downloads after manager backfill" 2>&1 | tee /tmp/step9.txt | grep -oE "新 commit: [a-f0-9]{8}" | head -1 | awk '{print $3}')
echo "STEP9_COMMIT=$COMMIT2" >> "$SUMMARY"

echo "=== RECOVER END $(date) ==="
log "DONE. Summary file: $SUMMARY"
cat "$SUMMARY"
