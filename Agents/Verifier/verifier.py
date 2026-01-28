#!/usr/bin/env python3

import sys
import pathlib

# Add parent directory to path for imports
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

# Import and run from core engine
from core.engine import create_verifier
from config import DEFAULT_PATCH_INPUT_DIR, LATEST_PATCHER_OUTPUT

if __name__ == "__main__":
    # For now, use the engine directly
    # This will be replaced with LangGraph node in the pipeline
    verifier = create_verifier()
    
    # Example usage - will be replaced by LangGraph state management
    import argparse
    parser = argparse.ArgumentParser(description="Verifier Agent")
    parser.add_argument("--input", type=str, help="Path to Patcher output JSON")
    parser.add_argument("--latest-patcher", action="store_true", help="Use latest Patcher output")
    args = parser.parse_args()
    
    if args.latest_patcher:
        input_path = LATEST_PATCHER_OUTPUT
    elif args.input:
        input_path = pathlib.Path(args.input)
    else:
        print("Please specify --input or --latest-patcher")
        sys.exit(1)
    
    # Find the JSON file
    if input_path.is_dir():
        json_files = list(input_path.glob("patch_*.json"))
        if not json_files:
            print(f"No patch_*.json files found in {input_path}")
            sys.exit(1)
        input_file = json_files[0]
    else:
        input_file = input_path
    
    print(f"Running Verifier on: {input_file}")
    results = verifier.verify_fixer_output(str(input_file))
    
    print(f"\n✅ Verification complete! {len(results)} patch(es) verified")