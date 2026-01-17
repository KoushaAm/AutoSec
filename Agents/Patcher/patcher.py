# Patcher/patcher.py
import argparse
import sys
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from .config import OUTPUT_PATH, VULNERABILITIES, MODEL_NAME, MODEL_VALUE
from .constants import VulnerabilityInfo, SYSTEM_MESSAGE, DEVELOPER_MESSAGE
from .core import (
    AgentFields,
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
    build_method_flow_snippets,
)
from .utils import (
    combine_prompt_messages,
    build_user_msg_single,
    estimate_prompt_tokens,
    determine_max_tokens,
    process_llm_output_single,
    write_run_manifest,
)

# Initialize OpenRouter client
load_dotenv()
api_key = getenv("OPENROUTER_API_KEY")
if not api_key:
    raise RuntimeError("OPENROUTER_API_KEY environment variable not set.")
client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)


def _save_prompt_debug(
    messages: List[Dict[str, str]],
    model_name: str,
    *,
    task_id: Optional[int] = None,
    cwe: Optional[str] = None,
) -> None:
    """
    Save the exact prompt text sent to the LLM for debugging and reproducibility.

    Writes to:
        output/prompts/task-XXX_CWE-YYY_<timestamp>.txt

    One file per prompt invocation (never overwritten).
    """
    output_root = Path(OUTPUT_PATH)
    prompts_dir = output_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    parts: List[str] = []
    if task_id is not None:
        parts.append(f"task-{task_id:03d}")
    if cwe:
        safe_cwe = cwe.replace("/", "_")
        parts.append(f"CWE-{safe_cwe}")
    parts.append(timestamp)

    filename = "_".join(parts) + ".txt"
    debug_path = prompts_dir / filename

    debug_lines: List[str] = []
    debug_lines.append("=== PROMPT DEBUG DUMP ===")
    debug_lines.append(f"Model: {model_name}")
    debug_lines.append(f"Timestamp: {timestamp}")
    if task_id is not None:
        debug_lines.append(f"Task ID: {task_id}")
    if cwe:
        debug_lines.append(f"CWE: {cwe}")
    debug_lines.append("=" * 80)

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "").strip()
        debug_lines.append(f"\n[{role}]\n{content}\n")
        debug_lines.append("-" * 80)

    debug_path.write_text("\n".join(debug_lines), encoding="utf-8")
    print(f"[debug] Saved prompt to {debug_path.resolve()}")


def mk_agent_fields(vuln_class: VulnerabilityInfo) -> AgentFields:
    language: str = vuln_class.LANGUAGE
    function_name: str = vuln_class.FUNC_NAME
    cwe_id: str = vuln_class.CWE
    constraints: ConstraintDict = vuln_class.CONSTRAINTS
    sink_meta: SinkDict = vuln_class.SINK
    flow_meta: List[FlowStepDict] = vuln_class.FLOW or []
    pov_tests_meta: List[PoVTestDict] = vuln_class.POV_TESTS or []
    vuln_title: str = getattr(vuln_class, "VULN_TITLE", "")

    return AgentFields(
        language=language,
        function=function_name,
        CWE=cwe_id,
        constraints=constraints,
        sink=sink_meta,
        flow=flow_meta,
        pov_tests=pov_tests_meta,
        vuln_title=vuln_title,
    )


def patcher_main() -> bool:
    parser = argparse.ArgumentParser(description="Patcher tool")
    parser.add_argument(
        "-sp",
        "--save-prompt",
        action="store_true",
        help="Save each generated Patcher prompt to output/prompts/ for debugging",
    )
    args = parser.parse_args()

    REPO_ROOT = Path(__file__).resolve().parents[2]

    # Create ONE run dir for the whole patcher execution
    dt = datetime.now(timezone.utc)
    run_ts = dt.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"patcher_{run_ts}"
    run_timestamp_iso = dt.isoformat().replace("+00:00", "Z")

    output_root = Path(OUTPUT_PATH)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_patches: List[Dict[str, Any]] = []
    all_ok = True

    for task_index, Vulnerability in enumerate(VULNERABILITIES, start=1):
        agent_fields = mk_agent_fields(Vulnerability)

        bundle = build_method_flow_snippets(
            repo_root=REPO_ROOT,
            language=agent_fields.language,
            sink=agent_fields.sink,
            flow=agent_fields.flow,
        )

        user_msg = build_user_msg_single(task_index, agent_fields, bundle)
        messagesArray = combine_prompt_messages(SYSTEM_MESSAGE, DEVELOPER_MESSAGE, user_msg)

        prompt_tokens = estimate_prompt_tokens(messagesArray)
        max_tokens = determine_max_tokens(MODEL_NAME, prompt_tokens)

        print(f"\n=== Task {task_index}: CWE={agent_fields.CWE} func={agent_fields.function} ===")
        print(f"[debug] Estimated prompt tokens: {prompt_tokens}")
        print(f"[debug] Using max_tokens={max_tokens} for model '{MODEL_VALUE}'")

        if args.save_prompt:
            _save_prompt_debug(
                messagesArray,
                MODEL_NAME,
                task_id=task_index,
                cwe=agent_fields.CWE,
            )

        print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
        try:
            completion = client.chat.completions.create(
                model=MODEL_VALUE,
                messages=messagesArray,
                temperature=0.0,
                max_tokens=max_tokens,
            )
        except Exception as e:
            all_ok = False
            print(f"[error] OpenRouter error on task {task_index}: {e}", file=sys.stderr)
            continue

        llm_output = completion.choices[0].message.content or ""
        if not llm_output.strip():
            all_ok = False
            print(f"[error] No output from LLM for task {task_index}", file=sys.stderr)
            continue

        try:
            manifest_entry, _artifact_path = process_llm_output_single(
                llm_output,
                MODEL_VALUE,
                run_dir=run_dir,
                run_id=run_id,
                run_timestamp_iso=run_timestamp_iso,
                task_id=task_index,
            )
            manifest_patches.append(manifest_entry)
        except Exception as exc:
            all_ok = False
            print(f"[fatal] Failed to process LLM output for task {task_index}: {exc}", file=sys.stderr)
            continue

    write_run_manifest(
        run_dir=run_dir,
        run_id=run_id,
        model_name=MODEL_VALUE,
        run_timestamp_iso=run_timestamp_iso,
        manifest_patches=manifest_patches,
    )

    print(f"\n=== Patcher completed: {len(manifest_patches)} patches written to {run_dir.resolve()} ===")
    return all_ok


if __name__ == "__main__":
    patcher_main()
