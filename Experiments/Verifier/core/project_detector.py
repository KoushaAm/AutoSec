#!/usr/bin/env python3
"""
Handling detection of Java project types (Maven, Gradle, plain javac)
and extracts project metadata for build planning
"""
import pathlib
from dataclasses import dataclass
from typing import Optional, Tuple, Dict, Any


def has_files(project_path: pathlib.Path, *filenames) -> bool:
    """check if any of the specified files exist in the project path"""
    return any((project_path / filename).exists() for filename in filenames)


def count_java_files(project_path: pathlib.Path) -> int:
    """count all Java source files in the project recursively"""
    return len(list(project_path.rglob("*.java")))


@dataclass
class JavaBuildStack:
    """represents a Java build system config"""
    name: str
    build_cmd_with_wrapper: str
    build_cmd_without_wrapper: str
    test_cmd_with_wrapper: Optional[str] = None
    test_cmd_without_wrapper: Optional[str] = None

    def get_build_command(self, has_wrapper: bool) -> str:
        """get appropriate build command based on wrapper availability."""
        return self.build_cmd_with_wrapper if has_wrapper else self.build_cmd_without_wrapper

    def get_test_command(self, has_wrapper: bool) -> Optional[str]:
        """get appropriate test command based on wrapper availability."""
        if self.test_cmd_with_wrapper and self.test_cmd_without_wrapper:
            return self.test_cmd_with_wrapper if has_wrapper else self.test_cmd_without_wrapper
        return None


class JavaProjectDetector:
    """detects Java project types and builds metadata for verification."""
    
    def __init__(self):
        self._build_stacks = self._initialize_build_stacks()
    
    def _initialize_build_stacks(self) -> Dict[str, JavaBuildStack]:
        return {
            "maven": JavaBuildStack(
                name="maven",
                build_cmd_with_wrapper="./mvnw clean compile -B",
                build_cmd_without_wrapper="mvn clean compile -B",
                test_cmd_with_wrapper="./mvnw test -B",
                test_cmd_without_wrapper="mvn test -B"
            ),
            "gradle": JavaBuildStack(
                name="gradle",
                build_cmd_with_wrapper="./gradlew build --no-daemon",
                build_cmd_without_wrapper="gradle build --no-daemon",
                test_cmd_with_wrapper="./gradlew test --no-daemon",
                test_cmd_without_wrapper="gradle test --no-daemon"
            ),
            "javac": JavaBuildStack(
                name="javac",
                build_cmd_with_wrapper="javac *.java && mkdir -p out && mv *.class out/",
                build_cmd_without_wrapper="javac *.java && mkdir -p out && mv *.class out/"
            )
        }
    
    def detect_project(self, project_path: pathlib.Path) -> Tuple[Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
        """
        Returns:
            Tuple of (stack_name, build_command, test_command, metadata)
        """
        metadata = self._build_project_metadata(project_path)
        
        # Check for Maven 
        if has_files(project_path, "pom.xml"):
            return self._configure_maven_project(project_path, metadata)
        
        # Check for Gradle 
        if has_files(project_path, "build.gradle", "build.gradle.kts"):
            return self._configure_gradle_project(project_path, metadata)
        
        # Check for plain Java 
        if metadata["java_files"] > 0:
            return self._configure_javac_project(project_path, metadata)
        
        # No recognizable Java project found
        metadata["error"] = "No Java files or recognized build system found"
        return None, None, None, metadata
    
    def _build_project_metadata(self, project_path: pathlib.Path) -> Dict[str, Any]:
        java_count = count_java_files(project_path)
        
        metadata = {
            "java_files": java_count,
            "project_size": self._classify_project_size(java_count),
            "has_wrapper": False,
            "wrapper_type": None
        }
        
        return metadata
    
    def _classify_project_size(self, java_count: int) -> str:
        """project size based on number of Java files"""
        if java_count == 1:
            return "single_file"
        elif java_count <= 10:
            return "small"
        elif java_count <= 100:
            return "medium"
        else:
            return "large"
    
    def _configure_maven_project(self, project_path: pathlib.Path, metadata: Dict[str, Any]) -> Tuple[str, str, str, Dict[str, Any]]:
        """config Maven project detection results"""
        metadata["has_wrapper"] = has_files(project_path, "mvnw", "mvnw.cmd")
        metadata["wrapper_type"] = "maven" if metadata["has_wrapper"] else None
        
        maven_stack = self._build_stacks["maven"]
        return (
            maven_stack.name,
            maven_stack.get_build_command(metadata["has_wrapper"]),
            maven_stack.get_test_command(metadata["has_wrapper"]),
            metadata
        )
    
    def _configure_gradle_project(self, project_path: pathlib.Path, metadata: Dict[str, Any]) -> Tuple[str, str, str, Dict[str, Any]]:
        """config Gradle project detection results"""
        metadata["has_wrapper"] = has_files(project_path, "gradlew", "gradlew.bat")
        metadata["wrapper_type"] = "gradle" if metadata["has_wrapper"] else None
        
        gradle_stack = self._build_stacks["gradle"]
        return (
            gradle_stack.name,
            gradle_stack.get_build_command(metadata["has_wrapper"]),
            gradle_stack.get_test_command(metadata["has_wrapper"]),
            metadata
        )
    
    def _configure_javac_project(self, project_path: pathlib.Path, metadata: Dict[str, Any]) -> Tuple[str, str, Optional[str], Dict[str, Any]]:
        """config plain javac project detection results"""
        javac_stack = self._build_stacks["javac"]
        return (
            javac_stack.name,
            javac_stack.get_build_command(False),
            None,  # No test command for plain javac projects
            metadata
        )


# Convenience function for backward compatibility
def detect_java_project(project_path: pathlib.Path) -> Tuple[Optional[str], Optional[str], Optional[str], Dict[str, Any]]:
    """
    cetect poject type and return build configuration
    
    This is a convenience function that maintains backward compatibility
    with the original verifier_build.py interface.
    """
    detector = JavaProjectDetector()
    return detector.detect_project(project_path)