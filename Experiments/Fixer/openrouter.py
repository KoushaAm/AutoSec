# openrouter.py
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
import json
import sys
from pathlib import Path
from typing import Any, Dict

# local imports
from constants import prompts, models, vuln_info
from utils import generic_utils as gu, prompt_utils as pu

# ================== Constants ==================
load_dotenv()

client = OpenAI(
  base_url="https://openrouter.ai/api/v1",
  api_key=getenv("OPENROUTER_API_KEY"),
)

#! Set current vulnerability to test here
CURRENT_VULN = vuln_info.CWE_22

AGENT_FIELDS_EXAMPLE = pu.AgentFields(
    language="Java",
    file=CURRENT_VULN.FILE_NAME.value,
    # function="public static void main(String[] args) throws Exception",
    CWE=CURRENT_VULN.CWE.value,
    # vuln_title="Fixing a command-line injection in a Java CLI program",
    constraints={"max_lines": 30, "max_hunks": 2, "no_new_deps": True, "keep_signature": True},
    # pov_root_cause="user input is concatenated into a shell command string and passed to Runtime.exec(), allowing command injection.",
)

# ================== Helper ==================
def _validate_schema(obj: Dict[str, Any]) -> None:
    required_keys = ["plan","unified_diff","why_safe","risk_notes","touched_files","assumptions","behavior_change","confidence"]
    for k in required_keys:
        if k not in obj:
            raise ValueError(f"Missing required key: {k}")
    # Optional keys: validate types if present
    if "generated_tests" in obj and not isinstance(obj["generated_tests"], list):
        raise ValueError("generated_tests must be a list")
    if "cve_matches" in obj and not isinstance(obj["cve_matches"], list):
        raise ValueError("cve_matches must be a list")
    for k in ["verifier_verdict","verifier_rationale","verifier_confidence"]:
        if k in obj and obj[k] in (None, ""):
            raise ValueError(f"{k} is present but empty")

def process_llm_output(llm_output: str, model_name: str):
    """Process LLM output: extract JSON, validate, save, and print summary."""
    # Extract/parse JSON
    json_text = gu.extract_json_block(llm_output)
    obj = json.loads(json_text)
    _validate_schema(obj)

    # Save full JSON
    file_to_save = gu.utc_timestamped_filename(model_name)
    gu.save_output_to_file(file_to_save, json.dumps(obj, indent=2))

    # Pretty print summary
    print("\n=== Fixer Summary ===")
    print("Plan:", " / ".join(obj.get("plan", [])))
    if obj.get("cwe_matches"):
        print("CWE Matches:")
        for cwe in obj["cwe_matches"]:
            print(f" - {cwe.get('cwe_id')} -> sim={cwe.get('similarity')}")
    if obj.get("generated_tests"):
        print("Generated tests:")
        for t in obj["generated_tests"]:
            print(f" - {t.get('id')}: {t.get('desc')} (expected: {t.get('expected')})")
    if obj.get("verifier_verdict"):
        print(f"Verifier: {obj['verifier_verdict']} ({obj.get('verifier_confidence','?')}%)")
        print(f"Reason: {obj.get('verifier_rationale','')}")

    print("\n=== Unified Diff ===\n")
    print(gu.prettify_unified_diff(json_text))

# ================== Main ==================
def main():
    CURRENT_MODEL = models.Model.DEEPSEEK
    MODEL_VALUE = CURRENT_MODEL.value

    # Repo root = AutoSec (two levels up from this file: Fixer -> Experiments -> AutoSec)
    REPO_ROOT = Path(__file__).resolve().parents[2]

    try:
        vuln_relpath = str(CURRENT_VULN.FILE_PATH.value)  # e.g., "Experiments/vulnerable/CWE_78.java"
        vuln_start = int(CURRENT_VULN.START_LINE.value) if CURRENT_VULN.START_LINE.value is not None else None
        vuln_end = int(CURRENT_VULN.END_LINE.value) if CURRENT_VULN.END_LINE.value is not None else None
    except Exception as exc:
        print(f"ERROR: invalid vuln_info selection: {exc}", file=sys.stderr)
        sys.exit(1)

    # Read snippet using repo-root policy; NO static fallback.
    try:
        REPO_ROOT = Path(__file__).resolve().parents[2]
        snippet = pu.get_vuln_snippet_from_file(
            vuln_relpath,
            start_line=vuln_start,
            end_line=vuln_end,
            repo_root=REPO_ROOT
        )
    except Exception as exc:
        print(f"ERROR: Could not read snippet for '{vuln_relpath}': {exc}", file=sys.stderr)
        sys.exit(1)

    # Build the user message (always dynamic; no static fallback in production)
    isStaticUserMessage = False
    USER_MESSAGE = prompts.USER_MESSAGE if isStaticUserMessage else pu.build_user_msg(AGENT_FIELDS_EXAMPLE, snippet)

    # Build messages array
    messagesArray = pu.get_messages(client, 
                        MODEL_VALUE, 
                        prompts.SYSTEM_MESSAGE, 
                        prompts.DEVELOPER_MESSAGE, 
                        USER_MESSAGE, 
                        ignore_developer_support_check=True
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
