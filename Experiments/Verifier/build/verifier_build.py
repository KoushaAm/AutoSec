#!/usr/bin/env python3
import argparse, json, pathlib, subprocess, sys, shlex, time, datetime
from dataclasses import dataclass
from typing import Optional, List, Tuple

from behavior_check import execute_behavior_validation, format_behavior_results_for_display

def has(p: pathlib.Path, *names):
    return any((p / n).exists() for n in names)

def count_java_files(p: pathlib.Path) -> int:
    return len(list(p.rglob("*.java")))

@dataclass
class JavaBuildStack:
    name: str
    docker_image: str
    build_cmd_with_wrapper: str
    build_cmd_without_wrapper: str
    test_cmd_with_wrapper: Optional[str] = None
    test_cmd_without_wrapper: Optional[str] = None

    def get_build_command(self, has_wrapper: bool) -> str:
        return self.build_cmd_with_wrapper if has_wrapper else self.build_cmd_without_wrapper

    def get_test_command(self, has_wrapper: bool) -> Optional[str]:
        if self.test_cmd_with_wrapper and self.test_cmd_without_wrapper:
            return self.test_cmd_with_wrapper if has_wrapper else self.test_cmd_without_wrapper
        return None

def detect_java_project(p: pathlib.Path) -> Tuple[str, str, Optional[str], dict]:
    metadata = {
        "java_files": count_java_files(p),
        "project_size": "unknown"
    }
    
    java_count = metadata["java_files"]
    if java_count == 1:
        metadata["project_size"] = "single_file"
    elif java_count <= 10:
        metadata["project_size"] = "small"
    elif java_count <= 100:
        metadata["project_size"] = "medium"
    else:
        metadata["project_size"] = "large"

    if has(p, "pom.xml"):
        metadata["has_wrapper"] = has(p, "mvnw", "mvnw.cmd")
        metadata["wrapper_type"] = "maven" if metadata["has_wrapper"] else None
        
        maven = JavaBuildStack(
            name="maven",
            docker_image="maven:3.9-eclipse-temurin-17",
            build_cmd_with_wrapper="./mvnw clean compile -B",
            build_cmd_without_wrapper="mvn clean compile -B",
            test_cmd_with_wrapper="./mvnw test -B",
            test_cmd_without_wrapper="mvn test -B"
        )
        return maven.name, maven.get_build_command(metadata["has_wrapper"]), maven.get_test_command(metadata["has_wrapper"]), metadata

    if has(p, "build.gradle", "build.gradle.kts"):
        metadata["has_wrapper"] = has(p, "gradlew", "gradlew.bat")
        metadata["wrapper_type"] = "gradle" if metadata["has_wrapper"] else None
        
        gradle = JavaBuildStack(
            name="gradle",
            docker_image="gradle:8-jdk17",
            build_cmd_with_wrapper="./gradlew build --no-daemon",
            build_cmd_without_wrapper="gradle build --no-daemon",
            test_cmd_with_wrapper="./gradlew test --no-daemon",
            test_cmd_without_wrapper="gradle test --no-daemon"
        )
        return gradle.name, gradle.get_build_command(metadata["has_wrapper"]), gradle.get_test_command(metadata["has_wrapper"]), metadata

    if java_count > 0:
        javac = JavaBuildStack(
            name="javac",
            docker_image="eclipse-temurin:17-jdk",
            build_cmd_with_wrapper="javac *.java && mkdir -p out && mv *.class out/",
            build_cmd_without_wrapper="javac *.java && mkdir -p out && mv *.class out/"
        )
        return javac.name, javac.get_build_command(False), None, metadata

    metadata["error"] = "No Java files or recognized build system found"
    return None, None, None, metadata

def get_docker_image_for_stack(stack: str) -> str:
    images = {
        "maven": "maven:3.9-eclipse-temurin-17",
        "gradle": "gradle:8-jdk17", 
        "javac": "eclipse-temurin:17-jdk"
    }
    return images.get(stack, "eclipse-temurin:17-jdk")

def check_docker() -> bool:
    try:
        result = subprocess.run(["docker", "--version"], 
                              capture_output=True, text=True, timeout=10)
        if result.returncode != 0:
            return False
        
        result = subprocess.run(["docker", "ps"], 
                              capture_output=True, text=True, timeout=10)
        return result.returncode == 0
        
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return False

def get_image_digest(image: str) -> Optional[str]:
    try:
        cmd = ["docker", "inspect", "--format={{index .RepoDigests 0}}", image]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0 and result.stdout.strip():
            digest = result.stdout.strip()
            return digest if digest != "<no value>" else None
            
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass
    return None

def run_build_in_docker(image: str, cmd: str, worktree: pathlib.Path, artifacts: pathlib.Path,
                       timeout_seconds: int = 1800) -> Tuple[int, float]:
    artifacts.mkdir(parents=True, exist_ok=True)
    
    start_time = time.time()
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{worktree.absolute()}:/workspace",
        "-v", f"{artifacts.absolute()}:/artifacts", 
        "-w", "/workspace",
        image,
        "bash", "-c", cmd
    ]
    
    try:
        result = subprocess.run(
            docker_cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd=worktree
        )
        
        duration = time.time() - start_time
        log_file = artifacts / "build_log.txt"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"Command: {' '.join(docker_cmd)}\n")
            f.write(f"Return code: {result.returncode}\n")
            f.write(f"Duration: {duration:.2f}s\n\n")
            f.write("=== STDOUT ===\n")
            f.write(result.stdout)
            f.write("\n=== STDERR ===\n")
            f.write(result.stderr)
            
        return result.returncode, duration
        
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return 124, duration
    except Exception as e:
        duration = time.time() - start_time
        log_file = artifacts / "build_log.txt"
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"Docker execution failed: {e}\n")
        return 125, duration

def validate_build_artifacts(project_path: pathlib.Path, stack: str) -> dict:
    validation = {
        "artifacts_found": [],
        "artifact_count": 0,
        "has_artifacts": False
    }
    artifact_patterns = {
        "maven": ["target/**/*.class", "target/**/*.jar", "target/**/*.war"],
        "gradle": ["build/**/*.class", "build/**/*.jar", "build/**/*.war"],
        "javac": ["out/**/*.class", "*.class"]
    }
    
    patterns = artifact_patterns.get(stack, ["**/*.class"])
    
    for pattern in patterns:
        artifacts = list(project_path.glob(pattern))
        for artifact in artifacts:
            if artifact.is_file():
                validation["artifacts_found"].append(str(artifact.relative_to(project_path)))
    
    validation["artifact_count"] = len(validation["artifacts_found"])
    validation["has_artifacts"] = validation["artifact_count"] > 0
    
    return validation

def classify_build_failure(return_code: int) -> dict:
    classification = {
        "type": "unknown_failure",
        "action": "investigate",
        "reason": "Unknown failure"
    }
    if return_code == 0:
        classification.update({
            "type": "success",
            "action": "continue",
            "reason": "Build succeeded"
        })
    elif return_code == 1:
        classification.update({
            "type": "compilation_error", 
            "action": "stop",
            "reason": "Java compilation failed (javac)"
        })
    elif return_code == 124:
        classification.update({
            "type": "timeout",
            "action": "retry_with_longer_timeout",
            "reason": "Build timed out"
        })
    elif return_code == 125:
        classification.update({
            "type": "docker_error",
            "action": "check_docker_setup", 
            "reason": "Docker execution failed"
        })
    elif return_code == 2:
        classification.update({
            "type": "missing_dependencies",
            "action": "install_dependencies",
            "reason": "Missing build dependencies"
        })
    else:
        classification.update({
            "type": "build_failure",
            "action": "stop", 
            "reason": f"Unknown build failure (exit code {return_code})"
        })
    
    classification["return_code"] = return_code
    return classification

def main():
    """Main entry point for Java build verification"""
    parser = argparse.ArgumentParser(
        description="Java Build Verifier - Handles any Java project from single files to enterprise applications",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ex.:
  # Single Java file
  python3 verifier_build.py --input /path/to/HelloWorld.java --docker
  
  # Maven project  
  python3 verifier_build.py --input /path/to/maven-project --docker
  
  # Gradle project
  python3 verifier_build.py --input /path/to/gradle-project --docker
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
    parser.add_argument("--use-digest", action="store_true",
                       help="Use exact image digests for reproducible builds")
    
    args = parser.parse_args()
    
    if not check_docker():
        print("ERROR: Docker is not available or not running", file=sys.stderr)
        print("Please start Docker and try again", file=sys.stderr)
        sys.exit(2)
    
    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(2)
    
    if input_path.is_file():
        worktree = input_path.parent
        if args.verbose:
            print(f"Single file detected: {input_path.name}")
            print(f"Using parent directory as worktree: {worktree}")
    else:
        worktree = input_path
        if args.verbose:
            print(f"Directory project: {worktree}")
    
    artifacts = pathlib.Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    
    summary_file = artifacts / "build_summary.json"
    
    process_start = datetime.datetime.now(datetime.timezone.utc)
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
    
    image = get_docker_image_for_stack(stack)
    image_digest = get_image_digest(image)
    if args.use_digest and image_digest:
        actual_image = image_digest
    else:
        actual_image = image
        
    if args.verbose:
        print(f"Using Docker image: {image}")
    
    build_rc, build_duration = run_build_in_docker(
        actual_image, build_cmd, worktree, artifacts, args.timeout_build
    )
    build_failure = classify_build_failure(build_rc)
    artifact_validation = {"artifacts_found": [], "artifact_count": 0, "has_artifacts": False}
    build_passed = False
    
    if build_rc == 0:
        artifact_validation = validate_build_artifacts(worktree, stack)
        build_passed = build_rc == 0 and artifact_validation['has_artifacts']
        
        if args.verbose:
            print(f"Build: PASS ({artifact_validation['artifact_count']} artifacts)")
    else:
        if args.verbose:
            failure_type = build_failure['type']
            print(f"Build: FAIL ({failure_type})")

    test_rc, test_duration = 0, 0
    if test_cmd and build_rc == 0:
        test_rc, test_duration = run_build_in_docker(
            actual_image, test_cmd, worktree, artifacts, args.timeout_test
        )

    behavior_result = None
    if build_passed:
        from behavior_check import execute_behavior_validation
        behavior_result = execute_behavior_validation(
            worktree, artifacts, stack, actual_image,
            has_wrapper=metadata.get('has_wrapper', False),
            docker_runner_func=run_build_in_docker,
            timeout=args.timeout_test, verbose=args.verbose
        )

    behavior_passed = behavior_result is None or behavior_result['status'] in ['PASS', 'SKIP']
    status = "PASS" if build_passed and test_rc == 0 and behavior_passed else "FAIL"
    process_end = datetime.datetime.now(datetime.timezone.utc)
    summary = {
        "status": status,
        "detected_stack": stack,
        "docker_image": image,
        "docker_image_digest": image_digest,
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
    
    summary_file.write_text(json.dumps(summary, indent=2))
    
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