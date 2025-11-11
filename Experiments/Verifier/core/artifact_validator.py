#!/usr/bin/env python3
import pathlib
from typing import Dict, List, Any


class BuildArtifactValidator:
    """Validates build artifacts to ensure successful compilation"""
    
    ARTIFACT_PATTERNS = {
        "maven": [
            "target/**/*.class",
            "target/**/*.jar", 
            "target/**/*.war",
            "target/**/*.ear"
        ],
        "gradle": [
            "build/**/*.class",
            "build/**/*.jar",
            "build/**/*.war", 
            "build/**/*.ear",
            "build/classes/**/*.class"
        ],
        "javac": [
            "out/**/*.class",
            "*.class"
        ]
    }
    
    def __init__(self):
        self._validation_cache = {}
    
    def validate_artifacts(self, project_path: pathlib.Path, stack: str) -> Dict[str, Any]:
        """Returns dictionary with validation results"""
        cache_key = f"{project_path.absolute()}:{stack}"
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]
        
        validation_result = {
            "artifacts_found": [],
            "artifact_count": 0,
            "has_artifacts": False,
            "artifact_types": {
                "class_files": 0,
                "jar_files": 0,
                "war_files": 0,
                "ear_files": 0
            },
            "build_directories": [],
            "validation_status": "unknown"
        }
        
        patterns = self.ARTIFACT_PATTERNS.get(stack, self.ARTIFACT_PATTERNS["javac"])
        
        # Find all artifacts matching the patterns
        for pattern in patterns:
            artifacts = list(project_path.glob(pattern))
            for artifact in artifacts:
                if artifact.is_file():
                    relative_path = str(artifact.relative_to(project_path))
                    validation_result["artifacts_found"].append(relative_path)
                    
                    # Categorize artifact types
                    self._categorize_artifact(artifact, validation_result["artifact_types"])
        
        validation_result["build_directories"] = self._find_build_directories(project_path, stack)
        validation_result["artifact_count"] = len(validation_result["artifacts_found"])
        validation_result["has_artifacts"] = validation_result["artifact_count"] > 0
        validation_result["validation_status"] = self._determine_validation_status(validation_result, stack)
        
        self._validation_cache[cache_key] = validation_result
        return validation_result
    
    def _categorize_artifact(self, artifact_path: pathlib.Path, artifact_types: Dict[str, int]):
        suffix = artifact_path.suffix.lower()
        
        if suffix == ".class":
            artifact_types["class_files"] += 1
        elif suffix == ".jar":
            artifact_types["jar_files"] += 1
        elif suffix == ".war":
            artifact_types["war_files"] += 1
        elif suffix == ".ear":
            artifact_types["ear_files"] += 1
    
    def _find_build_directories(self, project_path: pathlib.Path, stack: str) -> List[str]:
        build_dirs = []
        
        potential_dirs = {
            "maven": ["target", "target/classes", "target/test-classes"],
            "gradle": ["build", "build/classes", "build/libs", "build/test-results"],
            "javac": ["out", "."]
        }
        
        dirs_to_check = potential_dirs.get(stack, potential_dirs["javac"])
        
        for dir_name in dirs_to_check:
            dir_path = project_path / dir_name
            if dir_path.exists() and dir_path.is_dir():
                build_dirs.append(str(dir_path.relative_to(project_path)))
        
        return build_dirs
    
    def _determine_validation_status(self, validation_result: Dict[str, Any], stack: str) -> str:
        if not validation_result["has_artifacts"]:
            return "no_artifacts"
        
        artifact_types = validation_result["artifact_types"]
        
        # For Maven/Gradle projects, expect at least class files
        if stack in ["maven", "gradle"]:
            if artifact_types["class_files"] > 0:
                return "success"
            elif artifact_types["jar_files"] > 0 or artifact_types["war_files"] > 0:
                return "success"
            else:
                return "insufficient_artifacts"
        elif stack == "javac":
            if artifact_types["class_files"] > 0:
                return "success"
            else:
                return "no_class_files"
        
        return "unknown"
    
    def get_validation_summary(self, validation_result: Dict[str, Any]) -> str:
        """Generate human-readable summary of validation results"""
        if not validation_result["has_artifacts"]:
            return "No build artifacts found - compilation may have failed"
        
        artifact_types = validation_result["artifact_types"]
        parts = []
        
        if artifact_types["class_files"] > 0:
            parts.append(f"{artifact_types['class_files']} class files")
        if artifact_types["jar_files"] > 0:
            parts.append(f"{artifact_types['jar_files']} JAR files")
        if artifact_types["war_files"] > 0:
            parts.append(f"{artifact_types['war_files']} WAR files")
        if artifact_types["ear_files"] > 0:
            parts.append(f"{artifact_types['ear_files']} EAR files")
        
        if parts:
            return f"Found {', '.join(parts)}"
        else:
            return f"Found {validation_result['artifact_count']} artifacts"
    
    def clear_cache(self):
        self._validation_cache.clear()


class BuildOutputAnalyzer:
    """Analyzes build outputs for common patterns and issues"""
    
    @staticmethod
    def analyze_build_log(artifacts_dir: pathlib.Path) -> Dict[str, Any]:
        """Returns dictionary with analysis results"""
        analysis = {
            "log_found": False,
            "compilation_errors": [],
            "warnings": [],
            "dependency_issues": [],
            "test_failures": [],
            "analysis_summary": "No build log found"
        }
        
        log_file = artifacts_dir / "build_log.txt"
        if not log_file.exists():
            return analysis
        
        analysis["log_found"] = True
        
        try:
            log_content = log_file.read_text(encoding='utf-8', errors='ignore')
            
            analysis["compilation_errors"] = BuildOutputAnalyzer._find_compilation_errors(log_content)
            analysis["warnings"] = BuildOutputAnalyzer._find_warnings(log_content)
            analysis["dependency_issues"] = BuildOutputAnalyzer._find_dependency_issues(log_content)
            analysis["test_failures"] = BuildOutputAnalyzer._find_test_failures(log_content)
            analysis["analysis_summary"] = BuildOutputAnalyzer._generate_summary(analysis)
            
        except Exception as e:
            analysis["analysis_summary"] = f"Error analyzing build log: {e}"
        
        return analysis
    
    @staticmethod
    def _find_compilation_errors(log_content: str) -> List[str]:
        errors = []
        lines = log_content.split('\n')
        
        error_patterns = [
            "error:",
            "compilation failed",
            "cannot find symbol",
            "package does not exist",
            "unreachable statement"
        ]
        
        for line in lines:
            line_lower = line.lower()
            for pattern in error_patterns:
                if pattern in line_lower and line.strip():
                    errors.append(line.strip())
                    break
        
        return errors[:10]
    
    @staticmethod
    def _find_warnings(log_content: str) -> List[str]:
        warnings = []
        lines = log_content.split('\n')
        
        warning_patterns = [
            "warning:",
            "deprecated",
            "unchecked"
        ]
        
        for line in lines:
            line_lower = line.lower()
            for pattern in warning_patterns:
                if pattern in line_lower and line.strip():
                    warnings.append(line.strip())
                    break
        
        return warnings[:5]
    
    @staticmethod
    def _find_dependency_issues(log_content: str) -> List[str]:
        issues = []
        lines = log_content.split('\n')
        
        dependency_patterns = [
            "could not resolve dependencies",
            "failed to collect dependencies",
            "artifact not found",
            "missing artifact",
            "connection refused"
        ]
        
        for line in lines:
            line_lower = line.lower()
            for pattern in dependency_patterns:
                if pattern in line_lower and line.strip():
                    issues.append(line.strip())
                    break
        
        return issues[:5]
    
    @staticmethod
    def _find_test_failures(log_content: str) -> List[str]:
        failures = []
        lines = log_content.split('\n')
        
        test_patterns = [
            "test failed",
            "tests failed",
            "failure:",
            "error:",
            "assertion"
        ]
        
        in_test_section = False
        for line in lines:
            line_lower = line.lower()
            
            if "running tests" in line_lower or "test results" in line_lower:
                in_test_section = True
                continue
            
            if in_test_section:
                for pattern in test_patterns:
                    if pattern in line_lower and line.strip():
                        failures.append(line.strip())
                        break
        
        return failures[:5]
    
    @staticmethod
    def _generate_summary(analysis: Dict[str, Any]) -> str:
        parts = []
        
        if analysis["compilation_errors"]:
            parts.append(f"{len(analysis['compilation_errors'])} compilation errors")
        
        if analysis["warnings"]:
            parts.append(f"{len(analysis['warnings'])} warnings")
        
        if analysis["dependency_issues"]:
            parts.append(f"{len(analysis['dependency_issues'])} dependency issues")
        
        if analysis["test_failures"]:
            parts.append(f"{len(analysis['test_failures'])} test failures")
        
        if parts:
            return f"Build log analysis: {', '.join(parts)}"
        else:
            return "Build log analysis: No significant issues found"


def validate_build_artifacts(project_path: pathlib.Path, stack: str) -> Dict[str, Any]:
    """Convenience function for backward compatibility"""
    validator = BuildArtifactValidator()
    return validator.validate_artifacts(project_path, stack)