# utils/prompt_utils.py
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional, Union, List, Iterable, Tuple

"""
Encapsulates metadata fields relevant to a vulnerability fixing agent.
Provides helpers to build prompts and to safely extract code snippets from disk.
"""

# ============ AgentFields dataclass =============
@dataclass
class AgentFields:
    language: str = ""
    file: str = ""
    function: str = ""
    CWE: str = ""
    constraints: Optional[dict] = None
    vuln_title: str = ""
    pov_root_cause: str = ""

    def __post_init__(self):
        if self.constraints is None:
            self.constraints = {}

    def to_dict(self):
        return {
            "language": self.language,
            "file": self.file,
            "function": self.function,
            "CWE": self.CWE,
            "constraints": self.constraints,
            "vuln_title": self.vuln_title,
            "pov_root_cause": self.pov_root_cause,
        }

# ============= Multi-task User message builder (handles single-task too) =============
def build_user_msg_multi(tasks: Iterable[Tuple[int, AgentFields, str]]) -> str:
    """
    Build a composite USER message that lists one or more tasks.
    Each item is (task_id, AgentFields, vulnerable_snippet).
    The Developer prompt should require patch_id == task_id and same ordering.

    Pass a list with one element for single-task mode.
    """
    parts: List[str] = []
    parts.append(
        "You will receive multiple independent fix tasks. "
        "For each task, produce one patch in the same order, and set `patch_id` equal to the provided `task_id`.\n"
    )
    parts.append("tasks:\n")

    for task_id, agent_fields, vuln_snippet in tasks:
        fields = agent_fields.to_dict() if hasattr(agent_fields, "to_dict") else dict(agent_fields)
        # fields
        parts.append(f"- task_id: {task_id}")
        parts.append(f"  language: {json.dumps(fields.get('language',''), ensure_ascii=False)}")
        parts.append(f"  file: {json.dumps(fields.get('file',''), ensure_ascii=False)}")
        parts.append(f"  function: {json.dumps(fields.get('function',''), ensure_ascii=False)}")
        parts.append(f"  CWE: {json.dumps(fields.get('CWE',''), ensure_ascii=False)}")
        constraints = fields.get("constraints") or {}
        parts.append("  constraints: " + json.dumps(constraints, separators=(", ", ": "), ensure_ascii=False))
        parts.append(f"  vuln_title: {json.dumps(fields.get('vuln_title',''), ensure_ascii=False)}")
        parts.append(f"  pov_root_cause: {json.dumps(fields.get('pov_root_cause',''), ensure_ascii=False)}")

        # language fence heuristic for nicer rendering
        lang = (fields.get("language", "") or "text").lower()
        parts.append("  vulnerable_snippet:")
        parts.append(f"  ```{lang}")
        parts.append("\n".join("  " + line for line in vuln_snippet.strip().splitlines()))
        parts.append("  ```\n")

    return "\n".join(parts)

# ============= Extract Vuln Snippet from File =============
def get_vuln_snippet_from_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    context: int = 2,
    *,
    repo_root: Union[str, Path],
    max_bytes: int = 2_000_000,
) -> str:
    """
    Read a snippet safely from a file given its path RELATIVE TO repo_root.

    Example:
        get_vuln_snippet_from_file(
            "Experiments/vulnerable/CWE_78.java",
            start_line=5,
            end_line=14,
            repo_root="AutoSec/Experiments"
        )
    """
    rr = Path(repo_root).expanduser().resolve()
    raw = Path(path)
    file_p = (rr / raw).resolve()

    # Ensure containment within the repo root
    if not (file_p == rr or rr in file_p.parents):
        raise PermissionError(f"'{file_p}' is outside repo root '{rr}'.")

    if not file_p.exists():
        raise FileNotFoundError(f"File not found: {file_p}")

    size = file_p.stat().st_size
    if size > max_bytes:
        raise ValueError(f"File too large: {size} > {max_bytes}")

    raw_lines = file_p.read_text(encoding="utf-8").splitlines()
    total = len(raw_lines)

    if start_line is None and end_line is None:
        s, e = 1, total
    else:
        s = max(1, int(start_line))
        e = int(end_line) if end_line is not None else min(total, s + context * 2)

    if s < 1 or e < s or s > total:
        raise ValueError(f"Invalid range {s}-{e} for {total} lines")

    rel_display = str(file_p.relative_to(rr))
    snippet = raw_lines[s - 1 : e]
    header = f"// SNIPPET SOURCE: {rel_display} lines {s}-{e}\n"
    return header + "\n".join(snippet) + ("\n" if snippet and snippet[-1] != "" else "")

# ============= Helper functions for OpenRouter interaction =============
def supports_developer_role(client, model):
    """Check if the model supports 'developer' role by sending a test message."""
    test_msgs = [
        {"role": "system", "content": "You are an obedient assistant."},
        {"role": "developer", "content": "If you see this, answer DEVELOPER_OK only."},
        {"role": "user", "content": "What do you reply?"}
    ]
    try:
        req = client.chat.completions.create(model=model, messages=test_msgs, max_tokens=100)
        res = req.choices[0].message.content
        return "DEVELOPER_OK" in (res or "")
    except Exception:
        return False

def get_messages(client, model, system_msg, developer_msg, user_msg, ignore_developer_support_check=False) -> List[dict]:
    """
    Build messages array for OpenRouter chat completion.
    If the model does not support 'developer' role, merge developer policies into system message.
    """
    if not ignore_developer_support_check and not supports_developer_role(client, model):
        print(f"=== Model {model} does not support 'developer' role; merging into system message === \n\n")
        # collapse developer into system
        combined_system = system_msg + "\n\n--- Developer policies merged ---\n" + developer_msg
        return [
            {"role": "system", "content": combined_system},
            {"role": "user", "content": user_msg},
        ]
    return [
        {"role": "system", "content": system_msg},
        {"role": "developer", "content": developer_msg},
        {"role": "user", "content": user_msg},
    ]
