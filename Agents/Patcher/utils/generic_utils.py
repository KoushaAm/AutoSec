# Patcher/utils/generic_utils.py
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# local imports
from ..config import OUTPUT_PATH

def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    """
    Generate a UTC-based timestamped filename like:
        <base>_20251112T205501Z.<ext>
    This is safe on Windows and Unix (no spaces or colons).
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"


def _build_invalid_json_filename(run_timestamp: str, stage: str, task_id: Optional[int]) -> str:
    """
    Build a run-scoped invalid JSON filename:
        invalid_json_<run_timestamp>__<stage>__task_<id>.txt
    """
    safe_stage = re.sub(r"[^a-zA-Z0-9_-]+", "_", stage).strip("_") or "unknown"
    if task_id is not None:
        return f"invalid_json_{run_timestamp}__{safe_stage}__task_{task_id:03d}.txt"
    return f"invalid_json_{run_timestamp}__{safe_stage}.txt"


def save_invalid_json_dump(
    text: str,
    reason: str,
    *,
    run_dir: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    stage: str = "parse",
    task_id: Optional[int] = None,
) -> Path:
    """
    Save a debug dump of an invalid / non-JSON LLM output to disk for inspection.

    Creates:
      - <run_dir>/invalid_json_<run_timestamp>__<stage>__task_<id>.txt   (preferred)
      - output/invalid_json_<timestamp>.txt                      (fallback)
    """
    if run_dir is not None and run_timestamp is not None:
        output_dir = Path(run_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _build_invalid_json_filename(run_timestamp, stage, task_id)
        debug_path = output_dir / filename
    else:
        output_dir = Path(OUTPUT_PATH)
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


def extract_json_block(
    text: str,
    *,
    run_dir: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    stage: str = "extract_json_block",
    task_id: Optional[int] = None,
) -> str:
    """
    Extract the first valid top-level JSON object from text.

    Supports:
      - Markdown fenced JSON blocks (```json ... ```)
      - Extra prose before/after JSON
      - Multiple JSON objects → returns first complete one

    If extraction fails, writes an invalid-json dump into the run_dir when provided.
    """
    text = text.strip()

    # --- Try fenced JSON ```
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()

    # --- Fallback: first {...} balanced
    start_index = text.find("{")
    if start_index == -1:
        debug_path = save_invalid_json_dump(
            text,
            reason="No '{' character found - cannot locate a JSON object.",
            run_dir=run_dir,
            run_timestamp=run_timestamp,
            stage=stage,
            task_id=task_id,
        )
        raise ValueError(
            f"No '{{' found in text - cannot extract JSON. Saved to: {debug_path}"
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
                    return text[start_index : i + 1].strip()

    debug_path = save_invalid_json_dump(
        text,
        reason="Unbalanced braces - full JSON object not found.",
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        stage=stage,
        task_id=task_id,
    )
    raise ValueError(
        f"Unbalanced braces - could not extract JSON. Saved to: {debug_path}"
    )


def save_output_to_file(filename: str, content: str):
    """
    Save content to /output directory.
    Pretty-prints JSON if possible.
    """
    output_dir = Path(OUTPUT_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    try:
        obj = json.loads(content)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        path.write_text(content, encoding="utf-8")

    print("Wrote", path.resolve())


def prettify_unified_diff(payload: Union[str, Dict[str, Any]]) -> str:
    """
    Accepts:
      - Multi-patch JSON → prints all diffs
      - Single patch JSON → print unified_diff
      - Raw string → return unescaped

    Returns: unified diff or diagnostic message.
    """
    # Parse JSON if possible
    if isinstance(payload, dict):
        obj = payload
    else:
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            return _unescape_newlines(payload)

    # Multi-patch
    if "patches" in obj and isinstance(obj["patches"], list):
        diffs: List[str] = []
        for idx, patch in enumerate(obj["patches"], start=1):
            diff_text = _unescape_newlines(patch.get("unified_diff", "") or "")
            if not diff_text.strip():
                continue
            header = f"### Patch {idx} (id={patch.get('patch_id', '?')})"
            diffs.append(header + "\n" + diff_text)
        return "\n\n".join(diffs) if diffs else "(No unified_diffs found in patches[])"

    # Legacy single-patch
    if "unified_diff" in obj:
        return _unescape_newlines(obj.get("unified_diff", "") or "")

    return "(No JSON / unified_diff not found)"


def write_manifest(path: Path, manifest: Dict[str, Any]) -> Path:
    """
    Write the manifest JSON to the given absolute path.

    Ensures directory exists:
        output/patcher_<timestamp>/patcher_manifest_<timestamp>.json
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote manifest:", path.resolve())
    return path


def write_patch_artifact(path: Path, artifact: Dict[str, Any]) -> Path:
    """
    Write a single patch artifact JSON to the given absolute path.

    Ensures directory exists:
        output/patcher_<timestamp>/patch_XXX.json
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("Wrote patch artifact:", path.resolve())
    return path


def _unescape_newlines(s: str) -> str:
    """
    Convert escaped newlines to real newlines.
    Normalize CRLF → LF.
    """
    if not isinstance(s, str):
        return ""
    s = s.replace("\\r\\n", "\n").replace("\\n", "\n")
    return s.replace("\r\n", "\n")
