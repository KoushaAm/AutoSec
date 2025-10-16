import json
from datetime import datetime, timezone
from pathlib import Path


def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"

def strip_code_fence(text: str) -> str:
    """
    Remove a leading/trailing triple-backtick fence, optionally with a language tag.
    If no fence present, returns the text unchanged.
    """
    text = text.strip()
    if text.startswith("```"):
        # remove leading fence line
        # find the first newline after the opening fence
        idx = text.find("\n")
        if idx != -1:
            # drop the opening fence line
            text = text[idx+1:]
        # remove trailing fence (```), if present
        if text.endswith("```"):
            text = text[: -3].rstrip()
    return text

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