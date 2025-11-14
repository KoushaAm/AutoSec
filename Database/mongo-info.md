# MongoDB Information
Information related to MongoDB Atlas and How to use it

## How to
Based off the [Example Patcher Output Schema](#example-patcher-output-schema) file schema given at the end of this file

### Find all patch runs:
`db.patch_runs.find()`

### Find a run by timestamp:
`db.patch_runs.find({ "metadata.timestamp": "2025-11-13T06:20:15.493814Z" })`

### Find all patch runs where any patch has a certain CWE:
`db.patch_runs.find({ "patches.cwe_matches.cwe_id": "CWE-78" })`

### Find patches with high confidence:
`db.patch_runs.find({ "patches.confidence": { "$gte": 80 } })`

### Find patches that touched a specific file:
`db.patch_runs.find({ "patches.touched_files": "Experiments/vulnerable/CWE_78.java" })`

### A slightly more advanced query:
Find only the CWE matches for CWE-78:
```
db.patch_runs.find(
  { "patches.cwe_matches.cwe_id": "CWE-78" },
  { "patches.cwe_matches.$": 1 }   // projection
)
```

## Example Patcher Output Schema
```json
{
  "_id": ObjectId("..."),
  "metadata": {
    "total_patches": 1,
    "timestamp": "2025-11-13T06:20:15.493814Z",
    "tool_version": "fixer-1.2.1"
  },
  "patches": [
    {
      "patch_id": 1,
      "plan": [...],
      "cwe_matches": [...],
      "unified_diff": "...",
      "safety_verification": "...",
      "risk_notes": "...",
      "touched_files": [...],
      "assumptions": "...",
      "behavior_change": "...",
      "confidence": 90,
      "verifier_confidence": 95
    }
  ]
}
```