"""
OpenRouter LLM Client for Regression Test Generation

Reuses the existing OpenRouter pattern from patch_applicator.py
"""

from typing import Dict, Any, Optional
from pathlib import Path
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

# Import configuration and prompts from same directory
from . import config
from . import prompts

# Load environment variables
load_dotenv()


class TestGenerationClient:
    """LLM client for generating regression tests using OpenRouter"""
    
    def __init__(self, model=None, verbose: bool = True):
        """Initialize OpenRouter client"""
        self.model = model or config.CURRENT_MODEL
        self.verbose = verbose
        
        # Initialize OpenRouter client (same pattern as patch_applicator.py)
        api_key = getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        if self.verbose:
            print(f"[TestGen] Initialized with model: {self.model.value}")
    
    def generate_tests(
        self,
        patched_code: str,
        cwe_id: str,
        vulnerability_description: str,
        patch_plan: list,
        security_notes: str,
        num_tests: int = 3
    ) -> Optional[str]:
        """
        Generate regression tests using failure-driven prompts
        
        Args:
            patched_code: The patched code to test
            cwe_id: CWE identifier (e.g., "CWE-78")
            vulnerability_description: Description of the vulnerability
            patch_plan: List of patch plan steps
            security_notes: Security verification notes
            num_tests: Number of tests to generate
            
        Returns:
            Generated test code as string, or None if generation fails
        """
        # Format patch plan
        plan_text = "\n".join(f"{i+1}. {step}" for i, step in enumerate(patch_plan))
        
        # Build user message from template
        user_message = prompts.USER_PROMPT_TEMPLATE.format(
            cwe_id=cwe_id,
            vulnerability_description=vulnerability_description,
            patch_plan=plan_text,
            patched_code=patched_code,
            security_notes=security_notes,
            num_tests=num_tests
        )
        
        messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        # Send request to OpenRouter with retry logic
        if self.verbose:
            print(f"[TestGen] Generating {num_tests} tests for {cwe_id}...")
        
        for attempt in range(config.TEST_GENERATION_SETTINGS["retry_attempts"]):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model.value,
                    messages=messages,
                    temperature=config.TEST_GENERATION_SETTINGS["temperature"],
                    max_tokens=config.TEST_GENERATION_SETTINGS["max_tokens"],
                    timeout=config.TEST_GENERATION_SETTINGS["timeout"]
                )
                
                test_code = completion.choices[0].message.content or ""
                
                if not test_code.strip():
                    raise ValueError("LLM returned empty response")
                
                # Clean up markdown formatting if present
                test_code = self._clean_markdown(test_code)
                
                if self.verbose:
                    print(f"[TestGen] Successfully generated tests ({len(test_code)} chars)")
                
                return test_code
                
            except Exception as e:
                if attempt < config.TEST_GENERATION_SETTINGS["retry_attempts"] - 1:
                    if self.verbose:
                        print(f"[TestGen] Attempt {attempt + 1} failed, retrying: {e}")
                    continue
                else:
                    if self.verbose:
                        print(f"[TestGen] Failed after {config.TEST_GENERATION_SETTINGS['retry_attempts']} attempts: {e}")
                    return None
    
    def repair_test(self, original_test_code: str, compilation_errors: str) -> Optional[str]:
        """
        Attempt to repair test code that failed to compile
        
        Args:
            original_test_code: The test code that failed
            compilation_errors: Compiler error messages
            
        Returns:
            Repaired test code, or None if repair fails
        """
        user_message = prompts.REPAIR_PROMPT_TEMPLATE.format(
            compilation_errors=compilation_errors,
            original_test_code=original_test_code
        )
        
        messages = [
            {"role": "system", "content": prompts.SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]
        
        if self.verbose:
            print(f"[TestGen] Attempting to repair test code...")
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model.value,
                messages=messages,
                temperature=0.1,  # Lower temperature for repairs
                max_tokens=config.TEST_GENERATION_SETTINGS["max_tokens"],
                timeout=config.TEST_GENERATION_SETTINGS["timeout"]
            )
            
            repaired_code = completion.choices[0].message.content or ""
            repaired_code = self._clean_markdown(repaired_code)
            
            if self.verbose:
                print(f"[TestGen] Repair successful")
            
            return repaired_code
            
        except Exception as e:
            if self.verbose:
                print(f"[TestGen] Repair failed: {e}")
            return None
    
    def _clean_markdown(self, code: str) -> str:
        """Remove markdown code fences if present"""
        if code.startswith("```") and code.endswith("```"):
            lines = code.split('\n')
            # Remove first line if it's a fence (```java or ```)
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove last line if it's a fence
            if lines and lines[-1] == "```":
                lines = lines[:-1]
            code = '\n'.join(lines)
        
        return code.strip()
