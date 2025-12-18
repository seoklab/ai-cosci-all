# FastChat Critic & Evaluation - Quick Reference

## Quick Start

### Evaluate a Single Answer
```bash
python -m src.cli --question "Your question here" --evaluate
```

### Compare Multiple Model Answers
```bash
python -m src.cli --question "Your question" --compare answers.json --output report.md
```

## Common CLI Commands

| Task | Command |
|------|---------|
| Evaluate with GPT-4 | `--question "q" --evaluate --judge-model gpt-4` |
| Use Claude judge | `--question "q" --evaluate --judge-api-provider anthropic --judge-model claude-3-sonnet` |
| Custom eval categories | `--evaluate --eval-categories scientific_accuracy literature_support` |
| Save comparison report | `--compare answers.json --output report.md` |

## Evaluation Categories

```
1. scientific_accuracy    - Claims support, reference accuracy
2. completeness           - Addresses all aspects
3. reasoning_quality      - Logical soundness
4. data_analysis          - Appropriate methods, correct interpretation
5. literature_support     - Proper citations, relevant papers
6. practical_feasibility  - Realistic approaches
7. clarity                - Well-organized, clear explanation
```

## Python API Quick Examples

### Single Evaluation
```python
from src.evaluation.evaluator import AnswerEvaluator

evaluator = AnswerEvaluator()
result = evaluator.evaluate_answer(
    question="Your question",
    answer="Your answer",
    model_name="model_name"
)
print(f"Score: {result['overall_score']}/10")
```

### Multiple Models
```python
answers = {
    "model_a": "Answer from model A",
    "model_b": "Answer from model B",
}
results = evaluator.evaluate_multiple("Question", answers)
report = evaluator.generate_report("Question", results)
print(report)
```

### Benchmark Suite
```python
from src.evaluation.evaluator import BenchmarkSuite

questions = [
    {"id": "q1", "question": "Q1?"},
    {"id": "q2", "question": "Q2?"},
]
suite = BenchmarkSuite(evaluator, questions)
results = suite.benchmark(model_answers)
```

## FastChat Critic in Agent

### Run with Evaluation
```python
from src.agent.agent import BioinformaticsAgent

agent = BioinformaticsAgent()
answer, evaluation = agent.run_with_fastchat_critic(
    "Your question",
    judge_model="gpt-4"
)

if evaluation:
    print(f"Score: {evaluation.overall_score:.1f}/10")
    for cat, score in evaluation.scores.items():
        print(f"  {cat}: {score.score:.1f}/10")
```

## Output Formats

### JSON (Python)
```python
from src.utils.evaluation_utils import save_answers_json, save_evaluation_results_csv

# Save answers
save_answers_json({"model_a": "answer"}, "file.json")

# Save results
save_evaluation_results_csv(results, "results.csv")
```

### Markdown Report
```python
from src.utils.evaluation_utils import generate_evaluation_markdown_report

report = generate_evaluation_markdown_report(
    "Question",
    results,
    include_full_assessment=True
)
```

## Performance Notes

| Judge Model | Speed | Cost | Quality |
|-----------|-------|------|---------|
| GPT-4 | Slow | $$ | Highest |
| Claude 3 Opus | Medium | $ | Very High |
| GPT-3.5-turbo | Fast | $ | Good |

## Configuration

Set in `.env`:
```bash
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
```

## Full Documentation

See `docs/FASTCHAT_EVALUATION.md` for complete documentation.

## Architecture Overview

```
src/agent/fastchat_critic.py
├── FastChatCritic         # Main evaluator
├── CriticScore            # Per-category scores
└── EvaluationResult       # Complete evaluation

src/evaluation/evaluator.py
├── AnswerEvaluator        # High-level interface
├── EvaluationStrategy     # Strategy enum
├── ComparisonMetrics      # Comparison stats
└── BenchmarkSuite         # Multi-question eval

src/utils/evaluation_utils.py
├── save/load functions
├── CSV/JSON operations
└── Report generation

src/agent/agent.py
└── run_with_fastchat_critic()  # Agent integration
```

## Troubleshooting

**No API key error:**
```bash
# Set in environment or .env
export OPENAI_API_KEY=sk-...
```

**Judge model not available:**
```bash
# Use a different judge
--judge-model gpt-3.5-turbo
```

**Slow evaluation:**
```bash
# Use faster judge
--judge-api-provider openai --judge-model gpt-3.5-turbo
```
