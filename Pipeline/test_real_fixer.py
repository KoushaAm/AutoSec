#!/usr/bin/env python3

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from verifier_core import VerifierCore

def test_real_fixer_output():
    print("Testing VerifierCore with Real Fixer Output")
    print("-" * 50)
    
    fixer_json_path = pathlib.Path(__file__).parent.parent / "Experiments" / "Fixer" / "output"
    
    json_files = list(fixer_json_path.glob("LLAMA3_*.json"))
    if not json_files:
        print(f"ERROR: No Fixer output found in: {fixer_json_path}")
        return False
    
    latest_json = max(json_files, key=lambda f: f.stat().st_mtime)
    print(f"Using Fixer output: {latest_json.name}")
    
    config = {'docker_enabled': True}
    verifier = VerifierCore(config)
    
    try:
        results = verifier.verify_fixer_output(str(latest_json))
        
        print(f"\nProcessed {len(results)} patches with regression testing")
        
        for result in results:
            print(f"\n--- Patch {result.patch_id} ---")
            print(f"Status: {result.status.value}")
            print(f"Reasoning: {result.reasoning}")
            print(f"Confidence: {result.confidence_score:.2f}")
            print(f"Build Success: {result.build_success}")
            print(f"Test Success: {result.test_success}")
            print(f"Duration: {result.verification_time:.3f}s")
            
            feedback = result.patcher_feedback
            regression_results = feedback.get('regression_test_results', {})
            if regression_results.get('has_tests'):
                total = regression_results.get('total_tests', 0)
                failed = regression_results.get('failed_tests', 0)
                print(f"Regression Tests: {total - failed}/{total} passed")
                if failed > 0:
                    print(f"   WARNING: {failed} tests failed")
            else:
                print(f"Regression Tests: {regression_results.get('reason', 'No tests found')}")
            
            print(f"Patcher Feedback:")
            print(f"   Requires Revision: {feedback.get('requires_revision')}")
            print(f"   Quality Assessment: {feedback.get('patch_quality_assessment', {})}")
            
            recommendations = feedback.get('recommendations', [])
            if recommendations:
                print(f"   Recommendations: {recommendations[0]}")
        
        return True
        
    except Exception as e:
        print(f"ERROR: Error processing Fixer output: {str(e)}")
        return False

def main():
    print("Test")
    print("=" * 4)
    
    success = test_real_fixer_output()
    
    if success:
        print("\nVerification complete.")
        return 0
    else:
        print("\nTest failed - check error messages above")
        return 1

if __name__ == "__main__":
    exit(main())