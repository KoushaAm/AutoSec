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
