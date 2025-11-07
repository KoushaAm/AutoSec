from datetime import datetime, timezone
from pathlib import Path
import re
import json
from typing import Any, Dict, List, Union

def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"

def extract_json_block(text: str) -> str:
    """
    Extract the first valid top-level JSON object from text.
    Handles cases with markdown fences, multiple JSON blocks, or extra prose.
    """
    text = text.strip()

    # --- Try to capture fenced JSON block first ---
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()

    # --- Fallback: find first {...} balanced pair ---
    start = text.find("{")
    if start == -1:
        raise ValueError("No '{' found in text — cannot extract JSON.")

    depth = 0
    in_str = False
    esc = False
    for i, ch in enumerate(text[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        else:
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start:i+1].strip()

    raise ValueError("Unbalanced braces — could not find a full JSON object.")

def save_output_to_file(filename: str, content: str):
    Path("output").mkdir(parents=True, exist_ok=True)  # ensure output dir exists
    p = Path("output") / filename
    # Try to pretty-validate JSON; if it fails, save raw for debugging
    try:
        obj = json.loads(content)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        p.write_text(content, encoding="utf-8")
    print("Wrote", p)

def _unescape_newlines(s: str) -> str:
    """
    Convert escaped newlines to real newlines if the model returned a JSON-stringified diff.
    Also normalizes CRLF to LF.
    """
    if not isinstance(s, str):
        return ""
    # First, replace literal backslash-n with real newline.
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
        outs: List[str] = []
        for idx, p in enumerate(obj["patches"], start=1):
            diff = _unescape_newlines(p.get("unified_diff", "") or "")
            if not diff.strip():
                continue
            header = f"### Patch {idx} (id={p.get('patch_id', '?')})"
            outs.append(header + "\n" + diff)
        return "\n\n".join(outs) if outs else "(No unified_diffs found in patches[])"

    # Legacy single-patch JSON object
    if "unified_diff" in obj:
        return _unescape_newlines(obj.get("unified_diff", "") or "")

    return "(No JSON / unified_diff not found)"
