#!/usr/bin/env python3
import argparse, json, pathlib, subprocess, sys, shlex, time, datetime
from dataclasses import dataclass
from typing import Optional, List, Tuple

def has(p: pathlib.Path, *names):
    """check if any of the given file names exist in a directory"""
    return any((p / n).exists() for n in names)

def count_java_files(p: pathlib.Path) -> int:
    """count total .java files in the project"""
    return len(list(p.rglob("*.java")))

@dataclass
class JavaBuildStack:
    """encapsulates Java build system detection and Docker configuration"""
    name: str
    docker_image: str
    build_cmd_with_wrapper: str
    build_cmd_without_wrapper: str
    test_cmd_with_wrapper: Optional[str]
    test_cmd_without_wrapper: Optional[str]
    marker_files: List[str]
    wrapper_files: List[str]
    priority: int  # lower number = higher priority
    
    def get_build_cmd(self, has_wrapper: bool) -> str:
        """Get the actual build command based on wrapper availability"""
        return self.build_cmd_with_wrapper if has_wrapper else self.build_cmd_without_wrapper
    
    def get_test_cmd(self, has_wrapper: bool) -> Optional[str]:
        """Get the actual test command based on wrapper availability"""
        if not self.test_cmd_with_wrapper and not self.test_cmd_without_wrapper:
            return None
        return self.test_cmd_with_wrapper if has_wrapper else self.test_cmd_without_wrapper

JAVA_BUILD_STACKS = [
    # maven - highest priority for enterprise java
    JavaBuildStack(
        name="maven",
        docker_image="maven:3.9-eclipse-temurin-17",
        build_cmd_with_wrapper="./mvnw clean compile -B -DskipTests",
        build_cmd_without_wrapper="mvn clean compile -B -DskipTests",
        test_cmd_with_wrapper="./mvnw test -B",
        test_cmd_without_wrapper="mvn test -B",
        marker_files=["pom.xml"],
        wrapper_files=["mvnw"],
        priority=1
    ),
    # gradle - second priority
    JavaBuildStack(
        name="gradle", 
        docker_image="gradle:8.8-jdk17",
        build_cmd_with_wrapper="./gradlew clean compileJava -Dorg.gradle.daemon=false --no-build-cache",
        build_cmd_without_wrapper="gradle clean compileJava -Dorg.gradle.daemon=false --no-build-cache",
        test_cmd_with_wrapper="./gradlew test -Dorg.gradle.daemon=false",
        test_cmd_without_wrapper="gradle test -Dorg.gradle.daemon=false",
        marker_files=["build.gradle", "build.gradle.kts"],
        wrapper_files=["gradlew"],
        priority=2
    ),
    # javac - fallback for any java files
    JavaBuildStack(
        name="javac",
        docker_image="eclipse-temurin:17-jdk",
        build_cmd_with_wrapper="find . -name '*.java' -print0 | xargs -0 javac -d out -cp out",
        build_cmd_without_wrapper="find . -name '*.java' -print0 | xargs -0 javac -d out -cp out",
        test_cmd_with_wrapper=None,
        test_cmd_without_wrapper=None,
        marker_files=[],  # special case - any .java files
        wrapper_files=[],
        priority=99  # lowest priority - fallback only
    )
]

def check_docker() -> bool:
    try:
        result = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"], 
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def detect_java_project(project: pathlib.Path) -> Tuple[Optional[str], Optional[str], Optional[str], dict]:
    """
    Return (stack_name, build_command, test_command, metadata)
    Handles everything from single .java files to bigger projects
    """
    
    java_file_count = count_java_files(project)
    if java_file_count == 0:
        return None, None, None, {"java_files": 0, "error": "No .java files found"}
    
    metadata = {
        "java_files": java_file_count,
        "project_size": "single_file" if java_file_count == 1 else 
                       "small" if java_file_count <= 10 else
                       "medium" if java_file_count <= 100 else "large"
    }
    
    # sort by prio and check each build system
    for stack in sorted(JAVA_BUILD_STACKS, key=lambda x: x.priority):
        
        if stack.name == "javac":
            # fallback - if we have java files but no build system
            if java_file_count > 0:
                # create output directory in the build command
                build_cmd = "mkdir -p out && " + stack.get_build_cmd(False)
                return stack.name, build_cmd, stack.get_test_cmd(False), metadata
            continue
            
        # check for build system marker files
        if has(project, *stack.marker_files):
            has_wrapper = has(project, *stack.wrapper_files)
            metadata["has_wrapper"] = has_wrapper
            metadata["wrapper_type"] = stack.wrapper_files[0] if has_wrapper else None
            
            return (
                stack.name,
                stack.get_build_cmd(has_wrapper),
                stack.get_test_cmd(has_wrapper),
                metadata
            )
    
    # should never reach here due to javac fallback
    return None, None, None, metadata

def get_docker_image_for_stack(stack_name: str) -> Optional[str]:
    """get Docker image for a given stack name"""
    for stack in JAVA_BUILD_STACKS:
        if stack.name == stack_name:
            return stack.docker_image
    return None

def get_image_digest(image: str) -> Optional[str]:
    """get the actual image digest for reproducibility tracking"""
    try:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{index .RepoDigests 0}}", image],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except subprocess.TimeoutExpired:
        pass
    return None

def run_build_in_docker(image: str, cmd: str, worktree: pathlib.Path, artifacts: pathlib.Path,
                       timeout: int, log_path: pathlib.Path) -> Tuple[int, float]:
    """Execute build command in Docker container with full logging"""
    start_time = time.time()
    
    # construct docker run command
    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{worktree.resolve()}:/workspace",
        "-v", f"{artifacts.resolve()}:/artifacts",  
        "-w", "/workspace",
        image, "bash", "-lc", cmd
    ]
    
    # logging
    with open(log_path, "w", encoding="utf-8", errors="ignore") as log:
        log.write(f"Build Command: {cmd}\n")
        log.write(f"Docker Command: {' '.join(shlex.quote(x) for x in docker_cmd)}\n")
        log.write(f"Started: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
        log.write("-" * 80 + "\n\n")
        
        try:
            returncode = subprocess.run(
                docker_cmd, 
                stdout=log, 
                stderr=subprocess.STDOUT, 
                timeout=timeout
            ).returncode
            
            duration = time.time() - start_time
            log.write(f"\n\n" + "-" * 80 + "\n")
            log.write(f"Completed: {datetime.datetime.now(datetime.timezone.utc).isoformat()}\n")
            log.write(f"Duration: {duration:.2f}s\n")
            log.write(f"Exit Code: {returncode}\n")
            
            return returncode, duration
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            log.write(f"\n\n[TIMEOUT] Process killed after {duration:.1f}s\n")
            return 124, duration  # timeout exit code

def main():
    """Main entry point for Java build verification"""
    
    # command line interface
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
    
    # validate docker availability
    if not check_docker():
        print("ERROR: Docker is not available or not running", file=sys.stderr)
        print("Please start Docker and try again", file=sys.stderr)
        sys.exit(2)
    
    # setup paths - handle both files and directories
    input_path = pathlib.Path(args.input)
    if not input_path.exists():
        print(f"ERROR: Input path does not exist: {input_path}", file=sys.stderr)
        sys.exit(2)
    
    # if input is a single file, use its parent directory as worktree
    if input_path.is_file():
        worktree = input_path.parent
        if args.verbose:
            print(f"Single file detected: {input_path.name}")
            print(f"Using parent directory as worktree: {worktree}")
    else:
        worktree = input_path
        if args.verbose:
            print(f"Directory project: {worktree}")
    
    # setup artifacts directory
    artifacts = pathlib.Path(args.artifacts)
    artifacts.mkdir(parents=True, exist_ok=True)
    
    build_log = artifacts / "build.log"
    test_log = artifacts / "test.log"
    summary_file = artifacts / "build_summary.json"
    
    # record start time
    process_start = datetime.datetime.now(datetime.timezone.utc)
    
    if args.verbose:
        print(f"Starting Java build verification at {process_start.isoformat()}")
    
    # detect java project type and build system
    stack, build_cmd, test_cmd, metadata = detect_java_project(worktree)
    
    if args.verbose:
        print(f"Detected: {stack} ({metadata.get('java_files', 0)} Java files)")
    
    # handle detection failure
    if not build_cmd:
        error_msg = metadata.get('error', 'Unknown detection error')
        build_log.write_text(f"Java project detection failed: {error_msg}\n")
        
        summary = {
            "status": "FAIL",
            "error": error_msg,
            "detected_stack": None,
            "metadata": metadata,
            "build": {"rc": 2, "log": str(build_log), "duration_seconds": 0},
            "test": {"rc": 0, "log": None, "duration_seconds": 0},
            "start_time": process_start.isoformat(),
            "end_time": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        
        summary_file.write_text(json.dumps(summary, indent=2))
        print(json.dumps(summary, indent=2))
        sys.exit(1)
    
    # get docker image
    image = get_docker_image_for_stack(stack)
    image_digest = get_image_digest(image)
    
    # use digest if requested and available
    if args.use_digest and image_digest:
        actual_image = image_digest
        if args.verbose:
            print(f"Using exact digest: {image_digest}")
    else:
        actual_image = image
        if args.verbose:
            print(f"Using Docker image: {image}")
            if image_digest:
                print(f"Image digest: {image_digest}")
    
    # execute build
    if args.verbose:
        print("Starting build phase...")
    
    build_rc, build_duration = run_build_in_docker(
        actual_image, build_cmd, worktree, artifacts, args.timeout_build, build_log
    )
    
    # execute tests if build succeeded and tests are available
    test_rc, test_duration = 0, 0
    if test_cmd and build_rc == 0:
        if args.verbose:
            print("Build succeeded, starting test phase...")
        test_rc, test_duration = run_build_in_docker(
            actual_image, test_cmd, worktree, artifacts, args.timeout_test, test_log
        )
    elif test_cmd and build_rc != 0:
        if args.verbose:
            print("Build failed, skipping tests")
    
    # determine final status
    status = "OK" if build_rc == 0 and test_rc == 0 else "FAIL"
    process_end = datetime.datetime.now(datetime.timezone.utc)
    
    # create summary
    summary = {
        "status": status,
        "detected_stack": stack,
        "docker_image": image,
        "docker_image_digest": image_digest,
        "metadata": metadata,
        "build": {
            "rc": build_rc,
            "log": str(build_log),
            "duration_seconds": round(build_duration, 2)
        },
        "test": {
            "rc": test_rc,
            "log": str(test_log) if test_cmd else None,
            "duration_seconds": round(test_duration, 2)
        },
        "timing": {
            "start_time": process_start.isoformat(),
            "end_time": process_end.isoformat(),
            "total_duration_seconds": round((process_end - process_start).total_seconds(), 2)
        }
    }
    
    # write summary and display results
    summary_file.write_text(json.dumps(summary, indent=2))
    
    if args.verbose:
        print(f"\nBuild completed with status: {status}")
        print(f"Total duration: {summary['timing']['total_duration_seconds']}s")
        print(f"Artifacts written to: {artifacts}")
        print(f"Build log: {build_log}")
        print(f"Summary JSON: {summary_file}")
        if status == "FAIL":
            print(f";Check {build_log} for error details")
    
    # always output the machine-readable JSON for automation
    print(json.dumps(summary, indent=2))
    
    # exit with appropriate code
    sys.exit(0 if status == "OK" else 1)

if __name__ == "__main__":
    main()
