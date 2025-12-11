# OpenRouter Migration Guide

## Summary

PaperQA integration has been updated to use **OpenRouter** instead of OpenAI, allowing you to use 100+ models with a single API key!

## What Changed

### 1. Default LLM Provider
- **Before**: `openai:gpt-4o-mini` (requires OPENAI_API_KEY)
- **After**: `openrouter/google/gemini-2.0-flash-exp:free` (requires OPENROUTER_API_KEY)

### 2. Default Embedding Provider
- **Before**: `text-embedding-3-small` (requires OPENAI_API_KEY)
- **After**: `openrouter/openai/text-embedding-3-small` (uses OPENROUTER_API_KEY)

### 3. API Key Validation
- Added automatic detection of which API key is needed based on configuration
- Clear error messages if the required API key is missing

## Quick Setup

### 1. Get OpenRouter API Key
Visit https://openrouter.ai/keys to get your API key (many models have free tiers!)

### 2. Update `.env` file
```bash
# Only one API key needed for PaperQA!
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Optional: Override defaults
PAPERQA_LLM=openrouter/google/gemini-2.0-flash-exp:free
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-small
```

### 3. Install/Reinstall dependencies
```bash
pip install -r requirements.txt
```

## Available OpenRouter Models for PaperQA

### LLM Models (for text generation)
```bash
# Free tier models
PAPERQA_LLM=openrouter/google/gemini-2.0-flash-exp:free
PAPERQA_LLM=openrouter/meta-llama/llama-3.3-70b-instruct:free
PAPERQA_LLM=openrouter/qwen/qwen-2.5-7b-instruct:free

# Premium models (paid)
PAPERQA_LLM=openrouter/anthropic/claude-3.5-sonnet
PAPERQA_LLM=openrouter/openai/gpt-4o
PAPERQA_LLM=openrouter/google/gemini-pro-1.5
```

### Embedding Models
```bash
# OpenRouter embeddings (recommended)
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-small
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-large

# Check https://openrouter.ai/models?fmt=cards&output_modalities=embeddings
# for the full list of available embedding models
```

## Alternative: Local Embeddings

If you want to avoid embedding costs, you can use local models:

### 1. Install local support
```bash
pip install paper-qa[local]
```

### 2. Update config
```bash
# Use local embedding model (no API calls)
PAPERQA_EMBEDDING=st-multi-qa-MiniLM-L6-cos-v1

# Still use OpenRouter for LLM
PAPERQA_LLM=openrouter/google/gemini-2.0-flash-exp:free
```

## Testing the Setup

Run the integration test:
```bash
python test_paperqa_integration.py
```

Or test directly:
```python
from src.tools.implementations import search_literature

result = search_literature(
    question="What are the mechanisms of EGFR inhibitor resistance?",
    mode="online",
    max_sources=3
)

print(result.output["answer"] if result.success else result.error)
```

## Cost Comparison

| Setup | LLM Cost | Embedding Cost | Total API Keys Needed |
|-------|----------|----------------|----------------------|
| **OpenRouter (default)** | $0-$0.30/M tokens | $0.13/M tokens | 1 (OPENROUTER_API_KEY) |
| **OpenAI (old)** | $0.15-$2.50/M tokens | $0.13/M tokens | 1 (OPENAI_API_KEY) |
| **OpenRouter + Local** | $0-$0.30/M tokens | Free | 1 (OPENROUTER_API_KEY) |

**Savings**: Using free OpenRouter models can reduce costs to $0 for LLM + $0.13/M tokens for embeddings!

## Reverting to OpenAI (if needed)

If you need to use OpenAI directly:

```bash
# .env file
OPENAI_API_KEY=your_openai_api_key

# Override in config
PAPERQA_LLM=openai:gpt-4o-mini
PAPERQA_EMBEDDING=text-embedding-3-small
```

## Troubleshooting

### Error: "OPENROUTER_API_KEY not found"
- Add the key to your `.env` file
- Or set environment variable: `export OPENROUTER_API_KEY=sk-...`
- Get your key from: https://openrouter.ai/keys

### Error: "Model not found" or 403
- Check available models at: https://openrouter.ai/models
- Some models require credits/payment
- Try a free tier model first

### Slow performance
- Try a faster model: `openrouter/google/gemini-2.0-flash-exp:free`
- Reduce `PAPERQA_MAX_SOURCES` (default: 5)
- Use local embeddings to reduce API calls

## More Information

- **OpenRouter Models**: https://openrouter.ai/models
- **OpenRouter Docs**: https://openrouter.ai/docs
- **PaperQA Integration Guide**: [PAPERQA_INTEGRATION.md](./PAPERQA_INTEGRATION.md)
- **LiteLLM OpenRouter Support**: https://docs.litellm.ai/docs/providers/openrouter
