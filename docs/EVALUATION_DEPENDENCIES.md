# FastChat Evaluation Features - Dependencies

## Required Packages

The evaluation features use the following key packages:

### LLM Provider Clients
```
openai>=1.0.0          # For GPT models
anthropic>=0.7.0       # For Claude models
```

### Additional (Optional, based on judge API provider)
```
litellm>=0.0.0         # For OpenRouter API compatibility
```

## Installation

### Install via pip
```bash
pip install openai anthropic
```

### For OpenRouter support
```bash
pip install litellm
```

### All in one
```bash
pip install -e ".[evaluation]"  # If you update setup.py/pyproject.toml
```

## Usage Notes

1. **OpenAI (Default)**
   - Requires `openai` package
   - API key: `OPENAI_API_KEY`

2. **Anthropic**
   - Requires `anthropic` package
   - API key: `ANTHROPIC_API_KEY`

3. **OpenRouter**
   - Can use either `openai` (via base_url override) or `litellm`
   - API key: `OPENROUTER_API_KEY`

## Environment Variables

```bash
# .env file
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-...
```

## Compatibility

- **Python:** 3.8+
- **FastChat:** No direct dependency (features are independent)
- **Existing Dependencies:** All compatible with current setup
