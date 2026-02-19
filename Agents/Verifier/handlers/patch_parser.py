import pathlib
import shutil
from typing import Dict, Any, List, Optional
from ..models.verification import PatchInfo

class PatchParser:
    
    def parse_fixer_patch(self, patch_data: Dict[str, Any]) -> PatchInfo:
        """
        Parse patch data from Patcher output
        
        Patcher format:
        {
          "metadata": {"patch_id": 1, "file_path": "...", ...},
          "patch": {"unified_diff": "...", "plan": [...], ...}
        }
        """
        # Handle Patcher's nested structure
        if 'metadata' in patch_data and 'patch' in patch_data:
            metadata = patch_data['metadata']
            patch = patch_data['patch']
            
            return PatchInfo(
                patch_id=metadata.get('patch_id', 0),
                unified_diff=patch.get('unified_diff', ''),
                touched_files=patch.get('touched_files', []),
                cwe_matches=patch.get('cwe_matches', []),
                plan=patch.get('plan', []),
                confidence=patch.get('confidence', 0),
                verifier_confidence=patch.get('confidence', 0),  
                risk_notes=patch.get('risk_notes', ''),
                assumptions=patch.get('assumptions', ''),
                behavior_change=patch.get('behavior_change', ''),
                safety_verification=patch.get('safety_verification', ''),
                pov_tests=None  # POV tests come from Exploiter separately
            )
        
        # Fallback: handle old flat format (if needed)
        return PatchInfo(
            patch_id=patch_data.get('patch_id', 0),
            unified_diff=patch_data.get('unified_diff', ''),
            touched_files=patch_data.get('touched_files', []),
            cwe_matches=patch_data.get('cwe_matches', []),
            plan=patch_data.get('plan', []),
            confidence=patch_data.get('confidence', 0),
            verifier_confidence=patch_data.get('verifier_confidence', 0),
            risk_notes=patch_data.get('risk_notes', ''),
            assumptions=patch_data.get('assumptions', ''),
            behavior_change=patch_data.get('behavior_change', ''),
            safety_verification=patch_data.get('safety_verification', ''),
            pov_tests=None
        )


class ProjectManager:
    """Manages project copying and file operations"""
    
    @staticmethod
    def create_patched_copy(original_path: pathlib.Path, output_path: pathlib.Path, target_files: List[str] = None) -> bool:
        try:
            if output_path.exists():
                shutil.rmtree(output_path)
            output_path.mkdir(parents=True)
            
            # Copy entire project directory
            shutil.copytree(original_path, output_path, dirs_exist_ok=True)
            return True
        except Exception as e:
            print(f"      Error creating project copy: {e}")
            return False
    
    @staticmethod
    def find_project_root(file_path: str) -> pathlib.Path:
        """
        Extract project root from the full file path.
        
        Expects: "Projects/Sources/project_name/src/main/File.java"
        Returns: Projects/Sources/project_name/
        """
        file_path_obj = pathlib.Path(file_path)
        
        # Check if path contains "Projects/Sources/"
        if "Projects" in file_path_obj.parts and "Sources" in file_path_obj.parts:
            # Find the index of "Sources" in the path
            parts = file_path_obj.parts
            try:
                sources_idx = parts.index("Sources")
                # Project root is one level after "Sources"
                # e.g., Projects/Sources/project_name/
                if sources_idx + 1 < len(parts):
                    # Reconstruct path up to and including the project directory
                    project_root_parts = parts[:sources_idx + 2]
                    project_root = pathlib.Path(*project_root_parts)
                    
                    # Make it absolute if it's not already
                    if not project_root.is_absolute():
                        # Navigate to AutoSec root and construct absolute path
                        current_file = pathlib.Path(__file__)
                        autosec_root = current_file.parent.parent.parent.parent
                        project_root = autosec_root / project_root
                    
                    return project_root
            except (ValueError, IndexError):
                pass
        
        # Fallback: if path doesn't match expected format, raise error
        raise ValueError(
            f"Invalid file path format: {file_path}\n"
            f"Expected format: 'Projects/Sources/project_name/src/...'"
        )
    
    @staticmethod
    def extract_relative_file_path(patcher_file_path: str) -> str:
        """
        Extract the relative file path within the project.
        
        Input: "Projects/Sources/project_name/src/main/File.java"
        Output: "src/main/File.java"
        """
        path_obj = pathlib.Path(patcher_file_path)
        
        # Find "Sources" in the path and get everything after the project name
        if "Projects" in path_obj.parts and "Sources" in path_obj.parts:
            parts = path_obj.parts
            try:
                sources_idx = parts.index("Sources")
                # Everything after Sources/project_name/ is the relative path
                if sources_idx + 2 < len(parts):
                    relative_parts = parts[sources_idx + 2:]
                    return str(pathlib.Path(*relative_parts))
            except (ValueError, IndexError):
                pass
        
        # Fallback: just return the filename
        return path_obj.name