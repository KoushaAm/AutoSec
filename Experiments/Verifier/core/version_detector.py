#!/usr/bin/env python3
import pathlib
import re
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Tuple


class ProjectVersionDetector:
    """Detects Java and build tool versions from project configuration files"""
    
    def detect_versions(self, project_path: pathlib.Path, stack: str) -> Dict[str, str]:
        """Returns dictionary with detected versions (java_version, build_tool_version, etc.)"""
        versions = {
            "java_version": None,
            "build_tool_version": None,
            "stack": stack
        }
        
        if stack == "maven":
            versions.update(self._detect_maven_versions(project_path))
        elif stack == "gradle":
            versions.update(self._detect_gradle_versions(project_path))
        elif stack == "javac":
            versions.update(self._detect_javac_versions(project_path))
        
        if not versions["java_version"]:
            versions["java_version"] = "17"
            
        return versions
    
    def _detect_maven_versions(self, project_path: pathlib.Path) -> Dict[str, str]:
        versions = {}
        pom_file = project_path / "pom.xml"
        
        if not pom_file.exists():
            return versions
        
        try:
            tree = ET.parse(pom_file)
            root = tree.getroot()
            
            # Handle namespace
            ns = ""
            if root.tag.startswith("{"):
                ns = root.tag.split("}")[0] + "}"
            
            java_version = self._extract_java_version_from_maven(root, ns)
            if java_version:
                versions["java_version"] = java_version
            
            maven_version = self._detect_maven_wrapper_version(project_path)
            if maven_version:
                versions["build_tool_version"] = maven_version
            else:
                versions["build_tool_version"] = "3.9"
                
        except Exception:
            pass
        
        return versions
    
    def _extract_java_version_from_maven(self, root, ns: str) -> Optional[str]:
        # Try java.version property
        properties = root.find(f"{ns}properties")
        if properties is not None:
            java_version = properties.find(f"{ns}java.version")
            if java_version is not None and java_version.text:
                return self._normalize_java_version(java_version.text)
            
            # Try maven.compiler.source/target
            compiler_source = properties.find(f"{ns}maven.compiler.source")
            if compiler_source is not None and compiler_source.text:
                return self._normalize_java_version(compiler_source.text)
            
            compiler_target = properties.find(f"{ns}maven.compiler.target")
            if compiler_target is not None and compiler_target.text:
                return self._normalize_java_version(compiler_target.text)
        
        # Try maven-compiler-plugin configuration
        build = root.find(f"{ns}build")
        if build is not None:
            plugins = build.find(f"{ns}plugins")
            if plugins is not None:
                for plugin in plugins.findall(f"{ns}plugin"):
                    artifact_id = plugin.find(f"{ns}artifactId")
                    if artifact_id is not None and artifact_id.text == "maven-compiler-plugin":
                        config = plugin.find(f"{ns}configuration")
                        if config is not None:
                            source = config.find(f"{ns}source")
                            if source is not None and source.text:
                                return self._normalize_java_version(source.text)
        
        return None
    
    def _detect_maven_wrapper_version(self, project_path: pathlib.Path) -> Optional[str]:
        wrapper_props = project_path / "maven-wrapper.properties"
        if not wrapper_props.exists():
            wrapper_props = project_path / ".mvn" / "wrapper" / "maven-wrapper.properties"
        
        if wrapper_props.exists():
            try:
                content = wrapper_props.read_text(encoding="utf-8")
                match = re.search(r"apache-maven/([0-9]+\.[0-9]+\.[0-9]+)/", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        return None
    
    def _detect_gradle_versions(self, project_path: pathlib.Path) -> Dict[str, str]:
        versions = {}
        
        build_file = project_path / "build.gradle"
        if not build_file.exists():
            build_file = project_path / "build.gradle.kts"
        
        if build_file.exists():
            try:
                content = build_file.read_text(encoding="utf-8")
                
                java_version = self._extract_java_version_from_gradle(content)
                if java_version:
                    versions["java_version"] = java_version
                    
            except Exception:
                pass
        
        gradle_version = self._detect_gradle_wrapper_version(project_path)
        if gradle_version:
            versions["build_tool_version"] = gradle_version
        else:
            versions["build_tool_version"] = "8"
        
        return versions
    
    def _extract_java_version_from_gradle(self, content: str) -> Optional[str]:
        patterns = [
            r"sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?",
            r"targetCompatibility\s*=\s*['\"]?(\d+)['\"]?",
            r"java\s*{\s*toolchain\s*{\s*languageVersion\s*=\s*JavaLanguageVersion\.of\((\d+)\)",
            r"compileJava\s*{\s*sourceCompatibility\s*=\s*['\"]?(\d+)['\"]?",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content)
            if match:
                return self._normalize_java_version(match.group(1))
        
        return None
    
    def _detect_gradle_wrapper_version(self, project_path: pathlib.Path) -> Optional[str]:
        wrapper_props = project_path / "gradle" / "wrapper" / "gradle-wrapper.properties"
        
        if wrapper_props.exists():
            try:
                content = wrapper_props.read_text(encoding="utf-8")
                match = re.search(r"gradle-([0-9]+\.[0-9]+(?:\.[0-9]+)?)-", content)
                if match:
                    return match.group(1)
            except Exception:
                pass
        
        return None
    
    def _detect_javac_versions(self, project_path: pathlib.Path) -> Dict[str, str]:
        versions = {}
        
        java_files = list(project_path.glob("*.java"))
        
        if java_files:
            java_version = self._infer_java_version_from_source(java_files)
            if java_version:
                versions["java_version"] = java_version
        
        return versions
    
    def _infer_java_version_from_source(self, java_files: list) -> Optional[str]:
        """Infer minimum Java version from source code features"""
        try:
            for java_file in java_files[:5]:
                content = java_file.read_text(encoding="utf-8")
                
                if "var " in content:
                    return "11"
                if "record " in content:
                    return "17"
                if "sealed " in content:
                    return "17"
                if "switch " in content and "->" in content:
                    return "17"
                    
        except Exception:
            pass
        
        return "11"
    
    def _normalize_java_version(self, version: str) -> str:
        version = version.strip()
        
        if version.startswith("1."):
            return version.split(".")[1]
        else:
            return version.split(".")[0]


def detect_project_versions(project_path: pathlib.Path, stack: str) -> Dict[str, str]:
    """Returns dictionary with detected versions"""
    detector = ProjectVersionDetector()
    return detector.detect_versions(project_path, stack)