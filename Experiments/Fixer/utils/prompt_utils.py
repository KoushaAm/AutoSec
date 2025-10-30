# utils/prompt_utils.py
import json
from pathlib import Path
from typing import Optional, Union, List

"""
Encapsulates metadata fields relevant to a vulnerability fixing agent.
Provides helpers to build prompts and to safely extract code snippets from disk.
"""

class AgentFields:
    def __init__(
        self,
        language: str = "",
        file: str = "",
        function: str = "",
        CWE: str = "",
        vuln_title: str = "",
        constraints: Optional[dict] = None,
        pov_root_cause: str = ""
    ):
        self.language = language
        self.file = file
        self.function = function
        self.CWE = CWE
        self.vuln_title = vuln_title
        self.constraints = constraints or {}
        self.pov_root_cause = pov_root_cause

    def to_dict(self):
        return {
            "language": self.language,
            "file": self.file,
            "function": self.function,
            "CWE": self.CWE,
            "vuln_title": self.vuln_title,
            "constraints": self.constraints,
            "pov_root_cause": self.pov_root_cause,
        }


def build_user_msg(agent_fields, vuln_snippet: str) -> str:
    """
    Build a user message from AgentFields (or dict) and a vulnerable snippet.
    """
    if hasattr(agent_fields, "to_dict"):
        fields = agent_fields.to_dict()
    elif isinstance(agent_fields, dict):
        fields = agent_fields
    else:
        raise TypeError("agent_fields must be AgentFields or dict")

    def jq(val):
        return json.dumps(val, ensure_ascii=False)

    constraints = fields.get("constraints") or {}
    constraints_json = json.dumps(constraints, separators=(", ", ": "), ensure_ascii=False)

    parts = []
    parts.append("Fields provided to the agent:")
    parts.append(f"- language: {jq(fields.get('language', ''))}")
    parts.append(f"- file: {jq(fields.get('file', ''))}")
    parts.append(f"- function: {jq(fields.get('function', ''))}")
    parts.append(f"- CWE: {jq(fields.get('CWE', ''))}")
    parts.append(f"- vuln_title: {jq(fields.get('vuln_title', ''))}")
    parts.append(f"- constraints: {constraints_json}")
    parts.append(f"- pov_root_cause: {jq(fields.get('pov_root_cause', ''))}")

    parts.append("\nVulnerable snippet:")
    parts.append(f"```{(fields.get('language', '') or 'text').lower()}")
    parts.append(vuln_snippet.strip())
    parts.append("```")

    return "\n".join(parts)


# ============= Extract Vuln Snippet from File =============
def get_vuln_snippet_from_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    context: int = 2,
    *,
    repo_root: Union[str, Path],  # required now
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