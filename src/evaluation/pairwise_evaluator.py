"""
Pairwise evaluation system for comparing two AI-generated answers.
Based on FastChat's LLM-as-a-judge approach, adapted for ai-cosci biomedical answers.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

import requests
from dotenv import load_dotenv

# Load .env file to get OPENROUTER_API_KEY
load_dotenv()


@dataclass
class PairwiseResult:
    """Result of a pairwise comparison."""
    winner: str  # "A", "B", or "tie"
    explanation: str
    score_a: Optional[float] = None
    score_b: Optional[float] = None
    raw_judgment: str = ""


class OpenRouterJudge:
    """OpenRouter-based judge for answer evaluation."""
    
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
    
    def create_biomedical_prompt(self, question: str, answer_a: str, answer_b: str) -> str:
        """Create a biomedical-focused pairwise comparison prompt.
        
        Args:
            question: The original research question
            answer_a: First answer to compare
            answer_b: Second answer to compare
            
        Returns:
            Formatted prompt for the judge
        """
        return f"""Please act as an expert biomedical researcher and evaluate the quality of two AI-generated responses to a scientific question. 

Your evaluation should consider:
1. **Scientific Accuracy**: Correctness of facts, mechanisms, and interpretations
2. **Evidence Quality**: Proper citations (PMID format), use of peer-reviewed sources
3. **Methodological Rigor**: Appropriate analysis methods, statistical approaches
4. **Completeness**: Thoroughness in addressing all aspects of the question
5. **Clarity**: Clear explanation for scientific audience
6. **Limitations**: Acknowledgment of uncertainties and study limitations
7. **Relevance**: Direct relevance to the research question

Compare the two responses and determine which one provides a better scientific answer. Consider both the depth of analysis and the reliability of information.

**Research Question:**
{question}

**Assistant A's Answer:**
{answer_a}

**Assistant B's Answer:**
{answer_b}

**Instructions:**
1. Provide a detailed comparison highlighting strengths and weaknesses of each answer
2. Focus on scientific rigor and evidence quality
3. Consider which answer would be more valuable to a biomedical researcher
4. Output your final verdict in the format: [[A]] if Assistant A is better, [[B]] if Assistant B is better, or [[tie]] for equivalent quality

Begin your evaluation:"""

    def evaluate_pairwise(self, question: str, answer_a: str, answer_b: str) -> PairwiseResult:
        """Evaluate two answers in pairwise comparison.
        
        Args:
            question: The original research question
            answer_a: First answer to compare  
            answer_b: Second answer to compare
            
        Returns:
            PairwiseResult with winner and explanation
        """
        prompt = self.create_biomedical_prompt(question, answer_a, answer_b)
        
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
            
            # Extract the verdict
            winner = self._extract_verdict(judgment_text)
            
            return PairwiseResult(
                winner=winner,
                explanation=judgment_text,
                raw_judgment=judgment_text
            )
            
        except Exception as e:
            return PairwiseResult(
                winner="error",
                explanation=f"Error during evaluation: {str(e)}",
                raw_judgment=str(e)
            )
    
    def _extract_verdict(self, judgment_text: str) -> str:
        """Extract the final verdict from judgment text.
        
        Args:
            judgment_text: Raw judgment from the model
            
        Returns:
            "A", "B", "tie", or "unclear"
        """
        # Look for verdict patterns
        patterns = [
            r'\[\[([ABab])\]\]',  # [[A]] or [[B]]
            r'\[\[tie\]\]',       # [[tie]]
            r'Final verdict:.*?\[\[([ABab])\]\]',  # Final verdict: [[A]]
            r'Final verdict:.*?\[\[tie\]\]'        # Final verdict: [[tie]]
        ]
        
        for pattern in patterns:
            match = re.search(pattern, judgment_text, re.IGNORECASE)
            if match:
                if 'tie' in pattern:
                    return "tie"
                else:
                    return match.group(1).upper()
        
        # Fallback: look for explicit statements
        text_lower = judgment_text.lower()
        if "assistant a is better" in text_lower or "response a is superior" in text_lower:
            return "A"
        elif "assistant b is better" in text_lower or "response b is superior" in text_lower:
            return "B"
        elif "tie" in text_lower or "equivalent" in text_lower or "similar quality" in text_lower:
            return "tie"
        
        return "unclear"


def load_text_file(file_path: str) -> str:
    """Load text content from file (supports .txt, .md files)."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    
    return path.read_text(encoding='utf-8')


def save_evaluation_result(result: PairwiseResult, question: str, 
                          file_a: str, file_b: str, output_path: Optional[str] = None) -> str:
    """Save evaluation result to a Markdown file.
    
    Args:
        result: PairwiseResult object
        question: Original question
        file_a: Path to first answer file
        file_b: Path to second answer file
        output_path: Optional output path
        
    Returns:
        Path to saved result file
    """
    if output_path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"tests/evaluation/pairwise_result_{timestamp}.md"
    
    # Create markdown content
    winner_display = result.winner.upper() if result.winner != "tie" else "TIE"
    
    md_content = f"""# Pairwise Evaluation Result

**Evaluation Date:** {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Research Question

{question}

---

## Answer Files Compared

- **Answer A:** `{file_a}`
- **Answer B:** `{file_b}`

---

## Evaluation Result

### Winner: {winner_display}

### Detailed Analysis

{result.explanation}

---

## Metadata

- **Evaluation Timestamp:** {datetime.now().isoformat()}
- **Score A:** {result.score_a if result.score_a is not None else 'N/A'}
- **Score B:** {result.score_b if result.score_b is not None else 'N/A'}

---

## Raw Judgment

```
{result.raw_judgment}
```
"""
    
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(md_content)
    
    return str(output_file)


def main():
    """Main function for pairwise evaluation CLI."""
    parser = argparse.ArgumentParser(
        description="Pairwise evaluation of two AI-generated biomedical answers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Compare two answer files
  python pairwise_evaluator.py --question "What are the molecular mechanisms of cancer?" \\
    --answer-a answer1.txt --answer-b answer2.txt

  # With custom output path
  python pairwise_evaluator.py -q question.txt -a ans1.md -b ans2.md \\
    --output results/comparison.json
  
  # Use different judge model
  python pairwise_evaluator.py -q "Gene therapy approaches" \\
    -a answer_claude.txt -b answer_gpt.txt --judge-model "openai/gpt-4"
        """
    )
    
    parser.add_argument(
        "--question", "-q",
        type=str,
        required=True,
        help="Research question (as string or path to file containing question)"
    )
    
    parser.add_argument(
        "--answer-a", "-a",
        type=str,
        required=True,
        help="Path to first answer file (.txt, .md)"
    )
    
    parser.add_argument(
        "--answer-b", "-b", 
        type=str,
        required=True,
        help="Path to second answer file (.txt, .md)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output path for evaluation result (default: auto-generated)"
    )
    
    parser.add_argument(
        "--judge-model",
        type=str,
        default="anthropic/claude-3.5-sonnet",
        help="Judge model to use (default: anthropic/claude-3.5-sonnet)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed evaluation process"
    )
    
    args = parser.parse_args()
    
    try:
        # Load question (from string or file)
        if os.path.exists(args.question):
            question = load_text_file(args.question)
            if args.verbose:
                print(f"Loaded question from file: {args.question}")
        else:
            question = args.question
            if args.verbose:
                print("Using question as direct input")
        
        # Load answers
        if args.verbose:
            print(f"Loading answer A from: {args.answer_a}")
        answer_a = load_text_file(args.answer_a)
        
        if args.verbose:
            print(f"Loading answer B from: {args.answer_b}")
        answer_b = load_text_file(args.answer_b)
        
        # Initialize judge
        if args.verbose:
            print(f"Initializing judge with model: {args.judge_model}")
        judge = OpenRouterJudge(model=args.judge_model)
        
        # Perform evaluation
        print("\n" + "="*60)
        print("PAIRWISE EVALUATION")
        print("="*60)
        print(f"Question: {question[:100]}{'...' if len(question) > 100 else ''}")
        print(f"Answer A: {len(answer_a)} characters")
        print(f"Answer B: {len(answer_b)} characters")
        print(f"Judge: {args.judge_model}")
        print("\nEvaluating...")
        
        result = judge.evaluate_pairwise(question, answer_a, answer_b)
        
        # Display results
        print("\n" + "="*60)
        print("EVALUATION RESULT")
        print("="*60)
        print(f"Winner: {result.winner.upper()}")
        print("\nDetailed Analysis:")
        print("-" * 40)
        print(result.explanation)
        
        # Save results
        output_file = save_evaluation_result(
            result, question, args.answer_a, args.answer_b, args.output
        )
        
        print(f"\n✅ Results saved to: {output_file}")
        
        # Return appropriate exit code
        if result.winner == "error":
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        print("\n❌ Evaluation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during evaluation: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()