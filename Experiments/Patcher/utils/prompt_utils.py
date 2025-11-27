# utils/prompt_utils.py
import json
from typing import (
    Union,
    List,
    Iterable,
    Tuple,
    Mapping,
)

# local imports
from constants import VulnerabilityInfo
from core import (
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
