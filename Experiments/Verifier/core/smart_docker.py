#!/usr/bin/env python3
import pathlib
import subprocess
import time
import tempfile
import shutil
from typing import Tuple, Dict, Optional
from .version_detector import detect_project_versions


class SmartDockerSelector:
    """Selects optimal Docker images based on project version requirements"""
    
    OFFICIAL_IMAGE_MATRIX = {
        "maven": {
            "8.3.8": "maven:3.8-openjdk-8",
            "8.3.9": "maven:3.9-openjdk-8", 
            "11.3.8": "maven:3.8-openjdk-11",
            "11.3.9": "maven:3.9-openjdk-11",
            "17.3.8": "maven:3.8-eclipse-temurin-17",
            "17.3.9": "maven:3.9-eclipse-temurin-17",
            "21.3.9": "maven:3.9-eclipse-temurin-21",
        },
        "gradle": {
            "8.7": "gradle:7-jdk8",
            "8.8": "gradle:8-jdk8",
            "11.7": "gradle:7-jdk11", 
            "11.8": "gradle:8-jdk11",
            "17.7": "gradle:7-jdk17",
            "17.8": "gradle:8-jdk17",
            "21.8": "gradle:8-jdk21",
        },
        "javac": {
            "8": "openjdk:8-jdk",
            "11": "eclipse-temurin:11-jdk", 
            "17": "eclipse-temurin:17-jdk",
            "21": "eclipse-temurin:21-jdk",
        }
    }
    
    def __init__(self):
        self.templates_dir = pathlib.Path(__file__).parent / "docker_templates"
        
    def get_best_image_for_project(
        self, 
        project_path: pathlib.Path, 
        stack: str
    ) -> Tuple[str, bool, Dict[str, str]]:
        """Returns tuple of (image_name, is_custom_built, detected_versions)"""
        versions = detect_project_versions(project_path, stack)
        
        # Try to find matching official image
        official_image = self._find_matching_official_image(versions)
        if official_image:
            return official_image, False, versions
        
        # Build custom image with exact versions
        custom_image = self._build_custom_image(project_path, versions)
        if custom_image:
            return custom_image, True, versions
        
        # Fallback to default official image
        fallback_image = self._get_fallback_image(stack)
        return fallback_image, False, versions
    
    def _find_matching_official_image(self, versions: Dict[str, str]) -> Optional[str]:
        stack = versions["stack"]
        java_version = versions["java_version"]
        build_tool_version = versions.get("build_tool_version")
        
        if stack not in self.OFFICIAL_IMAGE_MATRIX:
            return None
        
        stack_matrix = self.OFFICIAL_IMAGE_MATRIX[stack]
        
        if stack in ["maven", "gradle"] and build_tool_version:
            key = f"{java_version}.{build_tool_version}"
            if key in stack_matrix:
                return stack_matrix[key]
            
            # Try major version match (e.g., 3.9.6 -> 3.9)
            major_build_version = ".".join(build_tool_version.split(".")[:2])
            key = f"{java_version}.{major_build_version}"
            if key in stack_matrix:
                return stack_matrix[key]
        
        elif stack == "javac":
            if java_version in stack_matrix:
                return stack_matrix[java_version]
        
        return None
    
    def _build_custom_image(
        self, 
        project_path: pathlib.Path, 
        versions: Dict[str, str]
    ) -> Optional[str]:
        stack = versions["stack"]
        java_version = versions["java_version"]
        
        project_name = project_path.name.lower().replace(" ", "-").replace("_", "-")
        timestamp = int(time.time())
        image_tag = f"verifier-{stack}-java{java_version}-{project_name}:{timestamp}"
        
        self._ensure_templates_exist()
        
        dockerfile_content = self._generate_dockerfile(stack, versions)
        if not dockerfile_content:
            return None
        
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                build_context = pathlib.Path(temp_dir)
                
                self._prepare_build_context(project_path, build_context, stack)
                
                dockerfile_path = build_context / "Dockerfile"
                dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
                
                success = self._execute_docker_build(build_context, image_tag)
                return image_tag if success else None
                
        except Exception:
            return None
    
    def _generate_dockerfile(self, stack: str, versions: Dict[str, str]) -> Optional[str]:
        java_version = versions["java_version"]
        build_tool_version = versions.get("build_tool_version", "")
        
        if stack == "maven":
            return f"""# Custom Maven build with Java {java_version}
FROM maven:{build_tool_version or "3.9"}-eclipse-temurin-{java_version} as builder

WORKDIR /workspace
COPY pom.xml ./
COPY src/ ./src/

RUN mvn clean compile -DskipTests=true

FROM eclipse-temurin:{java_version}-jdk
WORKDIR /app
COPY --from=builder /workspace/target/classes/ ./
CMD ["java", "-cp", ".", "Main"]
"""
        
        elif stack == "gradle":
            return f"""# Custom Gradle build with Java {java_version}
FROM gradle:{build_tool_version or "8"}-jdk{java_version} as builder

WORKDIR /workspace
COPY build.gradle* gradle.properties* gradlew* ./
COPY gradle/ ./gradle/
COPY src/ ./src/

RUN gradle clean build -x test

FROM eclipse-temurin:{java_version}-jre-alpine
WORKDIR /app
COPY --from=builder /workspace/build/classes/java/main/ ./
CMD ["java", "-cp", ".", "Main"]
"""
        
        elif stack == "javac":
            return f"""# Custom javac build with Java {java_version}
FROM eclipse-temurin:{java_version}-jdk as builder

WORKDIR /workspace
COPY *.java ./

RUN javac -d build *.java

FROM eclipse-temurin:{java_version}-jdk
WORKDIR /app
COPY --from=builder /workspace/build/ ./
CMD ["java", "Main"]
"""
        
        return None
    
    def _prepare_build_context(
        self, 
        project_path: pathlib.Path, 
        build_context: pathlib.Path, 
        stack: str
    ):
        if stack == "maven":
            files_to_copy = ["pom.xml", "src/"]
        elif stack == "gradle": 
            files_to_copy = [
                "build.gradle", "build.gradle.kts", "gradle.properties",
                "gradlew", "gradlew.bat", "gradle/", "src/"
            ]
        elif stack == "javac":
            files_to_copy = ["*.java"]
        else:
            return
        
        for file_pattern in files_to_copy:
            source_path = project_path / file_pattern
            
            if "*" in file_pattern:
                for file_path in project_path.glob(file_pattern):
                    if file_path.is_file():
                        dest_path = build_context / file_path.name
                        shutil.copy2(file_path, dest_path)
            else:
                if source_path.exists():
                    dest_path = build_context / source_path.name
                    if source_path.is_dir():
                        shutil.copytree(source_path, dest_path, dirs_exist_ok=True)
                    else:
                        shutil.copy2(source_path, dest_path)
    
    def _execute_docker_build(self, build_context: pathlib.Path, image_tag: str) -> bool:
        try:
            result = subprocess.run([
                "docker", "build", "--tag", image_tag, 
                "--quiet",
                str(build_context)
            ], capture_output=True, text=True, timeout=600)
            
            return result.returncode == 0
            
        except Exception:
            return False
    
    def _get_fallback_image(self, stack: str) -> str:
        fallback_images = {
            "maven": "maven:3.9-eclipse-temurin-17",
            "gradle": "gradle:8-jdk17", 
            "javac": "eclipse-temurin:17-jdk-alpine"
        }
        return fallback_images.get(stack, "eclipse-temurin:17-jdk-alpine")
    
    def _ensure_templates_exist(self):
        """Ensure template directory exists (for future extensibility)"""
        self.templates_dir.mkdir(exist_ok=True)


def get_smart_docker_image(
    project_path: pathlib.Path, 
    stack: str
) -> Tuple[str, bool, Dict[str, str]]:
    """Returns tuple of (image_name, is_custom_built, detected_versions)"""
    selector = SmartDockerSelector()
    return selector.get_best_image_for_project(project_path, stack)