#!/usr/bin/env bash
# ==============================================================================
# Start Dokimi Agent A/B Testing Platform in Detached Mode
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PID_FILE="${ROOT_DIR}/.app.pid"
LOG_FILE="${ROOT_DIR}/output/app.log"
PORT=8000
HOST="127.0.0.1"

# Ensure output directory exists for logs and results
mkdir -p "${ROOT_DIR}/output"
mkdir -p "${ROOT_DIR}/input"
mkdir -p "${ROOT_DIR}/data"

# Export PYTHONPATH so app modules resolve cleanly
export PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}"

# Check if application is already running
if [ -f "${PID_FILE}" ]; then
    PID=$(cat "${PID_FILE}")
    if ps -p "${PID}" > /dev/null 2>&1; then
        echo "====================================================================="
        echo "⚠️ Application is already running (PID: ${PID})."
        echo "🌐 Web Dashboard URL:   http://${HOST}:${PORT}"
        echo "📚 API Swagger Docs:    http://${HOST}:${PORT}/docs"
        echo "📖 API Redoc:           http://${HOST}:${PORT}/redoc"
        echo "❤️ Health Check:        http://${HOST}:${PORT}/health"
        echo "🎯 Use-Cases Endpoint:  http://${HOST}:${PORT}/api/use-cases"
        echo "🧬 Variants Endpoint:   http://${HOST}:${PORT}/api/variants"
        echo "📋 Questions Endpoint:  http://${HOST}:${PORT}/api/questions"
        echo "📊 Experiments API:     http://${HOST}:${PORT}/api/experiments"
        echo "📄 Application Logs:    ${LOG_FILE}"
        echo "====================================================================="
        exit 0
    else
        rm -f "${PID_FILE}"
    fi
fi

# Locate python and uv package manager
UV_BIN=""
if command -v uv > /dev/null 2>&1; then
    UV_BIN="uv"
elif [ -f "${HOME}/.local/bin/uv" ]; then
    UV_BIN="${HOME}/.local/bin/uv"
elif [ -f "/usr/local/bin/uv" ]; then
    UV_BIN="/usr/local/bin/uv"
fi

# Set up or verify virtual environment
if [ -f "${ROOT_DIR}/.venv/bin/python" ]; then
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
elif [ -n "${UV_BIN}" ]; then
    echo "Creating virtual environment using uv..."
    "${UV_BIN}" venv "${ROOT_DIR}/.venv"
    "${UV_BIN}" pip install --python "${ROOT_DIR}/.venv/bin/python" -r "${ROOT_DIR}/requirements.txt"
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
else
    echo "Creating virtual environment using python3 venv..."
    python3 -m venv "${ROOT_DIR}/.venv"
    "${ROOT_DIR}/.venv/bin/pip" install -r "${ROOT_DIR}/requirements.txt"
    PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
fi

# Ensure .env file exists
if [ ! -f "${ROOT_DIR}/.env" ] && [ -f "${ROOT_DIR}/.env.example" ]; then
    echo "Creating default .env from .env.example..."
    cp "${ROOT_DIR}/.env.example" "${ROOT_DIR}/.env"
fi

echo "🚀 Starting Dokimi Agent Context A/B Testing Platform in detached mode..."
cd "${ROOT_DIR}"

# Start uvicorn in background using nohup and disown to ensure persistence
nohup "${PYTHON_BIN}" -m uvicorn app.main:app --host "${HOST}" --port "${PORT}" > "${LOG_FILE}" 2>&1 &
APP_PID=$!
echo "${APP_PID}" > "${PID_FILE}"
disown "${APP_PID}" 2>/dev/null || true

# Wait and poll health check endpoint to confirm successful bootstrap
echo "⏳ Verifying application startup..."
MAX_RETRIES=10
RETRY_COUNT=0
IS_HEALTHY=false

while [ "${RETRY_COUNT}" -lt "${MAX_RETRIES}" ]; do
    sleep 1
    if ! ps -p "${APP_PID}" > /dev/null 2>&1; then
        echo "❌ Server process terminated unexpectedly."
        break
    fi
    if curl -s "http://${HOST}:${PORT}/health" > /dev/null 2>&1; then
        IS_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
done

if [ "${IS_HEALTHY}" = true ]; then
    echo "====================================================================="
    echo "✅ Dokimi Agent A/B Testing Platform is LIVE and HEALTHY!"
    echo "📌 Process PID:         ${APP_PID}"
    echo "🌐 Web Dashboard URL:   http://${HOST}:${PORT}"
    echo "📚 API Swagger Docs:    http://${HOST}:${PORT}/docs"
    echo "📖 API Redoc:           http://${HOST}:${PORT}/redoc"
    echo "❤️ Health Check:        http://${HOST}:${PORT}/health"
    echo "🎯 Use-Cases Endpoint:  http://${HOST}:${PORT}/api/use-cases"
    echo "🧬 Variants Endpoint:   http://${HOST}:${PORT}/api/variants"
    echo "📋 Questions Endpoint:  http://${HOST}:${PORT}/api/questions"
    echo "📊 Experiments API:     http://${HOST}:${PORT}/api/experiments"
    echo "📄 Application Logs:    ${LOG_FILE}"
    echo "====================================================================="
else
    echo "❌ Startup validation failed. Application log output:"
    echo "---------------------------------------------------------------------"
    cat "${LOG_FILE}" || true
    echo "---------------------------------------------------------------------"
    exit 1
fi
