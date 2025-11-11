"""
Testing Module

Contains all the testing-related functionality:
- test_discovery: Discovery and analysis of existing tests
- smoke_generator: Generation of smoke tests for different project types
- test_executor: Test execution coordination and result parsing
"""

from .test_discovery import discover_tests, TestDiscovery
from .smoke_generator import generate_smoke_tests, SmokeTestGenerator
from .test_executor import (
    execute_behavior_validation, format_behavior_results_for_display,
    TestExecutor, TestResultParser
)

__all__ = [
    'discover_tests', 'TestDiscovery',
    'generate_smoke_tests', 'SmokeTestGenerator', 
    'execute_behavior_validation', 'format_behavior_results_for_display',
    'TestExecutor', 'TestResultParser'
]