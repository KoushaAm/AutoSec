#!/usr/bin/env python3
"""
Test Discovery Module

Handles discovery and analysis of existing unit and integration tests
in Java projects (Maven, Gradle, plain javac)
"""
import pathlib
from typing import List, Dict, Any


class TestDiscovery:
    # Test patterns for different build systems
    TEST_PATTERNS = {
        "maven": {
            "directories": ["src/test/java", "src/it/java"],
            "file_patterns": ["**/*Test.java", "**/*Tests.java", "**/Test*.java", "**/*IT.java"],
            "frameworks": ["junit", "testng", "spock"]
        },
        "gradle": {
            "directories": ["src/test/java", "src/integrationTest/java", "src/functionalTest/java"],
            "file_patterns": ["**/*Test.java", "**/*Tests.java", "**/Test*.java", "**/*Spec.groovy"],
            "frameworks": ["junit", "testng", "spock"]
        },
        "javac": {
            "directories": ["."],
            "file_patterns": ["*Test.java", "*Tests.java", "Test*.java"],
            "frameworks": ["junit"]
        }
    }
    
    def __init__(self):
        self._discovery_cache = {}
    
    def discover_tests(self, project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
        """
        Args:
            project_path: Path to the project root
            stack_name: Build stack type (maven, gradle, javac)
            
        Returns:
            Dictionary with test discovery results
        """
        cache_key = f"{project_path.absolute()}:{stack_name}"
        if cache_key in self._discovery_cache:
            return self._discovery_cache[cache_key]
        
        test_discovery = {
            "has_tests": False,
            "test_framework": None,
            "test_directories": [],
            "test_files": [],
            "test_count": 0,
            "test_commands": [],
            "framework_confidence": 0.0
        }
        
        patterns = self.TEST_PATTERNS.get(stack_name, self.TEST_PATTERNS["javac"])
        
        # discover test directories
        for test_dir in patterns["directories"]:
            test_path = project_path / test_dir
            if test_path.exists() and test_path.is_dir():
                test_discovery["test_directories"].append(str(test_path.relative_to(project_path)))
        
        # discover test files
        for pattern in patterns["file_patterns"]:
            test_files = list(project_path.glob(pattern))
            for test_file in test_files:
                # skip the build output directories
                if any(skip in str(test_file) for skip in ["target/", "build/", "out/"]):
                    continue
                test_discovery["test_files"].append(str(test_file.relative_to(project_path)))
        
        test_discovery["test_count"] = len(test_discovery["test_files"])
        test_discovery["has_tests"] = test_discovery["test_count"] > 0
        
        if test_discovery["has_tests"]:
            framework, confidence = self._detect_test_framework(project_path, test_discovery["test_files"])
            test_discovery["test_framework"] = framework
            test_discovery["framework_confidence"] = confidence
            test_discovery["test_commands"] = self._get_test_commands_for_stack(stack_name)
        
        # cache result
        self._discovery_cache[cache_key] = test_discovery
        
        return test_discovery
    
    def _detect_test_framework(self, project_path: pathlib.Path, test_files: List[str]) -> tuple[str, float]:
        """
        Returns:
            Tuple of (framework_name, confidence_score)
        """
        framework_indicators = {
            "junit5": ["org.junit.jupiter", "@Test", "@ParameterizedTest", "@ExtendWith"],
            "junit4": ["org.junit.Test", "org.junit.Before", "org.junit.After", "@Test"],
            "testng": ["org.testng", "@Test", "@BeforeMethod", "@AfterMethod"],
            "spock": ["spock.lang", "extends Specification"]
        }
        
        framework_scores = {framework: 0 for framework in framework_indicators.keys()}
        total_indicators = 0
        
        # sample few test files for analysis
        sample_files = test_files[:5]
        
        for test_file in sample_files:
            try:
                file_path = project_path / test_file
                if not file_path.exists():
                    continue
                    
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                
                for framework, indicators in framework_indicators.items():
                    for indicator in indicators:
                        if indicator in content:
                            framework_scores[framework] += 1
                            total_indicators += 1
                            
            except Exception:
                continue
        
        if total_indicators == 0:
            return "junit5", 0.0  # default fallback
        
        # find the framework with the highest score
        best_framework = max(framework_scores, key=framework_scores.get)
        confidence = framework_scores[best_framework] / total_indicators
        
        return best_framework, confidence
    
    def _get_test_commands_for_stack(self, stack_name: str) -> List[str]:
        commands = {
            "maven": [
                "./mvnw test -B",
                "mvn test -B"
            ],
            "gradle": [
                "./gradlew test --no-daemon",
                "gradle test --no-daemon"
            ],
            "javac": [
                "echo 'Tests not supported for javac projects without build system'"
            ]
        }
        
        return commands.get(stack_name, commands["javac"])
    
    def analyze_test_quality(self, project_path: pathlib.Path, test_files: List[str]) -> Dict[str, Any]:
        """
        Args:
            project_path: Path to the project root
            test_files: List of test file paths
            
        Returns:
            Dictionary with test quality analysis
        """
        quality_analysis = {
            "total_test_methods": 0,
            "has_assertions": 0,
            "has_mocking": 0,
            "has_setup_teardown": 0, # cleanup
            "test_naming_quality": "unknown",
            "estimated_coverage": "unknown"
        }
        
        assertion_patterns = ["assert", "assertEquals", "assertTrue", "assertFalse", "assertNotNull"]
        mocking_patterns = ["mock", "Mock", "@Mock", "Mockito", "when(", "verify("]
        setup_patterns = ["@Before", "@BeforeEach", "@BeforeMethod", "setUp"]
        
        method_count = 0
        assertion_count = 0
        mocking_count = 0
        setup_count = 0
        
        # analyze a sample of test files
        sample_files = test_files[:10]  # limit analysis to avoid performance issues
        
        for test_file in sample_files:
            try:
                file_path = project_path / test_file
                if not file_path.exists():
                    continue
                
                content = file_path.read_text(encoding='utf-8', errors='ignore')
                
                # count test methods (rough estimate)
                method_count += content.count("@Test")
                
                # count assertions
                for pattern in assertion_patterns:
                    if pattern in content:
                        assertion_count += 1
                        break
                
                # count mocking usage
                for pattern in mocking_patterns:
                    if pattern in content:
                        mocking_count += 1
                        break
                
                # count setup/teardown
                for pattern in setup_patterns:
                    if pattern in content:
                        setup_count += 1
                        break
                        
            except Exception:
                continue
        
        quality_analysis["total_test_methods"] = method_count
        quality_analysis["has_assertions"] = assertion_count
        quality_analysis["has_mocking"] = mocking_count
        quality_analysis["has_setup_teardown"] = setup_count
        
        # determine test naming quality (basic heuristic)
        if len(sample_files) > 0:
            well_named = sum(1 for f in sample_files if any(keyword in f.lower() for keyword in ["test", "spec"]))
            quality_analysis["test_naming_quality"] = "good" if well_named / len(sample_files) > 0.8 else "fair"
        
        # estimate coverage based on test presence
        if method_count > 0:
            if method_count >= len(sample_files) * 3:  # rough heuristic
                quality_analysis["estimated_coverage"] = "good"
            elif method_count >= len(sample_files):
                quality_analysis["estimated_coverage"] = "fair"
            else:
                quality_analysis["estimated_coverage"] = "poor"
        
        return quality_analysis
    
    def clear_cache(self):
        """Clear the discovery cache."""
        self._discovery_cache.clear()


# convenience for backward compatibility
def discover_tests(project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
    """
    Discover existing unit and integration tests in the project.
    
    This function maintains backward compatibility with the original interface.
    """
    discovery = TestDiscovery()
    return discovery.discover_tests(project_path, stack_name)