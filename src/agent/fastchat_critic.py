"""FastChat-based critic implementation using LLM-as-a-judge pipeline.

This module integrates FastChat's evaluation framework to provide structured
criticism of generated answers using various LLM judge models.
"""

import json
import os
import re
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CriticScore:
    """Structured evaluation score from a critic judge."""
    score: float  # 1-10 scale
    max_score: float = 10.0
    reasoning: str = ""
    strengths: List[str] = None
    weaknesses: List[str] = None
    suggestions: List[str] = None
    
    def __post_init__(self):
        """Initialize default lists."""
        if self.strengths is None:
            self.strengths = []
        if self.weaknesses is None:
            self.weaknesses = []
        if self.suggestions is None:
            self.suggestions = []
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert score to dictionary."""
        return {
            "score": self.score,
            "max_score": self.max_score,
            "percentage": (self.score / self.max_score) * 100,
            "reasoning": self.reasoning,
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "suggestions": self.suggestions,
        }


@dataclass
class EvaluationResult:
    """Complete evaluation result from the critic pipeline."""
    answer: str
    question: str
    judge_model: str
    scores: Dict[str, CriticScore]  # category -> score
    overall_score: float
    overall_reasoning: str
    timestamp: str = None
    
    def __post_init__(self):
        """Set default timestamp."""
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "question": self.question,
            "answer": self.answer,
            "judge_model": self.judge_model,
            "timestamp": self.timestamp,
            "scores": {k: v.to_dict() for k, v in self.scores.items()},
            "overall_score": self.overall_score,
            "overall_reasoning": self.overall_reasoning,
        }


class FastChatCritic:
    """Uses FastChat's LLM judge pipeline to evaluate answers.
    
    This critic integrates with the fastchat.llm_judge module to provide
    structured evaluation of answers using various LLM judge models.
    """
    
    # Evaluation categories following MT-Bench style
    EVALUATION_CATEGORIES = {
        "scientific_accuracy": "Are claims supported by evidence? Are references correct?",
        "completeness": "Does the answer address all aspects of the question?",
        "reasoning_quality": "Is the logical reasoning sound and well-explained?",
        "data_analysis": "Are data analyses appropriate and results interpreted correctly?",
        "literature_support": "Are relevant papers cited with proper citations (PMID)?",
        "practical_feasibility": "Are proposed approaches realistic and resource-conscious?",
        "clarity": "Is the answer clear, well-organized, and easy to follow?",
    }
    
    def __init__(
        self,
        judge_model: str = "gpt-4",
        api_provider: str = "openai",
        api_key: Optional[str] = None,
        temperature: float = 0.3,
    ):
        """Initialize the FastChat critic.
        
        Args:
            judge_model: Model to use as judge (default: gpt-4)
            api_provider: API provider (openai, anthropic, openrouter)
            api_key: API key for the judge model
            temperature: Sampling temperature for consistent evaluation (default: 0.3)
        """
        self.judge_model = judge_model
        self.api_provider = api_provider
        self.api_key = api_key or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        self.temperature = temperature
        
        # Initialize the appropriate client
        self.client = self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the LLM client for the judge."""
        # Lazy import to avoid hard dependency
        try:
            if self.api_provider == "openai":
                import openai
                return openai.OpenAI(api_key=self.api_key)
            elif self.api_provider == "anthropic":
                import anthropic
                return anthropic.Anthropic(api_key=self.api_key)
            elif self.api_provider == "openrouter":
                # OpenRouter compatible with OpenAI format
                import openai
                return openai.OpenAI(
                    api_key=self.api_key,
                    base_url="https://openrouter.ai/api/v1"
                )
        except ImportError as e:
            raise ImportError(f"Required client library not found: {e}")
        
        return None
    
    def _build_single_evaluation_prompt(
        self,
        question: str,
        answer: str,
        category: str,
        category_desc: str,
    ) -> str:
        """Build an evaluation prompt for a single category.
        
        Args:
            question: The original question
            answer: The answer to evaluate
            category: Category name
            category_desc: Category description
            
        Returns:
            Evaluation prompt string
        """
        return f"""You are evaluating a scientific answer for a biomedical research question.

EVALUATION CATEGORY: {category.replace('_', ' ').title()}
CRITERIA: {category_desc}

QUESTION:
{question}

ANSWER TO EVALUATE:
{answer}

Provide an evaluation with:
1. Score (1-10 scale)
2. Brief reasoning (2-3 sentences)
3. 2-3 key strengths
4. 2-3 key weaknesses
5. 2-3 specific suggestions for improvement

Format your response as JSON with keys: "score", "reasoning", "strengths", "weaknesses", "suggestions"
"""
    
    def _build_overall_evaluation_prompt(
        self,
        question: str,
        answer: str,
        category_scores: Dict[str, float],
    ) -> str:
        """Build an overall evaluation prompt.
        
        Args:
            question: The original question
            answer: The answer to evaluate
            category_scores: Dictionary of category -> score
            
        Returns:
            Overall evaluation prompt string
        """
        scores_summary = "\n".join(
            f"  - {cat.replace('_', ' ').title()}: {score:.1f}/10"
            for cat, score in category_scores.items()
        )
        
        return f"""Based on the detailed evaluations below, provide an overall assessment of this scientific answer.

QUESTION:
{question}

ANSWER:
{answer}

CATEGORY SCORES:
{scores_summary}

Provide an overall evaluation with:
1. Overall Score (1-10 scale, weighted average or adjusted based on critical categories)
2. Overall reasoning (3-4 sentences summarizing key findings)
3. Critical issues (if any)
4. Major strengths (if any)

Format your response as JSON with keys: "overall_score", "overall_reasoning", "critical_issues", "major_strengths"
"""
    
    def _call_judge_model(self, prompt: str) -> str:
        """Call the judge model with a prompt.
        
        Args:
            prompt: Prompt text for the judge
            
        Returns:
            Judge response text
        """
        if self.client is None:
            raise RuntimeError("No API client initialized")
        
        try:
            if self.api_provider == "anthropic":
                response = self.client.messages.create(
                    model=self.judge_model,
                    max_tokens=1500,
                    temperature=self.temperature,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text
            else:  # OpenAI and OpenRouter use same format
                response = self.client.chat.completions.create(
                    model=self.judge_model,
                    temperature=self.temperature,
                    max_tokens=1500,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"Judge model call failed: {e}")
    
    def _extract_json_from_response(self, response: str) -> Dict[str, Any]:
        """Extract JSON from judge response.
        
        Args:
            response: Judge response text
            
        Returns:
            Parsed JSON dictionary
        """
        # Try to find JSON in the response
        json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response, re.DOTALL)
        
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback: try to parse the entire response
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            # If JSON extraction fails, create a structured response
            return {
                "reasoning": response,
                "score": 5.0,  # Neutral score if parsing fails
            }
    
    def evaluate_single_category(
        self,
        question: str,
        answer: str,
        category: str,
    ) -> CriticScore:
        """Evaluate answer for a single category.
        
        Args:
            question: The original question
            answer: The answer to evaluate
            category: Category to evaluate (from EVALUATION_CATEGORIES)
            
        Returns:
            CriticScore with evaluation results
        """
        if category not in self.EVALUATION_CATEGORIES:
            raise ValueError(f"Unknown category: {category}")
        
        category_desc = self.EVALUATION_CATEGORIES[category]
        prompt = self._build_single_evaluation_prompt(question, answer, category, category_desc)
        
        # Get judge response
        response = self._call_judge_model(prompt)
        eval_data = self._extract_json_from_response(response)
        
        # Parse response
        score = float(eval_data.get("score", 5.0))
        reasoning = eval_data.get("reasoning", "")
        strengths = eval_data.get("strengths", [])
        weaknesses = eval_data.get("weaknesses", [])
        suggestions = eval_data.get("suggestions", [])
        
        # Ensure lists
        if not isinstance(strengths, list):
            strengths = [strengths] if strengths else []
        if not isinstance(weaknesses, list):
            weaknesses = [weaknesses] if weaknesses else []
        if not isinstance(suggestions, list):
            suggestions = [suggestions] if suggestions else []
        
        return CriticScore(
            score=score,
            reasoning=reasoning,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
        )
    
    def evaluate(
        self,
        question: str,
        answer: str,
        categories: Optional[List[str]] = None,
        include_all_categories: bool = True,
    ) -> EvaluationResult:
        """Evaluate an answer using the FastChat critic pipeline.
        
        Args:
            question: The original question
            answer: The answer to evaluate
            categories: Specific categories to evaluate (if None, use specified or all)
            include_all_categories: Whether to evaluate all categories (default: True)
            
        Returns:
            EvaluationResult with comprehensive evaluation
        """
        if categories is None:
            categories = list(self.EVALUATION_CATEGORIES.keys()) if include_all_categories else ["scientific_accuracy"]
        
        # Evaluate each category
        scores = {}
        for category in categories:
            if category in self.EVALUATION_CATEGORIES:
                scores[category] = self.evaluate_single_category(question, answer, category)
        
        # Calculate overall score (average of all categories)
        if scores:
            overall_score = sum(s.score for s in scores.values()) / len(scores)
        else:
            overall_score = 5.0
        
        # Get overall reasoning
        category_scores = {cat: score.score for cat, score in scores.items()}
        overall_prompt = self._build_overall_evaluation_prompt(question, answer, category_scores)
        overall_response = self._call_judge_model(overall_prompt)
        overall_data = self._extract_json_from_response(overall_response)
        
        overall_reasoning = overall_data.get("overall_reasoning", "")
        if not overall_reasoning:
            # Create summary if reasoning not available
            strengths_all = []
            weaknesses_all = []
            for score in scores.values():
                strengths_all.extend(score.strengths)
                weaknesses_all.extend(score.weaknesses)
            
            overall_reasoning = f"Strengths: {'; '.join(strengths_all[:3])}. " \
                              f"Weaknesses: {'; '.join(weaknesses_all[:3])}."
        
        return EvaluationResult(
            question=question,
            answer=answer,
            judge_model=self.judge_model,
            scores=scores,
            overall_score=overall_score,
            overall_reasoning=overall_reasoning,
        )
    
    def evaluate_multiple(
        self,
        question: str,
        answers: Dict[str, str],
        categories: Optional[List[str]] = None,
    ) -> Dict[str, EvaluationResult]:
        """Evaluate multiple answers for the same question.
        
        Args:
            question: The original question
            answers: Dictionary of model_name -> answer
            categories: Specific categories to evaluate
            
        Returns:
            Dictionary of model_name -> EvaluationResult
        """
        results = {}
        for model_name, answer in answers.items():
            results[model_name] = self.evaluate(question, answer, categories)
        
        return results
    
    def compare_answers(
        self,
        question: str,
        answers: Dict[str, str],
        categories: Optional[List[str]] = None,
    ) -> str:
        """Generate a comparative analysis of multiple answers.
        
        Args:
            question: The original question
            answers: Dictionary of model_name -> answer
            categories: Specific categories to evaluate
            
        Returns:
            Comparison report as string
        """
        results = self.evaluate_multiple(question, answers, categories)
        
        # Build comparison report
        report = f"# Answer Comparison Report\n\n"
        report += f"**Question:** {question}\n\n"
        report += f"**Evaluated Models:** {', '.join(results.keys())}\n\n"
        
        # Overall scores comparison
        report += "## Overall Scores\n\n"
        for model_name in sorted(results.keys()):
            result = results[model_name]
            report += f"- **{model_name}**: {result.overall_score:.1f}/10\n"
        
        report += "\n## Detailed Evaluations\n\n"
        
        # Detailed results per model
        for model_name in sorted(results.keys()):
            result = results[model_name]
            report += f"### {model_name}\n\n"
            report += f"**Overall Score:** {result.overall_score:.1f}/10\n\n"
            report += f"**Overall Assessment:** {result.overall_reasoning}\n\n"
            
            # Category scores
            if result.scores:
                report += "**Category Scores:**\n"
                for category in sorted(result.scores.keys()):
                    score = result.scores[category]
                    report += f"  - {category.replace('_', ' ').title()}: {score.score:.1f}/10\n"
                report += "\n"
            
            report += "\n"
        
        return report
