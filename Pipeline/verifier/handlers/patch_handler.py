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
        """Parse unified diff into structured file changes"""
        lines = unified_diff.split('\n')
        file_changes = {}
        current_file = None
        
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('--- '):
                # Extract file path
                full_path = line[4:].strip()
                if full_path.startswith('Experiments/vulnerable/'):
                    current_file = full_path.replace('Experiments/vulnerable/', '')
                else:
                    current_file = pathlib.Path(full_path).name
                file_changes[current_file] = []
                
            elif line.startswith('@@ ') and current_file:
                # Parse this hunk and find where it ends
                hunk_start = i
                hunk_end = i + 1
                
                # Find the end of this hunk (next @@ or the end of file)
                while hunk_end < len(lines):
                    next_line = lines[hunk_end].strip()
                    if next_line.startswith('@@') or next_line.startswith('---') or next_line.startswith('+++'):
                        break
                    hunk_end += 1
                
                # Parse this specific hunk
                hunk_changes = self._parse_single_hunk(lines[hunk_start:hunk_end])
                file_changes[current_file].extend(hunk_changes)
                
                # Move to the end of this hunk
                i = hunk_end - 1
            
            i += 1
        
        return file_changes
    
    def _parse_single_hunk(self, hunk_lines: List[str]) -> List[PatchChange]:
        """Parse a single hunk (from @@ to next @@ or end)"""
        changes = []
        
        if not hunk_lines or not hunk_lines[0].startswith('@@'):
            return changes
        
        # Parse the @@ header to get line numbers
        header = hunk_lines[0]
        try:
            parts = header.split()
            if len(parts) >= 3:
                old_info = parts[1][1:]  # Remove '-'
                old_start = int(old_info.split(',')[0])
                current_old_line = old_start
                current_new_line = int(parts[2][1:].split(',')[0])  # Remove '+'
            else:
                current_old_line = 1
                current_new_line = 1
        except (ValueError, IndexError):
            current_old_line = 1
            current_new_line = 1
        
        # Process each line in the hunk (skip the @@ header)
        for line in hunk_lines[1:]:
            if not line:  # Empty line
                continue
                
            if line.startswith('-'):
                changes.append(PatchChange(
                    change_type=PatchChangeType.DELETE,
                    line_number=current_old_line,
                    content=line[1:],  # Remove '-'
                    file_path=""
                ))
                current_old_line += 1
            elif line.startswith('+'):
                changes.append(PatchChange(
                    change_type=PatchChangeType.ADD,
                    line_number=current_new_line,
                    content=line[1:],  # Remove '+'
                    file_path=""
                ))
                current_new_line += 1
            elif line.startswith(' '):
                # Context line - both counters advance
                current_old_line += 1
                current_new_line += 1
        
        return changes


class PatchApplicator:
    """Applies patches to project files"""
    
    def __init__(self):
        self.parser = PatchParser()
    
    def apply_patch(self, patch_info: PatchInfo, project_path: pathlib.Path) -> bool:
        """Apply a patch to the project files"""
        try:
            if not patch_info.unified_diff:
                return False
            
            # Parse and apply patch quietly
            file_changes = self.parser.parse_unified_diff(patch_info.unified_diff)
            
            if not file_changes:
                return False
            
            # Apply changes to each file
            for file_path, changes in file_changes.items():
                target_file = project_path / file_path
                
                if not target_file.exists():
                    return False
                
                success = self._apply_file_changes(target_file, changes)
                
                if not success:
                    return False
            
            return True
            
        except Exception as e:
            return False
    
    def _apply_file_changes(self, target_file: pathlib.Path, changes: List[PatchChange]) -> bool:
        """Apply changes to a single file using content matching"""
        try:
            original_lines = target_file.read_text().splitlines(keepends=True)
            deletions = [c for c in changes if c.change_type == PatchChangeType.DELETE]
            additions = [c for c in changes if c.change_type == PatchChangeType.ADD]
            
            new_lines = original_lines.copy()
            deletion_positions = []
            
            # Apply deletions
            for deletion in deletions:
                target_content = deletion.content.strip()
                found_line = None
                
                for i, line in enumerate(new_lines):
                    if line.strip() == target_content:
                        found_line = i
                        break
                
                if found_line is not None:
                    del new_lines[found_line]
                    deletion_positions.append(found_line)
            
            # Apply additions
            if deletions and additions and deletion_positions:
                insert_position = min(deletion_positions)
                insert_position = max(0, min(insert_position, len(new_lines)))
                
                for addition in additions:
                    line_content = addition.content
                    if not line_content.endswith('\n'):
                        line_content += '\n'
                    
                    new_lines.insert(insert_position, line_content)
                    insert_position += 1
                    
            elif additions and not deletions:
                for addition in additions:
                    line_content = addition.content
                    if not line_content.endswith('\n'):
                        line_content += '\n'
                    
                    insert_pos = self._find_insertion_point(new_lines, addition.content)
                    new_lines.insert(insert_pos, line_content)
            
            target_file.write_text(''.join(new_lines))
            return True
            
        except Exception as e:
            return False
    
    def _find_insertion_point(self, lines: List[str], new_content: str) -> int:
        """Find the best insertion point for new content"""
        # Insert at the end of the main method or class
        # Look for common patterns like method endings
        
        for i in reversed(range(len(lines))):
            line = lines[i].strip()
            # Insert before closing braces that look like method/class endings
            if line == '}' and i > 0:
                prev_line = lines[i-1].strip()
                if not prev_line.startswith('//') and prev_line != '':
                    return i
        
        # Fallback: insert at the end
        return len(lines)


class ProjectManager:
    """Manages project copying and file operations"""
    
    @staticmethod
    def create_patched_copy(original_path: pathlib.Path, output_path: pathlib.Path, target_files: List[str] = None) -> bool:
        """Create a copy of the project for patching with only target files"""
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
        """Find the root directory of a project"""
        # Navigate up from current file to find AutoSec root, then to vulnerable directory (TODO: later change?)
        current_file = pathlib.Path(__file__)
        # Go up to AutoSec root
        autosec_root = current_file.parent.parent.parent.parent
        vulnerable_dir = autosec_root / "Experiments" / "vulnerable"
        return vulnerable_dir