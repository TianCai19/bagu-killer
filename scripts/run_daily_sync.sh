#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT/artifacts/logs"
mkdir -p "$LOG_DIR"

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
LOG_PATH="$LOG_DIR/daily_sync_${TIMESTAMP}.log"

cd "$ROOT"
if [ -z "${CONDA_DEFAULT_ENV:-}" ] && command -v conda >/dev/null 2>&1; then
  source "$(conda info --base)/etc/profile.d/conda.sh"
  conda activate aicoder >/dev/null 2>&1 || true
fi

RUNTIME_LIB_DIR="$ROOT/.local_runtime/usr/lib/x86_64-linux-gnu"
if [ -d "$RUNTIME_LIB_DIR" ]; then
  export LD_LIBRARY_PATH="$RUNTIME_LIB_DIR:${LD_LIBRARY_PATH:-}"
fi
if [ -f "$RUNTIME_LIB_DIR/libffi.so.7" ]; then
  export LD_PRELOAD="$RUNTIME_LIB_DIR/libffi.so.7"
fi

echo "[daily-sync] started at $(date -Is)" | tee -a "$LOG_PATH"
ai-offer init-db | tee -a "$LOG_PATH"
ai-offer pipeline daily-sync \
  --job-name xhs_daily_sync \
  --date-from 2025-01-20 \
  --max-pages 200 \
  --batch-limit 100 | tee -a "$LOG_PATH"
ai-offer report --format json > "$ROOT/artifacts/reports/report_latest.json"
echo "[daily-sync] finished at $(date -Is)" | tee -a "$LOG_PATH"
