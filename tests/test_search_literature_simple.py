#!/usr/bin/env python3
"""Simple standalone test for search_literature function.

This test focuses solely on the literature search functionality to verify:
1. OpenRouter API key is properly configured
2. PaperQA can connect and make requests
3. Literature search returns valid results
4. Cache mechanism works correctly

Run with: python tests/test_search_literature_simple.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables FIRST (before any imports that need API keys)
from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("SEARCH_LITERATURE STANDALONE TEST")
print("=" * 70)

# Check environment setup
print("\n[1] Environment Check")
print("-" * 70)

openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
openrouter_key = os.getenv("OPENROUTER_KEY")

if openrouter_api_key:
    print(f"✓ OPENROUTER_API_KEY found: {openrouter_api_key[:20]}...")
elif openrouter_key:
    print(f"✓ OPENROUTER_KEY found: {openrouter_key[:20]}...")
else:
    print("✗ ERROR: Neither OPENROUTER_API_KEY nor OPENROUTER_KEY found!")
    print("  Please set OPENROUTER_API_KEY in your .env file")
    sys.exit(1)

# Import after env check
from src.tools.implementations import search_literature
from src.config import get_global_config

# Get configuration
config = get_global_config()

print(f"\n[2] Configuration")
print("-" * 70)
print(f"PaperQA LLM Model: {config.paperqa_llm}")
print(f"Embedding Model: {config.paperqa_embedding}")
print(f"Max Sources: {config.paperqa_max_sources}")
print(f"Paper Library Dir: {config.paper_library_dir}")

# Check for local PDFs
paper_lib_path = Path(config.paper_library_dir)
local_pdfs = []
if paper_lib_path.exists():
    local_pdfs = list(paper_lib_path.glob("**/*.pdf"))
    print(f"Local PDFs found: {len(local_pdfs)}")
else:
    print(f"Paper library directory does not exist (will use online only)")

# Set up test cache directory
test_cache_dir = project_root / ".test_paperqa_cache"
test_cache_dir.mkdir(parents=True, exist_ok=True)
print(f"Test cache directory: {test_cache_dir}")

# Test question
test_question = "Are there research that connect inhibitor or antagonists; Nr4a2 Nurr1 Slc17a6 VGLUT2 Spry1 Spry2 with T cell exhaustion reversal?"
# test_question = "inhibitors antagonists Nr4a2 Nurr1 Slc17a6 VGLUT2 Spry1 Spry2 reversal T cell exhaustion"
print(f"\n[3] Running Literature Search")
print("-" * 70)
print(f"Question: {test_question}")

# Determine search mode
if len(local_pdfs) > 0:
    search_mode = "auto"  # Will use local + online if needed
    print(f"Mode: auto (local-first with {len(local_pdfs)} local PDFs)")
else:
    search_mode = "online"  # Online only
    print(f"Mode: online (no local PDFs available)")

print("\nSearching... (this may take 30-60 seconds)")
print("-" * 70)

import time
start_time = time.time()

try:
    result = search_literature(
        question=test_question,
        mode=search_mode,
        max_sources=5,
        cache_base_dir=str(test_cache_dir)
    )

    elapsed = time.time() - start_time

    print(f"\n[4] Results (completed in {elapsed:.1f}s)")
    print("-" * 70)

    if result.success:
        print("✓ Search completed successfully")

        # Extract output
        output = result.output
        if output:
            # Show answer
            answer = output.get("answer", "")
            if answer:
                print(f"\n--- Answer ---")
                print(f"Length: {len(answer)} characters")
                print(f"\nPreview (first 500 chars):")
                print(answer[:500])
                if len(answer) > 500:
                    print(f"... ({len(answer) - 500} more characters)")

            # Show contexts
            contexts = output.get("contexts", [])
            print(f"\n--- Contexts Retrieved ---")
            print(f"Number of contexts: {len(contexts)}")
            if contexts and len(contexts) > 0:
                print(f"\nFirst context preview:")
                first_context = str(contexts[0])
                print(first_context[:300])
                if len(first_context) > 300:
                    print(f"... ({len(first_context) - 300} more characters)")

            # Show references
            references = output.get("references", [])
            print(f"\n--- References ---")
            print(f"Number of references: {len(references)}")
            if references:
                for i, ref in enumerate(references[:3], 1):
                    print(f"{i}. {ref}")
                if len(references) > 3:
                    print(f"... and {len(references) - 3} more")

            # Show cache stats
            cache_stats = output.get("cache_stats", {})
            if cache_stats:
                print(f"\n--- Cache Statistics ---")
                for key, value in cache_stats.items():
                    print(f"{key}: {value}")

            # Show cache directory
            cache_dir = output.get("cache_dir", "")
            if cache_dir:
                print(f"\n--- Cache Location ---")
                print(f"Cache directory: {cache_dir}")
                cache_path = Path(cache_dir)
                if cache_path.exists():
                    pdf_files = list(cache_path.glob("**/*.pdf"))
                    print(f"PDFs in cache: {len(pdf_files)}")
        else:
            print("⚠ Search succeeded but no output data returned")
    else:
        print(f"✗ Search failed")
        if result.error:
            print(f"\nError message:")
            print(result.error)

    print("\n" + "=" * 70)
    print("TEST COMPLETE")
    print("=" * 70)

    if result.success:
        print("\n✓ Literature search is working correctly!")
        print(f"\nTo inspect cached papers and data:")
        print(f"  ls -lah {test_cache_dir}/question_*/")
        sys.exit(0)
    else:
        print("\n✗ Literature search encountered errors")
        sys.exit(1)

except KeyboardInterrupt:
    print("\n\n✗ Test interrupted by user")
    sys.exit(1)

except Exception as e:
    elapsed = time.time() - start_time
    print(f"\n✗ ERROR after {elapsed:.1f}s")
    print("-" * 70)
    print(f"Exception: {type(e).__name__}")
    print(f"Message: {str(e)}")
    print("\nFull traceback:")
    import traceback
    traceback.print_exc()
    sys.exit(1)
