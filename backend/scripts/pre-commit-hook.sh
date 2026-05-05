#!/usr/bin/env bash
# .git/hooks/pre-commit
# Runs the MediRoute 40-case dispatch regression gate before every commit.
# Install:  cp scripts/pre-commit-hook.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
# Skip once (emergency):  git commit --no-verify

set -euo pipefail

BACKEND_DIR="$(git rev-parse --show-toplevel)/backend"

# Only run if dispatch engine or test files changed.
CHANGED=$(git diff --cached --name-only)
ENGINE_TOUCHED=$(echo "$CHANGED" | grep -E "^backend/(app/engine/|tests/)" | wc -l)

if [ "$ENGINE_TOUCHED" -eq 0 ]; then
    exit 0
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Dispatch engine files changed — running regression gate"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd "$BACKEND_DIR"
MODEL_SHA256="a46ae388b1fdc321edd355a3ae431d0eb5cd85f109227563d39c6edd8ee776b7" \
DISABLE_DRIFT_CHECK="1" \
DISABLE_LEARNING_UPDATE="1" \
python tests/test_validation.py

EXIT_CODE=$?
if [ $EXIT_CODE -ne 0 ]; then
    echo ""
    echo "❌ Regression gate failed. Commit blocked."
    echo "   Fix the failing cases or use  git commit --no-verify  to override."
    exit 1
fi

echo "✓ All 40 cases passed — commit allowed."
exit 0
