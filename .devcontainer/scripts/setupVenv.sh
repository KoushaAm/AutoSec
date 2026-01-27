#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/workspaces/autosec"
cd "${WORKSPACE}"

if [[ ! -d ".venv" ]]; then
  echo "🐍 Creating project venv at ${WORKSPACE}/.venv"
  python3 -m venv .venv
else
  echo "🐍 Project venv already exists."
fi

# Activate
# shellcheck disable=SC1091
source .venv/bin/activate

echo "⬆️  Upgrading pip tooling..."
python -m pip install --upgrade pip setuptools wheel

if [[ -f "requirements.txt" ]]; then
  echo "📦 Installing requirements.txt..."
  pip install -r requirements.txt
else
  echo "⚠️  requirements.txt not found; skipping pip install."
fi

echo "✅ venv ready."
