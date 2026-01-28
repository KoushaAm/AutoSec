"""
Prompt Templates for LLM-based Regression Test Generation

Based on empirical research findings:
- Failure-driven prompts produce stronger oracles
- Security-focused adversarial inputs for CVE patches
- Minimal context reduces hallucinations
"""

# ===== System Prompt =====

SYSTEM_PROMPT = """You are an expert security-focused test engineer specializing in generating JUnit tests for Java security patches.

Your goal is to generate tests that:
1. **Would FAIL if the vulnerability still exists** (failure-driven testing)
2. Use adversarial, boundary, and malformed inputs (for security patches)
3. Have strong assertions that check actual behavior, not implementation details
4. Are deterministic (no time, randomness, network, or external dependencies)
5. Are compilable and executable standalone tests

Follow these strict rules:
- Generate complete, runnable JUnit 4 test methods
- Include all necessary imports
- Use only standard Java/JUnit libraries (no external dependencies unless specified)
- Each test must have at least one assertion
- Focus on negative tests and edge cases
- Tests must be deterministic and repeatable
- Do not include implementation code, only tests
"""

# ===== User Prompt Template =====

USER_PROMPT_TEMPLATE = """Generate JUnit regression tests for a security patch.

## Vulnerability Context
**CWE**: {cwe_id}
**Vulnerability Type**: {vulnerability_description}

## Patch Plan
{patch_plan}

## Code Under Test (Patched Version)
```java
{patched_code}
```

## Security Context
{security_notes}

---

## Your Task
Generate {num_tests} JUnit test methods that would **FAIL on the vulnerable code but PASS on the patched code**.

**Focus on**:
- Adversarial inputs that exploit the vulnerability (e.g., command injection strings, path traversal sequences)
- Boundary conditions and edge cases
- Malformed or unexpected input patterns
- Security-specific assertions (e.g., checking sanitization, validation)

**Requirements**:
1. Each test must be a complete `@Test` method
2. Include all necessary imports at the top
3. Use descriptive test method names (e.g., `testCommandInjectionBlocked()`)
4. Add comments explaining what vulnerability scenario each test targets
5. Must be deterministic (no Date(), Random(), network calls, etc.)
6. Must compile and run standalone

**Output Format**:
Return ONLY valid Java code with imports and test methods. No markdown, no explanations outside code comments.

Example structure:
```java
import org.junit.Test;
import static org.junit.Assert.*;

public class SecurityRegressionTest {{
    
    @Test
    public void testMaliciousInputBlocked() {{
        // Test that command injection is blocked
        // This would fail on vulnerable code
        String maliciousInput = "valid; rm -rf /";
        // ... test code ...
        assertTrue("Malicious input should be sanitized", result.isValid());
    }}
}}
```

Generate the tests now:
"""

# ===== Repair Prompt Template =====

REPAIR_PROMPT_TEMPLATE = """The following test code failed to compile with these errors:

## Compilation Errors
```
{compilation_errors}
```

## Original Test Code
```java
{original_test_code}
```

## Fix Instructions
Fix the compilation errors while maintaining the test's intent and security focus.

**Rules**:
- Keep the same test scenarios and assertions
- Only fix syntax, import, or type errors
- Do not change the test's purpose or remove security checks
- Return ONLY the corrected Java code (no markdown, no explanations)

Generate the fixed test code now:
"""

# ===== Context Extraction Prompt (for extracting focal methods) =====

CONTEXT_EXTRACTION_PROMPT = """Analyze the following Java code and extract the focal method/class that was modified by the security patch.

## Code
```java
{full_code}
```

## Patch Diff
```
{unified_diff}
```

Return ONLY the relevant method(s) or class section that was changed, with minimal context (up to 50 lines).
Include method signatures and any direct dependencies.

Output the extracted code without markdown or explanations:
"""
