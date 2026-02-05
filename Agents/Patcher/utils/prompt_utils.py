# Patcher/utils/prompt_utils.py
import json
from typing import Any, Dict, Union, List, Mapping

from ..config import DEFAULT_CONTEXT_LIMIT, MODEL_CONTEXT_LIMITS
from ..core import AgentFields, FileSnippetBundle

def build_user_msg_single(
    task_id: int,
    agent_fields: AgentFields,
    snippet_payload: Union[str, FileSnippetBundle],
) -> str:
    """
    Build a USER message for exactly ONE patch task.
    """
    fields: Mapping[str, object] = agent_fields.to_dict()

    text_lines: List[str] = []
    text_lines.append(
        "You will receive exactly ONE independent PATCH TASK.\n"
        "Generate exactly ONE patch object.\n"
        "The patch's `patch_id` MUST equal the provided `task_id`.\n"
    )

    text_lines.append("task:\n")
    text_lines.append(f"  task_id: {task_id}")
    text_lines.append(f"  language: {json.dumps(fields['language'], ensure_ascii=False)}")
    text_lines.append(f"  function: {json.dumps(fields['function'], ensure_ascii=False)}")
    text_lines.append(f"  CWE: {json.dumps(fields['CWE'], ensure_ascii=False)}")
    text_lines.append("  constraints: " + json.dumps(fields["constraints"], ensure_ascii=False))
    text_lines.append(f"  vuln_title: {json.dumps(fields['vuln_title'], ensure_ascii=False)}")

    text_lines.append("  data_flow:")
    text_lines.append("    sink: " + json.dumps(fields["sink"], ensure_ascii=False))
    text_lines.append("    flow: " + json.dumps(fields["flow"], ensure_ascii=False))
    text_lines.append("  pov_tests: " + json.dumps(fields["pov_tests"], ensure_ascii=False))

    if isinstance(snippet_payload, dict) and "by_file" in snippet_payload:
        text_lines.append("  vulnerable_snippets:")
        for path_key, code_text in snippet_payload["by_file"].items():
            text_lines.append(f"  - path: {json.dumps(path_key, ensure_ascii=False)}")
            text_lines.append("    code: |")
            for line in code_text.splitlines():
                text_lines.append(f"      {line}")
        text_lines.append("")
    else:
        snippet_text = str(snippet_payload).strip()
        text_lines.append("  vulnerable_snippet:")
        text_lines.append("    code: |")
        for line in snippet_text.splitlines():
            text_lines.append(f"      {line}")
        text_lines.append("")

    return "\n".join(text_lines)

# keep estimate_prompt_tokens + determine_max_tokens unchanged
def estimate_prompt_tokens(messages: List[Dict[str, Any]]) -> int:
    total_chars = 0
    for msg in messages:
        content = msg.get("content", "")
        total_chars += len(content) if isinstance(content, str) else len(str(content))
    return max(1, total_chars // 4)

def determine_max_tokens(model_name: str, prompt_tokens: int) -> int:
    max_ctx = MODEL_CONTEXT_LIMITS.get(model_name, DEFAULT_CONTEXT_LIMIT)
    SAFETY_MARGIN = 256
    MIN_OUT = 512
    MAX_OUT = 6000

    available = max_ctx - prompt_tokens - SAFETY_MARGIN
    if available <= 0:
        return MIN_OUT
    if available < MIN_OUT:
        return available
    if available > MAX_OUT:
        return MAX_OUT
    return available
