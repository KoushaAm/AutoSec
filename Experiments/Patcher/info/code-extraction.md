# 🗃️ Code Extractor: A Path-Aware Approach

The **Code Extractor** is designed to replace the old **"sliding window”** approach with a system that matches how vulnerabilities work in real code: through **methods** and **source→sink dataflow paths**, not arbitrary line ranges.



## 🚫 Limitations of the Sliding Window Approach

Conceptually, the sliding-window strategy works by taking:

* For each "important” line from vuln metadata, it grabs **K lines above and below**.
* It merges **overlapping windows** and clips the result to **max_lines**.

This approach leads to:

* **Overlapping, noisy snippets** that often cut methods in half and miss key declarations or control-flow.
* Inclusion of lots of whitespace, comments, and **unrelated code**, especially when vulnerabilities span multiple methods or files.



## ✅ Goals of the New Extractor

In contrast, the new extractor starts from a clear set of goals. It must be:

* **Method-aware**: Respect function boundaries.
* **Dataflow-aware**: Follow the source→sink path.
* **Budget-aware**: Respect `max_lines` and similar constraints.
* Produce **stable, non-overlapping segments** that are easy for both humans and the LLM to reason about.



## ⚙️ High-Level Extractor Workflow

The Code Extractor runs once per vulnerability and produces a small set of meaningful code ranges.

1.  It uses **`vuln_info` metadata** (the **SINK** and **FLOW** arrays) to reconstruct a **logical trace** of the vulnerability: where untrusted data originates, how it is transformed, and where it hits the sink.
2.  It maps each trace point (`file`, `line`) to its **enclosing method** using a language-specific **`MethodLocator`**.
3.  Within each method, it focuses on the portions that actually participate in the dataflow: the lines where **source, intermediate steps, and sink** occur, plus the **"bridges”** between them.
4.  Across methods and files, it recognizes when the flow crosses boundaries and collects context from both **caller and callee methods** (and optionally **callsites**).
5.  It represents each extracted piece as a structured **"segment”** that encodes `file`, `line range`, `method name`, and **`role`** (e.g., source method, sink method), then merges and trims these segments to fit under constraints.



## 🏗️ Implementation Stages

The extractor pipeline has several stages:

### 1. Method Indexing via `MethodLocator`

This stage indexes methods to enable quick lookup of code boundaries.

* A **language-specific locator** (e.g., a tree-sitter–based Java locator) parses relevant source files and discovers method declarations, recording:
    * **Method name**
    * **Start and end lines** for the method body
    * **Textual signature**
* It builds an index, e.g., $methods[file] = [ \{name, start\_line, end\_line, signature\}, \dots ]$.
* It exposes an API, **`find_method_for_line(file_path, line_number)`**, to quickly answer "which method am I in?”

### 2. Dataflow Trace Construction

The vulnerability metadata is converted into an ordered, augmented list of trace points.

* It combines the **SINK** dictionary and **FLOW** list into an ordered list of trace points, each with `file`, `line`, `kind` ("sink" or "flow"), and `note`.
* Each trace point is augmented with its **enclosing method** by querying the `MethodLocator`.
* The logical source→sink order encoded in **FLOW** is preserved.

### 3. Intra-Procedural Extraction (Bridges)

For flows within a single method, the extractor derives a tight "bridge” connecting all relevant lines.

* It groups trace points by (`file`, `method`).
* Inside each group, it sorts points by line number and **infers bridge ranges** between consecutive points, capturing lines that transform or guard the tainted data.
* It finds the min/max lines of trace points and expands this region slightly with a small **padding margin**, while **clamping to the method’s own start and end lines**. This ensures the snippet is method-bounded and includes related logic without bleeding into unrelated code.

### 4. Inter-Procedural Extraction (Cross-Method Flow)

This handles when data moves across methods or files.

* When the flow spans methods, it:
    * Extracts the **callee method context** using the intra-procedural logic.
    * Optionally extracts the **caller callsite context** (a small window around the method invocation).
* **Roles** are assigned to segments to help the LLM: **Source method**, **Sink method**, **Bridge**, **Callsites**.

### 5. Segment Representation

A **segment** is the structured primitive unit of context:

* `file path`
* `start_line` and `end_line` (inclusive)
* `method name` (if any)
* `role` (e.g., "source\_method", "sink\_method", "callsite")

### 6. Merging and Deduplication

Segments are merged and deduplicated per file to avoid overlap and redundancy.

* It sorts all segments by `start_line` per file.
* It walks through to **merge overlapping or adjacent intervals** (e.g., `[10–20]` and `[18–30]` $\to$ `[10–30]`).
* It combines **roles** when segments merge.
* This produces **deterministic, clean, non-overlapping ranges**.

### 7. Budgeting and Shrinking

To respect `max_lines` constraints, a shrinking algorithm is applied based on priority tiers:

| Tier | Priority | Content | Shrinking Action |
| : | : | : | : |
| **Tier 1** | **Must keep** | Sink lines, immediate surrounding logic, direct uses of tainted variables. | Kept untouched. |
| **Tier 2** | **Strongly preferred** | Bridges, validation/sanitization lines, source regions. | Shrunk to smaller windows around key trace lines. |
| **Tier 3** | **Optional** | Large helper bodies, broad callsite context. | Aggressively shrunk or dropped. |

It is **always guaranteed** that every trace point (source, intermediate, sink) and a few lines of nearby context remain in the final output.

### 8. Final Cleanup

The extractor maximizes semantic density by cleaning up noise:

* Trims leading and trailing **blank lines**.
* Removes large, clearly **irrelevant comment blocks**.
* Avoids pulling in unnecessary **imports or boilerplate**.
* Ensures no **duplicated lines** after merging and rendering.



## 🔄 Integration and Comparison

The Code Context Extractor drops into the existing AutoSec pipeline as a direct replacement for sliding-window calls.

### Integration

Instead of doing "get K lines around this line,” the Fixer now:

1.  Calls the extractor with vulnerability metadata and the repo root.
2.  Receives a small number of **well-defined segments**.
3.  Renders these segments into a final snippet or multi-file bundle, annotated with file names, line ranges, method names, and roles, and passes it as `vulnerable_snippets` in the prompt.

### Comparison Summary

| Feature | 🗑️ Sliding-Window Approach | ✨ Code Context Extractor |
| --- | --- | --- |
| **Primary Unit** | Arbitrary line windows around points. | Methods and dataflow bridges. |
| **Dataflow/Scope**| Weak semantics; poor multi-function support. | **Explicitly dataflow-driven and multi-function aware.** |
| **Output Quality**| Overlapping, noisy, and high redundancy. | **Deterministic merging and noise reduction.** |
| **LLM Fit** | Gives partial logic that's hard to patch. | **Concise, semantically coherent context.** |

In summary, the new extractor provides a **principled, explainable, and tunable extraction flo