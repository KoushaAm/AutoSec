#!/usr/bin/env python3
"""
Unified Docker Build Runner with Retry Strategy

Inspired by IRIS/CWE-Bench-Java, this runner tries multiple Docker image combinations
until a successful build is found. Successful configurations are cached per project
for faster subsequent builds.
"""
import subprocess
import pathlib
import time
import json
from typing import Dict, Any, Tuple, Optional


class DockerRunner:
    """
    Unified Docker runner with intelligent retry strategy.
    
    Tries multiple JDK/build-tool combinations using pre-built official Docker images instead of local installations.
    """
    # Retry attempts aligned with CWE-Bench's proven success rates
    # Uses multi-arch images that work on both Intel (x86-64) and Apple Silicon (ARM64)
    BUILD_ATTEMPTS = {
        "maven": [
            # Attempt 1: Java 8 + Maven 3.9 (Temurin supports ARM64)
            {"image": "maven:3.9-eclipse-temurin-8", "jdk": "8", "tool": "3.9"},
            
            # Attempt 2: Java 17 + Maven 3.9 (modern default)
            {"image": "maven:3.9-eclipse-temurin-17", "jdk": "17", "tool": "3.9"},
            
            # Attempt 3: Java 11 + Maven 3.8
            {"image": "maven:3.8-openjdk-11", "jdk": "11", "tool": "3.8"},
            
            # Attempt 4: Java 8 + Maven 3.8 (Temurin)
            {"image": "maven:3.8-eclipse-temurin-8", "jdk": "8", "tool": "3.8"},
            
            # Attempt 5: Java 17 + Maven 3.8
            {"image": "maven:3.8-eclipse-temurin-17", "jdk": "17", "tool": "3.8"},
            
            # Attempt 6: Java 21 + Maven 3.9 (very modern projects)
            {"image": "maven:3.9-eclipse-temurin-21", "jdk": "21", "tool": "3.9"},
        ],
        
        "gradle": [
            # Attempt 1: Gradle 8 + Java 8 (modern Gradle with Java 8)
            {"image": "gradle:8-jdk8", "jdk": "8", "tool": "8"},
            
            # Attempt 2: Modern Gradle 8 + Java 17
            {"image": "gradle:8-jdk17", "jdk": "17", "tool": "8"},
            
            # Attempt 3: Gradle 8 + Java 11
            {"image": "gradle:8-jdk11", "jdk": "11", "tool": "8"},
            
            # Attempt 4: Gradle 7 + Java 11
            {"image": "gradle:7-jdk11", "jdk": "11", "tool": "7"},
            
            # Attempt 5: Gradle 8 + Java 21 (very modern)
            {"image": "gradle:8-jdk21", "jdk": "21", "tool": "8"},
        ],
        
        "javac": [
            # Attempt 1: Java 8 (Eclipse Temurin - supports ARM64)
            {"image": "eclipse-temurin:8-jdk", "jdk": "8", "tool": "n/a"},
            
            # Attempt 2: Java 17 (current LTS)
            {"image": "eclipse-temurin:17-jdk", "jdk": "17", "tool": "n/a"},
            
            # Attempt 3: Java 11 (older LTS)
            {"image": "eclipse-temurin:11-jdk", "jdk": "11", "tool": "n/a"},
            
            # Attempt 4: Java 21 (newest LTS)
            {"image": "eclipse-temurin:21-jdk", "jdk": "21", "tool": "n/a"},
        ],
    }
    
    def __init__(self, cache_dir: Optional[pathlib.Path] = None):
        """
        Initialize Docker runner with optional cache directory for build configs.
        
        Args:
            cache_dir: Directory to store successful build configurations.
                      Defaults to ./build-cache/ in current directory.
        """
        self.cache_dir = cache_dir or pathlib.Path("./build-cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
    
    def run_command(
        self, 
        image: str, 
        command: str, 
        worktree: pathlib.Path, 
        artifacts: pathlib.Path, 
        timeout: int
    ) -> Tuple[int, float]:
        """Execute a command in a Docker container."""
        worktree_abs = worktree.resolve()
        artifacts_abs = artifacts.resolve()
        
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{worktree_abs}:/workspace",
            "-v", f"{artifacts_abs}:/artifacts",
            "-w", "/workspace",
            image,
            "sh", "-c", command
        ]
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                text=True
            )
            duration = time.time() - start_time
            
            # Save output to artifacts
            (artifacts_abs / "docker_stdout.log").write_text(result.stdout, encoding='utf-8')
            (artifacts_abs / "docker_stderr.log").write_text(result.stderr, encoding='utf-8')
            
            return result.returncode, duration
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return 124, duration  # Timeout exit code
        except Exception as e:
            duration = time.time() - start_time
            (artifacts_abs / "docker_error.log").write_text(str(e), encoding='utf-8')
            return 125, duration  # Generic error
    
    def build_with_retry(
        self,
        stack: str,
        build_cmd: str,
        worktree: pathlib.Path,
        artifacts: pathlib.Path,
        timeout: int,
        project_identifier: Optional[str] = None,
        verbose: bool = False,
        test_cmd: Optional[str] = None  
    ) -> Dict[str, Any]:
        """
        Build a project with automatic retry using multiple Docker images.
        
        Now includes optional test validation during retry to catch runtime issues
        like PowerMock incompatibility that only appear when tests execute.
        
        Args:
            stack: Build system type ("maven", "gradle", "javac")
            build_cmd: Build command to execute
            worktree: Project directory
            artifacts: Artifacts output directory
            timeout: Command timeout in seconds
            project_identifier: Unique project ID for caching (optional)
            verbose: Print detailed progress
            test_cmd: Optional test command to validate during retry
            
        Returns:
            Dictionary with build and test validation results
        """
        if stack not in self.BUILD_ATTEMPTS:
            return {
                "success": False,
                "error": f"Unknown stack type: {stack}",
                "return_code": 1,
                "duration": 0.0
            }
        
        # Check if we have a cached working config for this project
        cached_config = None
        if project_identifier:
            cached_config = self._load_cached_config(project_identifier)
            if cached_config:
                if verbose:
                    print(f"[Build] Using cached config: {cached_config['image']} (JDK {cached_config['jdk']}, {stack.title()} {cached_config['tool']})")
                
                # Try cached config first
                rc, duration = self.run_command(
                    cached_config['image'], 
                    build_cmd, 
                    worktree, 
                    artifacts, 
                    timeout
                )
                
                # Validate tests if provided
                test_passed = True
                if rc == 0 and test_cmd:
                    test_rc, test_duration = self.run_command(
                        cached_config['image'],
                        test_cmd,
                        worktree,
                        artifacts,
                        timeout
                    )
                    test_passed = (test_rc == 0)
                    duration += test_duration
                
                if rc == 0 and test_passed:
                    return {
                        "success": True,
                        "return_code": rc,
                        "duration": duration,
                        "image_used": cached_config['image'],
                        "config": cached_config,
                        "attempt_number": 0,
                        "from_cache": True
                    }
                elif verbose:
                    reason = "build failed" if rc != 0 else "tests failed"
                    print(f"[Build] Cached config {reason} (RC={rc}), trying alternatives...")
        
        # Try each image configuration in sequence
        attempts = self.BUILD_ATTEMPTS[stack]
        
        for attempt_num, attempt in enumerate(attempts, start=1):
            image = attempt['image']
            jdk = attempt['jdk']
            tool_version = attempt['tool']
            
            if verbose:
                print(f"[Build] Attempt {attempt_num}/{len(attempts)}: {image} (JDK {jdk}, {stack.title()} {tool_version})...")
            
            rc, duration = self.run_command(image, build_cmd, worktree, artifacts, timeout)
            
            # NEW: If build succeeded but we have tests, validate them too
            test_passed = True
            if rc == 0 and test_cmd:
                if verbose:
                    print(f"[Build] Build succeeded, validating tests...")
                test_rc, test_duration = self.run_command(image, test_cmd, worktree, artifacts, timeout)
                test_passed = (test_rc == 0)
                duration += test_duration
                
                if not test_passed and verbose:
                    print(f"[Build] ✗ Tests failed with RC={test_rc}, trying next image...")
            
            if rc == 0 and test_passed:
                if verbose:
                    print(f"[Build] ✓ Success with {image} in {duration:.1f}s")
                
                # Save successful config to cache
                if project_identifier:
                    self._save_cached_config(project_identifier, attempt)
                
                return {
                    "success": True,
                    "return_code": rc,
                    "duration": duration,
                    "image_used": image,
                    "config": attempt,
                    "attempt_number": attempt_num,
                    "from_cache": False
                }
            elif verbose:
                if rc != 0:
                    print(f"[Build] ✗ Build failed with RC={rc}")
                # Test failure message already printed above
        
        # All attempts failed
        if verbose:
            print(f"[Build] All {len(attempts)} attempts failed")
        
        return {
            "success": False,
            "return_code": rc,
            "duration": duration,
            "image_used": attempts[-1]['image'],
            "config": attempts[-1],
            "attempt_number": len(attempts),
            "from_cache": False,
            "error": "All build attempts failed"
        }
    
    def _load_cached_config(self, project_identifier: str) -> Optional[Dict[str, Any]]:
        """Load cached build configuration for a project."""
        cache_file = self.cache_dir / f"{project_identifier}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text())
            except Exception:
                return None
        return None
    
    def _save_cached_config(self, project_identifier: str, config: Dict[str, Any]):
        """Save successful build configuration for a project."""
        cache_file = self.cache_dir / f"{project_identifier}.json"
        try:
            cache_file.write_text(json.dumps(config, indent=2))
        except Exception:
            pass  # Cache failure is not critical


def check_docker() -> bool:
    """Check if Docker is available and running."""
    try:
        result = subprocess.run(
            ["docker", "ps"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False


def get_docker_image_for_stack(stack: str) -> str:
    """
    Get default Docker image for a stack type.
    
    This is now primarily used as a fallback. The main build_with_retry()
    method handles intelligent image selection.
    """
    default_images = {
        "maven": "maven:3.9-eclipse-temurin-17",
        "gradle": "gradle:8-jdk17",
        "javac": "eclipse-temurin:17-jdk"
    }
    return default_images.get(stack, "eclipse-temurin:17-jdk")


def classify_build_failure(return_code: int) -> Dict[str, str]:
    """Classify build failure based on return code."""
    if return_code == 0:
        return {"type": "success", "reason": "Build completed successfully"}
    elif return_code == 1:
        return {"type": "compilation_error", "reason": "Compilation or build script failure"}
    elif return_code == 124:
        return {"type": "timeout", "reason": "Build exceeded time limit"}
    elif return_code == 125:
        return {"type": "docker_error", "reason": "Docker execution error"}
    else:
        return {"type": "unknown", "reason": f"Build failed with exit code {return_code}"}