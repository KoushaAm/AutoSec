import json


def prettify_unified_diff(model_output: str) -> str:
    try:
        response = json.loads(model_output)
        diff = response.get("unified_diff") or ""
        return diff.replace("\\n", "\n")
    except json.JSONDecodeError:
        return "(No JSON / unified_diff not found)"

def prettify_output_dir_unified_diffs(directory: str) -> dict:
    """Read all JSON files in `directory` matching '*.json', pass their raw
    contents to `prettify_unified_diff`, and return a mapping of filename -> pretty diff.

    The function does not create or modify files; it only reads them. Files that
    cannot be read are skipped with an error message in the returned value.
    """
    from pathlib import Path

    out = {}
    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return {"error": f"Directory not found: {directory}"}

    for fp in sorted(p.glob("*.json")):
        try:
            text = fp.read_text(encoding="utf-8")
        except Exception as e:
            out[fp.name] = f"(Error reading file: {e})"
            continue

        try:
            pretty = prettify_unified_diff(text)
        except Exception as e:
            pretty = f"(Error processing file: {e})"

        out[fp.name] = pretty

    return out

def main():
    # Default behavior when run as a script: read all JSON files under output/ and
    # print their prettified unified diffs.
    results = prettify_output_dir_unified_diffs("output")
    for fname, pretty in results.items():
        print("===", fname, "===")
        print(pretty)
        print()

# execute main
if __name__ == "__main__":
    main()
