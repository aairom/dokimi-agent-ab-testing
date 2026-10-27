#!/usr/bin/env bash
# ==============================================================================
# Gracefully Shutdown Dokimi Agent A/B Testing Platform
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${ROOT_DIR}/.app.pid"

if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p "${PID}" > /dev/null 2>&1; then
        echo "🛑 Gracefully shutting down application (PID: ${PID})..."
        kill "${PID}" || kill -9 "${PID}" 2>/dev/null || true
        rm -f "${PID_FILE}"
        echo "✅ Application stopped successfully."
    else
        echo "ℹ️ No running process found for PID: ${PID}. Clearing PID file."
        rm -f "${PID_FILE}"
    fi
else
    # Fallback search for any orphan uvicorn app.main:app process
    PID=$(pgrep -f "uvicorn app.main:app" || true)
    if [ -n "${PID}" ]; then
        echo "🛑 Stopping uvicorn process (PID: ${PID})..."
        kill ${PID} 2>/dev/null || true
        echo "✅ Application stopped."
    else
        echo "ℹ️ Application is not running."
    fi
fi
