# openrouter.py
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# local imports
from constants import prompts, models, vuln_info
from utils import generic_utils as gu, prompt_utils as pu

# ================== Constants ==================
load_dotenv()

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

#* Choose one or more vulnerabilities to test here
# Single-task: keep one item in the list
# Multi-task: add more items (order defines task_id)
VULNERABILITIES = [vuln_info.CWE_78, vuln_info.CWE_22, vuln_info.CWE_94]

def _mk_agent_fields(v) -> pu.AgentFields:
    return pu.AgentFields(
        language="Java",  # adjust per-vuln if needed
        file=v.FILE_NAME.value,
        function=v.FUNC_NAME.value,
        CWE=v.CWE.value,
        constraints={"max_lines": 30, "max_hunks": 2, "no_new_deps": True, "keep_signature": True},
        # vuln_title="Fixing a command-line injection in a Java CLI program",
        # pov_root_cause="user input is concatenated into a shell command string and passed to Runtime.exec(), allowing command injection."
    )

# ================== Validation (accept only 'patches') ==================
def _validate_single_patch_schema(patch: Dict[str, Any]) -> None:
    # Required per-patch keys
    required = ["plan","unified_diff","why_safe","risk_notes","touched_files","assumptions","behavior_change","confidence"]
    for k in required:
        if k not in patch:
            raise ValueError(f"Missing required key in patch: {k}")
    # Optional types
    if "generated_tests" in patch and not isinstance(patch["generated_tests"], list):
        raise ValueError("generated_tests must be a list")
    if "cwe_matches" in patch and not isinstance(patch["cwe_matches"], list):
        raise ValueError("cwe_matches must be a list")
    for k in ["verifier_verdict","verifier_rationale","verifier_confidence"]:
        if k in patch and patch[k] in (None, ""):
            raise ValueError(f"{k} is present but empty")

def _validate_multi_schema(obj: Dict[str, Any]) -> Dict[str, Any]:
    """Validate multi-patch schema and normalize metadata (returns obj)."""
    if "patches" not in obj or not isinstance(obj["patches"], list):
        raise ValueError("Expected key 'patches' with a list of patch objects")
    for p in obj["patches"]:
        _validate_single_patch_schema(p)
    obj.setdefault("metadata", {})
    obj["metadata"].setdefault("total_patches", len(obj["patches"]))
    return obj

def process_llm_output(llm_output: str, model_name: str):
    """Process LLM output: extract JSON, validate, save, and print summary."""
    # Extract/parse JSON
    json_text = gu.extract_json_block(llm_output)
    obj = json.loads(json_text)
    obj = _validate_multi_schema(obj)

    # Save full JSON
    file_to_save = gu.utc_timestamped_filename(model_name)
    gu.save_output_to_file(file_to_save, json.dumps(obj, indent=2))

    # Pretty print summaries per patch
    print("\n=== Fixer Summary (multi) ===")
    for i, p in enumerate(obj["patches"], start=1):
        print(f"\n--- Patch {i} (id={p.get('patch_id','?')}) ---")
        print("Plan:", " / ".join(p.get("plan", [])))
        if p.get("cwe_matches"):
            print("CWE Matches:")
            for cwe in p["cwe_matches"]:
                print(f" - {cwe.get('cwe_id')} -> sim={cwe.get('similarity')}")
        if p.get("generated_tests"):
            print("Generated tests:")
            for t in p["generated_tests"]:
                print(f" - {t.get('id')}: {t.get('desc')} (expected: {t.get('expected')})")
        if p.get("verifier_verdict"):
            print(f"Verifier: {p['verifier_verdict']} ({p.get('verifier_confidence','?')}%)")
            print(f"Reason: {p.get('verifier_rationale','')}")
        print("\n=== Unified Diff ===\n")
        print(gu.prettify_unified_diff(p.get("unified_diff","")))

# ================== Main ==================
def main():
    CURRENT_MODEL = models.Model.QWEN3
    MODEL_VALUE = CURRENT_MODEL.value

    # Repo root = AutoSec (two levels up from this file: Fixer -> Experiments -> AutoSec)
    REPO_ROOT = Path(__file__).resolve().parents[2]

    # Collect (task_id, AgentFields, snippet) tuples
    tasks: List[Tuple[int, pu.AgentFields, str]] = []
    for i, Vuln in enumerate(VULNERABILITIES, start=1):
        try:
            vuln_relpath = str(Vuln.FILE_PATH.value)
            vuln_start = int(Vuln.START_LINE.value) if Vuln.START_LINE.value is not None else None
            vuln_end = int(Vuln.END_LINE.value) if Vuln.END_LINE.value is not None else None
        except Exception as exc:
            print(f"ERROR: invalid vuln_info selection: {exc}", file=sys.stderr)
            sys.exit(1)
        try:
            snippet = pu.get_vuln_snippet_from_file(
                vuln_relpath, start_line=vuln_start, end_line=vuln_end, repo_root=REPO_ROOT
            )
        except Exception as exc:
            print(f"ERROR: Could not read snippet for '{vuln_relpath}': {exc}", file=sys.stderr)
            sys.exit(1)
        tasks.append((i, _mk_agent_fields(Vuln), snippet))

    # Build messages array
    messagesArray = pu.get_messages(
        client,
        MODEL_VALUE,
        prompts.SYSTEM_MESSAGE,
        prompts.DEVELOPER_MESSAGE,
        pu.build_user_msg_multi(tasks),  # USER_MESSAGE
        ignore_developer_support_check=False
    )

    print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
    try:
        completion = client.chat.completions.create(
            model=MODEL_VALUE,
            messages=messagesArray,
            temperature=0.0,
            max_tokens=4000
        )
    except Exception as e:
        print("OpenRouter error:", e, file=sys.stderr)
        sys.exit(1)

    # Extract LLM output & process
    llm_output = completion.choices[0].message.content or ""
    if llm_output == "":
        print("No output from LLM.", file=sys.stderr)
        sys.exit(1)

    process_llm_output(llm_output, CURRENT_MODEL.name)

# execute main
if __name__ == "__main__":
    main()
