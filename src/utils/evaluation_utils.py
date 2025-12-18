"""Utility functions for answer evaluation and benchmarking.

This module provides helper functions for formatting answers, aggregating
evaluation results, and generating comprehensive evaluation reports.
"""

import json
import csv
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from datetime import datetime


def save_answers_json(
    answers: Dict[str, str],
    output_path: str,
    question: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Save multiple answers to a JSON file.
    
    Args:
        answers: Dictionary of model_name -> answer
        output_path: Path to save JSON file
        question: Optional question that was answered
        metadata: Optional additional metadata
    """
    output_data = {
        "question": question,
        "answers": answers,
        "timestamp": datetime.now().isoformat(),
    }
    
    if metadata:
        output_data["metadata"] = metadata
    
    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)


def load_answers_json(file_path: str) -> Tuple[Dict[str, str], Optional[str]]:
    """Load answers from a JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Tuple of (answers_dict, question)
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
    
    answers = data.get("answers", {})
    question = data.get("question")
    
    return answers, question


def save_evaluation_results_csv(
    results: Dict[str, Dict[str, Any]],
    output_path: str,
    question: Optional[str] = None,
) -> None:
    """Save evaluation results to CSV format.
    
    Args:
        results: Dictionary of model_name -> evaluation_result
        output_path: Path to save CSV file
        question: Optional question that was evaluated
    """
    # Flatten results for CSV
    rows = []
    
    for model_name, result in results.items():
        row = {
            "model": model_name,
            "overall_score": result.get("overall_score", ""),
            "reasoning_summary": result.get("reasoning", "")[:100],  # First 100 chars
        }
        
        # Add category scores
        if "category_scores" in result:
            for category, score in result["category_scores"].items():
                row[f"{category}_score"] = score
        
        rows.append(row)
    
    if not rows:
        return
    
    # Get all field names
    fieldnames = list(rows[0].keys())
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def load_evaluation_results_csv(file_path: str) -> Dict[str, Dict[str, Any]]:
    """Load evaluation results from CSV format.
    
    Args:
        file_path: Path to CSV file
        
    Returns:
        Dictionary of model_name -> evaluation_result
    """
    results = {}
    
    with open(file_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            model_name = row.pop("model")
            
            # Convert numeric fields
            if "overall_score" in row:
                try:
                    row["overall_score"] = float(row["overall_score"])
                except (ValueError, TypeError):
                    pass
            
            # Extract category scores
            category_scores = {}
            keys_to_remove = []
            for key, value in row.items():
                if key.endswith("_score"):
                    try:
                        category_scores[key[:-6]] = float(value)
                        keys_to_remove.append(key)
                    except (ValueError, TypeError):
                        pass
            
            for key in keys_to_remove:
                del row[key]
            
            if category_scores:
                row["category_scores"] = category_scores
            
            results[model_name] = row
    
    return results


def aggregate_benchmark_results(
    per_question_results: Dict[str, Dict[str, Dict[str, Any]]]
) -> Dict[str, Dict[str, float]]:
    """Aggregate benchmark results across multiple questions.
    
    Args:
        per_question_results: Results from BenchmarkSuite.results
        
    Returns:
        Dictionary of model_name -> {'mean_score': float, ...}
    """
    model_scores = {}
    
    for question_id, question_results in per_question_results.items():
        for model_name, result in question_results.get("results", {}).items():
            if model_name not in model_scores:
                model_scores[model_name] = []
            
            score = result.get("overall_score", 0)
            model_scores[model_name].append(score)
    
    # Compute aggregate statistics
    aggregate = {}
    for model_name, scores in model_scores.items():
        if scores:
            aggregate[model_name] = {
                "mean_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "std_dev": _compute_std_dev(scores),
                "num_questions": len(scores),
            }
    
    return aggregate


def _compute_std_dev(values: List[float]) -> float:
    """Compute standard deviation.
    
    Args:
        values: List of numeric values
        
    Returns:
        Standard deviation
    """
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
    return variance ** 0.5


def format_evaluation_summary(
    results: Dict[str, Dict[str, Any]],
    max_length: int = 100,
) -> str:
    """Format evaluation results as a summary table.
    
    Args:
        results: Dictionary of model_name -> evaluation_result
        max_length: Maximum length of reasoning text in summary
        
    Returns:
        Formatted summary string
    """
    lines = ["Model Evaluation Summary:", "=" * 80]
    
    # Sort by score
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1].get("overall_score", 0),
        reverse=True
    )
    
    # Header
    lines.append(f"{'Model':<30} {'Score':<10} {'Assessment':<40}")
    lines.append("-" * 80)
    
    # Data rows
    for model_name, result in sorted_results:
        score = result.get("overall_score", "N/A")
        if isinstance(score, float):
            score_str = f"{score:.1f}/10"
        else:
            score_str = str(score)
        
        reasoning = result.get("reasoning", "")[:max_length]
        if len(result.get("reasoning", "")) > max_length:
            reasoning += "..."
        
        lines.append(f"{model_name:<30} {score_str:<10} {reasoning:<40}")
    
    return "\n".join(lines)


def generate_evaluation_markdown_report(
    question: str,
    results: Dict[str, Dict[str, Any]],
    title: str = "Answer Evaluation Report",
    include_full_assessment: bool = True,
) -> str:
    """Generate a comprehensive markdown report.
    
    Args:
        question: The evaluated question
        results: Dictionary of model_name -> evaluation_result
        title: Report title
        include_full_assessment: Whether to include full assessment text
        
    Returns:
        Markdown formatted report
    """
    report = []
    report.append(f"# {title}\n")
    report.append(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    report.append(f"**Question:** {question}\n\n")
    
    # Summary statistics
    scores = [r.get("overall_score", 0) for r in results.values() if isinstance(r.get("overall_score"), (int, float))]
    if scores:
        report.append("## Summary Statistics\n")
        report.append(f"- **Average Score:** {sum(scores)/len(scores):.2f}/10")
        report.append(f"- **Highest Score:** {max(scores):.2f}/10")
        report.append(f"- **Lowest Score:** {min(scores):.2f}/10")
        report.append(f"- **Models Evaluated:** {len(results)}\n")
    
    # Model rankings
    report.append("## Model Rankings\n")
    sorted_results = sorted(
        results.items(),
        key=lambda x: x[1].get("overall_score", 0),
        reverse=True
    )
    
    for i, (model_name, result) in enumerate(sorted_results, 1):
        score = result.get("overall_score", "N/A")
        if isinstance(score, float):
            score_str = f"{score:.2f}/10"
        else:
            score_str = str(score)
        
        report.append(f"{i}. **{model_name}**: {score_str}")
    
    report.append("")
    
    # Detailed assessments
    if include_full_assessment:
        report.append("## Detailed Assessments\n")
        
        for model_name, result in sorted_results:
            report.append(f"### {model_name}\n")
            
            score = result.get("overall_score", "N/A")
            if isinstance(score, float):
                report.append(f"**Score:** {score:.2f}/10\n")
            
            reasoning = result.get("reasoning", "")
            if reasoning:
                report.append(f"**Assessment:** {reasoning}\n")
            
            # Category breakdown
            if "category_scores" in result and result["category_scores"]:
                report.append("**Category Scores:**")
                for category, cat_score in sorted(
                    result["category_scores"].items(),
                    key=lambda x: x[1],
                    reverse=True
                ):
                    report.append(f"- {category.replace('_', ' ').title()}: {cat_score:.1f}/10")
                report.append("")
            
            report.append("")
    
    return "\n".join(report)


def compare_models_on_multiple_questions(
    questions: List[Dict[str, str]],
    model_answers: Dict[str, Dict[str, str]],
    evaluator,
    output_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Compare multiple models across multiple questions.
    
    Args:
        questions: List of question dictionaries with 'id' and 'question'
        model_answers: Dict of model_name -> {question_id -> answer}
        evaluator: AnswerEvaluator instance
        output_path: Optional path to save detailed results
        
    Returns:
        Comprehensive comparison results
    """
    comparison_results = {
        "timestamp": datetime.now().isoformat(),
        "num_questions": len(questions),
        "models": list(model_answers.keys()),
        "per_question_results": {},
        "model_statistics": {},
    }
    
    model_scores = {model: [] for model in model_answers.keys()}
    
    # Evaluate each question
    for question_data in questions:
        question = question_data.get("question")
        q_id = question_data.get("id", question[:50])
        
        # Collect answers for this question
        question_answers = {}
        for model_name, answers_dict in model_answers.items():
            if q_id in answers_dict:
                question_answers[model_name] = answers_dict[q_id]
        
        if question_answers:
            # Evaluate all models on this question
            results = evaluator.evaluate_multiple(question, question_answers)
            comparison_results["per_question_results"][q_id] = {
                "question": question,
                "results": results,
            }
            
            # Track scores
            for model_name, result in results.items():
                score = result.get("overall_score", 0)
                model_scores[model_name].append(score)
    
    # Compute aggregate statistics
    for model_name, scores in model_scores.items():
        if scores:
            comparison_results["model_statistics"][model_name] = {
                "mean_score": sum(scores) / len(scores),
                "min_score": min(scores),
                "max_score": max(scores),
                "std_dev": _compute_std_dev(scores),
                "num_questions": len(scores),
            }
    
    # Save if requested
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(comparison_results, f, indent=2)
    
    return comparison_results
