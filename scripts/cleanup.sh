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

# Function to forcefully remove a directory tree even with macOS Finder locks / flags / .DS_Store
force_clean_dir() {
    local target="$1"
    if [ -e "${target}" ] || [ -d "${target}" ]; then
        # Unlock files and clear macOS chflags (e.g. uchg, hidden) and extended attributes
        if [ "$(uname)" = "Darwin" ]; then
            chflags -R nouchg,nouappnd "${target}" 2>/dev/null || true
            xattr -rc "${target}" 2>/dev/null || true
            find "${target}" -name ".DS_Store" -delete 2>/dev/null || true
            find "${target}" -depth -type f -exec rm -f {} + 2>/dev/null || true
            find "${target}" -depth -type d -exec rmdir {} + 2>/dev/null || true
        fi
        rm -rf "${target}" 2>/dev/null || true
    fi
}

# Remove virtual environments
force_clean_dir "${ROOT_DIR}/.venv"
force_clean_dir "${ROOT_DIR}/.test_venv"
force_clean_dir "${ROOT_DIR}/venv"

# Remove node modules if present
force_clean_dir "${ROOT_DIR}/node_modules"

# Remove Python cache directories and artifacts
find "${ROOT_DIR}" -type d -name "__pycache__" -prune -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type d -name ".pytest_cache" -prune -exec rm -rf {} + 2>/dev/null || true
find "${ROOT_DIR}" -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.pyd" -o -name ".coverage" \) -exec rm -rf {} + 2>/dev/null || true

# Remove temporary pid and lock files
rm -rf "${ROOT_DIR}/.app.pid" 2>/dev/null || true

echo "✅ Project cleanup complete."
