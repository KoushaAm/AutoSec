# utils/generic_utils.py
from datetime import datetime, timezone
from pathlib import Path
import re
import json
from typing import Any, Dict, List, Union


def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    """
    Generate a UTC-based timestamped filename like:
        <base>_20251112T205501Z.<ext>
    This is safe on Windows and Unix (no spaces or colons).
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"


def save_invalid_json_dump(text: str, reason: str) -> Path:
    """
    Save a debug dump of an invalid / non-JSON LLM output to disk for inspection.

    Creates:
        output/invalid_json_<timestamp>.txt

    The file contains:
      - Reason for failure
      - Timestamp
      - The raw text returned by the model
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    filename = utc_timestamped_filename("invalid_json", "txt")
    debug_path = output_dir / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    debug_lines: List[str] = []
    debug_lines.append("=== INVALID JSON DUMP ===")
    debug_lines.append(f"Timestamp: {timestamp}")
    debug_lines.append(f"Reason: {reason}")
    debug_lines.append("=" * 80)
    debug_lines.append("\n[DUMP TEXT]\n")
    debug_lines.append(text)

    debug_text = "\n".join(debug_lines)
    debug_path.write_text(debug_text, encoding="utf-8")

    print(f"[error] Cannot extract/parse JSON; saved invalid output to {debug_path.resolve()}")
    return debug_path


def extract_json_block(text: str) -> str:
    """
    Extract the first valid top-level JSON object from text.

    Handles cases with:
      - Markdown fenced JSON blocks (```json ... ```)
      - Extra prose before/after the JSON
      - Multiple JSON objects (takes the first well-formed one)

    On failure:
      - Saves the raw text to output/invalid_json_<timestamp>.txt
      - Raises ValueError pointing to the dump file
    """
    text = text.strip()

    # --- Try to capture fenced JSON block first ---
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()

    # --- Fallback: find first {...} balanced pair ---
    start_index = text.find("{")
    if start_index == -1:
        debug_path = save_invalid_json_dump(
            text,
            reason="No '{' character found – cannot locate a JSON object.",
        )
        raise ValueError(
            f"No '{{' found in text – cannot extract JSON. "
            f"Raw output saved to: {debug_path}"
        )

    depth = 0
    in_string = False
    escape_active = False

    for i, ch in enumerate(text[start_index:], start_index):
        if in_string:
            if escape_active:
                escape_active = False
            elif ch == "\\":
                escape_active = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    # Found a complete top-level JSON object
                    return text[start_index : i + 1].strip()

    # If we exit the loop with non-zero depth, braces are unbalanced
    debug_path = save_invalid_json_dump(
        text,
        reason="Unbalanced braces – could not find a full JSON object.",
    )
    raise ValueError(
        f"Unbalanced braces – could not find a full JSON object. "
        f"Raw output saved to: {debug_path}"
    )


def save_output_to_file(filename: str, content: str):
    """
    Save output content to the /output directory.
    - If 'content' is valid JSON, it is pretty-printed.
    - Otherwise, it is saved as-is for debugging.
    """
    output_dir = Path("output")
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    try:
        obj = json.loads(content)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        path.write_text(content, encoding="utf-8")

    print("Wrote", path.resolve())


def _unescape_newlines(s: str) -> str:
    """
    Convert escaped newlines to real newlines if the model returned a JSON-stringified diff.
    Also normalizes CRLF to LF.
    """
    if not isinstance(s, str):
        return ""
    # First, replace literal backslash-n sequences with real newlines.
    s = s.replace("\\r\\n", "\n").replace("\\n", "\n")
    # Normalize any remaining CRLF
    return s.replace("\r\n", "\n")


def prettify_unified_diff(payload: Union[str, Dict[str, Any]]) -> str:
    """
    Accepts:
      - Full multi-patch JSON (str) with {"patches":[...]} and returns all diffs joined.
      - Single-patch JSON (str or dict) with {"unified_diff":"..."} and returns that diff.
      - A raw diff string and returns it (unescapes '\\n' to newlines).

    Returns a human-friendly unified diff string (possibly for multiple patches),
    or a diagnostic message if not found.
    """
    # If it's already a dict, treat it as parsed JSON
    if isinstance(payload, dict):
        obj = payload
    else:
        # payload is a string: either JSON or raw diff
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            # Not JSON: assume it's a raw diff string
            return _unescape_newlines(payload)

    # Handle new multi-patch structure
    if isinstance(obj, dict) and "patches" in obj and isinstance(obj["patches"], list):
        diffs: List[str] = []
        for idx, patch in enumerate(obj["patches"], start=1):
            diff_text = _unescape_newlines(patch.get("unified_diff", "") or "")
            if not diff_text.strip():
                continue
            header = f"### Patch {idx} (id={patch.get('patch_id', '?')})"
            diffs.append(header + "\n" + diff_text)
        return "\n\n".join(diffs) if diffs else "(No unified_diffs found in patches[])"

    # Legacy single-patch JSON object
    if "unified_diff" in obj:
        return _unescape_newlines(obj.get("unified_diff", "") or "")

    return "(No JSON / unified_diff not found)"
