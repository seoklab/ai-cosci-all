#!/usr/bin/env python
"""
Example script demonstrating FastChat critic and evaluation features.

This script shows various ways to use the new evaluation functionality
added to ai-cosci.
"""

import json
import sys
from pathlib import Path

# Example 1: Basic Single Answer Evaluation
def example_single_evaluation():
    """Evaluate a single answer using FastChat critic."""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Single Answer Evaluation")
    print("=" * 70 + "\n")
    
    from src.evaluation.evaluator import AnswerEvaluator
    
    # Create evaluator
    evaluator = AnswerEvaluator()
    
    # Example question and answer
    question = "What is the role of p53 in cancer?"
    answer = """
    p53, also known as the tumor suppressor gene, plays a critical role in cancer prevention
    and response to DNA damage. When cells are damaged, p53 activates genes that stop cell 
    division and trigger DNA repair mechanisms. If damage cannot be repaired, p53 can 
    initiate apoptosis (programmed cell death), preventing cancerous cells from proliferating.
    
    In approximately 50% of human cancers, the p53 gene is mutated, leading to loss of 
    its tumor-suppressing function. This allows damaged cells to continue dividing and 
    accumulating additional mutations, accelerating cancer development. Understanding p53 
    mutations has led to new therapeutic strategies targeting this pathway.
    """
    
    # Evaluate the answer
    result = evaluator.evaluate_answer(
        question=question,
        answer=answer,
        model_name="example_model",
        categories=None  # Use all categories
    )
    
    # Print results
    print(f"Question: {question}\n")
    print(f"Overall Score: {result['overall_score']:.1f}/10")
    print(f"\nAssessment:\n{result['reasoning']}\n")
    
    if "category_scores" in result:
        print("Category Breakdown:")
        for category, score in sorted(
            result["category_scores"].items(),
            key=lambda x: x[1],
            reverse=True
        ):
            print(f"  - {category.replace('_', ' ').title()}: {score:.1f}/10")


# Example 2: Comparing Multiple Model Answers
def example_model_comparison():
    """Compare answers from multiple models."""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Comparing Multiple Model Answers")
    print("=" * 70 + "\n")
    
    from src.evaluation.evaluator import AnswerEvaluator
    
    evaluator = AnswerEvaluator()
    
    question = "Explain the mechanism of CRISPR-Cas9 gene editing."
    
    # Hypothetical answers from different models
    answers = {
        "Model_A": """
        CRISPR-Cas9 is a gene-editing technology derived from bacterial immune systems.
        The guide RNA directs the Cas9 enzyme to a specific DNA sequence. Cas9 cuts both
        strands of DNA at the target location. The cell's natural repair mechanisms then
        fix the break, allowing insertion of new genetic material or disruption of genes.
        """,
        
        "Model_B": """
        CRISPR-Cas9 works by using a guide RNA (gRNA) that matches the target DNA sequence.
        The Cas9 protein unwinds the DNA and uses the guide to find the precise location.
        Upon finding the match, Cas9 creates a double-strand break (DSB). The cell repairs
        this break through either non-homologous end joining (NHEJ), which disrupts genes,
        or homology-directed repair (HDR), which allows precise edits. This flexibility
        makes CRISPR-Cas9 powerful for both therapeutic and research applications.
        """,
        
        "Model_C": """
        CRISPR-Cas9 is a revolutionary gene-editing tool. It uses guide RNAs and the Cas9
        enzyme to cut DNA at specific locations, enabling precise genetic modifications.
        """,
    }
    
    # Evaluate all models
    results = evaluator.evaluate_multiple(question, answers)
    
    # Generate and print comparison report
    comparison_metrics = evaluator.compute_comparison_metrics(question, results)
    report = evaluator.generate_report(question, results, comparison_metrics)
    
    print(report)


# Example 3: Benchmark Suite
def example_benchmark_suite():
    """Evaluate multiple models on multiple questions."""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: Benchmark Suite for Multiple Questions")
    print("=" * 70 + "\n")
    
    from src.evaluation.evaluator import BenchmarkSuite, AnswerEvaluator
    
    # Define benchmark questions
    questions = [
        {
            "id": "q1",
            "question": "What is a gene signature?"
        },
        {
            "id": "q2",
            "question": "Explain drug repositioning in computational biology."
        },
        {
            "id": "q3",
            "question": "What are biomarkers and their role in precision medicine?"
        },
    ]
    
    # Model answers (hypothetical)
    model_answers = {
        "Model_A": {
            "q1": "A gene signature is a set of genes whose expression pattern...",
            "q2": "Drug repositioning involves finding new uses for existing drugs...",
            "q3": "Biomarkers are measurable indicators of biological conditions...",
        },
        "Model_B": {
            "q1": "Gene signatures are combinations of genes used in classification...",
            "q2": "Computational drug repositioning predicts new indications...",
            "q3": "Biomarkers help predict treatment response and prognosis...",
        },
    }
    
    # Create benchmark
    evaluator = AnswerEvaluator()
    suite = BenchmarkSuite(evaluator, questions)
    
    # Run benchmark
    print("Running benchmark across 3 questions and 2 models...")
    print("(Note: This would call the evaluation API for each answer)\n")
    
    # In practice, you would call:
    # results = suite.benchmark(model_answers)
    # print(f"Overall winner: {results['overall_winner']}")
    # print(f"Statistics: {results['aggregate_statistics']}")


# Example 4: Using Evaluation Utilities
def example_evaluation_utilities():
    """Demonstrate evaluation utility functions."""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Evaluation Utility Functions")
    print("=" * 70 + "\n")
    
    from src.utils.evaluation_utils import (
        save_answers_json,
        generate_evaluation_markdown_report,
    )
    
    # Example answers to save
    answers = {
        "model_a": "Answer from model A...",
        "model_b": "Answer from model B...",
    }
    
    # Save to JSON
    output_file = "/tmp/example_answers.json"
    save_answers_json(
        answers,
        output_file,
        question="Example question",
        metadata={"timestamp": "2024-01-01", "version": "1.0"}
    )
    print(f"✓ Saved answers to {output_file}")
    
    # Example evaluation results
    example_results = {
        "model_a": {
            "overall_score": 8.5,
            "reasoning": "Good answer with some minor gaps",
            "category_scores": {
                "scientific_accuracy": 8.0,
                "completeness": 8.5,
                "clarity": 9.0,
            }
        },
        "model_b": {
            "overall_score": 7.5,
            "reasoning": "Reasonable but less comprehensive",
            "category_scores": {
                "scientific_accuracy": 7.5,
                "completeness": 7.0,
                "clarity": 8.0,
            }
        }
    }
    
    # Generate markdown report
    report = generate_evaluation_markdown_report(
        "Example Question",
        example_results,
        include_full_assessment=True
    )
    
    print("\n" + report)
    
    # Save report
    report_file = "/tmp/example_report.md"
    with open(report_file, 'w') as f:
        f.write(report)
    print(f"\n✓ Saved report to {report_file}")


# Example 5: Agent Integration
def example_agent_integration():
    """Show how to use evaluation with the agent."""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Integration with BioinformaticsAgent")
    print("=" * 70 + "\n")
    
    print("""
    To evaluate answers generated by the agent:
    
    from src.agent.agent import BioinformaticsAgent
    
    # Create agent
    agent = BioinformaticsAgent()
    
    # Run with FastChat critic evaluation
    question = "What is TP53?"
    answer, evaluation = agent.run_with_fastchat_critic(
        question,
        judge_model="gpt-4",
        judge_api_provider="openai"
    )
    
    # Print results
    if evaluation:
        print(f"Score: {evaluation.overall_score:.1f}/10")
        print(f"Assessment: {evaluation.overall_reasoning}")
        
        # Print category scores
        for category, score in evaluation.scores.items():
            print(f"  {category}: {score.score:.1f}/10")
    """)


# Example 6: CLI Usage
def example_cli_usage():
    """Show CLI command examples."""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: Command-Line Interface Usage")
    print("=" * 70 + "\n")
    
    examples = [
        ("Single answer evaluation", 
         "python -m src.cli --question 'What is p53?' --evaluate"),
        
        ("With specific judge model",
         "python -m src.cli --question '...' --evaluate --judge-model gpt-4"),
        
        ("Using Claude as judge",
         "python -m src.cli --question '...' --evaluate --judge-api-provider anthropic --judge-model claude-3-opus"),
        
        ("Specific evaluation categories",
         "python -m src.cli --question '...' --evaluate --eval-categories scientific_accuracy literature_support"),
        
        ("Compare multiple models",
         "python -m src.cli --question 'Your question' --compare answers.json --output report.md"),
        
        ("Verbose output",
         "python -m src.cli --question '...' --evaluate --verbose"),
    ]
    
    for title, command in examples:
        print(f"{title}:")
        print(f"  {command}\n")


def main():
    """Run all examples."""
    try:
        # Run examples that don't require API calls
        example_single_evaluation()
        example_model_comparison()
        example_benchmark_suite()
        example_evaluation_utilities()
        example_agent_integration()
        example_cli_usage()
        
        print("\n" + "=" * 70)
        print("Examples completed!")
        print("=" * 70)
        print("\nFor full documentation, see: docs/FASTCHAT_EVALUATION.md")
        print("For quick reference, see: docs/FASTCHAT_EVALUATION_QUICK_REF.md")
        
    except ImportError as e:
        print(f"Error: {e}")
        print("Make sure you're running from the project root directory.")
        sys.exit(1)


if __name__ == "__main__":
    main()
