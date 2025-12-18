# FastChat-Based Critic and Model Evaluation Features

This document describes the two new features added to ai-cosci:

1. **FastChat Pipeline Critic** - Uses FastChat's LLM-as-a-judge pipeline to evaluate answers
2. **Model Answer Evaluation** - Framework for evaluating answers from various models and comparing them

## Overview

These features integrate FastChat's proven evaluation methodology into the ai-cosci system, enabling:
- Structured, multi-category evaluation of generated answers
- Scoring on a 1-10 scale across 7 evaluation dimensions
- Comparison of answers from multiple models
- Benchmark suites for evaluating models on multiple questions
- Detailed evaluation reports in markdown and JSON formats

## Architecture

### Core Components

#### 1. `src/agent/fastchat_critic.py`
Wraps FastChat's LLM judge pipeline:
- `FastChatCritic` class - Main evaluator using configurable LLM judges
- `CriticScore` dataclass - Structured evaluation scores per category
- `EvaluationResult` dataclass - Complete evaluation with reasoning and suggestions
- Supports OpenAI, Anthropic, and OpenRouter APIs as judge models

**Evaluation Categories:**
- Scientific Accuracy
- Completeness
- Reasoning Quality
- Data Analysis
- Literature Support
- Practical Feasibility
- Clarity

#### 2. `src/evaluation/evaluator.py`
High-level evaluation framework:
- `AnswerEvaluator` class - Unified interface for answer evaluation
- `EvaluationStrategy` enum - Different evaluation approaches
- `ComparisonMetrics` dataclass - Statistics for multi-model comparisons
- `BenchmarkSuite` class - Benchmark across multiple questions and models
- Support for both single-answer and pairwise evaluation modes

#### 3. `src/utils/evaluation_utils.py`
Utility functions:
- Answer saving/loading in JSON format
- CSV export for evaluation results
- Report generation (Markdown format)
- Aggregation of benchmark results
- Comparison across multiple questions

#### 4. `src/agent/agent.py` - Extended
New method: `run_with_fastchat_critic()`
- Generates an answer using the agent
- Evaluates it using the FastChat critic pipeline
- Returns both answer and structured evaluation

## Usage

### 1. Using FastChat Critic with Single Agent

Evaluate an answer as the agent generates it:

```bash
# Basic evaluation with default judge (GPT-4)
python -m src.cli --question "What is TP53?" --evaluate

# With a specific judge model
python -m src.cli --question "Your question" \
  --evaluate \
  --judge-model "claude-3-sonnet" \
  --judge-api-provider "anthropic"

# Evaluate specific categories only
python -m src.cli --question "Your question" \
  --evaluate \
  --eval-categories "scientific_accuracy" "literature_support"
```

**Output:**
```
Overall Score: 8.5/10
Assessment: The answer provides a comprehensive overview...

Category Breakdown:
  - Scientific Accuracy: 8.0/10
  - Completeness: 9.0/10
  - Reasoning Quality: 8.5/10
  - Data Analysis: 8.0/10
  - Literature Support: 8.5/10
  - Practical Feasibility: 8.0/10
  - Clarity: 9.0/10
```

### 2. Comparing Multiple Model Answers

Evaluate and compare answers from different models:

```bash
# Create a JSON file with answers from multiple models
cat > answers.json << 'EOF'
{
  "gpt-4": "GPT-4's answer text...",
  "claude-3": "Claude 3's answer text...",
  "llama-2": "Llama 2's answer text..."
}
EOF

# Compare them
python -m src.cli \
  --question "Your research question" \
  --compare answers.json \
  --output comparison_report.md \
  --judge-model "gpt-4"
```

**Output:** Markdown report with:
- Overall scores ranking
- Per-model detailed evaluations
- Category breakdowns
- Statistical comparison metrics

### 3. Python API Usage

```python
from src.evaluation.evaluator import AnswerEvaluator, EvaluationStrategy

# Create evaluator
evaluator = AnswerEvaluator(
    strategy=EvaluationStrategy.FASTCHAT,
    judge_model="gpt-4",
    api_provider="openai"
)

# Evaluate single answer
result = evaluator.evaluate_answer(
    question="What is CRISPR?",
    answer="CRISPR is...",
    model_name="my_model"
)

print(f"Score: {result['overall_score']:.1f}/10")
print(f"Assessment: {result['reasoning']}")

# Compare multiple answers
answers = {
    "model_a": "Answer from model A...",
    "model_b": "Answer from model B...",
}

results = evaluator.evaluate_multiple(
    "Your question",
    answers,
    categories=["scientific_accuracy", "literature_support"]
)

# Generate comparison report
report = evaluator.generate_report(
    "Your question",
    results,
    include_details=True
)

print(report)
```

### 4. Benchmark Suite for Multiple Questions

```python
from src.evaluation.evaluator import BenchmarkSuite

# Define questions to benchmark
questions = [
    {"id": "q1", "question": "What is TP53?"},
    {"id": "q2", "question": "Explain CRISPR mechanism"},
    {"id": "q3", "question": "What are biomarkers?"},
]

# Organize answers by model
model_answers = {
    "model_a": {
        "q1": "answer...",
        "q2": "answer...",
        "q3": "answer...",
    },
    "model_b": {
        "q1": "answer...",
        "q2": "answer...",
        "q3": "answer...",
    },
}

# Run benchmark
suite = BenchmarkSuite(evaluator, questions)
results = suite.benchmark(model_answers)

# Results contain:
# - Per-question results for each model
# - Aggregate statistics (mean, min, max scores)
# - Overall winner
print(results["aggregate_statistics"])
```

### 5. Using Evaluation Utilities

```python
from src.utils.evaluation_utils import (
    save_answers_json,
    load_answers_json,
    save_evaluation_results_csv,
    generate_evaluation_markdown_report,
)

# Save answers for later evaluation
answers = {
    "model_a": "Answer text...",
    "model_b": "Answer text...",
}
save_answers_json(answers, "answers.json", question="Your question")

# Load and evaluate
loaded_answers, question = load_answers_json("answers.json")

# Save results to CSV
save_evaluation_results_csv(results, "results.csv")

# Generate markdown report
report = generate_evaluation_markdown_report(
    question="Your question",
    results=results,
    include_full_assessment=True
)

with open("report.md", "w") as f:
    f.write(report)
```

## Configuration

### Judge Models

Supported judge models by provider:

**OpenAI (default):**
- `gpt-4` (recommended, most thorough)
- `gpt-4-turbo`
- `gpt-3.5-turbo` (faster, lower cost)

**Anthropic:**
- `claude-3-opus` (recommended)
- `claude-3-sonnet`
- `claude-3-haiku`

**OpenRouter:**
- Any model available on OpenRouter (supports 70+ models)
- Format: `provider/model-name`

### Environment Variables

Set API keys in `.env` file:
```bash
# OpenAI
OPENAI_API_KEY=sk-...

# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# OpenRouter
OPENROUTER_API_KEY=sk-or-...
```

## Features

### 1. Structured Evaluation

Each answer is evaluated across 7 key dimensions:

| Category | Description |
|----------|-------------|
| Scientific Accuracy | Are claims supported by evidence? Are references correct? |
| Completeness | Does it address all aspects of the question? |
| Reasoning Quality | Is the logical reasoning sound? |
| Data Analysis | Are analyses appropriate and results correctly interpreted? |
| Literature Support | Are relevant papers cited with proper citations? |
| Practical Feasibility | Are proposed approaches realistic? |
| Clarity | Is the answer clear and well-organized? |

### 2. Multi-Model Comparison

Compare multiple model outputs on the same question:
- Automatic ranking by score
- Category-by-category comparison
- Statistical analysis (mean, variance, etc.)
- Detailed reasoning for each score

### 3. Benchmark Suites

Evaluate models on multiple questions:
- Per-question results
- Aggregate statistics
- Identification of strengths/weaknesses
- Performance consistency analysis

### 4. Flexible Output Formats

- **Markdown:** Human-readable reports
- **JSON:** Structured data for processing
- **CSV:** For spreadsheet analysis
- **Console:** Immediate feedback

## Integration with Existing Features

### With Virtual Lab Mode
```bash
python -m src.cli --question "..." --virtual-lab --evaluate
```
The final synthesis answer will be evaluated using the FastChat critic.

### With Critic Feedback Loop
```bash
python -m src.cli --question "..." --with-critic --evaluate
```
The refined answer will be evaluated after critic feedback.

### In Interactive Mode
Answers are evaluated in real-time:
```bash
python -m src.cli --interactive --evaluate
```

## Performance Considerations

- **Evaluation Speed:** ~30-60 seconds per answer depending on judge model
- **Token Usage:** Varies by answer length and judge model
- **Cost Estimation:** 
  - GPT-4: ~$0.10-0.50 per answer
  - Claude 3 Opus: ~$0.05-0.20 per answer
  - GPT-3.5-turbo: ~$0.01-0.05 per answer

## Examples

### Example 1: Single Question Evaluation
```bash
python -m src.cli \
  --question "Describe the mechanism of action of ACE inhibitors" \
  --evaluate \
  --judge-model "gpt-4" \
  --verbose
```

### Example 2: Model Comparison
```bash
# Answers from 3 different models
python -m src.cli \
  --question "What is the role of p53 in cancer?" \
  --compare \
  model_a_answers.json \
  model_b_answers.json \
  model_c_answers.json \
  --output comparison_report.md \
  --judge-api-provider "anthropic" \
  --judge-model "claude-3-opus"
```

### Example 3: Benchmark across Multiple Questions
```python
from src.evaluation.evaluator import BenchmarkSuite, AnswerEvaluator
import json

# Load questions and answers
with open("benchmark_questions.json") as f:
    questions = json.load(f)

with open("model_answers.json") as f:
    model_answers = json.load(f)

# Create benchmark
evaluator = AnswerEvaluator()
suite = BenchmarkSuite(evaluator, questions)
results = suite.benchmark(model_answers)

# Print winner
winner = results["overall_winner"]
stats = results["aggregate_statistics"][winner]
print(f"Winner: {winner} (Mean Score: {stats['mean_score']:.2f})")
```

## Error Handling

The system provides graceful fallbacks:
- If FastChat judge unavailable, falls back to basic evaluation
- If API fails, returns partial results with error messages
- Proper error logging with `--verbose` flag

## Future Enhancements

Planned improvements:
1. Fine-tuned judge models for biomedical domain
2. Custom evaluation criteria per domain
3. Pairwise win-rate evaluation
4. Multi-turn evaluation for conversational answers
5. Reference-based evaluation (comparing to gold answers)
6. Batch evaluation optimization
