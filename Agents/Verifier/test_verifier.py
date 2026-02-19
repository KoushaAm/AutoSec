#!/usr/bin/env python3
"""
Standalone test script for Verifier

Tests the complete Verifier workflow using existing Patcher output
"""

import sys
from pathlib import Path

# Add AutoSec root to path
autosec_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(autosec_root))

from Agents.Verifier import verifier_main

if __name__ == "__main__":
    # Test with existing Patcher output for codehaus 2018 project
    patcher_manifest = autosec_root / "Agents" / "Patcher" / "output" / "patcher_codehaus_2018_output" / "patcher_20260212T100508Z.json"
    project_name = "codehaus-plexus__plexus-archiver_CVE-2018-1002200_3.5"
    
    print("Testing Verifier with:")
    print(f"  Patcher manifest: {patcher_manifest}")
    print(f"  Project: {project_name}")
    print()
    
    success, output_dir = verifier_main(
        patcher_manifest_path=str(patcher_manifest),
        project_name=project_name,
        exploiter_pov_test_path=None,  # No POV tests for this test
    )
    
    if success:
        print(f"\n✅ Verifier test completed successfully!")
        print(f"   All patches passed verification")
    else:
        print(f"\n⚠️  Verifier test completed - some patches failed")
    
    print(f"   Results: {output_dir}")
