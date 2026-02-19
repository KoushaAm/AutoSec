#!/usr/bin/env python3

import sys
from pathlib import Path
from typing import Dict, Any, List
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

# Local imports - use Verifier's constants
sys.path.insert(0, str(Path(__file__).parent.parent))
from constants.models import Model
from constants.prompts import SYSTEM_MESSAGE, USER_MESSAGE_TEMPLATE
import config

# Load environment variables
load_dotenv()

class LLMPatchApplicator:
    """Applies patches using LLM to understand and modify code intelligently"""
    
    def __init__(self, model: Model = None):
        """Initialize with OpenRouter client and model selection"""
        self.model = model or config.CURRENT_MODEL
        
        # Initialize OpenRouter client
        api_key = getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        
        # Load patch settings from config
        self.patch_settings = config.PATCH_SETTINGS.copy()
        
        print(f"Initialized LLM Patch Applicator")
        print(f"   Model: {self.model.value}")
        print(f"   Version: {config.TOOL_VERSION}")
    
    def apply_patch(self, patch_info: dict) -> Dict[str, Any]:
        """
        Apply a patch to a file and OVERWRITE it in place.
        The original file in Projects/Sources/... is replaced with the patched version.
        
        Args:
            patch_info: Patch information containing:
                - file_path: Full path to file in Projects/Sources/...
                - unified_diff: The patch to apply
                - plan: List of steps (optional)
                - safety_verification: Safety notes (optional)
            
        Returns:
            Dict with status, paths, and metadata
        """
        try:
            # Get the file path from patch info
            file_path_str = patch_info.get("file_path")
            if not file_path_str:
                # Fall back to touched_files if available
                touched_files = patch_info.get("touched_files", [])
                if not touched_files:
                    return {
                        "status": "error",
                        "error": "No file_path or touched_files specified in patch info"
                    }
                file_path_str = touched_files[0]  # take first file for now
            
            file_path = Path(file_path_str)
            
            if not file_path.exists():
                return {
                    "status": "error",
                    "error": f"File not found: {file_path}"
                }
            
            print(f"   Reading original file: {file_path.name}")
            original_code = file_path.read_text(encoding='utf-8')
            
            print(f"   Applying patch using {self.model.value}...", end=" ", flush=True)
            modified_code = self._apply_patch_with_llm(
                original_code,
                patch_info.get("unified_diff", ""),
                patch_info.get("plan", []),
                patch_info.get("safety_verification", "")
            )
            print("✓")
            
            # Overwrite the original file in place (no _patched suffix)
            print(f"   Overwriting file: {file_path.name}")
            file_path.write_text(modified_code, encoding='utf-8')
            
            return {
                "status": "success",
                "original_file": str(file_path),
                "patched_file": str(file_path),  # Same file, now patched
                "patch_applied": True,
                "model_used": self.model.value,
                "operation": "overwrite_in_place"
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to apply patch: {str(e)}",
                "file_path": file_path_str if 'file_path_str' in locals() else "unknown"
            }
    
    def _apply_patch_with_llm(self, original_code: str, unified_diff: str, 
                              plan: List[str], safety_verification: str) -> str:
        """Use LLM to intelligently apply the unified diff to the original code"""
        
        # Format plan context
        plan_context = "\n".join(f"- {step}" for step in plan) if plan else "No plan provided"
        
        # Build user message from template
        user_message = USER_MESSAGE_TEMPLATE.format(
            original_code=original_code,
            unified_diff=unified_diff,
            plan_context=plan_context,
            safety_verification=safety_verification or "No safety verification provided"
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_MESSAGE},
            {"role": "user", "content": user_message}
        ]
        
        # Send request to OpenRouter with retry logic
        for attempt in range(self.patch_settings["retry_attempts"]):
            try:
                completion = self.client.chat.completions.create(
                    model=self.model.value,
                    messages=messages,
                    temperature=self.patch_settings["temperature"],
                    max_tokens=self.patch_settings["max_tokens"],
                    timeout=self.patch_settings["timeout"]
                )
                
                modified_code = completion.choices[0].message.content or ""
                
                if not modified_code.strip():
                    raise ValueError("LLM returned empty response")
                
                # Clean up any markdown formatting that might have been added
                if modified_code.startswith("```") and modified_code.endswith("```"):
                    lines = modified_code.split('\n')
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines[-1] == "```":
                        lines = lines[:-1]
                    modified_code = '\n'.join(lines)
                
                return modified_code.strip()
                
            except Exception as e:
                if attempt < self.patch_settings["retry_attempts"] - 1:
                    print(f"Attempt {attempt + 1} failed, retrying: {e}")
                    continue
                else:
                    raise RuntimeError(f"OpenRouter API error after {self.patch_settings['retry_attempts']} attempts: {e}")