"""
Testing Module

Contains all the testing-related functionality:
- test_discovery: Discovery and analysis of existing tests
- test_executor: Test execution coordination and result parsing
- regression: LLM-based security test generation
"""

from .test_discovery import discover_tests, TestDiscovery
from .test_executor import (
    execute_behavior_validation, format_behavior_results_for_display,
    TestExecutor, TestResultParser
)

__all__ = [
    'discover_tests', 'TestDiscovery',
    'execute_behavior_validation', 'format_behavior_results_for_display',
    'TestExecutor', 'TestResultParser'
]