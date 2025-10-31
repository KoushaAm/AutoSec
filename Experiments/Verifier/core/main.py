#!/usr/bin/env python3
"""
Main Entry Point

Orchestrates project detection, Docker execution, build validation, and testing.
"""
import argparse
import json
import pathlib
import sys
import datetime

from .project_detector import detect_java_project
from .docker_runner import (
    DockerRunner, check_docker, get_docker_image_for_stack, 
    classify_build_failure
)
from .artifact_validator import validate_build_artifacts

# Use absolute import instead of relative import that goes beyond top-level package
import sys
import pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from testing.test_executor import execute_behavior_validation, format_behavior_results_for_display


def convert_paths_to_strings(obj):
    """
    Recursively convert all pathlib.Path objects to strings for JSON serialization.
    """
    if isinstance(obj, pathlib.Path):
        return str(obj).replace('\\', '/')
    elif isinstance(obj, dict):
        return {key: convert_paths_to_strings(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_paths_to_strings(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_paths_to_strings(item) for item in obj)
    else:
        return obj


def main():
    """Main entry point for Java build verification."""
    parser = argparse.ArgumentParser(
        description="Java Build Verifier - Handles any Java project from single files to enterprise applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single Java file
  python3 -m core.main --input /path/to/HelloWorld.java --docker
  
  # Maven project  
  python3 -m core.main --input /path/to/maven-project --docker
  
  # Gradle project
  python3 -m core.main --input /path/to/gradle-project --docker
        """
    )
    
    parser.add_argument("--input", required=True, 
                       help="Path to Java file, directory, or project root")
    parser.add_argument("--artifacts", default="./artifacts", 
                       help="Directory for build logs and results")
    parser.add_argument("--timeout-build", type=int, default=1800,
                       help="Build timeout in seconds (default: 1800)")
    parser.add_argument("--timeout-test", type=int, default=1200,
                       help="Test timeout in seconds (default: 1200)")
    parser.add_argument("--docker", action="store_true", required=True,
                       help="Required flag - all builds run in Docker")
    parser.add_argument("--verbose", "-v", action="store_true",
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    # validate Docker availability
    if not check_docker():
        print("ERROR: Docker is not available or not running", file=sys.stderr)
        print("Please start Docker and try again", file=sys.stderr)
        sys.exit(2)
    
    # validate input path
    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(2)
    
    # determine working directory
    if input_path.is_file():
        worktree = input_path.parent
        if args.verbose:
            print(f"Single file detected: {input_path.name}")
            print(f"Using parent directory as worktree: {worktree}")
    else:
        worktree = input_path
        if args.verbose:
            print(f"Directory project: {worktree}")
    
    # set up artifacts directory
    artifacts = pathlib.Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    summary_file = artifacts / "build_summary.json"
    
    # start the verification process
    process_start = datetime.datetime.now(datetime.timezone.utc)
    
    # Phase 1: Project Detection
    stack, build_cmd, test_cmd, metadata = detect_java_project(worktree)
    
    if args.verbose:
        print(f"Detected: {stack} ({metadata.get('java_files', 0)} Java files)")
    
    if not build_cmd:
        error_msg = metadata.get('error', 'Unknown detection error')
        
        summary = {
            "status": "FAIL",
            "error": error_msg,
            "detected_stack": None,
            "metadata": metadata,
            "build": {"rc": 2, "duration_seconds": 0},
            "test": {"rc": 0, "duration_seconds": 0},
            "start_time": process_start.isoformat(),
            "end_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        summary_file.write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        sys.exit(1)
    
    # Phase 2: Docker Setup
    image = get_docker_image_for_stack(stack)
    docker_runner = DockerRunner()
    
    if args.verbose:
        print(f"Using Docker image: {image}")
    
    # Phase 3: Build Execution
    build_rc, build_duration = docker_runner.run_command(
        image, build_cmd, worktree, artifacts, args.timeout_build
    )
    
    build_failure = classify_build_failure(build_rc)
    build_passed = False
    artifact_validation = {"artifacts_found": [], "artifact_count": 0, "has_artifacts": False}
    
    if build_rc == 0:
        artifact_validation = validate_build_artifacts(worktree, stack)
        build_passed = build_rc == 0 and artifact_validation['has_artifacts']
        
        if args.verbose:
            print(f"Build: PASS ({artifact_validation['artifact_count']} artifacts)")
    else:
        if args.verbose:
            failure_type = build_failure['type']
            print(f"Build: FAIL ({failure_type})")
    
    # Phase 4: Test Execution (legacy test command - if provided)
    test_rc, test_duration = 0, 0
    if test_cmd and build_rc == 0:
        test_rc, test_duration = docker_runner.run_command(
            image, test_cmd, worktree, artifacts, args.timeout_test
        )
    
    # Phase 5: Behavior Validation
    behavior_result = None
    if build_passed:
        behavior_result = execute_behavior_validation(
            worktree, artifacts, stack, image,
            has_wrapper=metadata.get('has_wrapper', False),
            docker_runner_func=lambda img, cmd, wt, art, timeout: docker_runner.run_command(img, cmd, wt, art, timeout),
            timeout=args.timeout_test, verbose=args.verbose
        )
    else:
        if args.verbose:
            print("Behavior: SKIP (build failed)")
    
    # Phase 6: Summary and Results
    behavior_passed = behavior_result is None or behavior_result['status'] in ['PASS', 'SKIP']
    status = "PASS" if build_passed and test_rc == 0 and behavior_passed else "FAIL"
    process_end = datetime.datetime.now(datetime.timezone.utc)
    
    summary = {
        "status": status,
        "detected_stack": stack,
        "docker_image": image,
        "metadata": metadata,
        "build_validation": {
            "build_classification": build_failure,
            "artifact_validation": artifact_validation,
            "build_status": "PASS" if build_passed else "FAIL"
        },
        "behavior_validation": behavior_result,
        "build": {
            "rc": build_rc,
            "duration_seconds": round(build_duration, 2)
        },
        "test": {
            "rc": test_rc,
            "duration_seconds": round(test_duration, 2)
        },
        "timing": {
            "start_time": process_start.isoformat(),
            "end_time": process_end.isoformat(),
            "total_duration_seconds": round((process_end - process_start).total_seconds(), 2)
        }
    }
    
    # Save summary
    summary_file.write_text(json.dumps(convert_paths_to_strings(summary), indent=2))
    
    # Display results
    if args.verbose:
        print(f"\nVerification Status: {status}")
        if summary['build_validation']['build_status'] == 'FAIL':
            failure_info = summary['build_validation']['build_classification']
            print(f"Build Failed: {failure_info['type']} - {failure_info['reason']}")
        else:
            artifacts_count = summary['build_validation']['artifact_validation']['artifact_count']
            print(f"Build Passed: {artifacts_count} artifacts created")
        
        format_behavior_results_for_display(behavior_result, verbose=True)
    else:
        print(f"Status: {status}")
    
    sys.exit(0 if status == "PASS" else 1)


if __name__ == "__main__":
    main()