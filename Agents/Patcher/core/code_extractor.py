# core/code_extractor.py
"""
Trace-driven, method-aware code extractor for the Patcher.

Given a VulnerabilitySpec (Finder-aligned traces), returns a FileSnippetBundle
where each entry is a concatenation of whole methods that participate in the
traces (including sink), grouped per file.

Key properties:
- Uses tree-sitter-backed MethodLocator (e.g., JavaMethodLocator).
- One snippet per method per file (no overlapping method snippets).
- Minimal context: method bodies only + a small header summarizing trace points.
- Fallback: if a trace line is not inside any method, emit a single line-window
  block for that file covering all such points.
- Dedup: trace points are deduped by (uri, line, message).
- Line caps: respects spec.constraints["max_lines"] as a PER-FILE soft cap.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Union, Set

from .types import VulnerabilitySpec, TraceStepDict, FileSnippetBundle
from .method_locator import get_method_locator, MethodInfo


@dataclass(frozen=True)
class _TracePoint:
    """
    Internal representation of a single trace point in a file.

    Attributes:
        line:  1-based line number in the file.
        note:  Human-readable note (from Finder step.message).
        kind:  "trace" for normal steps, "sink" for the derived sink step.
    """
    line: int
    note: str
    kind: str  # "trace" or "sink"


def _normalize_repo_root(repo_root: Union[str, Path]) -> Path:
    """Expand, resolve, and normalize the repo_root path."""
    return Path(repo_root).expanduser().resolve()


def _prefix_uri(project_name: str, uri: str) -> str:
    """
    Convert Finder uri (e.g. 'src/main/java/...') into repo-relative path
    used in this repo layout:

        Projects/Sources/<project_name>/<uri>

    Finder guarantees no leading '/', but we still sanitize.
    """
    clean = uri.lstrip("/").strip()
    return f"Projects/Sources/{project_name}/{clean}"


def extract_snippets_for_vuln(
    *,
    spec: VulnerabilitySpec,
    repo_root: Union[str, Path],
    context_lines: int = 4,
) -> FileSnippetBundle:
    """
    Build a FileSnippetBundle containing minimal, non-overlapping method snippets
    that cover all trace steps (across all traces) plus the derived sink.

    Args:
        spec: VulnerabilitySpec (Finder-aligned).
        repo_root: Absolute or relative path to the AutoSec repo root.
        context_lines: Fallback window context lines around non-method points.

    Returns:
        {
          "by_file": {
            "<repo-relative-path>": "<annotated method snippets for that file>"
          }
        }
    """
    sink_step = spec.sink
    sink_uri = (sink_step.get("uri") or "").strip()
    sink_line = int(sink_step.get("line") or 0)

    if not sink_uri or sink_line < 1:
        raise ValueError(f"Invalid sink in VulnerabilitySpec: uri={sink_uri!r} line={sink_line!r}")

    
    repo_root_path = _normalize_repo_root(repo_root)
    locator = get_method_locator(spec.language, repo_root_path)

    # 1) Collect trace points per repo-relative file path.
    points_by_file: Dict[str, List[_TracePoint]] = {}

    seen_points: Set[Tuple[str, int, str]] = set()

    # Gather ALL steps from ALL traces.
    for trace in spec.traces:
        for step in trace:
            uri = step["uri"]
            line = int(step["line"])
            msg = (step.get("message") or "").strip()
            key = (uri, line, msg)
            if key in seen_points:
                continue
            seen_points.add(key)

            rel_path = _prefix_uri(spec.project_name, uri)
            points_by_file.setdefault(rel_path, []).append(
                _TracePoint(line=line, note=msg or "trace step", kind="trace")
            )

    # Ensure sink is explicitly marked as sink (even if already present as a normal step).
    sink_step: TraceStepDict = spec.sink
    sink_rel_path = _prefix_uri(spec.project_name, sink_step["uri"])
    sink_line = int(sink_step["line"])
    sink_note = (sink_step.get("message") or "").strip() or "sink"
    points_by_file.setdefault(sink_rel_path, []).append(
        _TracePoint(line=sink_line, note=sink_note, kind="sink")
    )

    by_file: Dict[str, str] = {}
    per_file_cap = int(spec.constraints["max_lines"])

    # 2) For each file, resolve lines to methods and build snippets.
    for rel_path in sorted(points_by_file.keys()):
        file_points = points_by_file[rel_path]
        abs_path = (repo_root_path / rel_path).resolve()
        rel_path_obj = Path(rel_path)

        # Map (start_line, end_line) -> {"info": MethodInfo, "points": [_TracePoint]}
        methods_for_file: Dict[Tuple[int, int], Dict[str, object]] = {}
        fallback_points: List[_TracePoint] = []

        for tp in file_points:
            try:
                mi: MethodInfo | None = locator.find_method_for_line(rel_path_obj, tp.line)
            except ValueError:
                mi = None

            if mi is None:
                fallback_points.append(tp)
                continue

            key = (mi.start_line, mi.end_line)
            bucket = methods_for_file.setdefault(key, {"info": mi, "points": []})
            bucket["points"].append(tp)  # type: ignore[assignment]

        # Read source if possible; otherwise emit a placeholder.
        try:
            source_text = abs_path.read_text(encoding="utf-8")
            lines = source_text.splitlines()
        except FileNotFoundError:
            by_file[rel_path] = f"// FILE MISSING: {rel_path}\n"
            continue

        snippets: List[str] = []
        used_line_budget = 0

        # File header.
        snippets.append(f"// FILE: {rel_path}")
        used_line_budget += 1

        # 2a) Emit method snippets, sorted by start_line.
        for (start_line, end_line), payload in sorted(
            methods_for_file.items(), key=lambda item: item[0][0]
        ):
            mi: MethodInfo = payload["info"]  # type: ignore[assignment]
            points: List[_TracePoint] = payload["points"]  # type: ignore[assignment]

            # Method body (clamped to file length).
            start_idx = max(1, mi.start_line) - 1
            end_idx = min(len(lines), mi.end_line)
            body_lines = lines[start_idx:end_idx]

            header_lines: List[str] = []
            header_lines.append(f"// METHOD: {mi.name} [{mi.start_line}-{mi.end_line}]")

            if points:
                header_lines.append("// TRACE POINTS:")
                # stable ordering: sink first, then line asc
                points_sorted = sorted(points, key=lambda p: (0 if p.kind == "sink" else 1, p.line))
                for tp in points_sorted:
                    tag = "SINK" if tp.kind == "sink" else "TRACE"
                    header_lines.append(f"//   - {tag} line {tp.line}: {tp.note}")

            block_len = len(header_lines) + len(body_lines) + 1  # +1 for blank separator
            if used_line_budget + block_len > per_file_cap:
                snippets.append("// [TRUNCATED] max_lines budget reached for this file")
                break

            snippets.append("\n".join(header_lines))
            snippets.extend(body_lines)
            snippets.append("")  # blank line
            used_line_budget += block_len

        # 2b) Fallback: points not contained in any method -> single window block.
        if fallback_points and used_line_budget < per_file_cap:
            all_lines = sorted(tp.line for tp in fallback_points)
            min_line = max(1, all_lines[0])
            max_line = min(len(lines), all_lines[-1])

            block_start = max(1, min_line - context_lines)
            block_end = min(len(lines), max_line + context_lines)

            header_lines: List[str] = []
            header_lines.append(f"// BLOCK: {rel_path} [lines {block_start}-{block_end}]")
            header_lines.append("// TRACE POINTS:")
            for tp in sorted(fallback_points, key=lambda p: (0 if p.kind == "sink" else 1, p.line)):
                tag = "SINK" if tp.kind == "sink" else "TRACE"
                header_lines.append(f"//   - {tag} line {tp.line}: {tp.note}")

            body_lines = lines[block_start - 1 : block_end]
            block_len = len(header_lines) + len(body_lines) + 1

            if used_line_budget + block_len <= per_file_cap:
                snippets.append("\n".join(header_lines))
                snippets.extend(body_lines)
                snippets.append("")
            else:
                snippets.append("// [TRUNCATED] fallback block omitted due to max_lines budget")

        by_file[rel_path] = "\n".join(snippets).rstrip() + "\n"

    return {"by_file": by_file}


__all__ = [
    "extract_snippets_for_vuln",
]
