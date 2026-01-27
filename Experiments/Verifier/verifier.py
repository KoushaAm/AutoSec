#!/usr/bin/env python3
"""
Verifier Entry Point

Simple entry point that delegates to the pipeline_verifier module.
This maintains backward compatibility while using the clean module structure.

Usage:
    python3 verifier.py --latest-patcher
    python3 verifier.py --input /path/to/patcher/output
"""

import sys
import pathlib

# Add the pipeline_verifier module to path
sys.path.insert(0, str(pathlib.Path(__file__).parent / "pipeline_verifier"))

# Import and run the CLI
from pipeline_verifier.cli import main

if __name__ == "__main__":
    main()