# fixer.py
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
TOOL_VERSION = "fixer-1.2.1"

# Choose one or more vulnerability definitions to test here.
VULNERABILITIES = [vuln_info.CWE_78, vuln_info.CWE_22, vuln_info.CWE_94]
# VULNERABILITIES = [vuln_info.CWE_918]


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


# ================== Validation (new strict schema) ==================
def _validate_single_patch_schema(patch: Dict[str, Any]) -> None:
    """
    Enforce the new, strict patch schema.
    cwe_matches and verifier_confidence are required.
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
        "verifier_confidence",
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
    if patch["verifier_confidence"] in (None, ""):
        raise ValueError("verifier_confidence must be provided and non-empty")


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
    Extract JSON from LLM output, validate, save, and print a readable summary.

    If JSON parsing fails, dumps the full raw output to output/invalid_json_*.txt
    via generic_utils.save_invalid_json_dump, then raises a clear error.
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

    obj = _validate_multi_schema(obj)

    # Save full JSON
    file_to_save = gu.utc_timestamped_filename(model_name)
    gu.save_output_to_file(file_to_save, json.dumps(obj, indent=2))

    print("\n=== Fixer Summary (multi) ===")
    for idx, patch in enumerate(obj["patches"], start=1):
        print(f"\n--- Patch {idx} (id={patch.get('patch_id','?')}) ---")
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
        print("Verifier confidence:", patch.get("verifier_confidence", ""))


# ================== Main ==================
def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Fixer tool")
    parser.add_argument(
        "-sp", "--save-prompt", 
        action="store_true", 
        help="Save the generated prompt to output/given_prompt.txt for debugging")
    args = parser.parse_args()

    # Select model
    CURRENT_MODEL = models.Model.LLAMA3
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
            max_tokens=8000,
        )
    except Exception as e:
        print("OpenRouter error:", e, file=sys.stderr)
        sys.exit(1)

    llm_output = completion.choices[0].message.content or ""
    if llm_output == "":
        print("No output from LLM; confirm max_tokens setting.\n", file=sys.stderr)
        sys.exit(1)

    try:
        process_llm_output(llm_output, CURRENT_MODEL.name)
    except ValueError as exc:
        print(f"[fatal] Failed to process LLM output: {exc}", file=sys.stderr)
        sys.exit(1)


# execute main
if __name__ == "__main__":
    main()
