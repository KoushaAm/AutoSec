# Patcher Code Context Extractor
The current *sliding-window* snippet selection (e.g., "±K lines around
each vulnerable line") is fundamentally misaligned with what we need:
**semantically coherent, path-aware code context** for LLM-based
vulnerability fixing.

We replace it with a **Code Context Extractor**, inspired by 
[ZeroFalse](https://github.com/mhsniranmanesh/ZeroFalse), that:

-   Treats **methods and dataflow paths** as the primary units of
    context (not raw line ranges).
-   Uses vuln metadata (`SINK` + `FLOW`) to reconstruct a **source→sink
    trace** across functions/files.
-   Extracts **method-bounded segments** and **bridges** between
    dataflow steps instead of arbitrary windows.
-   Merges overlapping segments and shrinks them via **priority-based
    budgeting** to satisfy `max_lines`.
-   Produces a single, ordered, non-redundant context snippet per
    vulnerability, tailored to the Fixer's constraints.

The result: significantly more informative and compact prompts, with
minimal overlap and much better alignment to the actual vulnerability
path.

<!-- ================================================================= -->
## Table of Contents
1. [Background and Problem Statement](#1-background-and-problem-statement)
   - [1.1 Current approach: sliding window](#11-current-approach-sliding-window)
   - [1.2 Desired properties](#12-desired-properties)
2. [High-Level Design: Code Context Extractor](#2-high-level-design-code-context-extractor)
3. [Step-by-Step Algorithm](#3-step-by-step-algorithm)
   - [3.1 Preprocessing: Method Index (MethodLocator)](#31-preprocessing-method-index-methodlocator)
   - [3.2 Dataflow Trace Construction from Vulnerability Metadata](#32-dataflow-trace-construction-from-vulnerability-metadata)
   - [3.3 Intra-Procedural Extraction: Context Within a Single Method](#33-intra-procedural-extraction-context-within-a-single-method)
   - [3.4 Inter-Procedural Extraction](#34-inter-procedural-extraction)
   - [3.5 Segment Representation](#35-segment-representation)
4. [Segment Merging and Deduplication](#4-segment-merging-and-deduplication)
5. [Budgeting vs `max_lines` and Other Constraints](#5-budgeting-vs-max_lines-and-other-constraints)
   - [5.1 Priority tiers](#51-priority-tiers)
   - [5.2 Shrinking algorithm](#52-shrinking-algorithm)
6. [Noise Reduction: Whitespace and Unhelpful Lines](#6-noise-reduction-whitespace-and-unhelpful-lines)
7. [Integration into the AutoSec Pipeline](#7-integration-into-the-autosec-pipeline)
8. [Comparison: Sliding Window vs. Code Context Extractor](#8-comparison-sliding-window-vs-code-context-extractor)
9. [Summary](#9-summary)


<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 1. Background and Problem Statement

### 1.1 Current approach: sliding window

Right now, snippet extraction is roughly:

-   For each important line (e.g., from `vuln_info`):
    -   Take `K` lines before and after that line.
    -   Merge these windows into a snippet.
    -   Clip or truncate based on `max_lines`.

This *line-distance-based* strategy has three core issues:

1.  **Overlapping windows**
    -   Multiple important lines in the same region → overlapping ranges
        → complex merging and wasted budget.
2.  **Incomplete semantics**
    -   The window may:
        -   Cut a method in half.
        -   Omit variable declarations, control-flow, or intermediate
            transformations.
    -   The LLM sees partial logic and cannot reason precisely about
        taint, guards, or side effects.
3.  **Noise and whitespace**
    -   To hit `max_lines`, we often include large amounts of
        whitespace, comments, or unrelated code (especially if windows
        cross method boundaries).

These problems grow worse when the vulnerability spans **multiple
functions or files**.

<!-- ============================== -->
### 1.2 Desired properties

We want a snippet extractor that:

-   Is **method-aware**: respects function boundaries and signatures.
-   Is **dataflow-aware**: follows the **source→sink path** rather than
    arbitrary distances.
-   Is **budget-aware**: respects `max_lines`, `max_hunks` and other
    constraints.
-   Produces **stable, non-overlapping segments**, easy to reason about
    and debug.
-   Provides enough context for the LLM to:
    -   Understand how data flows from source to sink.
    -   See relevant checks/sanitization.
    -   Propose minimal, correct patches.

This is precisely the philosophy behind ZeroFalse's Code Context
Extraction, which we adapt to AutoSec.

<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 2. High-Level Design: Code Context Extractor

We introduce a dedicated **Code Context Extractor** component that
replaces the sliding window.

At a high level, for each vulnerability:

1.  Use `vuln_info` metadata (`SINK`, `FLOW`, file paths, line numbers)
    to build a **trace** of points involved in the vulnerability.
2.  Map each trace point to its **enclosing method** using a
    **MethodLocator** (per language).
3.  Within each method:
    -   Identify **key lines** (source, sink, intermediate steps).
    -   Extract the **bridge code** between them (lines that carry or
        transform tainted data).
    -   Add small, method-bounded padding.
4.  Across methods/files:
    -   When flow crosses method boundaries, include:
        -   Target method context.
        -   Relevant **call sites** and signatures, as available.
5.  Collect these as **ContextSegments**, then:
    -   Merge overlapping segments.
    -   Enforce `max_lines` using a **priority-based budgeting
        strategy**.
    -   Strip unhelpful whitespace and large irrelevant comment blocks.

The output is a small, semantically coherent set of code ranges that
capture the dataflow path with minimal redundancy.

<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 3. Step-by-Step Algorithm

### 3.1 Preprocessing: Method Index (MethodLocator)

**Goal:** For any `(file, line)` pair, quickly determine which method
(if any) contains that line, and what the method's boundaries are.

For each relevant source file:

1.  **Parse or scan the file** using language-specific logic:

    -   For Java, for example:
        -   Detect method declarations via the AST or regex-style
            parsing.
        -   Track opening/closing braces to find their start/end line
            numbers.

2.  Build a **method index** per file:

    ```py
    methods[file] = [
        {
            "name": "doGet",
            "start_line": 15,
            "end_line": 45,
            "signature": "void doGet(HttpServletRequest req, HttpServletResponse resp) throws IOException"
        },
        ...
    ]
    ```

3.  Provide a query API:

    ```py
    method_meta = find_method_for_line(file_path, line_number)
    # returns None if the line is not inside any method (e.g., top-level code)
    ```

This is analogous to the ["MethodLocator" abstraction used by ZeroFalse](https://github.com/mhsniranmanesh/ZeroFalse/tree/main/OpenVuln/code-context/method-finder).

<!-- ============================== -->
### 3.2 Dataflow Trace Construction from Vulnerability Metadata

**Goal:** Convert your structured `VulnerabilityInfo` into an ordered
list of *trace points*.

Given a `VulnerabilityInfo` subclass:

-   `SINK` with `file` and `line`
-   `FLOW` array with intermediate steps (`file`, `line`, `note`, etc.)

We construct:

```py
trace_points = [
    {"file": SINK["file"], "line": SINK["line"], "kind": "sink"},
    {"file": step["file"], "line": step["line"], "kind": "flow", "note": step["note"], ...},
    ...
]
```

Ordering:

-   Generally, we respect the **logical order** encoded in `FLOW`
    (source → sink).
-   When needed, we may sort by `(file, line)` within a given method,
    but we do not randomize or lose the overall sequence.

Each trace point then gets augmented with its method metadata:

```py
for p in trace_points:
    p["method"] = find_method_for_line(p["file"], p["line"]) or "__global__"
```

<!-- ============================== -->
### 3.3 Intra-Procedural Extraction: Context Within a Single Method

**Goal:** For steps that occur within the same method, extract the full
**bridge** between them plus a bit of padding, clipped to method
boundaries.

For each `(file, method)` group:

1.  Filter `trace_points` to those that share the same `file` and
    method.

2.  Sort these by line number.

3.  For each consecutive pair `(p_i, p_j)` in that method:

    -   Let `a = min(p_i.line, p_j.line)`,
        `b = max(p_i.line, p_j.line)`.
    -   Define a **bridge range** `[a, b]`:
        -   This covers assignments, checks, loops, and any intermediate
            transformations applied to tainted data between the two
            points.

4.  Determine the **outermost** lines touched in this method:

    ```py
    min_line = min(p.line for p in method_points)
    max_line = max(p.line for p in method_points)
    ```

5.  Add **method-bounded padding**:

    ```py
    start = max(method_start_line, min_line - PADDING)
    end   = min(method_end_line,   max_line + PADDING)
    ```

6.  Create a **ContextSegment** for this method:

    ```py
    ContextSegment(
        file=file,
        start_line=start,
        end_line=end,
        method=method_name,
        role=role,    # e.g. "sink_method", "source_method", "bridge"
    )
    ```

Roles are assigned by semantics:

-   Method containing the sink line: `"sink_method"`.
-   Method containing the first source: `"source_method"`.
-   Intermediate methods: `"bridge"` or `"intermediate_method"`.

<!-- ============================== -->
### 3.4 Inter-Procedural Extraction

When flow crosses method boundaries:

-   Extract callee method context same as intra-procedural.
-   Extract caller **callsite window**.
-   Assign roles:
    -   `"callee_method"`
    -   `"callsite"`

This includes argument propagation context.

<!-- ============================== -->
### 3.5 Segment Representation

A segment is:

```py
ContextSegment(
    file="...",
    start_line=...,
    end_line=...,
    method="...",
    role="sink_method"/"source_method"/"bridge"/"callsite"/...
)
```

These segments encode ordered, meaningful code ranges.


<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 4. Segment Merging and Deduplication

For all segments in one file:

1.  Convert to intervals `(start, end, roles)`.

2.  Sort by `start`.

3.  Merge overlapping or adjacent segments:

        [10,20], [18,30] → [10,30]

4.  Combine role sets for merged segments.

This eliminates redundant overlaps and simplifies downstream budgeting.


<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 5. Budgeting vs `max_lines` and Other Constraints

### 5.1 Priority tiers

**Tier 1 (Must Keep):**

-   Sink lines and surrounding logic\
-   Direct usage of tainted variables

**Tier 2 (Strongly Preferred):**

-   Bridges connecting source→sink\
-   Lines containing sanitization logic\
-   Source method regions

**Tier 3 (Optional):**

-   Large helper method bodies\
-   Minimal callsite windows

<!-- ============================== -->
### 5.2 Shrinking algorithm

If `total_lines > max_lines`:

1.  Keep Tier 1 unchanged.
2.  Shrink Tier 2 segments to local windows around their key trace
    lines.
3.  Shrink Tier 3 segments aggressively or drop them.
4.  Always preserve:
    -   Lines containing trace points
    -   A few lines of context for readability

<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 6. Noise Reduction: Whitespace and Unhelpful Lines

Internal cleanup of each final range:

-   Trim leading/trailing blank lines
-   Remove large irrelevant comments
-   Avoid boilerplate imports accidentally included
-   Ensure no duplicated lines

This ensures maximal semantic density.

<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 7. Integration into the AutoSec Pipeline

### Replacing the sliding-window call

**Old:**
```py
snippet = get_snippet_around_line(file, line, window_size=K)
```

**New:**
```py
segments = extract_context(vuln, repo)
snippet = render_context(segments)
```

### Render function annotates:
-   File name
-   Line numbers
-   Segment roles

Ideal for Fixer, Exploiter, Verifier agents.

<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 8. Comparison: Sliding Window vs. Code Context Extractor

| Property                 | Sliding Window      | Code Context Extractor     |
|--------------------------|---------------------|----------------------------|
| Unit of extraction       | Lines around point  | Methods + dataflow bridges |
| Semantics                | Weak                | Strong, dataflow-driven    | 
| Multi-function support   | Poor                | Excellent                  |
| Overlap management       | Weak                | Deterministic merging      |
| Noise                    | High                | Low                        |
| LLM patch suitability    | Limited             | Strong                     |


<!-- ================================================================= -->
> ↑ [Back to Top](#patcher-code-context-extractor) ↑
## 9. Summary

The failing sliding-window approach is replaced by a **ZeroFalse-inspired**, **path-aware 
Code Context Extractor** that:

- Uses vuln metadata (`SINK` + `FLOW`) to reconstruct a logical dataflow trace.
- Anchors extraction to **methods** and **inter-step bridges**, not arbitrary line windows.
- Produces **non-overlapping**, **priority-ranked segments**, then compresses them under 
`max_lines` while preserving the crucial semantics.
- Integrates cleanly into AutoSec as a dedicated component used by the Fixer 
(and potentially Verifier/Exploiter) to supply high-quality code context for 
LLM reasoning.

This design gives us a principled, explainable, and tunable code extraction pipeline 
that aligns with ZeroFalse’s approach and directly addresses the shortcomings of the 
sliding-window method.

<!-- ================================================================= -->
---
> ↑ [Back to Top](#patcher-code-context-extractor) ↑