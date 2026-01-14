import pathlib
import shutil
from typing import Dict, Any, List, Optional
from ..models.verification import PatchInfo, PatchChange, PatchChangeType

class PatchParser:
    """Parses unified diff (Fixer output) patches into structured data"""
    
    def parse_fixer_patch(self, patch_data: Dict[str, Any]) -> PatchInfo:
        return PatchInfo(
            patch_id=patch_data['patch_id'],
            unified_diff=patch_data.get('unified_diff', ''),
            touched_files=patch_data.get('touched_files', []),
            cwe_matches=patch_data.get('cwe_matches', []),
            plan=patch_data.get('plan', []),
            confidence=patch_data.get('confidence', 0),
            verifier_confidence=patch_data.get('verifier_confidence', 0),
            risk_notes=patch_data.get('risk_notes', ''),
            assumptions=patch_data.get('assumptions', ''),
            behavior_change=patch_data.get('behavior_change', ''),
            safety_verification=patch_data.get('safety_verification', '')
        )
    
    def parse_unified_diff(self, unified_diff: str) -> Dict[str, List[PatchChange]]:
        lines = unified_diff.split('\n')
        file_changes = {}
        current_file = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('--- '):
                # Extract file path from Fixer format
                full_path = line[4:].strip()
                if full_path.startswith('Experiments/vulnerable/'):
                    current_file = full_path.replace('Experiments/vulnerable/', '')
                else:
                    current_file = pathlib.Path(full_path).name
                file_changes[current_file] = []
                
            elif line.startswith('@@ ') and current_file:
                # Parse complete hunk - find all lines until next @@ or end
                hunk_lines = [line]  # Include the @@ header
                i += 1
                
                # Collect all lines in this hunk
                while i < len(lines):
                    next_line = lines[i]
                    if next_line.strip().startswith('@@') or next_line.strip().startswith('---') or next_line.strip().startswith('+++'):
                        i -= 1  # Back up to process this line in outer loop
                        break
                    hunk_lines.append(next_line)
                    i += 1
                
                # Parse this complete hunk
                hunk_changes = self._parse_fixer_hunk(hunk_lines)
                file_changes[current_file].extend(hunk_changes)
            
            i += 1
        
        return file_changes
    
    def _parse_fixer_hunk(self, hunk_lines: List[str]) -> List[PatchChange]:
        changes = []
        
        if not hunk_lines or not hunk_lines[0].startswith('@@'):
            return changes
        
        # Process each line in the hunk (skip the @@ header)
        for line in hunk_lines[1:]:
            if not line:  # Skip empty lines
                continue
                
            if line.startswith('-'):
                # Deletion - store the exact content to find and remove
                content = line[1:]  # Remove '-' prefix
                changes.append(PatchChange(
                    change_type=PatchChangeType.DELETE,
                    line_number=0,  # We'll use content matching instead
                    content=content,
                    file_path=""
                ))
            elif line.startswith('+'):
                # Addition - store the exact content to add
                content = line[1:]  # Remove '+' prefix
                changes.append(PatchChange(
                    change_type=PatchChangeType.ADD,
                    line_number=0,  # We'll use content matching instead
                    content=content,
                    file_path=""
                ))
            # Skip context lines (lines starting with ' ')
        
        return changes


class ProjectManager:
    """Manages project copying and file operations"""
    
    @staticmethod
    def create_patched_copy(original_path: pathlib.Path, output_path: pathlib.Path, target_files: List[str] = None) -> bool:
        try:
            if output_path.exists():
                shutil.rmtree(output_path)
            output_path.mkdir(parents=True)
            
            # If no target files specified, copy everything (fallback)
            if not target_files:
                shutil.copytree(original_path, output_path)
                return True
            
            # Copy only specified target files
            for file_path in target_files:
                filename = pathlib.Path(file_path).name
                source_file = original_path / filename
                dest_file = output_path / filename
                
                if source_file.exists():
                    shutil.copy2(source_file, dest_file)
                else:
                    print(f"      Warning: Target file not found: {source_file}")
                    return False
            
            return True
        except Exception as e:
            print(f"      Error creating project copy: {e}")
            return False
    
    @staticmethod
    def find_project_root(file_path: str) -> pathlib.Path:
        """
        Find the vulnerable project root directory.
        If the file is in a subdirectory (e.g., perfecto/PerfectoBuildWrapper.java),
        use that subdirectory as the project root for proper isolation.
        """
        # Navigate up from current file to find AutoSec root, then to vulnerable directory
        current_file = pathlib.Path(__file__)
        # Go up: pipeline_verifier/handlers/patch_handler.py -> pipeline_verifier/handlers -> pipeline_verifier -> Verifier -> Experiments -> AutoSec
        autosec_root = current_file.parent.parent.parent.parent.parent
        vulnerable_dir = autosec_root / "Experiments" / "vulnerable"
        
        # Check if the file_path contains a subdirectory within vulnerable/
        # e.g., "Experiments/vulnerable/perfecto/PerfectoBuildWrapper.java"
        file_path_obj = pathlib.Path(file_path)
        
        # Try to find if there's a subdirectory specified in the path
        if "vulnerable/" in str(file_path):
            # Extract the part after "vulnerable/"
            parts_after_vulnerable = str(file_path).split("vulnerable/")[1]
            path_parts = pathlib.Path(parts_after_vulnerable).parts
            
            # If there are multiple parts, the first part is a subdirectory
            if len(path_parts) > 1:
                subdir_name = path_parts[0]
                project_root = vulnerable_dir / subdir_name
                
                # Verify the subdirectory exists
                if project_root.exists() and project_root.is_dir():
                    print(f"      Project root (subdirectory): {project_root}")
                    print(f"      Target file to be patched: {path_parts[-1]}")
                    if list(project_root.glob('*.java')):
                        print(f"      Java files in project: {[f.name for f in project_root.glob('*.java')]}")
                    return project_root
        
        # Fallback: Use the main vulnerable directory
        print(f"      Project root (vulnerable directory): {vulnerable_dir}")
        print(f"      Directory exists: {vulnerable_dir.exists()}")
        if vulnerable_dir.exists():
            java_files = list(vulnerable_dir.glob('*.java'))
            print(f"      Files in vulnerable directory: {[f.name for f in java_files]}")
            
            # Extract the specific file that will be patched from file_path
            target_filename = pathlib.Path(file_path).name
            print(f"      Target file to be patched: {target_filename}")
        
        return vulnerable_dir