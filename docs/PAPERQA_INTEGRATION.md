# PaperQA Integration Guide

## Overview

The Virtual Lab now includes **PaperQA** integration, providing advanced AI-powered literature search capabilities. This integration enables agents to:

- Search local PDF libraries
- Query online databases (PubMed, arXiv)
- Read and analyze full-text papers
- Generate evidence-based answers with citations
- Synthesize information from multiple sources

## Architecture

### Data Sources

The system supports multiple configurable data sources:

1. **Database Directory** (`DATABASE_DIR`)
   - DrugBank, BindingDB, Pharos, GWAS, StringDB
   - Used by `query_database` tool
   - Default: `/home.galaxy4/sumin/project/aisci/Competition_Data`

2. **Input Directory** (`INPUT_DIR`)
   - Question-specific data files
   - Used by `read_file` tool
   - Default: `./data`

3. **Paper Library Directory** (`PAPER_LIBRARY_DIR`)
   - Local PDF collection for PaperQA
   - Used by `search_literature` tool
   - Default: `./papers`

4. **Internet Search**
   - PubMed, arXiv, Google Scholar
   - Accessed dynamically via PaperQA
   - No local storage required

### Configuration System

Configuration is managed through `src/config.py` which provides:

- `DataConfig`: Centralized configuration dataclass
- `get_default_config()`: Loads from environment variables
- `create_custom_config()`: Programmatic configuration
- `get_global_config()`: Access global instance

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `paper-qa>=5.0.0` along with all dependencies.

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
# Required: OpenRouter API key (used for both main agent and PaperQA)
OPENROUTER_API_KEY=your_openrouter_api_key_here

# OR if you prefer Anthropic for main agent + OpenRouter for PaperQA
ANTHROPIC_API_KEY=your_anthropic_api_key_here
OPENROUTER_API_KEY=your_openrouter_api_key_here

# Data source paths (optional, uses defaults if not set)
DATABASE_DIR=/path/to/databases
INPUT_DIR=./data
PAPER_LIBRARY_DIR=./papers

# PubMed configuration (optional)
PUBMED_EMAIL=your.email@example.com
PUBMED_API_KEY=your_pubmed_api_key

# PaperQA configuration (optional, defaults use OpenRouter)
PAPERQA_LLM=openrouter/google/gemini-2.0-flash-exp:free
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-small
PAPERQA_MAX_SOURCES=5
```

**Note**: By default, PaperQA now uses OpenRouter instead of OpenAI, so you only need your `OPENROUTER_API_KEY`!

### 3. Prepare Paper Library

Create a directory for your PDF papers:

```bash
mkdir -p papers
```

Organize PDFs in any structure:

```
papers/
├── immunology/
│   ├── paper1.pdf
│   └── paper2.pdf
├── drug_development/
│   └── paper3.pdf
└── general_review.pdf
```

PaperQA will recursively search all subdirectories.

## Usage

### New Tool: `search_literature`

The `search_literature` tool is now available to all agents:

```python
# Example: Biomedical Scientist agent query
result = agent.call_tool("search_literature", {
    "question": "What are the mechanisms of EGFR inhibitor resistance?",
    "mode": "auto",  # or "local", "online"
    "max_sources": 5
})
```

#### Parameters

- **question** (required): Natural language research question
- **mode** (optional): Search mode
  - `"auto"` (default): Use local PDFs if available, otherwise online
  - `"local"`: Search only local PDF library
  - `"online"`: Search only internet databases
- **paper_dir** (optional): Override default paper library path
- **max_sources** (optional): Maximum contexts to retrieve (default: 5)

#### Return Format

```python
{
    "success": True,
    "output": {
        "answer": "Evidence-based answer with citations...",
        "contexts": [
            {
                "text": "Relevant passage from paper...",
                "citation": "Author et al., 2023",
                "score": 0.95
            },
            ...
        ],
        "references": ["Full bibliography..."],
        "sources_used": ["local_library (15 PDFs)", "pubmed_online"],
        "mode": "hybrid"
    },
    "error": None
}
```

### Comparison: `search_pubmed` vs `search_literature`

| Feature | `search_pubmed` | `search_literature` |
|---------|----------------|-------------------|
| **Speed** | Fast (< 5 sec) | Slower (30-60 sec) |
| **Depth** | Abstracts only | Full-text analysis |
| **Output** | List of papers | Synthesized answer |
| **Citations** | Paper metadata | Inline citations |
| **Local PDFs** | No | Yes |
| **Use Case** | Quick overview | Deep analysis |

**Recommendation**: Use `search_pubmed` for initial exploration, then `search_literature` for detailed investigation.

## Agent Integration

### Virtual Lab Meeting Workflow

Agents automatically have access to both literature search tools:

```python
# Example Virtual Lab meeting scenario
meeting = VirtualLabMeeting(
    question="Design a novel EGFR inhibitor for NSCLC",
    num_rounds=2
)

# Biomedical Scientist can now use:
# 1. search_pubmed - Quick literature scan
# 2. search_literature - Deep analysis of local papers
# 3. query_database - Drug/target databases
# 4. execute_python - Data analysis

answer, transcript = meeting.run()
```

### Agent Personas

Default team members and their typical tool usage:

1. **Bioinformatician**
   - Primary: `execute_python`, `query_database`
   - Secondary: `search_literature` (for methodology)

2. **Biomedical Scientist**
   - Primary: `search_literature`, `search_pubmed`
   - Secondary: `query_database` (for validation)

3. **Data Scientist**
   - Primary: `execute_python`, `read_file`
   - Secondary: `search_literature` (for statistical methods)

## Advanced Configuration

### Custom Data Paths

Override paths programmatically:

```python
from src.config import create_custom_config, set_global_config

config = create_custom_config(
    database_dir="/custom/path/to/databases",
    input_dir="/custom/input",
    paper_library_dir="/custom/papers",
    paperqa_llm="anthropic/claude-sonnet-4-20250514"
)

set_global_config(config)
```

### Using Different LLMs for PaperQA

PaperQA supports multiple LLM providers through LiteLLM. **OpenRouter is now the default!**

```bash
# OpenRouter (default) - Access 100+ models with one API key
PAPERQA_LLM=openrouter/google/gemini-2.0-flash-exp:free
PAPERQA_LLM=openrouter/anthropic/claude-3.5-sonnet
PAPERQA_LLM=openrouter/meta-llama/llama-3.3-70b-instruct

# Direct OpenAI (requires OPENAI_API_KEY)
PAPERQA_LLM=openai:gpt-4o-mini

# Direct Anthropic (requires ANTHROPIC_API_KEY)
PAPERQA_LLM=anthropic/claude-sonnet-4-20250514

# Other providers supported by LiteLLM
PAPERQA_LLM=google/gemini-pro
```

**Note**: When using `openrouter/`, you only need `OPENROUTER_API_KEY`. For other providers, you need their respective API keys.

### Embedding Models

Configure the embedding model for document indexing:

```bash
# OpenRouter embeddings (default) - Uses your OPENROUTER_API_KEY
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-small

# Higher quality via OpenRouter (slower, more expensive)
PAPERQA_EMBEDDING=openrouter/openai/text-embedding-3-large

# Alternative: Free local embeddings (requires pip install paper-qa[local])
PAPERQA_EMBEDDING=st-multi-qa-MiniLM-L6-cos-v1

# Direct OpenAI embeddings (requires OPENAI_API_KEY)
PAPERQA_EMBEDDING=text-embedding-3-small
```

**Recommended**: Use `openrouter/openai/text-embedding-3-small` for simplicity (one API key for everything).

## Performance Considerations

### Speed vs Accuracy

- **Fast mode**: `search_pubmed` + `max_sources=3`
  - ~10 seconds per query
  - Good for initial exploration

- **Balanced mode**: `search_literature` + `mode="auto"` + `max_sources=5`
  - ~30-45 seconds per query
  - Good general-purpose setting

- **Deep mode**: `search_literature` + `mode="hybrid"` + `max_sources=10`
  - ~60-90 seconds per query
  - Most comprehensive analysis

### Cost Management

PaperQA incurs API costs for:
1. Embedding generation (per document)
2. LLM queries (per question)

**Tips to reduce costs:**
- Use smaller embedding model (`text-embedding-3-small`)
- Use cheaper LLM (`gpt-4o-mini` instead of `gpt-4o`)
- Limit `max_sources` to 5 or fewer
- Cache embeddings (PaperQA does this automatically)

### Disk Usage

- Embeddings are cached in memory during agent execution
- No persistent vector database by default
- Each PDF adds ~1-5MB of memory for embeddings

## Troubleshooting

### Common Issues

1. **"PaperQA not installed"**
   ```bash
   pip install paper-qa>=5.0.0
   ```

2. **"OPENROUTER_API_KEY not found"**
   - Add `OPENROUTER_API_KEY` to `.env` file
   - Or set environment variable: `export OPENROUTER_API_KEY=sk-...`
   - Get your key from: https://openrouter.ai/keys

3. **"No local papers found"**
   - Check `PAPER_LIBRARY_DIR` path
   - Ensure PDFs exist in the directory
   - Use `mode="online"` to skip local search

4. **Slow performance**
   - Reduce `max_sources`
   - Use `mode="local"` to skip online search
   - Switch to faster LLM (`gpt-4o-mini`)

5. **"Rate limit exceeded" (PubMed)**
   - Add `PUBMED_EMAIL` to `.env`
   - Add `PUBMED_API_KEY` for higher limits
   - Reduce frequency of online searches

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Examples

### Example 1: Local PDF Analysis

```python
from src.agent.agent import BioinformaticsAgent

agent = BioinformaticsAgent()
result = agent.call_tool("search_literature", {
    "question": "What are the latest CRISPR off-target effects?",
    "mode": "local",
    "paper_dir": "./papers/crispr"
})

print(result["output"]["answer"])
```

### Example 2: Online Search Only

```python
result = agent.call_tool("search_literature", {
    "question": "Recent advances in mRNA vaccine technology",
    "mode": "online"
})
```

### Example 3: Hybrid Search

```python
# Best of both worlds
result = agent.call_tool("search_literature", {
    "question": "Mechanisms of CAR-T cell exhaustion in solid tumors",
    "mode": "auto",  # Uses local + online
    "max_sources": 7
})

# Check which sources were used
print("Sources:", result["output"]["sources_used"])
# Output: ['local_library (12 PDFs)', 'pubmed_online']
```

### Example 4: Virtual Lab Meeting

```python
from src.agent.meeting import VirtualLabMeeting

meeting = VirtualLabMeeting(
    question="Identify potential biomarkers for early Alzheimer's detection",
    num_rounds=2,
    api_key=os.getenv("OPENROUTER_API_KEY"),
    provider="openrouter"
)

answer, transcript = meeting.run()

# Biomedical Scientist likely used search_literature
# Bioinformatician likely used query_database
# Data Scientist likely used execute_python
```

## Best Practices

1. **Start broad, then narrow**
   - Use `search_pubmed` for initial scan
   - Use `search_literature` for deep dives

2. **Organize your PDFs**
   - Group by topic in subdirectories
   - Use descriptive filenames
   - Keep PDFs up-to-date

3. **Optimize for your use case**
   - Drug discovery: Focus on DrugBank + local papers
   - Disease research: Hybrid mode for comprehensive coverage
   - Method development: Local papers with detailed protocols

4. **Leverage multi-agent collaboration**
   - Let PI coordinate literature review
   - Biomedical Scientist handles literature search
   - Bioinformatician validates with databases

## Future Enhancements

Planned improvements:

- [ ] Persistent vector database for faster repeated queries
- [ ] Semantic Scholar integration
- [ ] Automatic PDF download from PMC/arXiv
- [ ] Citation network analysis
- [ ] Literature gap detection

## Support

For issues or questions:
1. Check this documentation
2. Review `.env.example` configuration
3. Check PaperQA documentation: https://github.com/Future-House/paper-qa
4. Enable debug logging for detailed errors

## License

This integration follows the same license as the main Virtual Lab project.
