# Agents/Patcher/__init__.py
"""
Entry point package for the Patcher Agent
"""

from .pipeline_test import test_pipeline_main
from .patcher import patcher_main
from .config import (
    TOOL_VERSION,
)

__all__ = [
    "test_pipeline_main",
    "patcher_main",
    "TOOL_VERSION",
]