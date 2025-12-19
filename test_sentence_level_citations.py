#!/usr/bin/env python3
"""
Test script for the enhanced OpenRouterPaperSolver with sentence-level citations.
"""

import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.agent.writer import OpenRouterPaperSolver, test_sentence_level_citations

def main():
    """
    Main test function for sentence-level citation functionality.
    """
    print("🚀 Testing Enhanced Paper Writing Agent with Sentence-Level Citations")
    print("=" * 80)
    
    # Test 1: Key term extraction functionality
    print("\n🔬 Test 1: Key Term Extraction from Sentences")
    print("-" * 50)
    
    try:
        key_terms, citations = test_sentence_level_citations()
        print("✅ Key term extraction test completed successfully!")
        
    except Exception as e:
        print(f"❌ Key term extraction test failed: {e}")
    
    # Test 2: Full paper generation with sentence-level citations
    print("\n📝 Test 2: Full Paper Generation with Sentence-Level Citations")
    print("-" * 50)
    
    # Read the research question and findings from test files
    try:
        with open('problems/ex2.txt', 'r') as f:
            research_question = f.read().strip()
        
        with open('tests/q2.md', 'r') as f:
            scientist_findings = f.read().strip()
        
        print(f"📋 Research Question: {research_question[:100]}...")
        print(f"🔬 Scientist Findings: {len(scientist_findings)} characters")
        
        # Initialize solver
        solver = OpenRouterPaperSolver(model="anthropic/claude-3.5-sonnet")
        
        # Generate paper with sentence-level citations
        print("\n🎯 Generating paper with sentence-level citations...")
        paper, validation = solver.generate_and_validate_paper(
            research_question=research_question,
            scientist_findings=scientist_findings,
            target_word_count=3000,
            save_to_file=True,
            output_filename="sentence_level_paper_test.md",
            use_sentence_level_citations=True
        )
        
        print("✅ Paper generation completed!")
        print("📊 Final paper statistics:")
        print(f"   - Characters: {len(paper)}")
        print(f"   - Words: {len(paper.split())}")
        print(f"   - Citations found: {validation.get('citation_count', 0)}")
        print(f"   - Has references section: {validation.get('references_populated', False)}")
        print(f"   - Structure complete: {validation.get('structure_complete', False)}")
        
        # Show sample of the paper
        print("\n📖 Paper preview (first 500 characters):")
        print("-" * 50)
        print(paper[:500] + "...")
        
        if validation.get('citation_count', 0) > 0:
            print(f"✅ SUCCESS: Paper includes {validation['citation_count']} citations!")
        else:
            print("⚠️  WARNING: No citations found in generated paper")
            
        if validation.get('references_populated', False):
            print("✅ SUCCESS: References section is populated!")
        else:
            print("⚠️  WARNING: References section may not be properly populated")
        
        return True
        
    except FileNotFoundError as e:
        print(f"❌ Test files not found: {e}")
        print("ℹ️  Please ensure 'problems/ex2.txt' and 'tests/q2.md' exist")
        return False
        
    except Exception as e:
        print(f"❌ Paper generation test failed: {e}")
        return False

    # Test 3: Compare traditional vs sentence-level approaches
    print("\n⚖️  Test 3: Comparison - Traditional vs Sentence-Level Citations")
    print("-" * 50)
    
    try:
        # Generate with traditional approach
        print("📝 Generating with traditional approach...")
        paper_traditional, validation_traditional = solver.generate_and_validate_paper(
            research_question=research_question,
            scientist_findings=scientist_findings,
            target_word_count=3000,
            save_to_file=True,
            output_filename="traditional_paper_test.md",
            use_sentence_level_citations=False
        )
        
        print("📊 Comparison results:")
        print(f"   Traditional citations: {validation_traditional.get('citation_count', 0)}")
        print(f"   Sentence-level citations: {validation.get('citation_count', 0)}")
        print(f"   Traditional references populated: {validation_traditional.get('references_populated', False)}")
        print(f"   Sentence-level references populated: {validation.get('references_populated', False)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Comparison test failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    
    print("\n" + "=" * 80)
    if success:
        print("🎉 All tests completed! Check the generated paper files:")
        print("   - sentence_level_paper_test.md")
        print("   - traditional_paper_test.md")
    else:
        print("⚠️  Some tests failed. Please check the error messages above.")
    
    print("=" * 80)
