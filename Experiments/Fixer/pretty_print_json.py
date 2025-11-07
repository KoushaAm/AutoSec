import json
from pathlib import Path
from typing import Dict, List, Tuple


def _normalize_newlines(s: str) -> str:
    # Model outputs may double-escape newlines; normalize to real \n
    return (s or "").replace("\\n", "\n")


def get_unified_diffs_map(model_output: str) -> Dict[str, str]:
    """
    Parse JSON string with shape:
      { "metadata": {...}, "patches": [ { "patch_id": "...", "unified_diff": "..." }, ... ] }
    Return a mapping: patch_id -> pretty unified_diff (with real newlines).
    Raises ValueError if structure is not as expected.
    """
    try:
        obj = json.loads(model_output)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON: {e}")

    if not isinstance(obj, dict) or "patches" not in obj or not isinstance(obj["patches"], list):
        raise ValueError("Expected top-level object with key 'patches' (list).")

    out: Dict[str, str] = {}
    for idx, p in enumerate(obj["patches"], start=1):
        if not isinstance(p, dict):
            raise ValueError(f"patches[{idx-1}] is not an object")
        patch_id = str(p.get("patch_id", idx))  # fall back to index if missing
        diff = _normalize_newlines(p.get("unified_diff", ""))
        out[patch_id] = diff
    return out


def prettify_unified_diff(model_output: str) -> str:
    """
    Backward-compatible pretty printer that returns a single string.
    For the new schema with multiple patches, it concatenates diffs with headers.
    """
    try:
        diffs = get_unified_diffs_map(model_output)
    except Exception as e:
        return f"(Error: {e})"

    if not diffs:
        return "(No patches / unified_diffs found)"

    lines: List[str] = []
    for i, (patch_id, diff) in enumerate(diffs.items(), start=1):
        header = f"### Patch {i} (id={patch_id}) ###"
        lines.append(header)
        lines.append(diff if diff else "(empty unified_diff)")
        if i != len(diffs):
            lines.append("")  # blank line between patches
    return "\n".join(lines)


def prettify_output_dir_unified_diffs(directory: str) -> Dict[str, str]:
    """
    Read all JSON files in `directory` matching '*.json', pass their raw
    contents to `prettify_unified_diff`, and return a mapping of filename -> pretty output.
    The function does not create or modify files; it only reads them.
    Files that cannot be read are skipped with an error message in the returned value.
    """
    out: Dict[str, str] = {}
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return {"error": f"Directory not found: {directory}"}

    for fp in sorted(p.glob("*.json")):
        try:
            text = fp.read_text(encoding="utf-8")
            pretty = prettify_unified_diff(text)
        except Exception as e:
            pretty = f"(Error processing file: {e})"
        out[fp.name] = pretty

    return out


def main():
    # Default behavior when run as a script: read all JSON files under output/ and
    # print their prettified unified diffs (with headers per patch).
    results = prettify_output_dir_unified_diffs("output")
    for fname, pretty in results.items():
        print("======", fname, "======")
        print(pretty)
        print()


if __name__ == "__main__":
    main()
