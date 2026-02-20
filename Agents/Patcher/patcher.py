# Agents/Patcher/patcher.py
import argparse
import sys
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

from .config import OUTPUT_PATH, MODEL_NAME, MODEL_VALUE
from .constants import SYSTEM_MESSAGE, DEVELOPER_MESSAGE

# Finder-aligned core types
from .core.types import ConstraintDict, Trace, VulnerabilitySpec, FileSnippetBundle

# Trace-driven extractor (fail-fast capable)
from .core.code_extractor import extract_snippets_for_vuln, SnippetExtractionError

# Prompt + LLM IO helpers
from .utils import (
    combine_prompt_messages,
    build_patch_prompt,
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
    run_dir: Path,
    task_id: Optional[int] = None,
    cwe_id: Optional[str] = None,
) -> None:
    """
    Save the exact prompt text sent to the LLM for debugging and reproducibility.

    Writes to:
        <run_dir>/prompts/task-XXX_cwe-022_<timestamp>.txt

    One file per prompt invocation (never overwritten).
    """
    prompts_dir = Path(run_dir) / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    parts: List[str] = []
    if task_id is not None:
        parts.append(f"task-{task_id:03d}")
    if cwe_id:
        safe_cwe = cwe_id.replace("/", "_")
        parts.append(safe_cwe)
    parts.append(timestamp)

    filename = "_".join(parts) + ".txt"
    debug_path = prompts_dir / filename

    debug_lines: List[str] = []
    debug_lines.append("=== PROMPT DEBUG DUMP ===")
    debug_lines.append(f"Model: {model_name}")
    debug_lines.append(f"Timestamp: {timestamp}")
    if task_id is not None:
        debug_lines.append(f"Task ID: {task_id}")
    if cwe_id:
        debug_lines.append(f"cwe_id: {cwe_id}")
    debug_lines.append("=" * 80)

    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "").strip()
        debug_lines.append(f"\n[{role}]\n{content}\n")
        debug_lines.append("-" * 80)

    debug_path.write_text("\n".join(debug_lines), encoding="utf-8")
    print(f"[debug] Saved prompt to {debug_path.resolve()}")


# TODO: refactor to specify constraints per CWE instance
def _constraints_for_cwe(cwe_id: str) -> ConstraintDict:
    """
    Placeholder: all CWEs share the same constraints for now.
    Later you can map per-cwe here.
    """
    return {
        "max_lines": 30,
        "max_hunks": 2,
        "no_new_deps": True,
        "keep_signature": True,
    }


def _clean_traces(traces: Any) -> List[Trace]:
    """
    Keep only non-empty traces (list of steps).
    Drops: None, non-lists, empty traces.
    """
    if not isinstance(traces, list):
        return []
    return [t for t in traces if isinstance(t, list) and len(t) > 0]


def populate_vulnerability_specs(
    *,
    language: str,
    cwe_id: str,
    vulnerabilities: List[Dict[str, Any]],
    project_name: str,
    pov_logic: str,
) -> List[VulnerabilitySpec]:
    """
    Convert pipeline-provided vulnerabilities into VulnerabilitySpec list.

    One spec per unique vulnerability instance.
    Each instance may contain multiple traces.

    Behavior:
      - Vulnerability instances with empty/invalid traces are skipped.
      - Non-empty traces still validated by VulnerabilitySpec.__post_init__.
    """
    specs: List[VulnerabilitySpec] = []
    constraints = _constraints_for_cwe(cwe_id)

    skipped = 0

    for v in vulnerabilities:
        raw_traces = v.get("traces", [])
        traces: List[Trace] = _clean_traces(raw_traces)

        if not traces:
            skipped += 1
            continue

        specs.append(
            VulnerabilitySpec(
                language=language.lower(),
                cwe_id=cwe_id,
                project_name=project_name,
                constraints=constraints,
                traces=traces,
                pov_logic=pov_logic,
            )
        )

    if skipped:
        print(f"[patcher] Skipped {skipped} vulnerability instance(s) with empty traces for {cwe_id}")

    return specs


def _detect_repo_root() -> Path:
    """
    Best-effort repo root detection.

    In devcontainer, we often have /workspaces/autosec.
    Fallback to walking up from this file.
    """
    preferred = Path("/workspaces/autosec")
    if preferred.exists():
        return preferred
    return Path(__file__).resolve().parents[2]


# =============== Main entrypoint for Patcher agent ===============

def patcher_main(
    *,
    language: str,
    cwe_id: str,
    vulnerability_list: List[Dict[str, Any]],
    project_name: str,
    pov_logic: str = "",
    save_prompt: bool = False,
) -> Tuple[bool, str]:
    """
    Pipeline-safe entrypoint (no argparse).

    Returns:
      (success: bool, run_dir_path: str)
    """
    repo_root = _detect_repo_root()

    specs = populate_vulnerability_specs(
        language=language,
        cwe_id=cwe_id,
        vulnerabilities=vulnerability_list,
        project_name=project_name,
        pov_logic=pov_logic,
    )

    # Create ONE run dir for the whole patcher execution
    dt = datetime.now(timezone.utc)
    run_timestamp = dt.strftime("%Y%m%dT%H%M%SZ")
    run_id = f"patcher_{project_name}_datetime_{run_timestamp}"
    run_timestamp_iso = dt.isoformat().replace("+00:00", "Z")

    output_root = Path(OUTPUT_PATH)
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest_patches: List[Dict[str, Any]] = []
    patcher_success = True

    for task_index, spec in enumerate(specs, start=1):
        print(f"\n=== Task {task_index}: cwe_id={spec.cwe_id} ===")

        # 1) Extract code context from all trace steps (dedup/merge inside extractor)
        try:
            snippets: FileSnippetBundle = extract_snippets_for_vuln(
                spec=spec,
                repo_root=repo_root,
            )
        except SnippetExtractionError as e:
            patcher_success = False
            print(f"[error] Snippet extraction failed for task {task_index}:\n{e}", file=sys.stderr)
            # Fail fast: do NOT build prompt, do NOT call LLM
            continue
        except Exception as e:
            patcher_success = False
            print(f"[error] Unexpected extractor error for task {task_index}: {e}", file=sys.stderr)
            continue

        # Hard guard: refuse to prompt if bundle is empty for any reason
        by_file = snippets.get("by_file", {})
        if not by_file or not any((v or "").strip() for v in by_file.values()):
            patcher_success = False
            print(
                f"[error] Empty snippet bundle for task {task_index}; refusing to call LLM.",
                file=sys.stderr,
            )
            continue

        # 2) Build exactly one prompt per vulnerability instance (only after extraction succeeded)
        user_msg: str = build_patch_prompt(
            task_id=task_index,
            spec=spec,
            snippet_payload=snippets,
        )

        # 3) Assemble messages
        messagesArray = combine_prompt_messages(SYSTEM_MESSAGE, DEVELOPER_MESSAGE, user_msg)

        if save_prompt:
            _save_prompt_debug(
                messagesArray,
                MODEL_NAME,
                run_dir=run_dir,
                task_id=task_index,
                cwe_id=spec.cwe_id,
            )

        print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
        try:
            completion = client.chat.completions.create(
                model=MODEL_VALUE,
                messages=messagesArray,
                temperature=0.0,
                max_tokens=6000, # TODO: determine programmatically
                response_format={"type": "json_object"},
            )
            if completion.choices[0].finish_reason != "stop":
                patcher_success = False
                print(f"[error] Unexpected finish reason: {completion.choices[0].finish_reason}")
                print("[debug] Content length:", len(completion.choices[0].message.content or ""))

        except Exception as e:
            patcher_success = False
            print(f"[error] OpenRouter error on task {task_index}: {e}", file=sys.stderr)
            continue

        llm_output = completion.choices[0].message.content or ""
        if not llm_output.strip():
            patcher_success = False
            print(f"[error] No output from LLM for task {task_index}\n", file=sys.stderr)
            print(f"[debug] Full completion response: {completion}\n", file=sys.stderr)
            print(f"[debug] Full LLM response: {llm_output}\n", file=sys.stderr)
            continue

        # 4) Persist artifact JSON + update manifest
        try:
            manifest_entry, _artifact_path = process_llm_output_single(
                llm_output,
                MODEL_VALUE,
                run_dir=run_dir,
                run_id=run_id,
                run_timestamp=run_timestamp,
                run_timestamp_iso=run_timestamp_iso,
                task_id=task_index,
            )
            manifest_patches.append(manifest_entry)
        except Exception as exc:
            patcher_success = False
            print(f"[fatal] Failed to process LLM output for task {task_index}: {exc}", file=sys.stderr)
            continue

    write_run_manifest(
        run_dir=run_dir,
        run_id=run_id,
        run_timestamp=run_timestamp,
        model_name=MODEL_VALUE,
        run_timestamp_iso=run_timestamp_iso,
        manifest_patches=manifest_patches,
    )

    print(f"\n=== Patcher completed: {len(manifest_patches)} patches written to {run_dir.resolve()} ===")
    return patcher_success, str(run_dir.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Patcher tool (standalone)")
    parser.add_argument("--save-prompt", action="store_true", help="Save prompts to output/prompts/")
    parser.add_argument("--use-experiments", action="store_true", help="(legacy) run experiment vulns (deprecated)")
    args = parser.parse_args()

    raise SystemExit("Standalone mode is deprecated. Call patcher_main(...) from pipeline with Finder output.")
