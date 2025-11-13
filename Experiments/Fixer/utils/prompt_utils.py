"""
utils/prompt_utils.py

Purpose:
- Strongly-typed metadata container (AgentFields) for vulnerability-fixing tasks.
- Safe, repo-root-constrained snippet extractors for:
    1) function/range slices (legacy single-file paths)
    2) small windows centered around specific lines (for source→sink data-flow)
- Multi-task USER message builder that supports:
    - Single-file: one snippet
    - Multi-file: labeled per-file bundles from data-flow steps
    - PoV test cases: included for downstream verifier reasoning

Design notes:
- All paths validated against repo_root (prevents directory traversal).
- Arguments after '*' are keyword-only for clarity and safety.
- Use descriptive variable names for readability and maintenance.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import (
    Optional,
    Union,
    List,
    Iterable,
    Tuple,
    Dict,
    TypedDict,
    Mapping,
)
from collections import defaultdict


# ================== Strong typing for structures: constraints, sink, flow, PoV ==================

class ConstraintDict(TypedDict):
    """
    Configuration constraints controlling patch generation limits.
    Enforced by the Fixer when producing diffs.
    """
    max_lines: int
    max_hunks: int
    no_new_deps: bool
    keep_signature: bool


class SinkDict(TypedDict, total=False):
    """Shape for the sink metadata (dangerous call site)."""
    file: str
    line: int
    start_col: int
    end_col: int
    symbol: str


class FlowStepDict(TypedDict, total=False):
    """Shape for one data-flow step (source/propagation)."""
    file: str
    line: int
    note: str


class PoVTestDict(TypedDict, total=False):
    """
    Shape for a Proof-of-Value (PoV) test case the agent can use for feedback.
    - entrypoint: what to run (CLI, method, route, etc.)
    - args/env: execution inputs
    - expected: result expectations used to confirm/negate a patch
    """
    name: str
    description: str
    entrypoint: str
    args: List[str]
    env: Dict[str, str]
    expected: Dict[str, object]


class FileSnippetBundle(TypedDict):
    """
    Multi-file snippet bundle structure:
        {"by_file": { "<repo-relative-path>": "<concatenated snippet text>" } }
    """
    by_file: Dict[str, str]


# ================== Agent metadata container ==================

@dataclass
class AgentFields:
    """
    Metadata describing the vulnerability to fix.

    Required:
        - language: e.g., "Java"
        - function: function/method name ("" if not applicable)
        - CWE: identifier string
        - constraints: strongly-typed ConstraintDict
        - sink: SinkDict (serves as anchor file)
        - flow: list of FlowStepDict entries (source→sink path)
        - pov_tests: list of PoVTestDict entries (for verifier feedback)

    Optional:
        - vuln_title: human-readable short title of the issue
    """
    language: str
    function: str
    CWE: str
    constraints: ConstraintDict
    sink: SinkDict
    flow: List[FlowStepDict] = field(default_factory=list)
    pov_tests: List[PoVTestDict] = field(default_factory=list)
    vuln_title: str = ""

    def to_dict(self) -> Dict[str, object]:
        """JSON-serializable representation for prompt assembly."""
        return {
            "language": self.language,
            "function": self.function,
            "CWE": self.CWE,
            "constraints": self.constraints,
            "vuln_title": self.vuln_title,
            "sink": self.sink,
            "flow": self.flow,
            "pov_tests": self.pov_tests,
        }


# ================== Multi-task USER message builder ==================

def build_user_msg_multi(
    tasks: Iterable[Tuple[int, AgentFields, Union[str, FileSnippetBundle]]]
) -> str:
    """
    Build a composite USER message listing one or more fix tasks.

    Each item = (task_id, AgentFields, snippet_payload)
    snippet_payload can be:
        - str (single-file legacy)
        - {"by_file": {...}} (multi-file bundle)

    Output:
        YAML-like list of tasks used as USER input to the Fixer.
    """
    text_lines: List[str] = []
    text_lines.append(
        "You will receive multiple independent fix tasks. "
        "For each task, produce one patch in the same order, and set `patch_id` equal to the provided `task_id`.\n"
    )
    text_lines.append("tasks:\n")

    for task_id, agent_fields, snippet_payload in tasks:
        fields: Mapping[str, object] = agent_fields.to_dict()

        # Metadata header
        text_lines.append(f"- task_id: {task_id}")
        text_lines.append(f"  language: {json.dumps(fields['language'], ensure_ascii=False)}")
        text_lines.append(f"  function: {json.dumps(fields['function'], ensure_ascii=False)}")
        text_lines.append(f"  CWE: {json.dumps(fields['CWE'], ensure_ascii=False)}")
        text_lines.append("  constraints: " + json.dumps(fields["constraints"], ensure_ascii=False))
        text_lines.append(f"  vuln_title: {json.dumps(fields['vuln_title'], ensure_ascii=False)}")

        # Always include data_flow + PoV tests
        text_lines.append("  data_flow:")
        text_lines.append("    sink: " + json.dumps(fields["sink"], ensure_ascii=False))
        text_lines.append("    flow: " + json.dumps(fields["flow"], ensure_ascii=False))
        text_lines.append("  pov_tests: " + json.dumps(fields["pov_tests"], ensure_ascii=False))

        # Add snippet content
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


# ================== Snippet extractors (repo-root constrained) ==================

def get_vuln_snippet_from_file(
    path: str,
    start_line: Optional[int] = None,
    end_line: Optional[int] = None,
    *,
    repo_root: Union[str, Path],
    context: int = 6,
    max_bytes: int = 2_000_000,
) -> str:
    """
    Extract a function-level or explicit-range snippet from a file.

    Notes:
    - `context` is the number of lines of padding around the requested range
      when either start_line or end_line is missing (default window = 2*context).
    - Arguments after `*` are keyword-only to avoid accidental positional misuse.
    """
    repo_root_path = Path(repo_root).expanduser().resolve()
    target_file = (repo_root_path / Path(path)).resolve()

    if not (target_file == repo_root_path or repo_root_path in target_file.parents):
        raise PermissionError(f"'{target_file}' is outside repo root '{repo_root_path}'.")
    if not target_file.exists():
        raise FileNotFoundError(f"File not found: {target_file}")
    if target_file.stat().st_size > max_bytes:
        raise ValueError(f"File too large: {target_file}")

    file_lines = target_file.read_text(encoding="utf-8").splitlines()
    total_lines = len(file_lines)

    if start_line is None and end_line is None:
        start_index = 1
        end_index = min(total_lines, start_index + context * 2)
    else:
        start_index = max(1, int(start_line or 1))
        end_index = int(end_line or start_index + context * 2)
        if end_index > total_lines:
            end_index = min(total_lines, start_index + context * 2)

    if start_index < 1 or end_index < start_index or start_index > total_lines:
        raise ValueError(f"Invalid range {start_index}-{end_index} for {total_lines} lines.")

    file_relative_path = str(target_file.relative_to(repo_root_path))
    snippet_lines = file_lines[start_index - 1 : end_index]
    header = f"// SNIPPET SOURCE: {file_relative_path} lines {start_index}-{end_index}\n"

    return header + "\n".join(snippet_lines) + ("\n" if snippet_lines and snippet_lines[-1] != "" else "")


def get_snippet_around_line(
    path: str,
    center_line: int,
    *,
    repo_root: Union[str, Path],
    context: int = 4,
    max_bytes: int = 2_000_000,
) -> str:
    """
    Extract a small window of code centered on a specific line.

    Notes:
    - `context` is the number of lines of padding on each side of `center_line`
      (window size = 2*context).
    - Center line is clamped to the file's bounds.
    """
    repo_root_path = Path(repo_root).expanduser().resolve()
    target_file = (repo_root_path / Path(path)).resolve()

    if not (target_file == repo_root_path or repo_root_path in target_file.parents):
        raise PermissionError(f"'{target_file}' is outside repo root '{repo_root_path}'.")
    if not target_file.exists():
        raise FileNotFoundError(f"File not found: {target_file}")
    if target_file.stat().st_size > max_bytes:
        raise ValueError(f"File too large: {target_file}")

    file_lines = target_file.read_text(encoding="utf-8").splitlines()
    total_lines = len(file_lines)
    center_line_number = max(1, min(int(center_line), total_lines))

    start_index = max(1, center_line_number - context)
    end_index = min(total_lines, center_line_number + context)

    file_relative_path = str(target_file.relative_to(repo_root_path))
    header = (
        f"// SNIPPET SOURCE: {file_relative_path} around line {center_line_number} "
        f"[{start_index}-{end_index}]\n"
    )

    snippet_block = file_lines[start_index - 1 : end_index]
    return header + "\n".join(snippet_block) + ("\n" if end_index <= total_lines else "")


# ================== Build multi-file snippet bundles (for data-flow) ==================

def build_flow_context_snippets(
    *,
    repo_root: Union[str, Path],
    sink: SinkDict,
    flow: List[FlowStepDict],
    base_context: int = 4,
) -> FileSnippetBundle:
    """
    Given a sink and a list of flow steps (each with file + line), build a per-file
    snippet bundle that we pass to the LLM. This ensures the model can see all
    relevant files and the rough path from source → sink.

    The returned structure is:
      {"by_file": { "<repo-relative-path>": "<concatenated annotated snippets>" }}
    """
    snippets_by_path: Dict[str, List[str]] = defaultdict(list)
    linearized_steps: List[Tuple[str, int, str]] = []

    # Flow steps (if any)
    for step in flow or []:
        linearized_steps.append((step["file"], int(step["line"]), step.get("note", "flow step")))

    # Sink is always included
    linearized_steps.append(
        (sink["file"], int(sink.get("line", 1)), f"sink: {sink.get('symbol', '')}".strip())
    )

    # Group by file and collect annotated windows
    linearized_steps.sort(key=lambda info: (info[0], info[1]))

    for repo_relative_path, line_number, note in linearized_steps:
        snippet_text = get_snippet_around_line(
            repo_relative_path,
            line_number,
            repo_root=repo_root,
            context=base_context,
        )
        snippets_by_path[repo_relative_path].append(
            f"// ---- {note} @ line {line_number} ----\n{snippet_text}"
        )

    return {"by_file": {path: "\n".join(blocks) for path, blocks in snippets_by_path.items()}}
