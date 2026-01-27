#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/workspaces/autosec"

echo "🔗 Finder bootstrap: linking /iris -> ${WORKSPACE}"
sudo mkdir -p /iris
sudo ln -sfn "${WORKSPACE}" /iris

# CodeQL: prefer the CLI directory if present, otherwise fallback to /opt/codeql
# (image sets CODEQL_DIR=/opt/codeql and unzips there)
if [[ -x "/opt/codeql/codeql/codeql" ]]; then
  echo "🔗 Finder bootstrap: linking /iris/codeql -> /opt/codeql/codeql"
  sudo ln -sfn /opt/codeql/codeql /iris/codeql
elif [[ -d "/opt/codeql" ]]; then
  echo "🔗 Finder bootstrap: linking /iris/codeql -> /opt/codeql"
  sudo ln -sfn /opt/codeql /iris/codeql
else
  echo "⚠️  CodeQL not found at /opt/codeql; Finder may fail."
fi

# Conda env (optional)
if [[ -f "${WORKSPACE}/environment.yml" ]]; then
  echo "🐍 Finder bootstrap: environment.yml found, creating conda env..."

  # shellcheck disable=SC1091
  source /opt/conda/etc/profile.d/conda.sh

  # Extract env name from first line: "name: iris"
  ENV_NAME="$(head -1 "${WORKSPACE}/environment.yml" | awk '{print $2}')"

  conda env remove -n "${ENV_NAME}" -y >/dev/null 2>&1 || true
  conda env create -f "${WORKSPACE}/environment.yml"

  # Convenience auto-activate (optional; comment out if it annoys you)
  grep -q "conda activate ${ENV_NAME}" ~/.bashrc || echo "conda activate ${ENV_NAME}" >> ~/.bashrc
  grep -q "conda activate ${ENV_NAME}" ~/.zshrc  || echo "conda activate ${ENV_NAME}" >> ~/.zshrc

  echo "✅ Conda env '${ENV_NAME}' created."
else
  echo "ℹ️  No environment.yml at repo root; skipping conda env setup."
fi
