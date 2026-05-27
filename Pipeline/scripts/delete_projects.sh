#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<EOF
Make it executable:
  chmod +x scripts/delete_projects.sh

Usage:
  $0 <directory> [name_to_keep...]
  $0 <directory1> <directory2> --keep <name_to_keep1> <name_to_keep2>

Examples:
  $0 /workspaces/autosec/Projects/Sources whitesource__curekit_CVE-2022-23082_1.1.3

  $0 /workspaces/autosec/Projects/Sources /workspaces/autosec/Projects/Zipped --keep project_a project_b.zip

Notes:
  - Deletes only immediate items inside the given directory/directories.
  - Deletes both folders and files.
  - Names after --keep are preserved by basename.
  - Example: --keep project_a project_a.zip keeps any immediate item with either name.
EOF
}

if [[ $# -lt 1 ]]; then
    usage
    exit 1
fi

dirs=()
keep_names=()
mode="dirs"
saw_keep_flag=false

for arg in "$@"; do
    if [[ "$arg" == "--keep" ]]; then
        mode="keep"
        saw_keep_flag=true
        continue
    fi

    if [[ "$mode" == "dirs" ]]; then
        dirs+=("$arg")
    else
        keep_names+=("$arg")
    fi
done

# Backward-compatible behavior:
# If exactly two args are provided and --keep was not used,
# treat arg1 as directory and arg2 as the item name to keep.
#
# Example:
#   ./scripts/delete_projects.sh /workspaces/autosec/Projects/Sources project_a
if [[ "$saw_keep_flag" == false && ${#dirs[@]} -eq 2 ]]; then
    first_dir="${dirs[0]}"
    possible_keep="${dirs[1]}"

    if [[ -d "$first_dir" ]]; then
        dirs=("$first_dir")
        keep_names=("$possible_keep")
    fi
fi

if [[ ${#dirs[@]} -eq 0 ]]; then
    echo "[error] No directories provided."
    usage
    exit 1
fi

should_keep() {
    local item_name="$1"

    for keep in "${keep_names[@]}"; do
        if [[ "$item_name" == "$keep" ]]; then
            return 0
        fi
    done

    return 1
}

for dir in "${dirs[@]}"; do
    if [[ ! -d "$dir" ]]; then
        echo "[error] Directory does not exist: $dir"
        exit 1
    fi

    echo "Scanning directory: $dir"

    while IFS= read -r -d '' item; do
        item_name="$(basename "$item")"

        if should_keep "$item_name"; then
            echo "[keep]   $item"
        else
            echo "[delete] $item"
            rm -rf -- "$item"
        fi
    done < <(find "$dir" -mindepth 1 -maxdepth 1 -print0)
done

echo "Done."