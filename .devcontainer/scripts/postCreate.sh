#!/usr/bin/env bash
set -euo pipefail

echo "🔧 Running AutoSec devcontainer postCreate..."

bash .devcontainer/scripts/bootstrapFinder.sh
bash .devcontainer/scripts/setupVenv.sh

echo "✅ Devcontainer setup complete."
