#!/usr/bin/env bash
# ==============================================================================
# Clean up virtual environments, cache, and build artifacts
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "🧹 Cleaning up project directory..."

# Stop application if running
if [ -f "${ROOT_DIR}/scripts/stop.sh" ]; then
    bash "${ROOT_DIR}/scripts/stop.sh" || true
fi

# Remove virtual environments
rm -rf "${ROOT_DIR}/.venv"
rm -rf "${ROOT_DIR}/.test_venv"
rm -rf "${ROOT_DIR}/venv"

# Remove node modules if present
rm -rf "${ROOT_DIR}/node_modules"

# Remove Python cache directories
find "${ROOT_DIR}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyc" -delete 2>/dev/null || true
find "${ROOT_DIR}" -type f -name "*.pyo" -delete 2>/dev/null || true
find "${ROOT_DIR}" -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true

# Remove temporary pid and lock files
rm -f "${ROOT_DIR}/.app.pid"

echo "✅ Project cleanup complete."
