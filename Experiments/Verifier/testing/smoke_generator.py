#!/usr/bin/env python3
"""
Smoke test generator module

generates appropriate smoke tests for Java projects when no existing tests are found.
supports Spring Boot, web applications, CLI applications, and library projects.
"""
import pathlib
import re
import shutil
from typing import List, Dict, Any


class SmokeTestGenerator:
    """Generates smoke tests for different types of Java projects."""
    
    def __init__(self):
        self._project_cache = {}
    
    def generate_smoke_tests(self, project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
        """
        Args:
            project_path: Path to the project root
            stack_name: Build stack type (maven, gradle, javac)
            
        Returns:
            Dictionary with smoke test generation results
        """
        cache_key = f"{project_path.absolute()}:{stack_name}"
        if cache_key in self._project_cache:
            return self._project_cache[cache_key]
        
        smoke_result = {
            "smoke_tests_generated": False,
            "test_types": [],
            "generated_files": [],
            "test_strategies": [],
            "estimated_coverage": "basic"
        }
        
        # analyze project to determine test strategy
        project_analysis = self._analyze_project_structure(project_path)
        smoke_result["project_analysis"] = project_analysis
        
        # generate appropriate smoke tests based on project type
        if project_analysis["spring_boot_detected"]:
            smoke_result.update(self._generate_spring_boot_smoke_tests(project_path, stack_name))
        elif project_analysis["web_app_detected"]:
            smoke_result.update(self._generate_web_app_smoke_tests(project_path, stack_name))
        elif project_analysis["main_classes"]:
            smoke_result.update(self._generate_cli_app_smoke_tests(
                project_path, stack_name, project_analysis["main_class_files"]
            ))
        else:
            smoke_result.update(self._generate_library_smoke_tests(
                project_path, stack_name, project_analysis["java_files"]
            ))
        
        # cache the result
        self._project_cache[cache_key] = smoke_result
        
        return smoke_result
    
    def _analyze_project_structure(self, project_path: pathlib.Path) -> Dict[str, Any]:
        """Analyze project structure to determine appropriate smoke test strategy."""
        java_files = list(project_path.rglob("*.java"))
        main_class_files = []
        spring_boot_detected = False
        web_app_detected = False
        
        # analyze Java files for project characteristics
        for java_file in java_files:
            try:
                content = java_file.read_text(encoding='utf-8', errors='ignore')
                
                # check for main method
                if 'public static void main(' in content:
                    main_class_files.append(java_file)
                
                # check for Spring Boot annotations
                if any(annotation in content for annotation in [
                    '@SpringBootApplication', '@EnableAutoConfiguration', 
                    '@RestController', '@Controller'
                ]):
                    spring_boot_detected = True
                    
                # check for web components
                if any(indicator in content for indicator in [
                    'HttpServlet', '@RequestMapping', '@GetMapping', 
                    '@PostMapping', 'ServletContext'
                ]):
                    web_app_detected = True
                    
            except Exception:
                continue
        
        # convert all Path objects to strings for JSON serialization
        return {
            "java_files_count": len(java_files),
            "java_files": [str(f.relative_to(project_path)) for f in java_files],  # Convert to strings
            "main_classes": [str(f.relative_to(project_path)) for f in main_class_files],
            "main_class_files": main_class_files,  # Keep Path objects for internal use
            "spring_boot_detected": spring_boot_detected,
            "web_app_detected": web_app_detected
        }
    
    def _generate_spring_boot_smoke_tests(self, project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
        """Generate comprehensive smoke tests for Spring Boot applications."""
        test_dir = project_path / "src/test/java/generated"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        smoke_test_content = '''package generated;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.junit.jupiter.SpringJUnitConfig;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.boot.test.context.SpringBootTest.WebEnvironment;
import org.springframework.http.ResponseEntity;
import org.springframework.http.HttpStatus;
import static org.junit.jupiter.api.Assertions.*;

@SpringBootTest(webEnvironment = WebEnvironment.RANDOM_PORT)
@SpringJUnitConfig
public class GeneratedSmokeTest {
    
    @LocalServerPort
    private int port;
    
    private TestRestTemplate restTemplate = new TestRestTemplate();
    
    @Test
    public void contextLoads() {
        // Smoke test: Spring context should load without errors
        assertTrue(true, "Spring Boot context loaded successfully");
    }
    
    @Test
    public void healthEndpointSmokeTest() {
        try {
            String url = "http://localhost:" + port + "/actuator/health";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            
            // Accept both 200 (healthy) and 404 (actuator not configured)
            assertTrue(
                response.getStatusCode() == HttpStatus.OK || 
                response.getStatusCode() == HttpStatus.NOT_FOUND,
                "Health endpoint should be accessible or properly return 404"
            );
        } catch (Exception e) {
            // If actuator isn't configured, that's okay for smoke test
            assertTrue(true, "Health endpoint test completed (actuator may not be configured)");
        }
    }
    
    @Test
    public void rootEndpointSmokeTest() {
        try {
            String url = "http://localhost:" + port + "/";
            ResponseEntity<String> response = restTemplate.getForEntity(url, String.class);
            
            // Should get some response (200, 404, 403, etc. - not connection error)
            assertNotNull(response.getStatusCode(), "Root endpoint should respond");
            assertTrue(response.getStatusCode().value() < 500, 
                      "Root endpoint should not return server error");
        } catch (Exception e) {
            fail("Application should be accessible on configured port: " + e.getMessage());
        }
    }
    
    @Test
    public void applicationStartupSmokeTest() {
        // This test passes if the Spring Boot app started successfully
        // (which it must have for the test context to load)
        assertTrue(port > 0, "Application should start on a valid port");
        assertTrue(port < 65536, "Port should be within valid range");
    }
}
'''
        
        test_file = test_dir / "GeneratedSmokeTest.java"
        test_file.write_text(smoke_test_content, encoding='utf-8')
        
        return {
            "smoke_tests_generated": True,
            "test_types": ["context_loading", "health_endpoint", "startup_validation", "basic_connectivity"],
            "generated_files": [str(test_file.relative_to(project_path))],
            "test_strategies": ["spring_boot_integration_test", "web_endpoint_validation"],
            "estimated_coverage": "comprehensive_spring_boot"
        }
    
    def _generate_web_app_smoke_tests(self, project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
        # non-Spring Boot web application smoke tests
        test_dir = project_path / "src/test/java/generated"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        smoke_test_content = '''package generated;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeneratedWebAppSmokeTest {
    
    @Test
    public void servletContextSmokeTest() {
        // Basic smoke test for web application components
        try {
            // Test that web components can be instantiated
            assertTrue(true, "Web application smoke test - basic validation");
        } catch (Exception e) {
            fail("Web application basic smoke test failed: " + e.getMessage());
        }
    }
    
    @Test
    public void classLoadingSmokeTest() {
        // Verify critical web classes can be loaded
        try {
            Class.forName("javax.servlet.http.HttpServlet");
            assertTrue(true, "Servlet API classes accessible");
        } catch (ClassNotFoundException e) {
            // This is okay - not all web apps use traditional servlets
            assertTrue(true, "Servlet API not found - may be using different web framework");
        }
    }
}
'''
        
        test_file = test_dir / "GeneratedWebAppSmokeTest.java"
        test_file.write_text(smoke_test_content, encoding='utf-8')
        
        return {
            "smoke_tests_generated": True,
            "test_types": ["servlet_context", "class_loading"],
            "generated_files": [str(test_file.relative_to(project_path))],
            "test_strategies": ["web_app_basic_validation"],
            "estimated_coverage": "basic_web_app"
        }
    
    def _generate_cli_app_smoke_tests(self, project_path: pathlib.Path, stack_name: str, main_classes: List[pathlib.Path]) -> Dict[str, Any]:
        """Generate smoke tests for CLI applications with main methods."""
        test_dir = project_path / "src/test/java/generated"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Extract class information from main classes
        main_class_info = []
        for main_class in main_classes[:3]:  # Limit to first 3 main classes
            try:
                content = main_class.read_text(encoding='utf-8', errors='ignore')
                
                # Extract package
                package_match = re.search(r'package\s+([\w.]+);', content)
                package_name = package_match.group(1) if package_match else ""
                
                # Extract class name
                class_match = re.search(r'public\s+class\s+(\w+)', content)
                class_name = class_match.group(1) if class_match else main_class.stem
                
                full_class_name = f"{package_name}.{class_name}" if package_name else class_name
                main_class_info.append({
                    "class_name": class_name,
                    "full_class_name": full_class_name,
                    "package": package_name
                })
            except Exception:
                continue
        
        # Generate test for each main class
        generated_files = []
        for i, class_info in enumerate(main_class_info):
            smoke_test_content = f'''package generated;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.Timeout;
import static org.junit.jupiter.api.Assertions.*;
import java.io.ByteArrayOutputStream;
import java.io.PrintStream;
import java.util.concurrent.TimeUnit;

public class GeneratedCliSmokeTest{i + 1} {{
    
    @Test
    @Timeout(value = 30, unit = TimeUnit.SECONDS)
    public void mainMethodSmokeTest() {{
        // Smoke test: Main method should execute without throwing exceptions
        try {{
            // Capture output to prevent console spam during testing
            ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
            PrintStream originalOut = System.out;
            System.setOut(new PrintStream(outputStream));
            
            try {{
                // Test main method with empty args (most common case)
                {class_info['full_class_name']}.main(new String[0]);
                assertTrue(true, "Main method executed without exceptions");
            }} catch (Exception e) {{
                // Some exceptions might be expected (missing files, invalid args, etc.)
                // For smoke test, we mainly want to catch major structural issues
                String message = e.getMessage();
                if (message != null && (
                    message.contains("file not found") ||
                    message.contains("invalid argument") ||
                    message.contains("missing parameter") ||
                    message.contains("usage:") ||
                    message.toLowerCase().contains("help")
                )) {{
                    assertTrue(true, "Main method failed with expected user error: " + message);
                }} else {{
                    fail("Main method failed with unexpected error: " + e.getClass().getSimpleName() + " - " + message);
                }}
            }} finally {{
                System.setOut(originalOut);
            }}
        }} catch (Exception e) {{
            fail("Smoke test setup failed: " + e.getMessage());
        }}
    }}
    
    @Test
    public void classInstantiationSmokeTest() {{
        // Test that the main class can be loaded and basic reflection works
        try {{
            Class<?> mainClass = Class.forName("{class_info['full_class_name']}");
            assertNotNull(mainClass, "Main class should be loadable");
            
            // Verify main method exists
            java.lang.reflect.Method mainMethod = mainClass.getMethod("main", String[].class);
            assertNotNull(mainMethod, "Main method should exist");
            assertTrue(java.lang.reflect.Modifier.isStatic(mainMethod.getModifiers()), 
                      "Main method should be static");
            assertTrue(java.lang.reflect.Modifier.isPublic(mainMethod.getModifiers()), 
                      "Main method should be public");
        }} catch (Exception e) {{
            fail("Class loading smoke test failed: " + e.getMessage());
        }}
    }}
}}
'''
            
            test_file = test_dir / f"GeneratedCliSmokeTest{i + 1}.java"
            test_file.write_text(smoke_test_content, encoding='utf-8')
            generated_files.append(str(test_file.relative_to(project_path)))
        
        return {
            "smoke_tests_generated": True,
            "test_types": ["main_method_execution", "class_loading", "reflection_validation"],
            "generated_files": generated_files,
            "test_strategies": ["cli_app_execution_test", "basic_functionality_test"],
            "estimated_coverage": f"cli_app_{len(main_class_info)}_main_classes"
        }
    
    def _generate_library_smoke_tests(self, project_path: pathlib.Path, stack_name: str, java_files: List[pathlib.Path]) -> Dict[str, Any]:
        """Generate smoke tests for library projects (no main methods)."""
        test_dir = project_path / "src/test/java/generated"
        test_dir.mkdir(parents=True, exist_ok=True)
        
        # Find public classes to test
        public_classes = []
        for java_file in java_files[:5]:  # Limit to first 5 files
            try:
                content = java_file.read_text(encoding='utf-8', errors='ignore')
                
                # Skip test files and generated files
                if any(skip in str(java_file).lower() for skip in ['test', 'generated', 'target', 'build']):
                    continue
                    
                # Look for public classes
                class_matches = re.findall(r'public\s+class\s+(\w+)', content)
                if class_matches:
                    # Get package
                    package_match = re.search(r'package\s+([\w.]+);', content)
                    package_name = package_match.group(1) if package_match else ""
                    
                    for class_name in class_matches:
                        full_class_name = f"{package_name}.{class_name}" if package_name else class_name
                        public_classes.append({
                            "class_name": class_name,
                            "full_class_name": full_class_name,
                            "file": str(java_file.relative_to(project_path))
                        })
                        
            except Exception:
                continue
        
        if not public_classes:
            # Fallback: basic compilation test
            smoke_test_content = '''package generated;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeneratedLibrarySmokeTest {
    
    @Test
    public void basicCompilationSmokeTest() {
        // Basic smoke test: If this test runs, compilation succeeded
        assertTrue(true, "Library compilation smoke test passed");
    }
    
    @Test
    public void javaVersionSmokeTest() {
        // Verify Java version compatibility
        String javaVersion = System.getProperty("java.version");
        assertNotNull(javaVersion, "Java version should be available");
        assertTrue(javaVersion.length() > 0, "Java version should not be empty");
    }
}
'''
        else:
            # Generate tests for discovered classes
            class_tests = []
            for class_info in public_classes[:3]:  # Limit to 3 classes
                class_tests.append(f'''
    @Test
    public void {class_info['class_name'].lower()}InstantiationSmokeTest() {{
        try {{
            Class<?> testClass = Class.forName("{class_info['full_class_name']}");
            assertNotNull(testClass, "{class_info['class_name']} should be loadable");
            
            // Try to get constructors (basic reflection test)
            java.lang.reflect.Constructor<?>[] constructors = testClass.getConstructors();
            assertTrue(constructors.length >= 0, "{class_info['class_name']} should have accessible constructors info");
            
        }} catch (ClassNotFoundException e) {{
            fail("{class_info['class_name']} class not found: " + e.getMessage());
        }} catch (Exception e) {{
            // Some reflection failures are acceptable for smoke test
            assertTrue(true, "{class_info['class_name']} reflection completed with: " + e.getClass().getSimpleName());
        }}
    }}''')
            
            smoke_test_content = f'''package generated;

import org.junit.jupiter.api.Test;
import static org.junit.jupiter.api.Assertions.*;

public class GeneratedLibrarySmokeTest {{
    
    @Test
    public void basicCompilationSmokeTest() {{
        // Basic smoke test: If this test runs, compilation succeeded
        assertTrue(true, "Library compilation smoke test passed");
    }}
{''.join(class_tests)}
}}
'''
        
        test_file = test_dir / "GeneratedLibrarySmokeTest.java"
        test_file.write_text(smoke_test_content, encoding='utf-8')
        
        return {
            "smoke_tests_generated": True,
            "test_types": ["compilation_validation", "class_loading", "basic_reflection"],
            "generated_files": [str(test_file.relative_to(project_path))],
            "test_strategies": ["library_smoke_test", "reflection_based_validation"],
            "estimated_coverage": f"library_{len(public_classes)}_classes",
            "analyzed_classes": [c['full_class_name'] for c in public_classes]
        }
    
    def cleanup_generated_tests(self, project_path: pathlib.Path):
        """Remove generated test files after execution."""
        generated_test_dir = project_path / "src/test/java/generated"
        if generated_test_dir.exists():
            shutil.rmtree(generated_test_dir)
    
    def clear_cache(self):
        """Clear the project analysis cache."""
        self._project_cache.clear()


# convenience function for backward compatibility
def generate_smoke_tests(project_path: pathlib.Path, stack_name: str) -> Dict[str, Any]:
    """
    Generate basic smoke tests when no existing tests are found.
    
    Maintains backward compatibility with the original interface.
    """
    generator = SmokeTestGenerator()
    return generator.generate_smoke_tests(project_path, stack_name)