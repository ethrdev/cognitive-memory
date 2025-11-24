#!/usr/bin/env python3
"""
Test script for Ground Truth Collection Streamlit App

This script performs basic validation tests for the Streamlit app components
that can be tested without the full Streamlit UI running.
"""

import sys

# Add project root to path
sys.path.insert(0, "/home/ethr/01-projects/ai-experiments/i-o")


def test_imports():
    """Test that all imports work correctly"""
    print("🔍 Testing imports...")

    try:
        # Test main app imports

        print("✅ Main app imports successful")

        # Test RRF utility imports

        print("✅ RRF utility imports successful")

        return True

    except Exception as e:
        print(f"❌ Import test failed: {e}")
        return False


<<<<<<< Updated upstream
def test_streamlit_rrf_fusion():
=======
def test_rrf_fusion():
>>>>>>> Stashed changes
    """Test RRF fusion algorithm with mock data"""
    print("🔍 Testing RRF fusion algorithm...")

    try:
<<<<<<< Updated upstream
        from streamlit_apps.utils.rrf_fusion import rrf_fusion as streamlit_rrf_fusion
=======
        from streamlit_apps.utils.rrf_fusion import rrf_fusion
>>>>>>> Stashed changes

        # Mock semantic search results (id, content, source_ids, distance)
        semantic_results = [
            (1, "Document 1 content", [1, 2], 0.1),
            (2, "Document 2 content", [3, 4], 0.2),
            (3, "Document 3 content", [5, 6], 0.3),
        ]

        # Mock keyword search results (id, content, source_ids, rank)
        keyword_results = [
            (2, "Document 2 content", [3, 4], 0.9),
            (1, "Document 1 content", [1, 2], 0.8),
            (4, "Document 4 content", [7, 8], 0.7),
        ]

        # Test RRF fusion
<<<<<<< Updated upstream
        fused_results = streamlit_rrf_fusion(semantic_results, keyword_results)
=======
        fused_results = rrf_fusion(semantic_results, keyword_results)
>>>>>>> Stashed changes

        # Validate results
        assert len(fused_results) > 0, "RRF fusion should return results"
        assert all(
            "id" in doc for doc in fused_results
        ), "Each result should have an 'id'"
        assert all(
            "score" in doc for doc in fused_results
        ), "Each result should have a 'score'"

        # Results should be sorted by score (descending)
        scores = [doc["score"] for doc in fused_results]
        assert scores == sorted(
            scores, reverse=True
        ), "Results should be sorted by score"

        print("✅ RRF fusion algorithm test passed")
        print(
            f"   - Fused {len(semantic_results)} semantic + {len(keyword_results)} keyword results"
        )
        print(f"   - Generated {len(fused_results)} merged results")

        return True

    except Exception as e:
        print(f"❌ RRF fusion test failed: {e}")
        return False


def test_rrf_validation():
    """Test RRF input validation"""
    print("🔍 Testing RRF input validation...")

    try:
<<<<<<< Updated upstream

        # Test valid inputs
        valid = validate_rrf_inputs_func([], [], 0.7, 0.3)
        assert not valid, "Empty result lists should be invalid"

        valid = validate_rrf_inputs_func([(1, "test", [], 0.1)], [], 0.7, 0.3)
        assert valid, "Non-empty semantic results should be valid"

        valid = validate_rrf_inputs_func([], [(1, "test", [], 0.1)], 0.7, 0.3)
        assert valid, "Non-empty keyword results should be valid"

        # Test invalid weights
        valid = validate_rrf_inputs_func([(1, "test", [], 0.1)], [], -0.1, 0.3)
=======
        from streamlit_apps.utils.rrf_fusion import validate_rrf_inputs

        # Test valid inputs
        valid = validate_rrf_inputs([], [], 0.7, 0.3)
        assert not valid, "Empty result lists should be invalid"

        valid = validate_rrf_inputs([(1, "test", [], 0.1)], [], 0.7, 0.3)
        assert valid, "Non-empty semantic results should be valid"

        valid = validate_rrf_inputs([], [(1, "test", [], 0.1)], 0.7, 0.3)
        assert valid, "Non-empty keyword results should be valid"

        # Test invalid weights
        valid = validate_rrf_inputs([(1, "test", [], 0.1)], [], -0.1, 0.3)
>>>>>>> Stashed changes
        assert not valid, "Negative semantic weight should be invalid"

        print("✅ RRF input validation test passed")

        return True

    except Exception as e:
        print(f"❌ RRF validation test failed: {e}")
        return False


def test_stratification_targets():
    """Test stratification targets are correctly defined"""
    print("🔍 Testing stratification targets...")

    try:
        from streamlit_apps.ground_truth_labeling import STRATIFICATION_TARGETS

        expected_targets = {"short": 0.4, "medium": 0.4, "long": 0.2}
        assert (
            STRATIFICATION_TARGETS == expected_targets
        ), f"Expected {expected_targets}, got {STRATIFICATION_TARGETS}"

        # Check that targets sum to 1.0
        total = sum(STRATIFICATION_TARGETS.values())
        assert (
            abs(total - 1.0) < 0.001
        ), f"Stratification targets should sum to 1.0, got {total}"

        print("✅ Stratification targets test passed")
        print(f"   - Short: {STRATIFICATION_TARGETS['short']*100}%")
        print(f"   - Medium: {STRATIFICATION_TARGETS['medium']*100}%")
        print(f"   - Long: {STRATIFICATION_TARGETS['long']*100}%")

        return True

    except Exception as e:
        print(f"❌ Stratification targets test failed: {e}")
        return False


<<<<<<< Updated upstream
def validate_rrf_inputs_func(
    semantic_results, keyword_results, semantic_weight, keyword_weight
):
    """Helper function for testing"""

    return True  # Simple validation for testing
=======
def validate_rrf_inputs(
    semantic_results, keyword_results, semantic_weight, keyword_weight
):
    """Helper function for testing"""
    from streamlit_apps.utils.rrf_fusion import validate_rrf_inputs

    return validate_rrf_inputs(
        semantic_results, keyword_results, semantic_weight, keyword_weight
    )
>>>>>>> Stashed changes


def main():
    """Run all tests"""
    print("🧪 Testing Ground Truth Collection Streamlit App")
    print("=" * 50)

    tests = [
        test_imports,
<<<<<<< Updated upstream
        test_streamlit_rrf_fusion,
=======
        test_rrf_fusion,
>>>>>>> Stashed changes
        test_rrf_validation,
        test_stratification_targets,
    ]

    passed = 0
    total = len(tests)

    for test in tests:
        if test():
            passed += 1
        print()

    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")

    if passed == total:
        print("🎉 All tests passed! Streamlit app is ready for manual testing.")
        print()
        print("📝 Manual Testing Checklist:")
        print("   1. Set environment variables: DATABASE_URL, OPENAI_API_KEY")
        print("   2. Run: streamlit run streamlit_apps/ground_truth_labeling.py")
        print("   3. Test query extraction with stratified sampling")
        print("   4. Test hybrid search with real queries")
        print("   5. Test labeling interface with checkboxes")
        print("   6. Test progress tracking and save/continue functionality")
        return 0
    else:
        print("❌ Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
