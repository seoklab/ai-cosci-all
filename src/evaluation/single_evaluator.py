"""
Single answer evaluation system for AI-generated answers.
Based on FastChat's single-v1 judging approach, adapted for biomedical answers.
"""

import os
import re
from typing import Optional
from dataclasses import dataclass

import requests
from dotenv import load_dotenv

# Load .env file to get OPENROUTER_API_KEY
load_dotenv()


@dataclass
class SingleEvaluationResult:
    """Result of a single answer evaluation."""
    score: float  # 1-10 scale
    explanation: str
    raw_judgment: str = ""


class SingleAnswerJudge:
    """OpenRouter-based judge for single answer evaluation."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "anthropic/claude-3.5-sonnet"):
        """Initialize the judge with OpenRouter API.
        
        Args:
            api_key: OpenRouter API key (defaults to OPENROUTER_API_KEY env var)
            model: Model to use for judging (default: Claude 3.5 Sonnet)
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not found in environment")
        
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/coscientist",
            "X-Title": "CoScientist Evaluator"
        }
    
    def create_biomedical_evaluation_prompt(self, question: str, answer: str) -> str:
        """Create a biomedical-focused evaluation prompt.
        
        Args:
            question: The original research question
            answer: The answer to evaluate
            
        Returns:
            Formatted prompt for the judge
        """
        return f"""Please act as an expert biomedical researcher and evaluate the quality of an AI-generated response to a scientific question.

Your evaluation should consider:

1. **Scientific Accuracy** (30%): Correctness of facts, mechanisms, and interpretations
2. **Evidence Quality** (20%): Proper citations (PMID format), use of peer-reviewed sources
3. **Methodological Rigor** (15%): Appropriate analysis methods, statistical approaches
4. **Completeness** (15%): Thoroughness in addressing all aspects of the question
5. **Clarity** (10%): Clear explanation suitable for scientific audience
6. **Critical Thinking** (10%): Acknowledgment of limitations, uncertainties, alternative hypotheses

**Research Question:**
{question}

**Answer to Evaluate:**
{answer}

**Instructions:**
1. Provide a detailed evaluation considering all criteria above
2. Identify specific strengths and weaknesses
3. Consider what additional information or analysis would improve the answer
4. Rate the overall quality on a scale of 1-10, where:
   - 1-3: Poor (major errors, missing critical information, unsupported claims)
   - 4-5: Below Average (some errors, incomplete analysis, weak evidence)
   - 6-7: Good (mostly accurate, reasonable completeness, some evidence)
   - 8-9: Excellent (accurate, comprehensive, well-supported, acknowledges limitations)
   - 10: Outstanding (exceptional accuracy, depth, rigor, and scholarly presentation)

5. Output your final rating in the format: [[rating]], for example: [[8]]

Begin your evaluation:"""

    def evaluate(self, question: str, answer: str) -> SingleEvaluationResult:
        """Evaluate a single answer.
        
        Args:
            question: The original research question
            answer: The answer to evaluate
            
        Returns:
            SingleEvaluationResult with score and explanation
        """
        prompt = self.create_biomedical_evaluation_prompt(question, answer)
        
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.2,  # Low temperature for consistent evaluation
                    "max_tokens": 2048
                },
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            judgment_text = result["choices"][0]["message"]["content"]
            
            # Extract the score
            score = self._extract_score(judgment_text)
            
            return SingleEvaluationResult(
                score=score,
                explanation=judgment_text,
                raw_judgment=judgment_text
            )
            
        except Exception as e:
            return SingleEvaluationResult(
                score=0.0,
                explanation=f"Error during evaluation: {str(e)}",
                raw_judgment=str(e)
            )
    
    def _extract_score(self, judgment_text: str) -> float:
        """Extract the numerical score from judgment text.
        
        Args:
            judgment_text: Raw judgment from the model
            
        Returns:
            Score as float (1.0-10.0), or 0.0 if extraction fails
        """
        # Look for [[rating]] pattern
        patterns = [
            r'\[\[(\d+\.?\d*)\]\]',  # [[8]] or [[7.5]]
            r'Rating:\s*\[\[(\d+\.?\d*)\]\]',  # Rating: [[8]]
            r'Final rating:\s*(\d+\.?\d*)',  # Final rating: 8
            r'Score:\s*(\d+\.?\d*)\s*/\s*10',  # Score: 8/10
        ]
        
        for pattern in patterns:
            match = re.search(pattern, judgment_text, re.IGNORECASE)
            if match:
                try:
                    score = float(match.group(1))
                    # Ensure score is in valid range
                    return max(1.0, min(10.0, score))
                except (ValueError, IndexError):
                    continue
        
        # Fallback: look for any number between 1-10 near "rating" or "score"
        rating_context = re.search(
            r'(?:rating|score).*?(\d+\.?\d*)',
            judgment_text,
            re.IGNORECASE | re.DOTALL
        )
        if rating_context:
            try:
                score = float(rating_context.group(1))
                if 1.0 <= score <= 10.0:
                    return score
            except (ValueError, IndexError):
                pass
        
        return 0.0


def evaluate_answer(question: str, answer: str, judge_model: str = "anthropic/claude-3.5-sonnet", 
                    api_key: Optional[str] = None, verbose: bool = False) -> SingleEvaluationResult:
    """Evaluate a single answer with automatic scoring.
    
    Args:
        question: The original research question
        answer: The answer to evaluate
        judge_model: Model to use for judging
        api_key: Optional API key (uses env var if not provided)
        verbose: Print evaluation details
        
    Returns:
        SingleEvaluationResult with score and explanation
    """
    if verbose:
        print("\n" + "=" * 60)
        print("AUTO-EVALUATION")
        print("=" * 60)
        print(f"Judge Model: {judge_model}")
        print(f"Answer Length: {len(answer)} characters")
        print("\nEvaluating answer quality...")
    
    judge = SingleAnswerJudge(api_key=api_key, model=judge_model)
    result = judge.evaluate(question, answer)
    
    if verbose:
        print("\n" + "=" * 60)
        print("EVALUATION RESULT")
        print("=" * 60)
        print(f"Score: {result.score:.1f}/10.0")
        print("\nDetailed Feedback:")
        print("-" * 60)
        print(result.explanation)
    
    return result
