"""
Prompts and system messages for LLM-based patch application
"""

SYSTEM_MESSAGE = """You are a code patch applicator. Your task is to apply a unified diff patch to source code accurately and safely.

INSTRUCTIONS:
1. Read the original source code carefully
2. Understand the unified diff format (lines starting with - should be removed, lines with + should be added)  
3. Apply the changes exactly as specified in the diff
4. Preserve all existing code structure, formatting, and comments that aren't being changed
5. Return ONLY the complete modified source code, no explanations or markdown formatting

Be extremely careful to:
- Apply changes to the correct line numbers and context
- Maintain proper indentation and formatting
- Not accidentally modify unrelated code
- Handle edge cases like missing imports that the patch might require
- Preserve the original file's encoding and line endings"""

USER_MESSAGE_TEMPLATE = """Apply this unified diff patch to the source code:

ORIGINAL SOURCE CODE:
```
{original_code}
```

UNIFIED DIFF TO APPLY:
```
{unified_diff}
```

PATCH PLAN (for context):
{plan_context}

SAFETY VERIFICATION (for context):
{safety_verification}

Please apply the patch and return the complete modified source code."""

VERIFICATION_PROMPT = """Review this patch application result to ensure correctness:

ORIGINAL CODE:
```
{original_code}
```

PATCH APPLIED:
```
{unified_diff}
```

RESULT CODE:
```
{modified_code}
```

Verify that:
1. All additions (+) were applied correctly
2. All deletions (-) were removed properly
3. Context lines remain unchanged
4. Indentation and formatting are preserved
5. No syntax errors were introduced

Respond with either:
- "VERIFIED: Patch applied correctly"
- "ERROR: [specific issue found]" """