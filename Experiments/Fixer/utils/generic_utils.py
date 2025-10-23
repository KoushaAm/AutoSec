from datetime import datetime, timezone
from pathlib import Path
import re
import json

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
    Path("output").mkdir(parents=True, exist_ok=True) # ensure output dir exists

    p = Path("output") / filename
    # Try to pretty-validate JSON; if it fails, save raw for debugging
    try: 
        obj = json.loads(content)
        p.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        p.write_text(content, encoding="utf-8")
    print("Wrote", p)

def prettify_unified_diff(model_output: str) -> str:
    try:
        response = json.loads(model_output)
        diff = response.get("unified_diff") or ""
        return diff.replace("\\n", "\n")
    except json.JSONDecodeError:
        return "(No JSON / unified_diff not found)"