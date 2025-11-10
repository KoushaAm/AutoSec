#!/usr/bin/env python3
import pathlib
import subprocess
import time
from typing import Tuple, Optional, Dict


class DockerRunner:
    """Manages Docker container execution for build and test operations"""
    
    # Docker image mappings for different build stacks
    STACK_IMAGES = {
        "maven": "maven:3.9-eclipse-temurin-17",
        "gradle": "gradle:8-jdk17",
        "javac": "eclipse-temurin:17-jdk"
    }
    
    @classmethod
    def check_docker_availability(cls) -> bool:
        """Check if Docker is installed and running"""
        try:
            # Check if docker command exists
            result = subprocess.run(
                ["docker", "--version"], 
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return False
            
            # Check if Docker daemon is running
            result = subprocess.run(
                ["docker", "ps"], 
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
            
        except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
            return False
    
    @classmethod
    def get_image_for_stack(cls, stack: str) -> str:
        """Get appropriate Docker image for a build stack"""
        return cls.STACK_IMAGES.get(stack, cls.STACK_IMAGES["javac"])
    
    def __init__(self):
        """Initialize Docker runner"""
        pass
    
    def run_command(
        self, 
        image: str, 
        command: str, 
        work_dir: pathlib.Path, 
        artifacts_dir: pathlib.Path,
        timeout_seconds: int = 1800
    ) -> Tuple[int, float]:
        """
        Args:
            image: Docker image to use
            command: Command to execute in container
            work_dir: Host directory to mount as /workspace
            artifacts_dir: Host directory to mount as /artifacts
            timeout_seconds: Maximum execution time
            
        Returns:
            Tuple of (return_code, duration_seconds)
        """
        # Ensure artifacts directory exists
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        # Build Docker command
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{work_dir.absolute()}:/workspace",
            "-v", f"{artifacts_dir.absolute()}:/artifacts", 
            "-w", "/workspace",
            image,
            "bash", "-c", command
        ]
        
        start_time = time.time()
        
        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                cwd=work_dir
            )
            
            duration = time.time() - start_time
            
            # Log execution results
            self._log_execution(
                artifacts_dir, docker_cmd, result.returncode, 
                result.stdout, result.stderr, duration
            )
            
            return result.returncode, duration
            
        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            self._log_timeout(artifacts_dir, docker_cmd, duration, timeout_seconds)
            return 124, duration  # Standard timeout exit code
            
        except Exception as e:
            duration = time.time() - start_time
            self._log_error(artifacts_dir, docker_cmd, str(e), duration)
            return 125, duration  # Docker execution error code
    
    def _log_execution(
        self, 
        artifacts_dir: pathlib.Path, 
        docker_cmd: list, 
        return_code: int,
        stdout: str, 
        stderr: str, 
        duration: float
    ):
        """Log Docker execution results to artifacts directory"""
        log_file = artifacts_dir / "build_log.txt"
        
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"Command: {' '.join(docker_cmd)}\n")
            f.write(f"Return code: {return_code}\n")
            f.write(f"Duration: {duration:.2f}s\n\n")
            f.write("=== STDOUT ===\n")
            f.write(stdout)
            f.write("\n=== STDERR ===\n")
            f.write(stderr)
    
    def _log_timeout(
        self, 
        artifacts_dir: pathlib.Path, 
        docker_cmd: list, 
        duration: float,
        timeout_seconds: int
    ):
        """Log Docker timeout to artifacts directory"""
        log_file = artifacts_dir / "build_log.txt"
        
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"Command: {' '.join(docker_cmd)}\n")
            f.write(f"Status: TIMEOUT after {timeout_seconds}s\n")
            f.write(f"Actual duration: {duration:.2f}s\n")
            f.write("Docker command execution timed out\n")
    
    def _log_error(
        self, 
        artifacts_dir: pathlib.Path, 
        docker_cmd: list, 
        error_msg: str,
        duration: float
    ):
        """Log Docker execution error to artifacts directory"""
        log_file = artifacts_dir / "build_log.txt"
        
        with log_file.open("w", encoding="utf-8") as f:
            f.write(f"Command: {' '.join(docker_cmd)}\n")
            f.write(f"Status: ERROR\n")
            f.write(f"Duration: {duration:.2f}s\n")
            f.write(f"Docker execution failed: {error_msg}\n")


class BuildFailureClassifier:
    """Classifies build failures based on return codes and provides actionable feedback"""
    
    @staticmethod
    def classify_failure(return_code: int) -> Dict[str, str]:
        """
        Classify build failure based on return code.
        
        Args:
            return_code: Process return code
            
        Returns:
            Dictionary with failure classification details
        """
        classification = {
            "return_code": return_code,
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
        
        return classification


# Convenience functions for backward compatibility
def check_docker() -> bool:
    """Check if Docker is available and running"""
    return DockerRunner.check_docker_availability()


def get_docker_image_for_stack(stack: str) -> str:
    """Get Docker image for build stack"""
    return DockerRunner.get_image_for_stack(stack)


def run_build_in_docker(
    image: str, 
    cmd: str, 
    worktree: pathlib.Path, 
    artifacts: pathlib.Path,
    timeout_seconds: int = 1800
) -> Tuple[int, float]:
    """Run build command in Docker container"""
    runner = DockerRunner()
    return runner.run_command(image, cmd, worktree, artifacts, timeout_seconds)


def classify_build_failure(return_code: int) -> Dict[str, str]:
    """Classify build failure based on return code"""
    return BuildFailureClassifier.classify_failure(return_code)