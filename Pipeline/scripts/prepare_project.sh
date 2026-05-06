#!/usr/bin/env bash
set -euo pipefail

# Usage:
# 1. make it executable: chmod +x Pipeline/scripts/prepare_project.sh
# 2. run: ./Pipeline/scripts/prepare_project.sh <project_name>
#
# Example:
#  ./Pipeline/scripts/prepare_project.sh xwiki__xwiki-rendering_CVE-2023-32070_14.6

if [ "$#" -ne 1 ]; then
  echo "Usage: $0 <project_name>"
  exit 1
fi

PROJECT_NAME="$1"

# All paths are relative to devcontainer root
ROOT_DIR="/workspaces/autosec"
FINDER_DIR="$ROOT_DIR/Agents/Finder"
FINDER_PROJECT_SOURCES="$FINDER_DIR/data/project-sources"
PROJECTS_SOURCES="$ROOT_DIR/Projects/Sources"
PROJECTS_ZIPPED="$ROOT_DIR/Projects/Zipped"

echo "=============== Fetch Project ==============="
cd "$FINDER_DIR"
python scripts/fetch_one.py "$PROJECT_NAME"

echo
echo "=============== Move Project to Sources ==============="
mkdir -p "$PROJECTS_SOURCES"

if [ ! -d "$FINDER_PROJECT_SOURCES/$PROJECT_NAME" ]; then
    echo "Error: fetched project not found at:"
    echo "$FINDER_PROJECT_SOURCES/$PROJECT_NAME"
    exit 1
fi

if [ -d "$PROJECTS_SOURCES/$PROJECT_NAME" ]; then
    echo "Error: project already exists in:"
    echo "$PROJECTS_SOURCES/$PROJECT_NAME"
    echo "Remove it first if you want to replace it."
    exit 1
fi

mv "$FINDER_PROJECT_SOURCES/$PROJECT_NAME" "$PROJECTS_SOURCES"

echo
echo "=============== ZIP Project & Move to Zipped ==============="
mkdir -p "$PROJECTS_ZIPPED"

cd "$PROJECTS_SOURCES/$PROJECT_NAME"

ZIP_NAME="$PROJECT_NAME.zip"

if [ -e "$PROJECTS_ZIPPED/$ZIP_NAME" ]; then
    echo "Error: project zip already exists in:"
    echo "$PROJECTS_ZIPPED/$ZIP_NAME"
    echo "Remove it first if you want to replace it."
    exit 1
fi

zip -r "$ZIP_NAME" ./

mv "$ZIP_NAME" "$PROJECTS_ZIPPED"

echo
echo "Done."
echo "Project source moved to:"
echo "$PROJECTS_SOURCES/$PROJECT_NAME"
echo
echo "Project zip moved to:"
echo "$PROJECTS_ZIPPED/$ZIP_NAME"