#!/usr/bin/env python3
import sys
import pathlib

# add the current directory to Python path
sys.path.insert(0, str(pathlib.Path(__file__).parent))

# import and run the main function
from core.main import main

if __name__ == "__main__":
    main()