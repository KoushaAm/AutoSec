# Patcher/utils/generic_utils.py
import re
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# local imports
from ..config import OUTPUT_PATH


def utc_timestamped_filename(base: str, ext: str = "json") -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{base}_{ts}.{ext}"


def _build_invalid_json_filename(run_timestamp: str, stage: str, task_id: Optional[int]) -> str:
    safe_stage = re.sub(r"[^a-zA-Z0-9_-]+", "_", stage).strip("_") or "unknown"
    if task_id is not None:
        return f"invalid_json_{run_timestamp}__{safe_stage}__task_{task_id:03d}.txt"
    return f"invalid_json_{run_timestamp}__{safe_stage}.txt"


def save_invalid_json_dump(
    text: str,
    reason: str,
    *,
    run_dir: Optional[Path],
    run_timestamp: Optional[str],
    stage: str,
    task_id: Optional[int],
    logger: logging.Logger,
) -> Path:
    """
    Save invalid JSON output and log the location.
    """

    if run_dir is None or run_timestamp is None:
        raise ValueError("run_dir and run_timestamp must be provided when saving invalid JSON.")

    run_dir.mkdir(parents=True, exist_ok=True)
    filename = _build_invalid_json_filename(run_timestamp, stage, task_id)
    debug_path = run_dir / filename

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    debug_lines: List[str] = [
        "=== INVALID JSON DUMP ===",
        f"Timestamp: {timestamp}",
        f"Reason: {reason}",
        "=" * 80,
        "\n[DUMP TEXT]\n",
        text,
    ]

    debug_path.write_text("\n".join(debug_lines), encoding="utf-8")

    logger.error(f"Invalid JSON saved to {debug_path.resolve()}")
    return debug_path


def extract_json_block(
    text: str,
    *,
    run_dir: Path,
    run_timestamp: str,
    stage: str = "extract_json_block",
    task_id: Optional[int],
    logger: logging.Logger,
) -> str:
    """
    Extract first valid top-level JSON object.
    """

    text = text.strip()

    # --- Try fenced JSON
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if fence_match:
        return fence_match.group(1).strip()

    # --- Fallback balanced brace extraction
    start_index = text.find("{")
    if start_index == -1:
        debug_path = save_invalid_json_dump(
            text=text,
            reason="No '{' found - cannot locate JSON object.",
            run_dir=run_dir,
            run_timestamp=run_timestamp,
            stage=stage,
            task_id=task_id,
            logger=logger,
        )
        raise ValueError(f"No '{{' found in text. Saved to: {debug_path}")

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
        text=text,
        reason="Unbalanced braces - JSON not complete.",
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        stage=stage,
        task_id=task_id,
        logger=logger,
    )

    raise ValueError(f"Unbalanced braces. Saved to: {debug_path}")


def save_output_to_file(filename: str, content: str, *, logger: logging.Logger) -> None:
    output_dir = Path(OUTPUT_PATH)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / filename

    try:
        obj = json.loads(content)
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except json.JSONDecodeError:
        path.write_text(content, encoding="utf-8")

    logger.info(f"Wrote file: {path.resolve()}")


def prettify_unified_diff(payload: Union[str, Dict[str, Any]]) -> str:
    if isinstance(payload, dict):
        obj = payload
    else:
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            return _unescape_newlines(payload)

    if "patches" in obj and isinstance(obj["patches"], list):
        diffs: List[str] = []
        for idx, patch in enumerate(obj["patches"], start=1):
            diff_text = _unescape_newlines(patch.get("unified_diff", "") or "")
            if not diff_text.strip():
                continue
            header = f"### Patch {idx} (id={patch.get('patch_id', '?')})"
            diffs.append(header + "\n" + diff_text)
        return "\n\n".join(diffs) if diffs else "(No unified_diffs found in patches[])"

    if "unified_diff" in obj:
        return _unescape_newlines(obj.get("unified_diff", "") or "")

    return "(No JSON / unified_diff not found)"


def write_manifest(path: Path, manifest: Dict[str, Any], *, logger: logging.Logger) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(f"Wrote manifest: {path.resolve()}")
    return path


def write_patch_artifact(path: Path, artifact: Dict[str, Any], *, logger: logging.Logger) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info(f"Wrote patch artifact: {path.resolve()}")
    return path


def _unescape_newlines(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s = s.replace("\\r\\n", "\n").replace("\\n", "\n")
    return s.replace("\r\n", "\n")