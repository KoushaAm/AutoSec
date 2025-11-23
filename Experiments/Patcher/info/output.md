# Output Structure for Patcher (Fixer) Agent
The Patcher agent defines two primary file types
1. [Manifest](#manifest-file) (one per run)
2. [Patch Artifact](#patch-artifact) (one per patch)

<!-- ==================================================================== -->
## Manifest File
- Example name: `output/patcher_<timestamp>/patcher_<timestamp>.json`

**Top-Level shape:**
```json
{
  "metadata": {
    "run_id": "patcher_20251120T123456Z",
    "timestamp": "2025-11-20T12:34:56Z",
    "tool_version": "patcher-1.2.1",
    "model_name": "meta-llama/llama-3.3-70b-instruct",
    "total_patches": 3
  },
  "patches": [
    {
      "patch_id": 1,
      "cwe_matches": [
        { "cwe_id": "CWE-78", "similarity": 90 }
      ],
      "artifact_path": "output/patcher_20251120T123456Z/patch_001.json"
    },
    {
      "patch_id": 2,
      "cwe_matches": [
        { "cwe_id": "CWE-79", "similarity": 85 }
      ],
      "artifact_path": "output/patcher_20251120T123456Z/patch_002.json"
    },
    {
      "patch_id": 3,
      "cwe_matches": [
        { "cwe_id": "CWE-89", "similarity": 88 }
      ],
      "artifact_path": "output/patcher_20251120T123456Z/patch_003.json"
    }
  ]
}
```

**Semantics**
- `metadata.run_id` - unique ID for this Fixer run (usually matches the filename stem).
- `metadata.timestamp` - when we processed the LLM output.
- `metadata.tool_version` - Fixer version.
- `metadata.model_name` - model used for this run.
- `metadata.total_patches` - len(patches).

**Each entry in `patches[]` is index-only:**
- `patch_id` - integer identifier (unique within this run).
- `cwe_matches` - quick summary of which CWE(s) this patch targets.
- `artifact_path` - relative path under `output/` to the patch artifact JSON.

<!-- ==================================================================== -->
## Patch Artifact
- Example name: `output/patcher_<timestamp>/patch_001.json`

**Top-Level shape:**
```json
{
  "metadata": {
    "patch_id": 1,
    "timestamp": "2025-11-20T12:34:56Z",
    "file_path": "Experiments/vulnerable/CWE_78.java",
    "file_name": "CWE_78.java"
  },
  "patch": {
    "plan": [
      "Identify the user input source and its propagation to the command string",
      "Use a whitelist approach to validate the user input before constructing the command",
      "Replace the vulnerable code with a secure alternative using ProcessBuilder"
    ],
    "cwe_matches": [
      { "cwe_id": "CWE-78", "similarity": 90 }
    ],
    "unified_diff": "--- Experiments/vulnerable/CWE_78.java\n+++ Experiments/vulnerable/CWE_78.java\n@@ -8,7 +8,7 @@\n...",
    "safety_verification": "Explain why the command injection is no longer possible and how the PoV tests confirm it.",
    "risk_notes": "Any changed behavior, performance implications, or config changes required.",
    "touched_files": [
      "Experiments/vulnerable/CWE_78.java"
    ],
    "assumptions": "Any non-trivial assumptions about environment, inputs, or usage.",
    "behavior_change": "Describe intended user-visible behavior change, or 'none'.",
    "confidence": "85"
  }
}
```

**Semantics**

`metadata`
- `patch_id` - numeric ID matching the manifest.
- `timestamp` - when this artifact was written.
- `file_path` - primary file the patch applies to (from vuln info / flow).
- `file_name` - basename of file_path.

If a patch touches multiple files, file_path/file_name will show the **sink file**

`patch`
- `plan` - ordered list of short, actionable fix steps.
- `cwe_matches` - CWEs the Fixer used as references, with similarity scores.
- `unified_diff` - git-style unified diff string applying the patch.
- `safety_verification` - combined rationale:
  - why the vulnerability is now mitigated, and
  - how PoV tests / reasoning support this.
- `risk_notes` - tradeoffs, potential regressions, config impacts.
- `touched_files` - list of all files the diff touches.
- `assumptions` - explicit, non-trivial assumptions.
- `behavior_change` - intended user-visible change, or "none".
- `confidence` - "0-100" score (as a string, as per your existing schema).