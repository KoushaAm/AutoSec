"""
Core Verifier Module

Contains the main verification components:
- project_detector: Java project detection and analysis
- docker_runner: Docker container execution and management
- artifact_validator: Build artifact validation and analysis
- main: Main entry point for the verification pipeline
"""

from .project_detector import detect_java_project, JavaProjectDetector
from .docker_runner import (
    DockerRunner, check_docker, get_docker_image_for_stack,
    classify_build_failure
)
from .artifact_validator import validate_build_artifacts, BuildArtifactValidator
from .main import main

__all__ = [
    'detect_java_project', 'JavaProjectDetector',
    'DockerRunner', 'check_docker', 'get_docker_image_for_stack',
    'classify_build_failure',
    'validate_build_artifacts', 'BuildArtifactValidator',
    'main'
]