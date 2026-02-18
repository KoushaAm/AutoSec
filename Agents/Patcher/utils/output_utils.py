# Patcher/utils/output_utils.py
import sys
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from ..config import TOOL_VERSION
from .generic_utils import (
    save_invalid_json_dump,
    extract_json_block,
    write_patch_artifact,
    write_manifest,
    prettify_unified_diff,
)


# ================== Diff normalization ==================
def _normalize_unified_diff(patch: Dict[str, Any]) -> str:
    """
    Prefer unified_diff_lines (new schema) and join into a single string.
    Backward compatible with legacy unified_diff (string).
    """
    if "unified_diff_lines" in patch:
        lines = patch.get("unified_diff_lines")
        if lines is None:
            return ""
        if not isinstance(lines, list) or any(not isinstance(x, str) for x in lines):
            raise ValueError("unified_diff_lines must be a list of strings")
        return "\n".join(lines)

    # Legacy fallback
    diff = patch.get("unified_diff", "")
    if not isinstance(diff, str):
        raise ValueError("unified_diff must be a string")
    return diff


# ================== Validation (strict schema) ==================
def _validate_single_patch_schema(patch: Dict[str, Any]) -> None:
    """
    Enforce the strict patch schema expected from the Patcher LLM output.
    """
    required_keys = [
        "patch_id",
        "plan",
        "cwe_matches",
        # unified_diff_lines (preferred) OR unified_diff (legacy) validated separately
        "safety_verification",
        "risk_notes",
        "touched_files",
        "assumptions",
        "behavior_change",
        "confidence",
    ]
    for key in required_keys:
        if key not in patch:
            raise ValueError(f"Missing required key in patch: {key}")

    if not isinstance(patch["patch_id"], int):
        raise ValueError(f"patch_id must be an integer, got {patch['patch_id']!r}")

    if not isinstance(patch["plan"], list):
        raise ValueError("plan must be a list")

    if not isinstance(patch["touched_files"], list):
        raise ValueError("touched_files must be a list")
    if any(not isinstance(x, str) for x in patch["touched_files"]):
        raise ValueError("touched_files must be a list of strings")

    if not isinstance(patch["cwe_matches"], list) or len(patch["cwe_matches"]) == 0:
        raise ValueError("cwe_matches must be a non-empty list")

    # Require at least one diff field to exist and be well-formed
    if "unified_diff_lines" not in patch and "unified_diff" not in patch:
        raise ValueError("Patch must include unified_diff_lines (preferred) or unified_diff (legacy)")

    # Validate/normalize diff content
    _ = _normalize_unified_diff(patch)

    # Confidence must be a realistic integer score
    conf = patch.get("confidence")
    if not isinstance(conf, int):
        raise ValueError(f"confidence must be an integer, got {conf!r}")
    if conf < 0 or conf > 100:
        raise ValueError(f"confidence must be in [0, 100], got {conf}")


def _parse_and_validate_single(
    llm_output: str,
    model_name: str,
    *,
    run_dir: Path,
    run_timestamp: str,
    task_id: int,
) -> Dict[str, Any]:
    """
    Extract JSON, parse it, then validate that it contains exactly one patch.
    Returns the single patch object (not the full top-level JSON).

    Invalid JSON dumps are written inside the patcher run artifact folder.
    """
    json_text = extract_json_block(
        llm_output,
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        stage="extract_json_block",
        task_id=task_id,
    )

    try:
        obj = json.loads(json_text)
    except json.JSONDecodeError as exc:
        debug_path = save_invalid_json_dump(
            llm_output,
            reason=f"JSON parsing error: {exc}",
            run_dir=run_dir,
            run_timestamp=run_timestamp,
            stage="json_parse",
            task_id=task_id,
        )
        print(
            f"[error] Failed to parse JSON for model '{model_name}'. "
            f"Raw output saved to: {debug_path}",
            file=sys.stderr,
        )
        raise

    if "patches" not in obj or not isinstance(obj["patches"], list):
        raise ValueError("Expected key 'patches' with a list of patch objects")

    if len(obj["patches"]) != 1:
        raise ValueError(f"Expected exactly 1 patch in patches[], got {len(obj['patches'])}")

    patch = obj["patches"][0]
    _validate_single_patch_schema(patch)
    return patch


def process_llm_output_single(
    llm_output: str,
    model_name: str,
    *,
    run_dir: Path,
    run_id: str,
    run_timestamp: str,
    run_timestamp_iso: str,
    task_id: int,
) -> Tuple[Dict[str, Any], str]:
    """
    Parse a single-task LLM output, validate it, write one patch artifact file.

    Returns:
      (manifest_entry, artifact_path_str)
    """
    patch = _parse_and_validate_single(
        llm_output,
        model_name,
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        task_id=task_id,
    )

    patch_id = patch["patch_id"]
    if patch_id != task_id:
        raise ValueError(f"patch_id mismatch: expected {task_id}, got {patch_id}")

    # Normalize unified diff to a single string for storage/printing
    unified_diff = _normalize_unified_diff(patch)

    touched_files = patch.get("touched_files") or []
    primary_path = touched_files[0] if touched_files else ""
    primary_name = Path(primary_path).name if primary_path else ""

    patch_artifact = {
        "metadata": {
            "run_id": run_id,
            "patch_id": patch_id,
            "timestamp": run_timestamp_iso,
            "file_path": primary_path,
            "file_name": primary_name,
        },
        "patch": {
            "plan": patch.get("plan", []),
            "cwe_matches": patch.get("cwe_matches", []),
            # Store the joined diff string for downstream compatibility
            "unified_diff": unified_diff,
            # Also keep the raw list if present (useful for debugging; consumers can ignore)
            "unified_diff_lines": patch.get("unified_diff_lines", []),
            "safety_verification": patch.get("safety_verification", ""),
            "risk_notes": patch.get("risk_notes", ""),
            "touched_files": touched_files,
            "assumptions": patch.get("assumptions", ""),
            "behavior_change": patch.get("behavior_change", ""),
            "confidence": patch.get("confidence", 0),
        },
    }

    patch_filename = f"patch_{patch_id:03d}.json"
    patch_path = Path(run_dir) / patch_filename
    write_patch_artifact(patch_path, patch_artifact)

    artifact_path_str = patch_path.as_posix()
    manifest_entry = {
        "patch_id": patch_id,
        "cwe_matches": patch.get("cwe_matches", []),
        "artifact_path": artifact_path_str,
    }

    # Human-readable per-patch summary
    print(f"\n--- Patch (id={patch_id}) written ---")
    print(f"Artifact: {artifact_path_str}")
    print("Plan:", " / ".join(patch.get("plan", [])) or "(none)")
    print("\n=== Safety & Verification ===")
    print(patch.get("safety_verification", ""))
    print("\n=== Risk Notes ===")
    print(patch.get("risk_notes", ""))
    print("\n=== Unified Diff ===")
    print(prettify_unified_diff(unified_diff))
    print("\nTouched files:", ", ".join(touched_files))
    print("Assumptions:", patch.get("assumptions", ""))
    print("Behavior change:", patch.get("behavior_change", ""))
    print("Confidence:", patch.get("confidence", 0))

    return manifest_entry, artifact_path_str


def write_run_manifest(
    *,
    run_dir: Path,
    run_id: str,
    run_timestamp: str,
    model_name: str,
    run_timestamp_iso: str,
    manifest_patches: List[Dict[str, Any]],
) -> Path:
    """
    Write one run-level manifest that indexes all per-task patch artifacts.

    Manifest filename:
      patcher_manifest_<run_timestamp>.json
    """
    manifest = {
        "metadata": {
            "run_id": run_id,
            "timestamp": run_timestamp_iso,
            "tool_version": TOOL_VERSION,
            "model_name": model_name,
            "total_patches": len(manifest_patches),
        },
        "patches": manifest_patches,
    }
    manifest_path = Path(run_dir) / f"patcher_manifest_{run_timestamp}.json"
    return write_manifest(manifest_path, manifest)
