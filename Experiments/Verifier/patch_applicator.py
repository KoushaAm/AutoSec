#!/usr/bin/env python3
"""
LLM-based Patch Applicator

Applies patches from Patcher JSON output files using OpenRouter LLM.
Replaces manual diff parsing with intelligent LLM-based code modification.
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
load_dotenv()

class LLMPatchApplicator:
    """Applies patches using LLM to understand and modify code intelligently"""
    
    def __init__(self, model: str = "deepseek/deepseek-chat-v3.1:free"):
        """Initialize with OpenRouter client and model selection"""
        self.model = model
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=getenv("OPENROUTER_API_KEY"),
        )
        
        if not getenv("OPENROUTER_API_KEY"):
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
    
    def apply_patch_from_json(self, patch_json_path: Path, dry_run: bool = True) -> Dict[str, Any]:
        """
        Apply a patch from a JSON file to the target source code.
        
        Args:
            patch_json_path: Path to the patch JSON file
            dry_run: If True, returns modified content without writing to file
            
        Returns:
            Dict with status, modified_content, and metadata
        """
        # Load patch JSON
        with open(patch_json_path, 'r') as f:
            patch_data = json.load(f)
        
        # Extract essential information
        metadata = patch_data.get("metadata", {})
        patch_info = patch_data.get("patch", {})
        
        file_path = Path(metadata.get("file_path", ""))
        unified_diff = patch_info.get("unified_diff", "")
        plan = patch_info.get("plan", [])
        safety_verification = patch_info.get("safety_verification", "")
        
        # Validate required fields
        if not file_path.exists():
            return {
                "status": "error",
                "error": f"Target file does not exist: {file_path}",
                "modified_content": None
            }
        
        if not unified_diff:
            return {
                "status": "error", 
                "error": "No unified_diff found in patch JSON",
                "modified_content": None
            }
        
        # Read original source code
        original_code = file_path.read_text(encoding='utf-8')
        
        # Apply patch using LLM
        try:
            modified_code = self._apply_patch_with_llm(
                original_code, unified_diff, plan, safety_verification
            )
            
            if not dry_run:
                # Write modified code back to file
                file_path.write_text(modified_code, encoding='utf-8')
                print(f"✅ Applied patch to {file_path}")
            
            return {
                "status": "success",
                "modified_content": modified_code,
                "original_content": original_code,
                "file_path": str(file_path),
                "patch_id": metadata.get("patch_id"),
                "dry_run": dry_run
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to apply patch: {str(e)}",
                "modified_content": None
            }
    
    def _apply_patch_with_llm(self, original_code: str, unified_diff: str, 
                              plan: List[str], safety_verification: str) -> str:
        """Use LLM to intelligently apply the unified diff to the original code"""
        
        # Build prompt for LLM
        system_prompt = """You are a code patch applicator. Your task is to apply a unified diff patch to source code accurately and safely.

INSTRUCTIONS:
1. Read the original source code carefully
2. Understand the unified diff format (lines starting with - should be removed, lines with + should be added)  
3. Apply the changes exactly as specified in the diff
4. Preserve all existing code structure, formatting, and comments that aren't being changed
5. Return ONLY the complete modified source code, no explanations or markdown formatting

Be extremely careful to:
- Apply changes to the correct line numbers and context
- Maintain proper indentation and formatting
- Not accidentally modify unrelated code
- Handle edge cases like missing imports that the patch might require"""

        user_prompt = f"""Apply this unified diff patch to the source code:

ORIGINAL SOURCE CODE:
```
{original_code}
```

UNIFIED DIFF TO APPLY:
```
{unified_diff}
```

PATCH PLAN (for context):
{chr(10).join(f"- {step}" for step in plan)}

SAFETY VERIFICATION (for context):
{safety_verification}

Please apply the patch and return the complete modified source code."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Send request to OpenRouter
        print(f"🤖 Applying patch using {self.model}...")
        
        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.0,  # Use deterministic output for code
                max_tokens=4000   # Sufficient for most source files
            )
            
            modified_code = completion.choices[0].message.content or ""
            
            if not modified_code.strip():
                raise ValueError("LLM returned empty response")
                
            return modified_code.strip()
            
        except Exception as e:
            raise RuntimeError(f"OpenRouter API error: {e}")
    
    def apply_multiple_patches(self, patch_directory: Path, dry_run: bool = True) -> List[Dict[str, Any]]:
        """
        Apply all patch JSON files in a directory.
        
        Args:
            patch_directory: Directory containing patch_*.json files
            dry_run: If True, doesn't actually modify files
            
        Returns:
            List of results for each patch application
        """
        results = []
        
        # Find all patch JSON files
        patch_files = sorted(patch_directory.glob("patch_*.json"))
        
        if not patch_files:
            print(f"⚠️  No patch files found in {patch_directory}")
            return results
        
        print(f"🔍 Found {len(patch_files)} patch files to process")
        
        for patch_file in patch_files:
            print(f"\n📄 Processing {patch_file.name}...")
            result = self.apply_patch_from_json(patch_file, dry_run=dry_run)
            result["patch_file"] = str(patch_file)
            results.append(result)
            
            # Print status
            if result["status"] == "success":
                mode = "DRY RUN" if dry_run else "APPLIED"
                print(f"✅ {mode}: {result['file_path']}")
            else:
                print(f"❌ ERROR: {result['error']}")
        
        return results


def main():
    """CLI interface for patch application"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Apply patches using LLM")
    parser.add_argument("--patch-dir", type=Path, required=True,
                       help="Directory containing patch JSON files")
    parser.add_argument("--apply", action="store_true", 
                       help="Actually apply patches (default is dry run)")
    parser.add_argument("--model", default="deepseek/deepseek-chat-v3.1:free",
                       help="OpenRouter model to use")
    
    args = parser.parse_args()
    
    if not args.patch_dir.exists():
        print(f"❌ Patch directory does not exist: {args.patch_dir}")
        sys.exit(1)
    
    # Initialize applicator
    try:
        applicator = LLMPatchApplicator(model=args.model)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    # Apply patches
    dry_run = not args.apply
    if dry_run:
        print("🔍 DRY RUN MODE - No files will be modified")
    else:
        print("⚠️  LIVE MODE - Files will be modified!")
    
    results = applicator.apply_multiple_patches(args.patch_dir, dry_run=dry_run)
    
    # Summary
    successful = sum(1 for r in results if r["status"] == "success")
    failed = len(results) - successful
    
    print(f"\n📊 SUMMARY:")
    print(f"  ✅ Successful: {successful}")
    print(f"  ❌ Failed: {failed}")
    print(f"  📝 Mode: {'DRY RUN' if dry_run else 'APPLIED'}")


if __name__ == "__main__":
    main()