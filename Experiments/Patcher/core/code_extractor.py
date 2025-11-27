# core/code_extractor.py
"""
Method-based, flow-aware code extractor for the Patcher.

Given a data-flow (sink + flow steps), it returns a FileSnippetBundle 
where each entry is a concatenation of whole methods that participate 
in the flow.

Key properties:
- Uses tree-sitter-backed MethodLocator (e.g., JavaMethodLocator).
- One snippet per method per file (no overlapping snippets).
- Minimal context: method bodies only, plus a small header summarizing flow.
- Fallback: if a flow line is not inside any method, we emit a single
  line-window block for that file covering all such points.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union

# local imports
from .types import SinkDict, FlowStepDict, FileSnippetBundle
from .method_locator import get_method_locator, MethodInfo


@dataclass(frozen=True)
class _FlowPoint:
    """
    Internal representation of a single data-flow point in a file.

    Attributes:
        line:  1-based line number in the file.
        note:  Human-readable note (from vuln FLOW or sink symbol).
        kind:  "flow" for intermediate steps, "sink" for the primary sink.
    """
    line: int
    note: str
    kind: str  # "flow" or "sink"


def _normalize_repo_root(repo_root: Union[str, Path]) -> Path:
    """Expand, resolve, and normalize the repo_root path."""
    return Path(repo_root).expanduser().resolve()


def build_method_flow_snippets(
    *,
    repo_root: Union[str, Path],
    language: str,
    sink: SinkDict,
    flow: List[FlowStepDict],
) -> FileSnippetBundle:
    """
    Build a FileSnippetBundle containing minimal, non-overlapping method snippets
    that cover all source→sink flow steps plus the sink.

    Args:
        repo_root: Absolute or relative path to the repository root.
        language: Logical language tag (e.g., "Java").
        sink: SinkDict metadata from vuln_info (file, line, symbol).
        flow: List of FlowStepDict representing the source→sink trace.

    Returns:
        {
          "by_file": {
            "<repo-relative-path>": "<annotated method snippets for that file>"
          }
        }
    """
    repo_root_path = _normalize_repo_root(repo_root)
    locator = get_method_locator(language, repo_root_path)

    # 1) Collect flow points per repo-relative file path.
    points_by_file: Dict[str, List[_FlowPoint]] = {}

    # Flow steps first (preserve logical order, but we sort by line later per file).
    for step in flow or []:
        rel_path = str(step["file"])
        line = int(step["line"])
        note = step.get("note", "flow step")
        points_by_file.setdefault(rel_path, []).append(
            _FlowPoint(line=line, note=note, kind="flow")
        )

    # Sink last.
    sink_rel_path = str(sink["file"])
    sink_line = int(sink.get("line", 1))
    sink_note = f"sink: {sink.get('symbol', '')}".strip() or "sink"
    points_by_file.setdefault(sink_rel_path, []).append(
        _FlowPoint(line=sink_line, note=sink_note, kind="sink")
    )

    by_file: Dict[str, str] = {}

    # 2) For each file, resolve lines to methods and build snippets.
    for rel_path in sorted(points_by_file.keys()):
        file_points = points_by_file[rel_path]
        abs_path = (repo_root_path / rel_path).resolve()

        # Map (start_line, end_line) -> {"info": MethodInfo, "points": [FlowPoint]}
        methods_for_file: Dict[Tuple[int, int], Dict[str, object]] = {}
        # Points that are not inside any method.
        fallback_points: List[_FlowPoint] = []

        for fp in file_points:
            try:
                mi: MethodInfo | None = locator.find_method_for_line(abs_path, fp.line)
            except ValueError:
                # File outside repo_root according to locator: treat as fallback.
                mi = None

            if mi is None:
                fallback_points.append(fp)
                continue

            key = (mi.start_line, mi.end_line)
            bucket = methods_for_file.setdefault(key, {"info": mi, "points": []})
            bucket["points"].append(fp)  # type: ignore[assignment]

        # Read source if possible; otherwise emit a placeholder.
        try:
            source_text = abs_path.read_text(encoding="utf-8")
            lines = source_text.splitlines()
        except FileNotFoundError:
            by_file[rel_path] = f"// FILE MISSING: {rel_path}\n"
            continue

        snippets: List[str] = []

        # File header at the top.
        snippets.append(f"// FILE: {rel_path}")

        # 2a) Emit method snippets, sorted by start_line.
        for (start_line, end_line), payload in sorted(
            methods_for_file.items(), key=lambda item: item[0][0]
        ):
            mi: MethodInfo = payload["info"]  # type: ignore[assignment]
            points: List[_FlowPoint] = payload["points"]  # type: ignore[assignment]

            # Header: method + flow summary.
            header_lines: List[str] = []
            header_lines.append(
                f"// METHOD: {mi.name} [{mi.start_line}-{mi.end_line}]"
            )

            if points:
                header_lines.append("// FLOW:")
                for fp in sorted(points, key=lambda p: p.line):
                    header_lines.append(f"//   - line {fp.line}: {fp.note}")

            # Method body (clamped to file length for safety).
            start_idx = max(1, mi.start_line) - 1
            end_idx = min(len(lines), mi.end_line)
            body_lines = lines[start_idx:end_idx]

            snippets.append("\n".join(header_lines))
            snippets.extend(body_lines)
            snippets.append("")  # blank line separator between methods/blocks

        # 2b) Fallback: lines not contained in any method -> single window block.
        if fallback_points:
            # Compute a single window that covers all fallback points to avoid overlap.
            all_lines = sorted(fp.line for fp in fallback_points)
            min_line = max(1, all_lines[0])
            max_line = min(len(lines), all_lines[-1])

            # Small context around min/max (similar to old window-based extractor).
            context = 4
            block_start = max(1, min_line - context)
            block_end = min(len(lines), max_line + context)

            header_lines: List[str] = []
            header_lines.append(
                f"// BLOCK: {rel_path} [lines {block_start}-{block_end}]"
            )
            header_lines.append("// FLOW:")
            for fp in sorted(fallback_points, key=lambda p: p.line):
                header_lines.append(f"//   - line {fp.line}: {fp.note}")

            body_lines = lines[block_start - 1 : block_end]

            snippets.append("\n".join(header_lines))
            snippets.extend(body_lines)
            snippets.append("")  # separator

        by_file[rel_path] = "\n".join(snippets).rstrip() + "\n"

    return {"by_file": by_file}


__all__ = [
    "build_method_flow_snippets",
]
