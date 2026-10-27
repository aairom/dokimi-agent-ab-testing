#!/usr/bin/env bash
# ==============================================================================
# Remove locally built / pulled container images
# ==============================================================================

set -euo pipefail

IMAGE_NAME="dokimi-agent-ab-testing"

echo "🗑️ Removing local container images for ${IMAGE_NAME}..."

if command -v podman > /dev/null 2>&1; then
    podman rmi -f "${IMAGE_NAME}:latest" 2>/dev/null || true
    echo "✅ Podman images cleaned."
elif command -v docker > /dev/null 2>&1; then
    docker rmi -f "${IMAGE_NAME}:latest" 2>/dev/null || true
    echo "✅ Docker images cleaned."
else
    echo "ℹ️ Neither Podman nor Docker found on system."
fi
