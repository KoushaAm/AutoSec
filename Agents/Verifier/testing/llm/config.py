"""
Configuration for LLM-based Regression Test Generation

"""

from pathlib import Path
from typing import Dict
import sys

# Import Model enum from Verifier's constants directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from constants.models import Model

# ===== Model Configuration =====
CURRENT_MODEL = Model.LLAMA3  # Using same model as patch application for consistency

# LLM Settings for test generation
TEST_GENERATION_SETTINGS = {
    "temperature": 0.2,  # Slightly higher than patch application for diversity
    "max_tokens": 3000,  # Sufficient for multiple test methods
    "timeout": 45,       # Longer timeout for test generation
    "retry_attempts": 3,
}

# ===== Test Generation Parameters (from research) =====

# Maximum number of tests to generate per vulnerability
# Research shows: "Fewer strong tests outperform many weak tests"
MAX_TESTS_PER_VULNERABILITY = 5

# Maximum repair iterations for failed test compilation
# Research: "Generate → run → repair loops outperform one-shot generation"
MAX_REPAIR_ITERATIONS = 2

# Context extraction limits
# Research: "Only focal method/class + direct dependencies"
MAX_CONTEXT_LINES = 200  # Maximum lines of code context to include
MAX_DEPENDENCY_DEPTH = 1  # How many levels of dependencies to include

# ===== Test Validation Settings =====

# Determinism checks - filter out tests that use:
FORBIDDEN_PATTERNS = [
    "System.currentTimeMillis()",
    "new Date()",
    "LocalDateTime.now()",
    "Random",
    "Math.random()",
    "UUID.randomUUID()",
    "Thread.sleep(",
    "HttpClient",
    "URL(",
    "URLConnection",
    "Socket(",
]

# Required patterns for valid tests
REQUIRED_PATTERNS = [
    "assert",  # Must have at least one assertion
    "@Test",   # Must be a JUnit test
]

# ===== Docker Execution Settings =====

# Test compilation and execution timeouts
TEST_COMPILE_TIMEOUT = 120  # seconds
TEST_EXECUTION_TIMEOUT = 60  # seconds

# ===== Output Directories =====

# Base output directory for generated tests
TEST_OUTPUT_DIR = Path(__file__).parent.parent / "test_output"
TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Directory for test artifacts (compilation logs, execution results)
TEST_ARTIFACTS_DIR = Path(__file__).parent.parent.parent / "artifacts" / "regression_tests"
TEST_ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

# ===== Logging =====
VERBOSE = True  # Enable detailed logging
