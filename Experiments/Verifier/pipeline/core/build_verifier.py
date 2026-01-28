#!/usr/bin/env python3
import sys
import pathlib

# Add the Verifier root directory to Python path so we can import from core/
verifier_root = pathlib.Path(__file__).parent.parent.parent
sys.path.insert(0, str(verifier_root))

from docker_core.main import main

if __name__ == "__main__":
    main()