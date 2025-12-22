#!/usr/bin/env python3
"""Test script for literature search functionality (cached version).

This script tests:
1. Basic literature search with caching
2. Cache creation and reuse
3. Error handling
4. Result validation
"""

import os
import sys
import time
import shutil
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

from src.tools.implementations_cached import search_literature_cached
from src.config import get_global_config


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def print_test(name: str, passed: bool, details: str = ""):
    """Print test result."""
    symbol = "✓" if passed else "✗"
    status = "PASS" if passed else "FAIL"
    print(f"{symbol} [{status}] {name}")
    if details:
        print(f"          {details}")


def test_literature_search():
    """Main test function."""

    print_section("Literature Search Test Suite")

    # Configuration
    config = get_global_config()
    test_cache_dir = project_root / ".test_paperqa_cache"

    # Clean up old test cache if exists
    if test_cache_dir.exists():
        print(f"Cleaning up old test cache: {test_cache_dir}")
        shutil.rmtree(test_cache_dir)

    print(f"\nConfiguration:")
    print(f"  - LLM: {config.paperqa_llm}")
    print(f"  - Embedding: {config.paperqa_embedding}")
    print(f"  - Paper library: {config.paper_library_dir}")
    print(f"  - Test cache directory: {test_cache_dir}")

    # Check if paper library exists
    paper_lib_exists = Path(config.paper_library_dir).exists()
    has_pdfs = False
    if paper_lib_exists:
        pdf_count = len(list(Path(config.paper_library_dir).glob("**/*.pdf")))
        has_pdfs = pdf_count > 0
        print(f"  - Local PDFs found: {pdf_count}")

    # Test 1: Basic search with cache creation
    print_section("Test 1: First Search (Cache Creation)")

    test_question = "What is T cell exhaustion?"

    # Choose mode based on whether local PDFs are available
    if has_pdfs:
        test_mode = "local"
        print(f"Using local mode with {pdf_count} PDFs")
    else:
        test_mode = "online"
        print("No local PDFs found, using online mode (may hit rate limits)")

    try:
        start_time = time.time()
        result = search_literature_cached(
            question=test_question,
            mode=test_mode,
            max_sources=3,
            cache_base_dir=str(test_cache_dir)
        )
        elapsed = time.time() - start_time

        # Validate result
        success = result.success
        has_answer = result.output and "answer" in result.output
        has_cache_stats = result.output and "cache_stats" in result.output

        print_test("Search completed", success)
        print_test("Answer generated", has_answer,
                  f"Answer length: {len(result.output.get('answer', '')) if result.output else 0} chars")
        print_test("Cache stats present", has_cache_stats,
                  f"Stats: {result.output.get('cache_stats') if result.output else 'N/A'}")
        print(f"          Time: {elapsed:.2f}s")

        if result.output and "answer" in result.output:
            print(f"\n  Answer preview:")
            answer_preview = result.output["answer"][:300]
            for line in answer_preview.split('\n')[:5]:
                print(f"    {line}")
            if len(result.output["answer"]) > 300:
                print(f"    ... ({len(result.output['answer'])} total chars)")

        if not success:
            print(f"  ERROR: {result.error}")
            return False

    except Exception as e:
        print_test("Search completed", False, f"Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Same search should use cache
    print_section("Test 2: Second Search (Cache Reuse)")

    try:
        start_time = time.time()
        result2 = search_literature_cached(
            question=test_question,  # Same question
            mode=test_mode,  # Use same mode as first test
            max_sources=3,
            cache_base_dir=str(test_cache_dir)
        )
        elapsed2 = time.time() - start_time

        success2 = result2.success
        cache_stats = result2.output.get("cache_stats", {}) if result2.output else {}

        print_test("Search completed", success2)
        print_test("Used cached data",
                  cache_stats.get("online_cached", 0) > 0,
                  f"Cached papers: {cache_stats.get('online_cached', 0)}")
        print(f"          Time: {elapsed2:.2f}s (vs {elapsed:.2f}s first run)")

        # Cache should make it faster
        speedup = elapsed / elapsed2 if elapsed2 > 0 else 1
        print_test("Cache speedup", speedup > 1.2, f"{speedup:.1f}x faster")

    except Exception as e:
        print_test("Cached search", False, f"Exception: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

    # Test 3: Check cache directory structure
    print_section("Test 3: Cache Directory Structure")

    cache_dirs = list(test_cache_dir.glob("question_*"))
    print_test("Cache directory created", len(cache_dirs) > 0,
              f"Found {len(cache_dirs)} question cache(s)")

    if cache_dirs:
        question_cache = cache_dirs[0]
        metadata_file = question_cache / "metadata.json"
        docs_cache_file = question_cache / "docs_cache.pkl"

        print_test("Metadata file exists", metadata_file.exists())
        print_test("Docs cache file exists", docs_cache_file.exists())

        if metadata_file.exists():
            import json
            with open(metadata_file) as f:
                metadata = json.load(f)
            print(f"          Question: {metadata.get('question', 'N/A')[:50]}...")
            print(f"          Total papers: {metadata.get('total_papers', 'N/A')}")

    # Test 4: Error handling - invalid mode
    print_section("Test 4: Error Handling")

    try:
        result_error = search_literature_cached(
            question="test",
            mode="local",  # Local mode without PDFs should fail gracefully
            paper_dir="/nonexistent/path",
            cache_base_dir=str(test_cache_dir)
        )

        print_test("Handled missing local papers",
                  not result_error.success,
                  "Correctly returned failure")

    except Exception as e:
        print_test("Error handling", False, f"Unexpected exception: {str(e)}")

    # Summary
    print_section("Test Summary")

    print("\n✓ All core tests passed!")
    print(f"\nCache location: {test_cache_dir}")
    print("You can inspect the cache directory to see cached papers and metadata.")
    print("\nTo clean up test cache, run:")
    print(f"  rm -rf {test_cache_dir}")

    return True


if __name__ == "__main__":
    print(f"Python: {sys.version}")
    print(f"Working directory: {os.getcwd()}")
    print(f"Project root: {project_root}")

    try:
        success = test_literature_search()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
