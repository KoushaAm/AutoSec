from .core.engine import VerifierCore, create_verifier
from .core.patch_applicator import LLMPatchApplicator
from .models.verification import (
    VerificationStatus,
    VerificationResult, 
    PatchInfo,
    VerificationSession
)
from . import cli

__all__ = [
    'VerifierCore',
    'create_verifier',
    'LLMPatchApplicator',
    'VerificationStatus',
    'VerificationResult',
    'PatchInfo',
    'VerificationSession',
    'cli'
]

__version__ = '1.0.0'

# Main entry point function for convenience
def main():
    """Main entry point for the verifier CLI"""
    cli.main()