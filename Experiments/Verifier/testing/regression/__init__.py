"""
Regression Test Generation Module

LLM-based regression test generation for security patches.
"""

from .config import (
    CURRENT_MODEL,
    TEST_GENERATION_SETTINGS,
    MAX_TESTS_PER_VULNERABILITY,
    MAX_REPAIR_ITERATIONS,
    TEST_OUTPUT_DIR,
    TEST_ARTIFACTS_DIR,
)

from .llm_client import TestGenerationClient

__all__ = [
    "TestGenerationClient",
    "CURRENT_MODEL",
    "TEST_GENERATION_SETTINGS",
    "MAX_TESTS_PER_VULNERABILITY",
    "MAX_REPAIR_ITERATIONS",
    "TEST_OUTPUT_DIR",
    "TEST_ARTIFACTS_DIR",
]

__version__ = "1.0.0"
