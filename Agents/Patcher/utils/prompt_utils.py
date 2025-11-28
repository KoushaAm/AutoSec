# Patcher//utils/prompt_utils.py
import json
from typing import (
    Any,
    Dict,
    Union,
    List,
    Iterable,
    Tuple,
    Mapping,
)

# local imports
from ..config import (
    DEFAULT_CONTEXT_LIMIT,
    MODEL_CONTEXT_LIMITS
)
from ..constants import VulnerabilityInfo
from ..core import (
    AgentFields,
    ConstraintDict,
    SinkDict,
    FlowStepDict,
    PoVTestDict,
    FileSnippetBundle
)

# ================== Multi-task USER message builder ==================
def build_user_msg_multi(
    tasks: Iterable[Tuple[int, AgentFields, Union[str, FileSnippetBundle]]]
) -> str:
    """
    Build a composite USER message listing multiple patch tasks.

    Each item = (task_id, AgentFields, snippet_payload)
    snippet_payload can be:
        - str (single snippet)
        - {"by_file": {...}} (multi-file data-flow bundle)

    Output:
        YAML-like list of patch tasks, used as USER prompt to the Patcher.

    The Patcher LLM must output:
        patches: [
          {
            "patch_id": <task_id>,
            "plan": [...],
            "cwe_matches": [...],
            ...
          }
        ]
    """
    text_lines: List[str] = []
    text_lines.append(
        "You will receive one or more independent PATCH TASKS.\n"
        "For each task, generate exactly one patch object.\n"
        "The patch's `patch_id` MUST equal the provided `task_id`.\n"
    )
    text_lines.append("tasks:\n")

    for task_id, agent_fields, snippet_payload in tasks:
        fields: Mapping[str, object] = agent_fields.to_dict()

        # --- Metadata header
        text_lines.append(f"- task_id: {task_id}")
        text_lines.append(f"  language: {json.dumps(fields['language'], ensure_ascii=False)}")
        text_lines.append(f"  function: {json.dumps(fields['function'], ensure_ascii=False)}")
        text_lines.append(f"  CWE: {json.dumps(fields['CWE'], ensure_ascii=False)}")
        text_lines.append("  constraints: " + json.dumps(fields["constraints"], ensure_ascii=False))
        text_lines.append(f"  vuln_title: {json.dumps(fields['vuln_title'], ensure_ascii=False)}")

        # --- Always include data-flow + PoV
        text_lines.append("  data_flow:")
        text_lines.append("    sink: " + json.dumps(fields["sink"], ensure_ascii=False))
        text_lines.append("    flow: " + json.dumps(fields["flow"], ensure_ascii=False))
        text_lines.append("  pov_tests: " + json.dumps(fields["pov_tests"], ensure_ascii=False))

        # --- Snippet payload (either single or multi-file)
        language_tag = str(fields["language"]).lower()

        if isinstance(snippet_payload, dict) and "by_file" in snippet_payload:
            text_lines.append("  vulnerable_snippets:")
            for path_key, code_text in snippet_payload["by_file"].items():
                text_lines.append(f"  - path: {json.dumps(path_key)}")
                text_lines.append("    code: |")
                for line in code_text.splitlines():
                    text_lines.append(f"      {line}")
            text_lines.append("")
        else:
            snippet_text = str(snippet_payload).strip()
            text_lines.append("  vulnerable_snippet:")
            text_lines.append(f"  ```{language_tag}")
            text_lines.append("\n".join("  " + line for line in snippet_text.splitlines()))
            text_lines.append("  ```\n")

    return "\n".join(text_lines)


def mk_agent_fields(vuln_class: VulnerabilityInfo) -> AgentFields:
    """
    Construct strongly-typed AgentFields from a vuln_info.* class.
    The vuln_info base class validates structure at import time, so
    we can rely on these attributes existing and being well-formed.
    """
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

def estimate_prompt_tokens(messages: List[Dict[str, Any]]) -> int:
    """
    Very rough token estimate: tokens ≈ total_characters / 4.

    This doesn't need to be exact; it just keeps us inside the model's
    context window when we set max_tokens for the completion.
    """
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total_chars += len(content)
        else:
            # In case of non-string content (tools, etc.), stringify.
            total_chars += len(str(content))
    # Avoid zero tokens, always at least a small positive number
    return max(1, total_chars // 4)


def determine_max_tokens(model_name: str, prompt_tokens: int) -> int:
    """
    Decide a max_tokens value based on:
      - estimated prompt_tokens
      - an approximate context limit per model

    Strategy:
      - max_ctx = context limit (prompt + completion)
      - reserve a small safety margin (e.g., 256 tokens)
      - max_tokens = max_ctx - prompt_tokens - margin
      - clamp to a reasonable [min_out, max_out] range
    """
    max_ctx = MODEL_CONTEXT_LIMITS.get(model_name, DEFAULT_CONTEXT_LIMIT)

    # Margin to avoid hitting hard context limit (tooling, small errors, etc.)
    SAFETY_MARGIN = 256

    # Floor and ceiling for response size. You can tune this depending on how
    # large your patches typically are.
    MIN_OUT = 512     # don't go lower than this unless we absolutely must
    MAX_OUT = 6000    # arbitrary ceiling to avoid insane completions

    available = max_ctx - prompt_tokens - SAFETY_MARGIN
    if available <= 0:
        # Worst case: prompt already uses (or slightly exceeds) the window.
        # Still request a small number of tokens; model/host will truncate if needed.
        return MIN_OUT

    # Clamp available to our [MIN_OUT, MAX_OUT] band
    if available < MIN_OUT:
        return available
    if available > MAX_OUT:
        return MAX_OUT
    return available