import pathlib
from verifier import create_verifier, VerificationStatus


def main():
    print("Verifier Agent - Patch Validation")
    print("=" * 40)
    
    # Find the Fixer output file
    fixer_output_dir = pathlib.Path("../Experiments/Fixer/output")
    fixer_files = list(fixer_output_dir.glob("*.json"))
    
    if not fixer_files:
        print("ERROR: No Fixer output files found!")
        return
    
    fixer_file = fixer_files[0]
    print(f"Input: {fixer_file.name}")
    
    # Create verifier
    config = {"output_directory": "verifier/verifier_output"}
    verifier = create_verifier(config)
    
    # Run verification
    results = verifier.verify_fixer_output(str(fixer_file))
    
    # Print core verification decisions
    print(f"\nVerification Decisions:")
    for result in results:
        patch_id = result.patch_id
        cwe_id = result.patcher_feedback.get('cwe_matches', [{}])[0].get('cwe_id', 'Unknown')
        decision = "SAFE" if result.status.value == "patch_valid" else "VULNERABLE"
        reasoning = result.reasoning
        
        print(f"  Patch {patch_id} ({cwe_id}): {decision}")
        print(f"    Reasoning: {reasoning}")
        
        if result.patcher_feedback.get('requires_revision'):
            print(f"    → Requires revision for patch refinement")
        else:
            print(f"    → Patch validated")
    
    # Summary for pipeline integration
    safe_patches = len([r for r in results if r.status.value == "patch_valid"])
    total_patches = len(results)
    
    print(f"\nSummary: {safe_patches}/{total_patches} patches validated as safe")

if __name__ == "__main__":
    main()