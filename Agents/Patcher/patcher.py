# Patcher/patcher.py
"""
The Patcher module serves as the LLM-driven security patch generator for the
AutoSec pipeline. It loads vulnerability definitions, extracts multi-file 
source-to-sink code context using the method-based Code Extractor,
and assembles a fully-structured prompt for the LLM.

The module handles:
- Building AgentFields for each vulnerability (language, sink, data-flow, constraints)
- Extracting method-level code bundles for sinks and flow steps
- Constructing system/developer/user messages for the LLM
- Estimating prompt token usage and dynamically computing max_tokens
- Processing and saving the generated patch artifacts

`patcher_main()` is the entrypoint invoked by the orchestrating pipeline.
It performs a full end-to-end patch generation run for all defined
vulnerabilities and outputs machine-readable JSON patches and optional prompt
debug logs.
"""
import argparse, sys
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union
from datetime import datetime, timezone

# local imports
from .config import (
    VULNERABILITIES,
    MODEL_NAME,
    MODEL_VALUE,
)
from .constants import (
    SYSTEM_MESSAGE,
    DEVELOPER_MESSAGE,
)
from .core import (
    AgentFields,
    build_method_flow_snippets,
)
from .utils import (
    combine_prompt_messages,
    build_user_msg_multi,
    mk_agent_fields,
    estimate_prompt_tokens,
    determine_max_tokens,
    process_llm_output,
)

# ================== Environment Setup ==================
load_dotenv()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=getenv("OPENROUTER_API_KEY", "OpenRouter API key not found"),
)

# ================== Helpers ==================
def _save_prompt_debug(messages: List[Dict[str, str]], model_name: str) -> None:
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

# ================== Main ==================
def patcher_main() -> bool:
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Patcher tool")
    parser.add_argument(
        "-sp",
        "--save-prompt",
        action="store_true",
        help="Save the generated Patcher prompt to output/given_prompt.txt for debugging",
    )
    args = parser.parse_args()

    # Repo root (two levels up from this file)
    REPO_ROOT = Path(__file__).resolve().parents[2]

    # Collect (task_id, AgentFields, snippet_or_bundle) tuples.
    tasks: List[Tuple[int, AgentFields, Union[str, Dict[str, str]]]] = []

    for task_index, Vulnerability in enumerate(VULNERABILITIES, start=1):
        agent_fields = mk_agent_fields(Vulnerability)

        # Build a multi-file bundle (includes sink + flow context) using
        # the new method-based code extractor.
        bundle = build_method_flow_snippets(
            repo_root=REPO_ROOT,
            language=agent_fields.language,
            sink=agent_fields.sink,
            flow=agent_fields.flow,
        )

        tasks.append((task_index, agent_fields, bundle))

    # Build final chat messages for OpenRouter API
    messagesArray = combine_prompt_messages(
        SYSTEM_MESSAGE,
        DEVELOPER_MESSAGE,
        build_user_msg_multi(tasks),
    )

    # Estimate prompt token usage and derive max_tokens for this run
    prompt_tokens = estimate_prompt_tokens(messagesArray)
    max_tokens = determine_max_tokens(MODEL_NAME, prompt_tokens)
    print(f"[debug] Estimated prompt tokens: {prompt_tokens}")
    print(f"[debug] Using max_tokens={max_tokens} for model '{MODEL_VALUE}'")

    # Save generated prompt for debugging, run with `-sp` flag
    if args.save_prompt:
        _save_prompt_debug(messagesArray, MODEL_NAME)

    # Send request to OpenRouter
    print(f"====== Sending request to OpenRouter with '{MODEL_VALUE}' ======")
    try:
        completion = client.chat.completions.create(
            model=MODEL_VALUE,
            messages=messagesArray,
            temperature=0.0,
            max_tokens=max_tokens,
        )
    except Exception as e:
        print("OpenRouter error:", e, file=sys.stderr)
        return False

    llm_output = completion.choices[0].message.content or ""
    if llm_output == "":
        print("No output from LLM; read output logs\n", file=sys.stderr)
        return False

    try:
        process_llm_output(llm_output, MODEL_VALUE)
    except ValueError as exc:
        print(f"[fatal] Failed to process LLM output: {exc}", file=sys.stderr)
        return False

    # Patcher run completed successfully    
    return True


# execute main
if __name__ == "__main__":
    patcher_main()
