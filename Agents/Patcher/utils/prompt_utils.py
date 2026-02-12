# Agents/Patcher/utils/prompt_utils.py
import json
from typing import Any, Dict, List, Union

from ..config import DEFAULT_CONTEXT_LIMIT, MODEL_CONTEXT_LIMITS
from ..core.types import VulnerabilitySpec, FileSnippetBundle


def build_patch_prompt(
    task_id: int,
    spec: VulnerabilitySpec,
    snippet_payload: Union[str, FileSnippetBundle],
) -> str:
    """
    Build a USER message for exactly ONE vulnerability patch task.

    This prompt is Finder-aligned and must remain stable:
    - One prompt per VulnerabilitySpec (unique vulnerability instance)
    - Includes ALL traces + derived sink + exploiter pov_logic
    - Includes extracted snippets for all referenced files
    """
    fields: Dict[str, Any] = spec.to_dict()

    text_lines: List[str] = []
    text_lines.append(
        "You will receive exactly ONE independent PATCH TASK.\n"
        "Generate exactly ONE patch object.\n"
        "The patch's `patch_id` MUST equal the provided `task_id`.\n"
    )

    text_lines.append("task:\n")
    text_lines.append(f"  task_id: {task_id}")
    text_lines.append(f"  language: {json.dumps(fields['language'], ensure_ascii=False)}")
    text_lines.append(f"  cwe_id: {json.dumps(fields['cwe_id'], ensure_ascii=False)}")
    text_lines.append(f"  project_name: {json.dumps(fields['project_name'], ensure_ascii=False)}")
    text_lines.append("  constraints: " + json.dumps(fields["constraints"], ensure_ascii=False))

    # Finder-aligned: traces + sink
    text_lines.append("  traces: " + json.dumps(fields["traces"], ensure_ascii=False))
    text_lines.append("  sink: " + json.dumps(fields["sink"], ensure_ascii=False))

    # Exploiter context (PoV)
    text_lines.append(f"  pov_logic: {json.dumps(fields.get('pov_logic', ''), ensure_ascii=False)}")

    # Guidance that matches your new rules
    text_lines.append(
        "  patch_rules: |\n"
        "    - Fix ONLY this vulnerability instance.\n"
        "    - Prefer a single-file fix whenever possible.\n"
        "    - Patch multiple files ONLY if it cannot be resolved in a single file.\n"
        "    - Keep changes minimal while fully mitigating all trace paths.\n"
        "    - Respect constraints (no new deps if no_new_deps=true; keep signature if keep_signature=true).\n"
    )

    # Snippets
    if isinstance(snippet_payload, dict) and "by_file" in snippet_payload:
        text_lines.append("  vulnerable_snippets:")
        for path_key, code_text in snippet_payload["by_file"].items():
            text_lines.append(f"  - path: {json.dumps(path_key, ensure_ascii=False)}")
            text_lines.append("    code: |")
            for line in str(code_text).splitlines():
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
