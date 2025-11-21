"""
utils/prompt_utils.py

Purpose:
- Strongly-typed metadata container (AgentFields) for patch-generation tasks.
- Safe, repo-root-constrained snippet extractors for:
    1) function/range slices (legacy single-file)
    2) line-centered windows for source→sink data-flow
- Multi-task USER message builder supporting:
    - Single-file snippet
    - Multi-file bundles for data-flow (source→sink)
    - PoV test cases for downstream patch verification

Design notes:
- All filesystem paths are validated against repo_root (prevents traversal).
- Arguments after '*' are keyword-only for safety and clarity.
- The LLM receives all context needed for accurate patch generation.
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import (
    Union,
    List,
    Iterable,
    Tuple,
    Dict,
    TypedDict,
    Mapping,
)
from collections import defaultdict


# ================== Strong typing for constraints, sink, flow, PoV ==================
class ConstraintDict(TypedDict):
    """
    Configuration constraints controlling patch generation limits.
    Enforced by the Patcher when producing diffs.
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
        {"by_file": { "<repo-relative-path>": "<concatenated snippet text>" }}
    """
    by_file: Dict[str, str]


# ================== Agent metadata container ==================
@dataclass
class AgentFields:
    """
    Metadata describing the vulnerability to patch.

    Required:
        - language: e.g., "Java"
        - function: method name (or "" for global)
        - CWE: identifier string
        - constraints: strongly-typed ConstraintDict
        - sink: SinkDict (primary file & line containing the sink)
        - flow: list of FlowStepDict (source→sink propagation)
        - pov_tests: list of PoVTestDict for guided reasoning

    Optional:
        - vuln_title: human-readable short title
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


# ================== Snippet extractors (repo-root constrained) ==================
def get_snippet_around_line(
    path: str,
    center_line: int,
    *,
    repo_root: Union[str, Path],
    context: int = 4,
    max_bytes: int = 2_000_000,
) -> str:
    """
    Extract a small window of code centered on a line.
    Used to show the LLM the source→sink context.
    """
    repo_root_path = Path(repo_root).expanduser().resolve()
    target_file = (repo_root_path / Path(path)).resolve()

    if not (target_file == repo_root_path or repo_root_path in target_file.parents):
        raise PermissionError(f"'{target_file}' is outside repo root '{repo_root_path}'.")
    if not target_file.exists():
        raise FileNotFoundError(f"File not found: {target_file}")
    if target_file.stat().st_size > max_bytes:
        raise ValueError(f"File too large: {target_file}")

    lines = target_file.read_text(encoding="utf-8").splitlines()
    total = len(lines)
    clamped_line = max(1, min(int(center_line), total))

    start_idx = max(1, clamped_line - context)
    end_idx = min(total, clamped_line + context)

    rel_path = str(target_file.relative_to(repo_root_path))
    header = f"// SNIPPET SOURCE: {rel_path} around line {clamped_line} [{start_idx}-{end_idx}]\n"

    snippet = lines[start_idx - 1 : end_idx]
    return header + "\n".join(snippet) + ("\n" if end_idx <= total else "")


# ================== Multi-file snippet bundle for data-flow ==================
def build_flow_context_snippets(
    *,
    repo_root: Union[str, Path],
    sink: SinkDict,
    flow: List[FlowStepDict],
    base_context: int = 4,
) -> FileSnippetBundle:
    """
    Returns:
        {"by_file": { "<repo-relative-path>": "<annotated concatenated snippets>" }}

    Provides complete source→sink context.
    """
    snippets_by_path: Dict[str, List[str]] = defaultdict(list)
    linearized: List[Tuple[str, int, str]] = []

    # Flow steps first
    for step in flow or []:
        linearized.append((step["file"], int(step["line"]), step.get("note", "flow step")))

    # Sink last
    linearized.append(
        (sink["file"], int(sink.get("line", 1)), f"sink: {sink.get('symbol', '')}".strip())
    )

    # Sort by filename, then line number
    linearized.sort(key=lambda tup: (tup[0], tup[1]))

    # Extract per-file snippets
    for rel_path, line_no, note in linearized:
        snippet = get_snippet_around_line(
            rel_path,
            line_no,
            repo_root=repo_root,
            context=base_context,
        )
        snippets_by_path[rel_path].append(
            f"// ---- {note} @ line {line_no} ----\n{snippet}"
        )

    return {"by_file": {p: "\n".join(blocks) for p, blocks in snippets_by_path.items()}}
