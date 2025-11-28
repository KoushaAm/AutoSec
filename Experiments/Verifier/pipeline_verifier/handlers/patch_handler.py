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


class PatchApplicator:
    """Applies patches to project files"""
    
    def __init__(self):
        self.parser = PatchParser()
    
    def apply_patch(self, patch_info: PatchInfo, project_path: pathlib.Path) -> bool:
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
        try:
            original_content = target_file.read_text()
            original_lines = original_content.splitlines()
            
            deletions = [c for c in changes if c.change_type == PatchChangeType.DELETE]
            additions = [c for c in changes if c.change_type == PatchChangeType.ADD]
            
            # Apply deletions first
            modified_lines = original_lines.copy()
            deletion_positions = []
            
            for deletion in deletions:
                target_content = deletion.content
                found_line = None
                
                # Try exact match first
                for i, line in enumerate(modified_lines):
                    if line == target_content:
                        found_line = i
                        break
                
                # If exact match fails, try stripped match
                if found_line is None:
                    target_stripped = target_content.strip()
                    for i, line in enumerate(modified_lines):
                        if line.strip() == target_stripped:
                            found_line = i
                            break
                
                if found_line is not None:
                    del modified_lines[found_line]
                    deletion_positions.append(found_line)
                else:
                    return False
            
            # Apply additions - insert at the positions where we deleted
            if deletion_positions and additions:
                # Sort deletion positions and apply additions in reverse order
                deletion_positions.sort()
                
                # Insert additions at the first deletion position
                insert_pos = deletion_positions[0]
                
                for addition in additions:
                    modified_lines.insert(insert_pos, addition.content)
                    insert_pos += 1
            
            # Write the modified content
            target_file.write_text('\n'.join(modified_lines) + '\n')
            return True
            
        except Exception as e:
            return False
    
    def _group_related_changes(self, deletions: List[PatchChange], additions: List[PatchChange], original_lines: List[str]) -> List[Dict]:
        groups = []
        
        # Simple strategy: pair deletions with additions based on proximity
        used_additions = set()
        
        for deletion in deletions:
            # Find the line to delete
            delete_line_idx = None
            target_content = deletion.content.strip()
            
            for i, line in enumerate(original_lines):
                if line.strip() == target_content:
                    delete_line_idx = i
                    break
            
            if delete_line_idx is not None:
                # Find related additions (heuristic: additions that should replace this deletion)
                related_additions = []
                
                # For Fixer patterns, additions usually come right after deletions in the same logical block
                for addition in additions:
                    if addition not in used_additions:
                        # Simple heuristic: if addition references variables from the deleted line
                        deleted_content = deletion.content.strip()
                        addition_content = addition.content.strip()
                        
                        # Check if they share variable names or are in same logical block
                        if self._are_related_changes(deleted_content, addition_content):
                            related_additions.append(addition)
                            used_additions.add(addition)
                
                groups.append({
                    'type': 'replace',
                    'line_index': delete_line_idx,
                    'delete_content': deletion.content,
                    'add_content': [add.content for add in related_additions]
                })
        
        # Handle standalone additions (not paired with deletions)
        for addition in additions:
            if addition not in used_additions:
                # Find best insertion point for standalone additions
                insertion_point = self._find_smart_insertion_point(original_lines, addition.content)
                groups.append({
                    'type': 'insert',
                    'line_index': insertion_point,
                    'add_content': [addition.content]
                })
        
        # Sort groups by line index for proper application order
        return sorted(groups, key=lambda g: g['line_index'])
    
    def _are_related_changes(self, deleted_content: str, addition_content: str) -> bool:
        # Extract variable names and keywords
        import re
        
        # Get variable names from both lines
        deleted_vars = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', deleted_content)
        addition_vars = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', addition_content)
        
        # Check for common variables
        common_vars = set(deleted_vars) & set(addition_vars)
        
        # They're related if they share variables or if addition is a control structure around similar content
        return len(common_vars) > 0 or 'if' in addition_content.lower()
    
    def _apply_change_group(self, lines: List[str], group: Dict) -> List[str]:
        modified_lines = lines.copy()
        line_idx = group['line_index']
        
        if group['type'] == 'replace':
            # Replace the line at line_idx with new content
            if 0 <= line_idx < len(modified_lines):
                # Remove the original line
                del modified_lines[line_idx]
                
                # Insert new lines at the same position
                for i, new_content in enumerate(group['add_content']):
                    modified_lines.insert(line_idx + i, new_content.rstrip())
        
        elif group['type'] == 'insert':
            # Insert new content at line_idx
            for i, new_content in enumerate(group['add_content']):
                insert_pos = min(line_idx + i, len(modified_lines))
                modified_lines.insert(insert_pos, new_content.rstrip())
        
        return modified_lines
    
    def _find_smart_insertion_point(self, lines: List[str], new_content: str) -> int:
        content_lower = new_content.lower().strip()
        
        # If it's an if statement or control structure, insert before method end
        if content_lower.startswith('if ') or content_lower.startswith('while ') or content_lower.startswith('for '):
            # Find the last non-empty line before method closing brace
            for i in reversed(range(len(lines))):
                line = lines[i].strip()
                if line and not line.startswith('//') and line != '}':
                    # Insert after this line, before the closing brace
                    return i + 1
        
        # Default: insert before the last closing brace
        for i in reversed(range(len(lines))):
            if lines[i].strip() == '}':
                return i
        
        # Fallback: append at end
        return len(lines)


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
        # Navigate up from current file to find AutoSec root, then to vulnerable directory (TODO: later change?)
        current_file = pathlib.Path(__file__)
        # Go up to AutoSec root
        autosec_root = current_file.parent.parent.parent.parent
        vulnerable_dir = autosec_root / "Experiments" / "vulnerable"
        return vulnerable_dir