# patcher.py
import argparse, sys, json
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime, timezone

# local imports
from constants import prompts, models, vuln_info
from utils import (
    generic_utils as gu,
    prompt_utils as pu,
    openrouter_utils as ou,
)

# ================== Constants ==================
load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=getenv("OPENROUTER_API_KEY"),
)

# Tool version stamped into saved output metadata (host-side only).
TOOL_VERSION = "patcher-1.3.0"

# Choose one or more vulnerability definitions to test here.
VULNERABILITIES = [vuln_info.CWE_78, vuln_info.CWE_22, vuln_info.CWE_94, vuln_info.CWE_918]

# ================== Helpers ==================
def save_prompt_debug(messages: List[Dict[str, str]], model_name: str) -> None:
    """
    Save the exact prompt text sent to the LLM for debugging and reproducibility.

    Writes to: /output/given_prompt.txt (same directory as JSON output files).
    Each message role and content is clearly separated for easy inspection.
    """
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)
    debug_path = output_dir / "given_prompt.txt"

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")

    # Compose readable dump
    debug_lines: List[str] = []
    debug_lines.append(f"=== PROMPT DEBUG DUMP ===")
    debug_lines.append(f"Model: {model_name}")
    debug_lines.append(f"Timestamp: {timestamp}")
    debug_lines.append("=" * 80)
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "").strip()
        debug_lines.append(f"\n[{role}]\n{content}\n")
        debug_lines.append("-" * 80)

    debug_text = "\n".join(debug_lines)
    debug_path.write_text(debug_text, encoding="utf-8")

    print(f"[debug] Saved generated prompt to {debug_path.resolve()}\n")


def _mk_agent_fields(vuln_class) -> pu.AgentFields:
    """
    Construct strongly-typed AgentFields from a vuln_info.* class.
    The vuln_info base class validates structure at import time, so
    we can rely on these attributes existing and being well-formed.
    """
    language: str = vuln_class.LANGUAGE
    function_name: str = vuln_class.FUNC_NAME
    cwe_id: str = vuln_class.CWE
    constraints: pu.ConstraintDict = vuln_class.CONSTRAINTS
    sink_meta: pu.SinkDict = vuln_class.SINK
    flow_meta: List[pu.FlowStepDict] = vuln_class.FLOW or []
    pov_tests_meta: List[pu.PoVTestDict] = vuln_class.POV_TESTS or []
    vuln_title: str = getattr(vuln_class, "VULN_TITLE", "")

    return pu.AgentFields(
        language=language,
        function=function_name,
        CWE=cwe_id,
        constraints=constraints,
        sink=sink_meta,
        flow=flow_meta,
        pov_tests=pov_tests_meta,
        vuln_title=vuln_title,
    )


# ================== Validation (strict schema) ==================
def _validate_single_patch_schema(patch: Dict[str, Any]) -> None:
    """
    Enforce the strict patch schema expected from the Patcher LLM output.

    Required keys (per patch object returned by the model):
        - patch_id
        - plan (list)
        - cwe_matches (non-empty list)
        - unified_diff
        - safety_verification
        - risk_notes
        - touched_files (list)
        - assumptions
        - behavior_change
        - confidence

    Note:
        - `verifier_confidence` is no longer required at this stage. Any such
          field returned by the model will be ignored when writing patch
          artifacts.
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

    if not isinstance(patch["plan"], list):
        raise ValueError("plan must be a list")
    if not isinstance(patch["touched_files"], list):
        raise ValueError("touched_files must be a list")
    if not isinstance(patch["cwe_matches"], list) or len(patch["cwe_matches"]) == 0:
        raise ValueError("cwe_matches must be a non-empty list")
    if not isinstance(patch["patch_id"], int):
        raise ValueError(f"patch_id must be an integer, got {patch['patch_id']!r}")


def _validate_multi_schema(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Validate multi-patch schema and set host-side metadata fields."""
    if "patches" not in obj or not isinstance(obj["patches"], list):
        raise ValueError("Expected key 'patches' with a list of patch objects")

    for patch in obj["patches"]:
        _validate_single_patch_schema(patch)

    # Host-owned metadata (LLM must NOT set these).
    meta = obj.setdefault("metadata", {})
    meta["total_patches"] = len(obj["patches"])
    meta["timestamp"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    meta["tool_version"] = TOOL_VERSION
    return obj


def process_llm_output(llm_output: str, model_name: str):
    """
    Extract JSON from LLM output, validate against the multi-patch schema,
    then write:
      1) A run-level manifest file
      2) One patch artifact file per patch

    Finally, print a human-readable summary of all patches.
    """
    # 1. Try to carve out a { ... } block
    json_text = gu.extract_json_block(llm_output)

    # 2. Try to parse JSON; if it fails, dump + raise
    try:
        obj = json.loads(json_text)
    except json.JSONDecodeError as exc:
        debug_path = gu.save_invalid_json_dump(
            llm_output,
            reason=f"JSON parsing error: {exc}",
        )
        print(
            f"[error] Failed to parse JSON for model '{model_name}'. "
            f"Raw output saved to: {debug_path}",
            file=sys.stderr,
        )
        raise

    # 3. Validate schema and set basic metadata
    full = _validate_multi_schema(obj)

    # Derive a run_id and output directory based on the metadata timestamp.
    # Manifest and patch artifact paths follow:
    #   output/patcher_<timestamp>/patcher_<timestamp>.json
    #   output/patcher_<timestamp>/patch_XXX.json
    ts_iso = full.get("metadata", {}).get("timestamp")

    try:
        if ts_iso:
            dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        else:
            dt = datetime.now(timezone.utc)
        run_ts = dt.strftime("%Y%m%dT%H%M%SZ")
    except Exception:
        dt = datetime.now(timezone.utc)
        run_ts = dt.strftime("%Y%m%dT%H%M%SZ")

    run_id = f"patcher_{run_ts}"
    output_root = Path("output")
    run_dir = output_root / run_id

    meta = full.setdefault("metadata", {})
    meta["run_id"] = run_id
    meta["tool_version"] = TOOL_VERSION
    meta["model_name"] = model_name
    meta["total_patches"] = len(full.get("patches", []))

    # Build manifest index entries + write each patch artifact.
    manifest_patches: List[Dict[str, Any]] = []
    artifact_paths_by_id: Dict[int, str] = {}

    for patch in full.get("patches", []):
        patch_id = patch.get("patch_id")
        if not isinstance(patch_id, int):
            raise ValueError(f"patch_id must be an integer, got: {patch_id!r}")

        # Derive primary file_path/file_name from touched_files (sink file).
        touched_files = patch.get("touched_files") or []
        if touched_files and isinstance(touched_files, list):
            primary_path = touched_files[0]
        else:
            primary_path = ""

        try:
            primary_name = Path(primary_path).name if primary_path else ""
        except TypeError:
            primary_path = ""
            primary_name = ""

        # Construct patch artifact payload per agreed schema.
        patch_artifact = {
            "metadata": {
                "patch_id": patch_id,
                "timestamp": meta["timestamp"],
                "file_path": primary_path,
                "file_name": primary_name,
            },
            "patch": {
                "plan": patch.get("plan", []),
                "cwe_matches": patch.get("cwe_matches", []),
                "unified_diff": patch.get("unified_diff", ""),
                "safety_verification": patch.get("safety_verification", ""),
                "risk_notes": patch.get("risk_notes", ""),
                "touched_files": touched_files,
                "assumptions": patch.get("assumptions", ""),
                "behavior_change": patch.get("behavior_change", ""),
                "confidence": patch.get("confidence", ""),
            },
        }

        # Write patch artifact: output/patcher_<ts>/patch_XXX.json
        patch_filename = f"patch_{patch_id:03d}.json"
        patch_path = run_dir / patch_filename
        gu.write_patch_artifact(patch_path, patch_artifact)

        artifact_path_str = patch_path.as_posix()
        manifest_entry = {
            "patch_id": patch_id,
            "cwe_matches": patch.get("cwe_matches", []),
            "artifact_path": artifact_path_str,
        }
        manifest_patches.append(manifest_entry)
        artifact_paths_by_id[patch_id] = artifact_path_str

    # 5. Write the manifest file itself.
    manifest = {
        "metadata": {
            "run_id": meta["run_id"],
            "timestamp": meta["timestamp"],
            "tool_version": meta["tool_version"],
            "model_name": meta["model_name"],
            "total_patches": meta["total_patches"],
        },
        "patches": manifest_patches,
    }

    manifest_path = run_dir / f"{run_id}.json"
    gu.write_manifest(manifest_path, manifest)

    # 6. Print a human-readable summary using the full patch objects.
    print("\n=== Patcher Summary (multi) ===")
    for idx, patch in enumerate(full.get("patches", []), start=1):
        patch_id = patch.get("patch_id", "?")
        artifact_path = artifact_paths_by_id.get(patch_id, "(unknown)")
        print(f"\n--- Patch {idx} (id={patch_id}) ---")
        print(f"Artifact: {artifact_path}")
        print("Plan:", " / ".join(patch.get("plan", [])) or "(none)")
        for match in patch.get("cwe_matches", []):
            print(f"  CWE {match.get('cwe_id')} (similarity={match.get('similarity')})")

        print("\n=== Safety & Verification ===")
        print(patch.get("safety_verification", ""))
        print("\n=== Risk Notes ===")
        print(patch.get("risk_notes", ""))
        print("\n=== Unified Diff ===")
        print(gu.prettify_unified_diff(patch.get("unified_diff", "")))
        print("\nTouched files:", ", ".join(patch.get("touched_files", [])))
        print("Assumptions:", patch.get("assumptions", ""))
        print("Behavior change:", patch.get("behavior_change", ""))
        print("Confidence:", patch.get("confidence", ""))


# ================== Main ==================
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Patcher tool")
    parser.add_argument(
        "-sp",
        "--save-prompt",
        action="store_true",
        help="Save the generated prompt to output/given_prompt.txt for debugging",
    )
    args = parser.parse_args()

    # Select model
    CURRENT_MODEL = models.Model.QWEN3
    MODEL_VALUE = CURRENT_MODEL.value

    # Repo root (two levels up from this file)
    REPO_ROOT = Path(__file__).resolve().parents[2]

    # Collect (task_id, AgentFields, snippet_or_bundle) tuples.
    tasks: List[Tuple[int, pu.AgentFields, Union[str, Dict[str, str]]]] = []

    for task_index, Vulnerability in enumerate(VULNERABILITIES, start=1):
        agent_fields = _mk_agent_fields(Vulnerability)

        # Always build a multi-file bundle (includes sink + flow context)
        bundle = pu.build_flow_context_snippets(
            repo_root=REPO_ROOT,
            sink=agent_fields.sink,
            flow=agent_fields.flow,
            base_context=4,
        )

        tasks.append((task_index, agent_fields, bundle))

    # Build final chat messages for OpenRouter API
    messagesArray = ou.format_prompt_message(
        client,
        CURRENT_MODEL.name,
        prompts.SYSTEM_MESSAGE,
        prompts.DEVELOPER_MESSAGE,
        pu.build_user_msg_multi(tasks),
        ignore_developer_support_check=False,
    )

    # Save generated prompt for debugging, run with `-sp` flag
    if args.save_prompt:
        save_prompt_debug(messagesArray, CURRENT_MODEL.name)

    print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
    try:
        completion = client.chat.completions.create(
            model=MODEL_VALUE,
            messages=messagesArray,
            temperature=0.0,
            # max_tokens=8000,
        )
    except Exception as e:
        print("OpenRouter error:", e, file=sys.stderr)
        sys.exit(1)

    llm_output = completion.choices[0].message.content or ""
    if llm_output == "":
        print("No output from LLM; confirm max_tokens setting.\n", file=sys.stderr)
        sys.exit(1)

    try:
        process_llm_output(llm_output, MODEL_VALUE)
    except ValueError as exc:
        print(f"[fatal] Failed to process LLM output: {exc}", file=sys.stderr)
        sys.exit(1)


# execute main
if __name__ == "__main__":
    main()
