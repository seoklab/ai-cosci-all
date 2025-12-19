"""
CACHED LITERATURE SEARCH IMPLEMENTATION - PER-QUESTION CACHING

REQUIRED IMPORTS (add to implementations.py):
from typing import Optional
from pathlib import Path
import json
import hashlib
import time
"""

"""
CACHED LITERATURE SEARCH IMPLEMENTATION - PER-QUESTION CACHING

This is the refactored search_literature function with proper caching.
Replace the old implementation in implementations.py with this.

Key improvements:
1. Uses SearchIndex for local papers (persistent disk cache)
2. Caches Docs object per question (separate directories per question)
3. Tracks online papers to avoid re-downloading
4. Only processes new papers, reuses embeddings for existing ones

DIRECTORY STRUCTURE:
.paperqa_cache/
  ├── question_<hash1>/
  │   ├── index/           # SearchIndex for this question
  │   ├── docs/            # Cached documents and embeddings
  │   └── metadata.json    # Question text and settings
  ├── question_<hash2>/
  │   └── ...
"""

from typing import Optional
from pathlib import Path
import json
import hashlib
import time
import sys
import os 

# Import ToolResult from implementations
from src.tools.implementations import ToolResult

# Global cache variables
_local_paper_index = None
_local_paper_index_dir = None
_cached_docs = None
_cached_docs_settings_hash = None
_online_papers_cache = {}

def search_literature_cached(
    question: str,
    mode: str = "auto",
    paper_dir: Optional[str] = None,
    max_sources: int = 5,
    cache_base_dir: Optional[str] = None
) -> ToolResult:
    """Advanced literature search with per-question caching.

    CACHING STRATEGY (PER-QUESTION):
    - Each question gets its own cache directory
    - Directory name: .paperqa_cache/question_<hash>/
    - Contains:
      * SearchIndex (local PDFs with embeddings)
      * Downloaded online papers
      * Docs object (serialized with all embeddings)
      * Metadata (question text, settings, timestamp)

    WORKFLOW:
    1. Generate hash from question text
    2. Check if cache directory exists for this question
    3. If exists: Load cached index + docs (FAST - no re-processing)
    4. If not: Create new cache, process papers (SLOW - first time only)
    5. Add any new papers not in cache
    6. Save updated cache for next iteration

    Args:
        question: Research question to answer (natural language)
        mode: Search mode:
            - 'auto' (default): Prioritize local, supplement with online if needed
            - 'local': Only local PDFs (uses SearchIndex)
            - 'online': Skip local, only internet search
            - 'hybrid': Search both simultaneously
        paper_dir: Directory containing local PDF papers (uses config default if None)
        max_sources: Maximum number of source contexts to retrieve (default: 5)
        cache_base_dir: Base directory for caches (default: .paperqa_cache in cwd)

    Returns:
        ToolResult with:
        - answer: Evidence-based answer with citations
        - contexts: List of relevant text passages from papers
        - references: Bibliography of cited papers
        - sources_used: Information about which sources were queried
        - cache_stats: Statistics about cache hits/misses (for debugging)
        - cache_dir: Path to this question's cache directory
    """
    global _local_paper_index, _local_paper_index_dir, _cached_docs
    global _cached_docs_settings_hash, _online_papers_cache

    try:
        # Lazy imports
        from paperqa import Docs, Settings
        from paperqa.settings import AnswerSettings, ParsingSettings, IndexSettings
        from paperqa.agents.search import get_directory_index
        from pathlib import Path
        import hashlib
        import asyncio
        import json
        import time
        import pickle

        # Get configuration
        from src.config import get_global_config
        config = get_global_config()

        # Setup embedding config
        embedding_config = config.paperqa_embedding
        using_local_embeddings = embedding_config.startswith("st-")

        # Setup API keys (same as before)
        if config.paperqa_llm.startswith("openrouter/"):
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
            if not api_key:
                return ToolResult(
                    False, None,
                    "OPENROUTER_API_KEY not found. Set it in .env file or environment."
                )
            os.environ["OPENROUTER_API_KEY"] = api_key
            os.environ["OPENROUTER_KEY"] = api_key
            os.environ["OPENAI_API_KEY"] = api_key

        # Verify dependencies
        if using_local_embeddings:
            try:
                import sentence_transformers
            except ImportError:
                return ToolResult(
                    False, None,
                    "Local embeddings require sentence-transformers. "
                    "Install with: pip install sentence-transformers"
                )

        # Use provided paper_dir or fall back to config
        if paper_dir is None:
            paper_dir = config.paper_library_dir
        paper_dir_path = Path(paper_dir)

        # ===================================================================
        # SETUP PER-QUESTION CACHE DIRECTORY
        # ===================================================================
        # Generate a stable hash from the question to create unique cache dir
        question_hash = hashlib.md5(question.encode()).hexdigest()[:12]

        if cache_base_dir is None:
            cache_base_dir = Path.cwd() / ".paperqa_cache"
        else:
            cache_base_dir = Path(cache_base_dir)

        question_cache_dir = cache_base_dir / f"question_{question_hash}"
        question_cache_dir.mkdir(parents=True, exist_ok=True)

        # Save question metadata
        metadata_file = question_cache_dir / "metadata.json"
        metadata = {
            "question": question,
            "question_hash": question_hash,
            "created_at": metadata_file.stat().st_ctime if metadata_file.exists() else None,
            "settings": {
                "llm": config.paperqa_llm,
                "embedding": embedding_config,
            }
        }

        # Check if this is a cached question
        is_cached_question = metadata_file.exists()
        if is_cached_question:
            with open(metadata_file, 'r') as f:
                cached_metadata = json.loads(f.read())
                print(f"[CACHE] Found cached question from {cached_metadata.get('created_at')}",
                      file=sys.stderr)
                print(f"[CACHE] Cache directory: {question_cache_dir}", file=sys.stderr)
        else:
            print(f"[CACHE] New question - creating cache at {question_cache_dir}",
                  file=sys.stderr)
            import time
            metadata["created_at"] = time.time()
            with open(metadata_file, 'w') as f:
                f.write(json.dumps(metadata, indent=2))

        # Update paper_dir for local papers (now relative to question cache)
        local_index_dir = question_cache_dir / "local_index"
        online_papers_dir = question_cache_dir / "online_papers"
        online_papers_dir.mkdir(exist_ok=True)

        # Check if local papers exist
        has_local_papers = paper_dir_path.exists() and any(paper_dir_path.glob("**/*.pdf"))

        # Adjust mode based on available resources
        if mode == "local" and not has_local_papers:
            return ToolResult(
                False, None,
                f"No local papers found in {paper_dir}. Use mode='online' or add PDFs."
            )

        if mode == "auto":
            actual_mode = "local_first" if has_local_papers else "online"
        else:
            actual_mode = mode

        # Create settings
        use_llm_during_parsing = ":free" not in config.paperqa_llm.lower()

        settings_kwargs = {
            "llm": config.paperqa_llm,
            "summary_llm": config.paperqa_llm,
            "embedding": embedding_config,
            "parsing": ParsingSettings(
                use_doc_details=use_llm_during_parsing,
                reader_config={
                    "chunk_chars": 3000,
                    "overlap": 100
                },
                multimodal=False,
                enrichment_llm=config.paperqa_llm,
            )
        }

        # Add answer settings
        if ":free" in config.paperqa_llm.lower():
            settings_kwargs["answer"] = AnswerSettings(
                answer_max_sources=min(max_sources, 3),
                evidence_k=5,
            )
        else:
            settings_kwargs["answer"] = AnswerSettings(
                answer_max_sources=max_sources,
                evidence_k=10
            )

        # Create settings hash to detect config changes
        settings_str = f"{config.paperqa_llm}|{embedding_config}|{use_llm_during_parsing}"
        settings_hash = hashlib.md5(settings_str.encode()).hexdigest()

        # Check if we need to reset cache due to settings change
        if _cached_docs_settings_hash != settings_hash:
            print("[CACHE] Settings changed, resetting caches", file=sys.stderr)
            _cached_docs = None
            _local_paper_index = None
            _online_papers_cache.clear()
            _cached_docs_settings_hash = settings_hash

        settings = Settings(**settings_kwargs)

        # ===================================================================
        # LOAD OR CREATE DOCS OBJECT FOR THIS QUESTION
        # ===================================================================
        docs_cache_file = question_cache_dir / "docs_cache.pkl"

        if docs_cache_file.exists():
            # Load cached Docs object
            try:
                import pickle
                with open(docs_cache_file, 'rb') as f:
                    docs = pickle.load(f)
                print(f"[CACHE] Loaded cached Docs ({len(docs.docs)} papers, "
                      f"{len(docs.texts)} text chunks)", file=sys.stderr)
            except Exception as e:
                print(f"[CACHE] Failed to load docs cache: {e}, creating new", file=sys.stderr)
                docs = Docs()
        else:
            print("[CACHE] Creating new Docs object for this question", file=sys.stderr)
            docs = Docs()
        sources_used = []
        cache_stats = {
            "local_cached": 0,
            "local_new": 0,
            "online_cached": 0,
            "online_new": 0
        }

        # ===================================================================
        # STAGE 1: Local Papers (via SearchIndex for caching)
        # ===================================================================
        if actual_mode in ["local", "hybrid", "local_first"]:
            # Build/load SearchIndex for local papers
            # Index is stored in the question-specific cache directory
            print(f"[CACHE] Building/loading SearchIndex for local papers", file=sys.stderr)

            # Configure index settings to use question-specific cache
            index_settings = IndexSettings(
                paper_directory=str(paper_dir_path),
                index_directory=str(local_index_dir),
                sync_with_paper_directory=True,  # Auto-sync on changes
            )
            settings.agent.index = index_settings

            # Build/load index asynchronously
            async def build_index():
                return await get_directory_index(settings=settings, build=True)

            local_index = asyncio.run(build_index())

            print(f"[CACHE] Index ready with {asyncio.run(local_index.count)} docs",
                  file=sys.stderr)

            # Query the index (returns Docs objects with embeddings already computed!)
            async def query_index():
                return await local_index.query(
                    query=question,
                    top_n=max_sources,
                    field_subset=["title", "body", "file_location"]
                )

            local_results = asyncio.run(query_index())

            # Add these docs to our main docs collection (only if not already there)
            for result_docs in local_results:
                for dockey, doc in result_docs.docs.items():
                    if dockey not in docs.docs:
                        # New paper - add it
                        async def add_texts():
                            await docs.aadd_texts(
                                texts=result_docs.texts,
                                doc=doc,
                                settings=settings,
                                embedding_model=settings.get_embedding_model()
                            )
                        asyncio.run(add_texts())
                        cache_stats["local_new"] += 1
                        print(f"[CACHE] Added new local paper: {doc.docname}",
                              file=sys.stderr)
                    else:
                        cache_stats["local_cached"] += 1

            if cache_stats["local_new"] + cache_stats["local_cached"] > 0:
                sources_used.append(
                    f"local_library ({cache_stats['local_new']} new, "
                    f"{cache_stats['local_cached']} cached)"
                )

            # Try answering with just local papers first (if local_first mode)
            if actual_mode == "local_first" and docs.docs:
                try:
                    async def query_local():
                        return await docs.aquery(question, settings=settings)

                    local_answer = asyncio.run(query_local())

                    has_good_answer = (
                        local_answer
                        and local_answer.contexts
                        and len(local_answer.contexts) > 0
                        and "cannot answer" not in local_answer.answer.lower()
                    )

                    if has_good_answer:
                        contexts = [
                            {
                                "text": ctx.context,
                                "citation": ctx.text.name,
                                "score": ctx.score
                            }
                            for ctx in local_answer.contexts
                        ]

                        return ToolResult(True, {
                            "answer": local_answer.answer,
                            "contexts": contexts,
                            "references": local_answer.references,
                            "sources_used": sources_used +
                                ["(local papers sufficient - skipped online search)"],
                            "mode": "local",
                            "cache_stats": cache_stats
                        })
                except Exception as e:
                    sources_used.append(f"(local query error: {str(e)[:50]})")

        # ===================================================================
        # STAGE 2: Online Papers (with deduplication cache)
        # ===================================================================
        if actual_mode in ["online", "hybrid", "local_first"]:
            import requests
            import urllib.parse
            import tempfile

            # Try Semantic Scholar
            try:
                s2_url = "https://api.semanticscholar.org/graph/v1/paper/search"
                params = {
                    "query": question,
                    "limit": max_sources,
                    "fields": "title,authors,year,abstract,openAccessPdf,externalIds"
                }

                headers = {}
                if s2_api_key := os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
                    headers["x-api-key"] = s2_api_key

                response = requests.get(s2_url, params=params, headers=headers, timeout=30)
                response.raise_for_status()
                papers_data = response.json().get("data", [])

                for paper in papers_data[:max_sources]:
                    try:
                        # Get DOI as cache key
                        external_ids = paper.get("externalIds", {})
                        doi = external_ids.get("DOI") or external_ids.get("ArXiv")

                        # Check cache - look for saved PDF in online_papers_dir
                        if doi:
                            # Create safe filename from DOI
                            safe_doi = doi.replace("/", "_").replace(":", "_")
                            cached_pdf = online_papers_dir / f"{safe_doi}.pdf"

                            if cached_pdf.exists():
                                # Already downloaded - check if in docs
                                doc_in_collection = any(
                                    safe_doi in str(doc.dockey)
                                    for doc in docs.docs.values()
                                )
                                if doc_in_collection:
                                    cache_stats["online_cached"] += 1
                                    print(f"[CACHE] Skipping cached paper: {doi}",
                                          file=sys.stderr)
                                    continue

                        # Get PDF URL
                        pdf_info = paper.get("openAccessPdf")
                        if not pdf_info or not pdf_info.get("url"):
                            arxiv_id = external_ids.get("ArXiv")
                            if arxiv_id:
                                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                            else:
                                continue
                        else:
                            pdf_url = pdf_info["url"]

                        # Build citation
                        title = paper.get("title", "Unknown")
                        year = paper.get("year", "")
                        authors = paper.get("authors", [])
                        author_names = ", ".join([a.get("name", "") for a in authors[:3]])
                        if len(authors) > 3:
                            author_names += " et al."
                        citation = f"{author_names}. {title}. {year}"

                        # Download PDF
                        pdf_headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                        }
                        pdf_response = requests.get(pdf_url, headers=pdf_headers, timeout=60)
                        pdf_response.raise_for_status()

                        # Verify it's a PDF
                        content_type = pdf_response.headers.get("Content-Type", "")
                        if "pdf" not in content_type.lower() and \
                           not pdf_response.content.startswith(b"%PDF"):
                            continue

                        # Save PDF to question-specific cache directory
                        safe_doi = doi.replace("/", "_").replace(":", "_") if doi else f"paper_{hash(title)}"
                        cached_pdf = online_papers_dir / f"{safe_doi}.pdf"

                        # Save PDF to cache
                        with open(cached_pdf, 'wb') as f:
                            f.write(pdf_response.content)

                        try:
                            async def add_paper():
                                return await docs.aadd(
                                    str(cached_pdf),
                                    citation=citation,
                                    dockey=safe_doi,  # Use DOI as dockey for tracking
                                    settings=settings
                                )

                            docname = asyncio.run(add_paper())
                            if docname:
                                cache_stats["online_new"] += 1
                                print(f"[CACHE] Added new online paper: {title[:50]}",
                                      file=sys.stderr)
                        except Exception as add_error:
                            print(f"[CACHE] Error adding paper: {add_error}", file=sys.stderr)

                    except Exception as e:
                        print(f"[CACHE] Error processing S2 paper: {e}", file=sys.stderr)
                        continue

                if cache_stats["online_new"] + cache_stats["online_cached"] > 0:
                    sources_used.append(
                        f"semantic_scholar ({cache_stats['online_new']} new, "
                        f"{cache_stats['online_cached']} cached)"
                    )

            except Exception as e:
                print(f"[CACHE] Semantic Scholar search failed: {e}", file=sys.stderr)

        # ===================================================================
        # FINAL QUERY
        # ===================================================================
        async def final_query():
            return await docs.aquery(question, settings=settings)

        answer_obj = asyncio.run(final_query())

        contexts = [
            {
                "text": ctx.context,
                "citation": ctx.text.name,
                "score": ctx.score
            }
            for ctx in answer_obj.contexts
        ]

        # ===================================================================
        # SAVE CACHE FOR NEXT ITERATION
        # ===================================================================
        try:
            import pickle
            with open(docs_cache_file, 'wb') as f:
                pickle.dump(docs, f)
            print(f"[CACHE] Saved Docs cache ({len(docs.docs)} papers)", file=sys.stderr)

            # Update metadata with usage stats
            metadata["last_used"] = time.time()
            metadata["total_papers"] = len(docs.docs)
            metadata["cache_stats"] = cache_stats
            with open(metadata_file, 'w') as f:
                f.write(json.dumps(metadata, indent=2))

        except Exception as e:
            print(f"[CACHE] Warning: Failed to save cache: {e}", file=sys.stderr)

        print(f"[CACHE] Final stats - Total papers in cache: {len(docs.docs)}",
              file=sys.stderr)
        print(f"[CACHE] Session stats: {cache_stats}", file=sys.stderr)
        print(f"[CACHE] Cache directory: {question_cache_dir}", file=sys.stderr)

        return ToolResult(True, {
            "answer": answer_obj.answer,
            "contexts": contexts,
            "references": answer_obj.references,
            "sources_used": sources_used,
            "mode": actual_mode,
            "cache_stats": cache_stats,
            "total_papers_cached": len(docs.docs),
            "cache_dir": str(question_cache_dir)
        })

    except ImportError:
        return ToolResult(False, None, "PaperQA not installed. Run: pip install paper-qa")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ToolResult(False, None, f"Literature search error: {str(e)}")
