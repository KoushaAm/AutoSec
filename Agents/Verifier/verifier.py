#!/usr/bin/env python3
"""
Standalone Verifier for Local Testing

Usage:
    # Test with Patcher output (applies patches + builds + tests)
    python3 verifier.py --patcher-output Agents/Patcher/output/patcher_codehaus_2018_output
    
    # Just build/test a project (no patches)
    python3 verifier.py --project codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15
"""

import sys
import pathlib
import json
from datetime import datetime

VERIFIER_ROOT = pathlib.Path(__file__).parent
sys.path.insert(0, str(VERIFIER_ROOT.parent.parent))  # AutoSec root

from Agents.Verifier.core.engine import create_verifier
from Agents.Verifier.core.patch_applicator import LLMPatchApplicator
from Agents.Verifier.handlers.build_handler import DockerBuildRunner
from Agents.Verifier.handlers.patch_parser import ProjectManager
from Agents.Verifier.models.verification import PatchInfo
from constants.models import Model


def verify_patcher_output(patcher_output_dir: str):
    """
    Full verification workflow: Apply patches → Build → Test
    
    Args:
        patcher_output_dir: Path to Patcher output directory (e.g., Agents/Patcher/output/patcher_20260212T100508Z/)
    """
    patcher_path = pathlib.Path(patcher_output_dir)
    
    if not patcher_path.exists():
        print(f"❌ Patcher output directory not found: {patcher_path}")
        return
    
    # find the manifest file (patcher_*.json)
    manifest_files = list(patcher_path.glob("patcher_*.json"))
    if not manifest_files:
        print(f"❌ No patcher manifest (patcher_*.json) found in {patcher_path}")
        return
    
    manifest_file = manifest_files[0]
    print(f"📋 Loading Patcher manifest: {manifest_file.name}")
    print("=" * 80)
    
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
    
    total_patches = manifest["metadata"]["total_patches"]
    print(f"Found {total_patches} patch(es) to verify\n")
    
    # create output directory for this verification run
    autosec_root = VERIFIER_ROOT.parent.parent
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_dir = VERIFIER_ROOT / "output" / "patcher_verification" / f"run_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    patch_applicator = LLMPatchApplicator(model=Model.GPT5_MINI)
    build_runner = DockerBuildRunner()
    
    results_summary = {
        "timestamp": timestamp,
        "patcher_manifest": str(manifest_file),
        "total_patches": total_patches,
        "patches": []
    }
    
    # process each patch
    for patch_entry in manifest["patches"]:
        patch_id = patch_entry["patch_id"]
        artifact_path = patch_entry["artifact_path"]
        
        # absolute path to relative if needed
        if artifact_path.startswith("/workspaces"):
            # docker path - convert to local path
            artifact_path = str(patcher_path / f"patch_{patch_id:03d}.json")
        
        print(f"\n{'='*80}")
        print(f"Verifying Patch {patch_id}/{total_patches}")
        print(f"{'='*80}")
        
        # load individual patch
        patch_file = pathlib.Path(artifact_path)
        if not patch_file.exists():
            print(f"❌ Patch file not found: {patch_file}")
            results_summary["patches"].append({
                "patch_id": patch_id,
                "status": "ERROR",
                "error": "Patch file not found"
            })
            continue
        
        with open(patch_file, "r") as f:
            patch_data = json.load(f)
        
        patch_content = patch_data["patch"]
        patch_metadata = patch_data["metadata"]
        
        # extract file path
        file_path = patch_metadata["file_path"]
        print(f"📄 File: {patch_metadata['file_name']}")
        print(f"🎯 CWE: {patch_content['cwe_matches'][0]['cwe_id']}")
        print(f"📝 Plan: {' → '.join(patch_content['plan'])}")
        
        # create patch output directory
        patch_output_dir = output_dir / f"patch_{patch_id:03d}"
        patch_output_dir.mkdir(parents=True, exist_ok=True)
        
        # convert file path to absolute
        if not pathlib.Path(file_path).is_absolute():
            file_path_abs = autosec_root / file_path
        else:
            file_path_abs = pathlib.Path(file_path)
        
        if not file_path_abs.exists():
            print(f"❌ Source file not found: {file_path_abs}")
            results_summary["patches"].append({
                "patch_id": patch_id,
                "status": "ERROR",
                "error": "Source file not found"
            })
            continue
        
        # determine project root
        project_manager = ProjectManager()
        try:
            project_root = project_manager.find_project_root(str(file_path))
        except ValueError as e:
            print(f"❌ Could not find project root: {e}")
            results_summary["patches"].append({
                "patch_id": patch_id,
                "status": "ERROR",
                "error": str(e)
            })
            continue
        
        print(f"\n[1/3] 🔧 Applying patch...")
        print("-" * 80)
        
        # apply patch using LLM patch applicator
        patch_info_dict = {
            "file_path": str(file_path_abs),
            "unified_diff": patch_content["unified_diff"],
            "plan": patch_content["plan"],
            "safety_verification": patch_content["safety_verification"]
        }
        
        patch_result = patch_applicator.apply_patch(patch_info_dict)
        
        if patch_result["status"] != "success":
            print(f"❌ Patch application failed: {patch_result.get('error', 'Unknown error')}")
            results_summary["patches"].append({
                "patch_id": patch_id,
                "status": "PATCH_FAILED",
                "error": patch_result.get("error", "Unknown error")
            })
            continue
        
        patched_file_path = pathlib.Path(patch_result["patched_file"])
        print(f"✅ Patch applied successfully!")
        print(f"   Original: {file_path_abs.name}")
        print(f"   Patched:  {patched_file_path.name}")
        
        # create PatchInfo for build/test
        patch_info = PatchInfo(
            patch_id=patch_id,
            unified_diff=patch_content["unified_diff"],
            touched_files=[str(file_path)],
            cwe_matches=patch_content["cwe_matches"],
            plan=patch_content["plan"],
            confidence=patch_content["confidence"],
            verifier_confidence=patch_content["confidence"],
            risk_notes=patch_content["risk_notes"],
            assumptions=patch_content["assumptions"],
            behavior_change=patch_content["behavior_change"],
            safety_verification=patch_content["safety_verification"],
            pov_tests=None
        )
        
        print(f"\n[2/3] 🏗️  Building patched project...")
        print("-" * 80)
        
        # build and test
        build_result = build_runner.run_verification(
            project_root,
            patch_info,
            output_dir=patch_output_dir
        )
        
        print(f"\n[3/3] 📊 Results for Patch {patch_id}")
        print("=" * 80)
        
        # display results
        if build_result.get("success"):
            print("✅ BUILD: SUCCESS")
            status = "BUILD_SUCCESS"
        else:
            print("❌ BUILD: FAILED")
            print(f"   Return code: {build_result.get('return_code', 'unknown')}")
            status = "BUILD_FAILED"
        
        print(f"⏱️  Duration: {build_result.get('duration', 0):.2f}s")
        print(f"🐳 Docker image: {build_result.get('docker_image', 'N/A')}")
        
        # test results
        test_execution = build_result.get("test_execution", {})
        if test_execution.get("status") != "SKIP":
            test_results = test_execution.get("test_results", {})
            total_tests = test_results.get("total_tests", 0)
            passed = test_results.get("passed_tests", 0)
            failed = test_results.get("failed_tests", 0)
            
            print(f"\n🧪 Test Results:")
            print(f"   Total:  {total_tests}")
            print(f"   Passed: {passed} ✅")
            print(f"   Failed: {failed} {'❌' if failed > 0 else ''}")
            
            if failed > 0:
                status = "TESTS_FAILED"
            elif passed > 0:
                status = "ALL_PASSED"
        
        # save patch-specific results
        patch_results_file = patch_output_dir / "verification_results.json"
        with open(patch_results_file, "w") as f:
            json.dump({
                "patch_id": patch_id,
                "patch_application": patch_result,
                "build_and_test": build_result,
                "status": status
            }, f, indent=2)
        
        results_summary["patches"].append({
            "patch_id": patch_id,
            "status": status,
            "file": patch_metadata["file_name"],
            "cwe": patch_content["cwe_matches"][0]["cwe_id"],
            "build_success": build_result.get("success", False),
            "test_success": test_execution.get("status") == "PASS" if test_execution.get("status") != "SKIP" else None,
            "output_dir": str(patch_output_dir)
        })
    
    summary_file = output_dir / "verification_summary.json"
    with open(summary_file, "w") as f:
        json.dump(results_summary, f, indent=2)
    
    print(f"\n\n{'='*80}")
    print("VERIFICATION SUMMARY")
    print(f"{'='*80}")
    
    passed_count = sum(1 for p in results_summary["patches"] if p["status"] == "ALL_PASSED")
    build_failed = sum(1 for p in results_summary["patches"] if p["status"] == "BUILD_FAILED")
    test_failed = sum(1 for p in results_summary["patches"] if p["status"] == "TESTS_FAILED")
    errors = sum(1 for p in results_summary["patches"] if "ERROR" in p["status"])
    
    print(f"Total patches verified: {total_patches}")
    print(f"✅ Passed (build + tests): {passed_count}")
    print(f"❌ Build failed: {build_failed}")
    print(f"❌ Tests failed: {test_failed}")
    print(f"⚠️  Errors: {errors}")
    
    print(f"\n💾 Detailed results saved to:")
    print(f"   {summary_file}")
    print(f"\n📂 Individual patch results in:")
    print(f"   {output_dir}/")
    print("=" * 80)
    
    return results_summary


def test_project_build(project_name: str, file_path: str = None):
    """
    Test building and running tests for a project in Projects/Sources/
    (No patches - just build + test existing code)
    """
    autosec_root = VERIFIER_ROOT.parent.parent
    projects_dir = autosec_root / "Projects" / "Sources"
    project_path = projects_dir / project_name
    
    if not project_path.exists():
        print(f"❌ Project not found: {project_path}")
        print(f"\nAvailable projects in Projects/Sources/:")
        for p in projects_dir.iterdir():
            if p.is_dir() and not p.name.startswith('.'):
                print(f"  - {p.name}")
        return
    
    print(f"🔍 Testing project: {project_name}")
    print(f"📂 Location: {project_path}")
    print("=" * 80)
    
    # create output directory for this test
    output_dir = VERIFIER_ROOT / "output" / "local_tests" / f"{project_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # minimal PatchInfo for testing (no actual patch, just build/test)
    patch_info = PatchInfo(
        patch_id=1,
        unified_diff="# Testing build and existing tests only",
        touched_files=[str(pathlib.Path("Projects") / "Sources" / project_name / "src")],
        cwe_matches=[{"cwe_id": "TEST", "description": "Local build test"}],
        plan=["Test project build", "Run existing tests"],
        confidence=100,
        verifier_confidence=100,
        risk_notes="Local testing only",
        assumptions="Project builds successfully",
        behavior_change="None - testing only",
        safety_verification="Safe - no code changes",
        pov_tests=None
    )
    
    print("\n[1/2] 🏗️  Building project and discovering tests...")
    print("-" * 80)
    
    # initialize build handler
    build_runner = DockerBuildRunner()
    
    try:
        # run build and test
        result = build_runner.run_verification(
            project_path,
            patch_info,
            output_dir=output_dir
        )
        
        print("\n[2/2] 📊 Results Summary")
        print("=" * 80)
        
        # display results
        if result.get("success"):
            print("✅ BUILD: SUCCESS")
        else:
            print("❌ BUILD: FAILED")
            print(f"   Return code: {result.get('return_code', 'unknown')}")
        
        print(f"⏱️  Duration: {result.get('duration', 0):.2f}s")
        print(f"🐳 Docker image: {result.get('docker_image', 'N/A')}")
        print(f"📦 Build system: {result.get('stack', 'N/A')}")
        
        # test discovery
        test_discovery = result.get("test_discovery", {})
        if test_discovery.get("has_tests"):
            print(f"\n🧪 Tests discovered: {test_discovery.get('test_count', 0)}")
            print(f"   Test directory: {test_discovery.get('test_dir', 'N/A')}")
        else:
            print(f"\n⚠️  No tests discovered: {test_discovery.get('message', 'Unknown')}")
        
        # test execution results
        test_execution = result.get("test_execution", {})
        if test_execution.get("status") != "SKIP":
            test_results = test_execution.get("test_results", {})
            total = test_results.get("total_tests", 0)
            passed = test_results.get("passed_tests", 0)
            failed = test_results.get("failed_tests", 0)
            
            print(f"\n📝 Test Results:")
            print(f"   Total:  {total}")
            print(f"   Passed: {passed} ✅")
            print(f"   Failed: {failed} {'❌' if failed > 0 else ''}")
            
            if total > 0:
                success_rate = (passed / total) * 100
                print(f"   Success rate: {success_rate:.1f}%")
        
        # save detailed results
        results_file = output_dir / "build_test_results.json"
        with open(results_file, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"\n💾 Detailed results saved to:")
        print(f"   {results_file}")
        
        # show log locations
        print(f"\n📄 Build logs:")
        if (output_dir / "docker_stdout.log").exists():
            print(f"   stdout: {output_dir / 'docker_stdout.log'}")
        if (output_dir / "docker_stderr.log").exists():
            print(f"   stderr: {output_dir / 'docker_stderr.log'}")
        
        print("\n" + "=" * 80)
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error during build/test: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Local Verifier - Apply patches and verify projects",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Verify Patcher output (apply patches + build + test)
  python3 verifier.py --patcher-output Agents/Patcher/output/patcher_codehaus_2018_output
  
  # Just test a project (build + run existing tests, no patches)
  python3 verifier.py --project codehaus-plexus__plexus-utils_CVE-2017-1000487_3.0.15
  
  # List available projects
  python3 verifier.py --list
        """
    )
    
    parser.add_argument(
        "--patcher-output",
        type=str,
        help="Path to Patcher output directory (e.g., Agents/Patcher/output/patcher_20260212T100508Z/)"
    )
    
    parser.add_argument(
        "--project",
        type=str,
        help="Project name from Projects/Sources/ (for build/test only, no patches)"
    )
    
    parser.add_argument(
        "--file",
        type=str,
        help="Specific file to test (relative to project root)"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available projects in Projects/Sources/"
    )
    
    args = argparse.ArgumentParser()
    
    # list projects
    if args.list:
        autosec_root = VERIFIER_ROOT.parent.parent
        projects_dir = autosec_root / "Projects" / "Sources"
        
        print("\n📁 Available projects in Projects/Sources/:")
        print("=" * 80)
        for p in sorted(projects_dir.iterdir()):
            if p.is_dir() and not p.name.startswith('.'):
                # Check if it has a pom.xml (Maven) or build.gradle (Gradle)
                build_file = "pom.xml" if (p / "pom.xml").exists() else "build.gradle" if (p / "build.gradle").exists() else "unknown"
                print(f"  • {p.name}")
                print(f"    Build: {build_file}")
        print("=" * 80)
        sys.exit(0)
    
    # verify Patcher output (full workflow: apply patches + build + test)
    if args.patcher_output:
        verify_patcher_output(args.patcher_output)
    
    # just build/test project (no patches)
    elif args.project:
        test_project_build(args.project, args.file)
    
    else:
        parser.print_help()
        print("\n💡 Tip: Use --patcher-output to verify patches, or --project to just build/test")
        sys.exit(1)