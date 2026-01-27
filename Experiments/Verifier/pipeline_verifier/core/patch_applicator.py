#!/usr/bin/env python3
"""
LLM-based Patch Applicator

Applies patches from Patcher JSON output files using OpenRouter LLM.
Replaces manual diff parsing with intelligent LLM-based code modification.
"""

import json
import sys
import datetime
from pathlib import Path
from typing import Dict, Any, List
from os import getenv
from dotenv import load_dotenv
from openai import OpenAI

# Local imports - use module's config and constants
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from constants import Model, SYSTEM_MESSAGE, USER_MESSAGE_TEMPLATE
from pipeline_verifier import config

# Load environment variables
load_dotenv()

class LLMPatchApplicator:
    """Applies patches using LLM to understand and modify code intelligently"""
    
    def __init__(self, model: Model = None, output_base_dir: Path = None):
        """Initialize with OpenRouter client and model selection"""
        self.model = model or config.CURRENT_MODEL
        self.output_base_dir = output_base_dir or config.DEFAULT_OUTPUT_DIR
        
        # Create output directory if it doesn't exist
        self.output_base_dir.mkdir(parents=True, exist_ok=True)
        
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
        print(f"   Output Base Dir: {self.output_base_dir}")
        print(f"   Version: {config.TOOL_VERSION}")
    
    def apply_patch_to_directory(self, source_dir: Path, patch_info: dict, output_dir: Path) -> Dict[str, Any]:
        """
        Apply a patch and create clean output with only the patched file.
        Creates: filename-patched.java (not a full directory copy)
        
        Args:
            source_dir: Directory containing original vulnerable files
            patch_info: Patch information (unified_diff, plan, etc.)
            output_dir: Where to create the patched file
            
        Returns:
            Dict with status, paths, and metadata
        """
        try:
            # Create clean output directory
            if output_dir.exists():
                import shutil
                shutil.rmtree(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Get the specific file to patch
            target_files = patch_info.get("touched_files", [])
            if not target_files:
                return {
                    "status": "error",
                    "error": "No touched files specified in patch info",
                    "source_dir": str(source_dir),
                    "output_dir": str(output_dir)
                }
            
            # Apply patch to each touched file (usually just one)
            results = []
            for file_path in target_files:
                # Extract just the filename from the full path
                file_name = Path(file_path).name
                source_file = source_dir / file_name
                
                if not source_file.exists():
                    results.append({
                        "file": file_name,
                        "status": "error", 
                        "error": f"Source file not found: {source_file}"
                    })
                    continue
                
                # Create patched filename: CWE_78.java -> CWE_78-patched.java
                base_name = source_file.stem  # CWE_78
                extension = source_file.suffix  # .java
                patched_filename = f"{base_name}-patched{extension}"
                patched_file = output_dir / patched_filename
                
                # Read original code
                original_code = source_file.read_text(encoding='utf-8')
                
                # Apply patch using LLM
                try:
                    modified_code = self._apply_patch_with_llm(
                        original_code,
                        patch_info.get("unified_diff", ""),
                        patch_info.get("plan", []),
                        patch_info.get("safety_verification", "")
                    )
                    
                    # Write only the patched file (not the full directory)
                    patched_file.write_text(modified_code, encoding='utf-8')
                    
                    results.append({
                        "file": file_name,
                        "patched_file": patched_filename,
                        "status": "success",
                        "source_path": str(source_file),
                        "output_path": str(patched_file),
                        "patch_applied": True
                    })
                    
                    print(f"   Created {patched_filename} from {file_name}")
                    
                except Exception as e:
                    results.append({
                        "file": file_name,
                        "status": "error",
                        "error": f"LLM patch application failed: {str(e)}",
                        "source_path": str(source_file)
                    })
                    print(f"   Failed to patch {file_name}: {e}")
            
            # Determine overall status
            successful_files = [r for r in results if r["status"] == "success"]
            failed_files = [r for r in results if r["status"] == "error"]
            
            return {
                "status": "success" if successful_files and not failed_files else "partial" if successful_files else "error",
                "source_dir": str(source_dir),
                "output_dir": str(output_dir),
                "files_processed": len(results),
                "files_successful": len(successful_files),
                "files_failed": len(failed_files),
                "file_results": results,
                "model_used": self.model.value
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": f"Failed to apply patch: {str(e)}",
                "source_dir": str(source_dir),
                "output_dir": str(output_dir)
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
        print(f"Applying patch using {self.model.value}...")
        
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
    
    def save_results(self, results: List[Dict[str, Any]], session_name: str = None) -> Path:
        """Save patch application results to output directory"""
        if not session_name:
            timestamp = datetime.datetime.now().strftime("%Y%m%dT%H%M%SZ")
            session_name = f"patch_application_{timestamp}"
        
        session_dir = self.output_base_dir / session_name
        session_dir.mkdir(parents=True, exist_ok=True)
        
        # Save detailed results
        results_file = session_dir / "results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Save summary
        summary = self._generate_summary(results)
        summary_file = session_dir / "summary.json"
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"Results saved to: {session_dir}")
        return session_dir
    
    def _generate_summary(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Generate summary statistics from results"""
        successful = sum(1 for r in results if r["status"] == "success")
        warnings = sum(1 for r in results if r["status"] == "warning")
        failed = sum(1 for r in results if r["status"] == "error")
        
        return {
            "timestamp": datetime.datetime.now().isoformat(),
            "model_used": self.model.value,
            "total_patches": len(results),
            "successful": successful,
            "warnings": warnings,
            "failed": failed,
            "success_rate": successful / len(results) if results else 0,
            "results": results
        }


def apply_latest_patcher_output(model: Model = None) -> List[Dict[str, Any]]:
    """Convenience function to apply patches from the latest Patcher output"""
    patcher_output_dir = config.LATEST_PATCHER_OUTPUT
    
    if not patcher_output_dir.exists():
        print(f"Patcher output directory not found: {patcher_output_dir}")
        return []
    
    print(f"Using Patcher output from: {patcher_output_dir}")
    
    applicator = LLMPatchApplicator(model=model)
    results = []
    
    for patch_file in patcher_output_dir.glob("patch_*.json"):
        try:
            with open(patch_file, 'r') as f:
                patch_info = json.load(f)
            
            source_dir = Path(patch_info["metadata"]["source_dir"])
            output_dir = applicator.output_base_dir / f"patched_{patch_file.stem}"
            
            result = applicator.apply_patch_to_directory(source_dir, patch_info, output_dir)
            results.append(result)
        except Exception as e:
            print(f"Failed to process {patch_file}: {e}")
    
    # Save results
    session_name = f"from_patcher_{patcher_output_dir.name}"
    applicator.save_results(results, session_name)
    
    return results


def main():
    """CLI interface for patch application"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Apply patches using LLM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Apply patches from latest Patcher output
  python patch_applicator.py
  
  # Apply from specific directory
  python patch_applicator.py --patch-dir /path/to/patches
  
  # Use different model
  python patch_applicator.py --model LLAMA3
        """
    )
    
    parser.add_argument("--patch-dir", type=Path,
                       help="Directory containing patch JSON files (default: latest Patcher output)")
    parser.add_argument("--model", choices=[m.name for m in Model],
                       help=f"OpenRouter model to use (default: {config.CURRENT_MODEL.name})")
    
    args = parser.parse_args()
    
    # Initialize applicator
    try:
        model = Model[args.model] if args.model else None
        
        # Use provided patch dir or default to latest Patcher output
        if args.patch_dir:
            if not args.patch_dir.exists():
                print(f"Patch directory does not exist: {args.patch_dir}")
                sys.exit(1)
            
            print(f"Using specified patch directory: {args.patch_dir}")
            applicator = LLMPatchApplicator(model=model)
            results = []
            
            for patch_file in args.patch_dir.glob("patch_*.json"):
                try:
                    with open(patch_file, 'r') as f:
                        patch_info = json.load(f)
                    
                    source_dir = Path(patch_info["metadata"]["source_dir"])
                    output_dir = applicator.output_base_dir / f"patched_{patch_file.stem}"
                    
                    result = applicator.apply_patch_to_directory(source_dir, patch_info, output_dir)
                    results.append(result)
                except Exception as e:
                    print(f"Failed to process {patch_file}: {e}")
            
            # Save results
            session_name = f"from_{args.patch_dir.name}"
            applicator.save_results(results, session_name)
        else:
            # Default to latest Patcher output
            results = apply_latest_patcher_output(model=model)
        
    except ValueError as e:
        print(f"{e}")
        print("Make sure OPENROUTER_API_KEY is set in your .env file")
        sys.exit(1)
    
    # Summary
    if results:
        successful = sum(1 for r in results if r["status"] == "success")
        warnings = sum(1 for r in results if r["status"] == "warning")
        failed = sum(1 for r in results if r["status"] == "error")
        
        print(f"\nSUMMARY:")
        print(f"  Successful: {successful}")
        print(f"  Warnings: {warnings}")
        print(f"  Failed: {failed}")


if __name__ == "__main__":
    main()