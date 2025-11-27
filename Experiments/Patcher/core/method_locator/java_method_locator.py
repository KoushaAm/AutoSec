"""
Tree-sitter-based MethodLocator implementation for Java.

This module parses Java source files and extracts method boundaries
(declarations + bodies), enabling mapping from (file, line) -> MethodInfo.

It uses the `tree_sitter` core library together with `tree_sitter_java`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import tree_sitter_java as tsjava
from tree_sitter import Language, Parser

from . import MethodInfo


# Build the Java language object once per process.
JAVA_LANGUAGE = Language(tsjava.language())

@dataclass
class _IndexedFile:
    """
    Internal representation of an indexed Java file.

    Attributes:
        path:         Absolute path to the file.
        source:       Full file contents as bytes.
        line_offsets: List of starting byte offsets for each line (0-based index -> byte offset).
        methods:      List of MethodInfo entries discovered in this file.
    """
    path: Path
    source: bytes
    line_offsets: List[int]
    methods: List[MethodInfo]


class JavaMethodLocator:
    """
    Java MethodLocator backed by Tree-sitter (tree_sitter + tree_sitter_java).

    Responsibilities:
      - Parse Java files under a given repo_root.
      - Extract method and constructor declarations.
      - Provide method boundaries in 1-based line coordinates.
    """

    def __init__(self, repo_root: Path) -> None:
        self._repo_root = Path(repo_root).resolve()

        # Parser instance for Java.
        self._parser = Parser(JAVA_LANGUAGE)

        # Cache of indexed files: absolute path -> _IndexedFile
        self._files: Dict[Path, _IndexedFile] = {}

    # ---------- Public API ----------

    def index_file(self, file_path: Path) -> List[MethodInfo]:
        """
        Parse and index a Java source file, returning a list of MethodInfo.

        Subsequent calls for the same file will return cached results.
        """
        abs_path = self._resolve_to_abs(file_path)

        if abs_path in self._files:
            return list(self._files[abs_path].methods)

        indexed = self._build_index_for_file(abs_path)
        self._files[abs_path] = indexed
        return list(indexed.methods)

    def find_method_for_line(self, file_path: Path, line: int) -> Optional[MethodInfo]:
        """
        Return the MethodInfo that contains the given 1-based line number,
        or None if the line is not inside any method.
        """
        if line < 1:
            return None

        abs_path = self._resolve_to_abs(file_path)
        if abs_path not in self._files:
            # Lazily index the file if not already present.
            self.index_file(abs_path)

        indexed = self._files.get(abs_path)
        if not indexed:
            return None

        for mi in indexed.methods:
            if mi.start_line <= line <= mi.end_line:
                return mi
        return None

    # ---------- Internal helpers ----------

    def _resolve_to_abs(self, file_path: Path) -> Path:
        """
        Resolve a user-supplied path (relative or absolute) to an absolute path
        under the repo root. Raises ValueError if the file escapes the repo.
        """
        p = Path(file_path)
        if not p.is_absolute():
            p = (self._repo_root / p).resolve()

        try:
            p.relative_to(self._repo_root)
        except ValueError:
            raise ValueError(
                f"File '{p}' is outside repo root '{self._repo_root}'. "
                "JavaMethodLocator expects repo-root–relative paths."
            )

        return p

    def _build_index_for_file(self, abs_path: Path) -> _IndexedFile:
        if not abs_path.exists():
            # Treat missing files as having no methods instead of crashing.
            return _IndexedFile(path=abs_path, source=b"", line_offsets=[], methods=[])

        source_bytes = abs_path.read_bytes()
        tree = self._parser.parse(source_bytes)
        root = tree.root_node

        line_offsets = self._compute_line_offsets(source_bytes)
        methods: List[MethodInfo] = []

        # Walk the tree and collect all method-like declarations.
        # Java grammar node types of interest:
        #   - "method_declaration"
        #   - "constructor_declaration"
        stack = [root]
        while stack:
            node = stack.pop()
            if node.type in ("method_declaration", "constructor_declaration"):
                mi = self._method_info_from_node(node, abs_path, source_bytes, line_offsets)
                if mi is not None:
                    methods.append(mi)
            # DFS: add children to stack
            stack.extend(node.children)

        return _IndexedFile(
            path=abs_path,
            source=source_bytes,
            line_offsets=line_offsets,
            methods=methods,
        )

    @staticmethod
    def _compute_line_offsets(source_bytes: bytes) -> List[int]:
        """
        Build a mapping from 0-based line index -> byte offset in the file.
        """
        offsets = [0]
        idx = 0
        while True:
            nl = source_bytes.find(b"\n", idx)
            if nl == -1:
                break
            offsets.append(nl + 1)
            idx = nl + 1
        return offsets

    def _method_info_from_node(
        self,
        node,
        abs_path: Path,
        source_bytes: bytes,
        line_offsets: List[int],
    ) -> Optional[MethodInfo]:
        """
        Convert a Tree-sitter node representing a method/constructor into MethodInfo.
        """
        # Node positions are given as (row, column) zero-based.
        # We'll convert rows to 1-based line numbers.
        start_row, _ = node.start_point
        end_row, _ = node.end_point

        start_line = start_row + 1
        end_line = end_row + 1

        # Extract method name
        name = self._extract_method_name(node, source_bytes) or "<anonymous>"

        # Best-effort signature: slice from start of node to end of its header line.
        signature = self._extract_signature_line(node, source_bytes, line_offsets)

        return MethodInfo(
            name=name,
            start_line=start_line,
            end_line=end_line,
            signature=signature,
            file=abs_path,
        )

    @staticmethod
    def _node_text(node, source_bytes: bytes) -> str:
        return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _extract_method_name(self, node, source_bytes: bytes) -> Optional[str]:
        """
        Attempt to extract the simple method name from the node.

        Tree-sitter Java grammar typically uses an 'identifier' child for names.
        """
        for child in node.children:
            if child.type == "identifier":
                return self._node_text(child, source_bytes).strip()
        return None

    def _extract_signature_line(
        self,
        node,
        source_bytes: bytes,
        line_offsets: List[int],
    ) -> str:
        """
        Approximate the signature by slicing the source line where the method
        starts, trimmed.
        """
        start_row, _ = node.start_point
        if start_row >= len(line_offsets):
            return ""

        # Determine start and end byte offsets for the first line of the method.
        start_byte = line_offsets[start_row]
        if start_row + 1 < len(line_offsets):
            end_byte = line_offsets[start_row + 1] - 1
        else:
            end_byte = len(source_bytes)

        line_bytes = source_bytes[start_byte:end_byte]
        return line_bytes.decode("utf-8", errors="replace").strip()
