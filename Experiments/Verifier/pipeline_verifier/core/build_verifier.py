#!/usr/bin/env python3
import sys
import pathlib

# Add the Verifier root directory to Python path so we can import from core/
# Current file: pipeline_verifier/core/build_verifier.py
# Need to go up: core -> pipeline_verifier -> Verifier (2 levels up)
verifier_root = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(verifier_root))

from core.main import main

if __name__ == "__main__":
    main()