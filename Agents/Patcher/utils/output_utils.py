# Patcher/utils/output_utils.py
import json
import logging
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
from .logging_utils import get_patch_logger


# ================== Validation (strict schema) ==================
def _validate_single_patch_schema(patch: Dict[str, Any]) -> None:
    """
    Enforce the strict patch schema expected from the Patcher LLM output.
    Requires unified_diff as a single string.
    """
    required_keys = [
        "patch_id",
        "plan",
        "cwe_matches",
        "unified_diff",
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

    if not isinstance(patch["unified_diff"], str):
        raise ValueError("unified_diff must be a string")

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
    run_logger: logging.Logger,
) -> Dict[str, Any]:
    """
    Extract JSON, parse it, then validate that it contains exactly one patch.
    Returns the single patch object.
    """
    json_text = extract_json_block(
        llm_output,
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        stage="extract_json_block",
        task_id=task_id,
        logger=run_logger,
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
            logger=run_logger,
        )
        run_logger.error(
            "Failed to parse JSON | model=%s | task_id=%s | debug_path=%s",
            model_name,
            task_id,
            str(debug_path),
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
    output_dir: Path,
    run_logger: logging.Logger,
) -> Tuple[Dict[str, Any], str]:
    """
    Parse a single-task LLM output, validate it, write one patch artifact file.

    Logging is REQUIRED:
      - run_logger: run-level lifecycle/errors
      - patch logger (derived from output_dir + patch_id): full human-readable patch summary

    Returns:
      (manifest_entry, artifact_path_str)
    """
    patch = _parse_and_validate_single(
        llm_output,
        model_name,
        run_dir=run_dir,
        run_timestamp=run_timestamp,
        task_id=task_id,
        run_logger=run_logger,
    )

    patch_id = patch["patch_id"]

    if patch_id != task_id:
        raise ValueError(f"patch_id mismatch: expected {task_id}, got {patch_id}")

    patch_logger = get_patch_logger(output_dir, str(patch_id), level="INFO")

    unified_diff = patch["unified_diff"]
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
            "unified_diff": unified_diff,
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
    write_patch_artifact(patch_path, patch_artifact, logger=patch_logger)

    artifact_path_str = patch_path.as_posix()

    manifest_entry = {
        "patch_id": patch_id,
        "cwe_matches": patch.get("cwe_matches", []),
        "artifact_path": artifact_path_str,
    }

    # Run logger: concise
    run_logger.info("Patch artifact written | patch_id=%s | artifact=%s", patch_id, artifact_path_str)

    # Patch logger: full summary
    patch_logger.info("--- Patch (id=%s) written ---", patch_id)
    patch_logger.info("Artifact: %s", artifact_path_str)
    patch_logger.info("Plan: %s", " / ".join(patch.get("plan", [])) or "(none)")
    patch_logger.info("=== Safety & Verification ===\n%s", patch.get("safety_verification", ""))
    patch_logger.info("=== Risk Notes ===\n%s", patch.get("risk_notes", ""))
    patch_logger.info("=== Unified Diff ===\n%s", prettify_unified_diff(unified_diff))
    patch_logger.info("Touched files: %s", ", ".join(touched_files))
    patch_logger.info("Assumptions: %s", patch.get("assumptions", ""))
    patch_logger.info("Behavior change: %s", patch.get("behavior_change", ""))
    patch_logger.info("Confidence: %s", patch.get("confidence", 0))

    return manifest_entry, artifact_path_str


def write_run_manifest(
    *,
    run_dir: Path,
    run_id: str,
    run_timestamp: str,
    model_name: str,
    run_timestamp_iso: str,
    manifest_patches: List[Dict[str, Any]],
    run_logger: logging.Logger,
) -> Path:
    """
    Write one run-level manifest that indexes all per-task patch artifacts.
    Logging is REQUIRED.
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
    return write_manifest(manifest_path, manifest, logger=run_logger)