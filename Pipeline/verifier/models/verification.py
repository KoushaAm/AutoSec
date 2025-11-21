from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, List
import datetime


class VerificationStatus(Enum):
    """Status outcomes for patch verification"""
    PATCH_VALID = "patch_valid"
    PATCH_BREAKS_BUILD = "patch_breaks_build"
    PATCH_BREAKS_TESTS = "patch_breaks_tests"
    VERIFICATION_ERROR = "verification_error"


@dataclass
class VerificationResult:
    """Result of verifying a single patch"""
    patch_id: int
    status: VerificationStatus
    reasoning: str
    confidence_score: float
    build_success: bool
    test_success: bool
    patcher_feedback: Dict[str, Any]
    verification_time: float


@dataclass
class PatchInfo:
    """Information about a patch to be verified"""
    patch_id: int
    unified_diff: str
    touched_files: List[str]
    cwe_matches: List[Dict[str, Any]]
    plan: List[str]
    confidence: int
    verifier_confidence: int
    risk_notes: str
    assumptions: str
    behavior_change: str
    safety_verification: str


@dataclass
class VerificationSession:
    """Information about a verification session"""
    session_id: str
    timestamp: datetime.datetime
    fixer_input_path: str
    output_directory: str
    total_patches: int
    results: List[VerificationResult]


class PatchChangeType(Enum):
    """Types of change in a patch"""
    ADD = "add"
    DELETE = "delete" 
    MODIFY = "modify"


@dataclass
class PatchChange:
    """Represents single change within a patch"""
    change_type: PatchChangeType
    line_number: int
    content: str
    file_path: str