"""Tool implementations for the bioinformatics agent."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Optional
import requests
import sys
import re
from io import StringIO
import signal
from contextlib import contextmanager
import os
import asyncio
import nest_asyncio
import csv
from datetime import datetime

# Allow nested event loops (needed for Paper-QA async calls)
nest_asyncio.apply()

# CRITICAL: Set environment variables at module level BEFORE any PaperQA imports
# LiteLLM reads these at import time, not runtime!
from dotenv import load_dotenv
load_dotenv()  # Load .env file to get OPENROUTER_KEY

# Ensure OPENROUTER_KEY is available for PaperQA/LiteLLM
# Note: LiteLLM expects OPENROUTER_KEY (not OPENROUTER_API_KEY) based on constants.py
if not os.getenv("OPENROUTER_KEY"):
    print("WARNING: OPENROUTER_KEY not set - PaperQA will fail", file=sys.stderr)
else:
    print(f"✓ OPENROUTER_KEY loaded: {os.getenv('OPENROUTER_KEY')[:15]}...", file=sys.stderr)

# Global cache for PaperQA Docs objects to reuse embeddings across queries
# Key: (paper_dir, llm, embedding_model) -> Docs object
_DOCS_CACHE: dict = {}


def _get_metadata_file(paper_dir: Path) -> Path:
    """Get path to metadata CSV file for tracking downloaded papers."""
    return paper_dir / "online_papers" / "metadata.csv"


def _get_failed_downloads_file(paper_dir: Path) -> Path:
    """Get path to failed downloads JSON file."""
    return paper_dir / "online_papers" / "failed_downloads.json"


def _load_failed_downloads(failed_file: Path) -> list:
    """Load list of previously failed downloads."""
    if failed_file.exists():
        with open(failed_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []


def _save_failed_download(failed_file: Path, entry: dict):
    """Record a failed download for later retry.
    
    Entry should contain: url, doi, arxiv_id, pmid, title, filename, source, reason, timestamp
    """
    failed_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Load existing failures
    failed_downloads = _load_failed_downloads(failed_file)
    
    # Add new failure
    entry['timestamp'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    failed_downloads.append(entry)
    
    # Save back
    with open(failed_file, 'w', encoding='utf-8') as f:
        json.dump(failed_downloads, f, indent=2, ensure_ascii=False)


def _remove_failed_download(failed_file: Path, identifier: str):
    """Remove a failed download entry after successful retry.
    
    Args:
        identifier: DOI, ArXiv ID, or PMID to identify the entry
    """
    if not failed_file.exists():
        return
    
    failed_downloads = _load_failed_downloads(failed_file)
    
    # Filter out the successfully downloaded paper
    failed_downloads = [
        entry for entry in failed_downloads
        if not any([
            entry.get('doi') == identifier,
            entry.get('arxiv_id') == identifier,
            entry.get('pmid') == identifier
        ])
    ]
    
    with open(failed_file, 'w', encoding='utf-8') as f:
        json.dump(failed_downloads, f, indent=2, ensure_ascii=False)


def _load_metadata(metadata_file: Path) -> dict:
    """Load metadata from CSV file.
    
    Returns dict with structure: {
        'doi:10.1038/xxx': {'doi': '10.1038/xxx', 'title': '...', 'filename': '...', ...},
        'arxiv:2103.12345': {...},
        'pmid:12345678': {...}
    }
    """
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Create key based on available IDs
                if row.get('doi'):
                    key = f"doi:{row['doi']}"
                elif row.get('arxiv_id'):
                    key = f"arxiv:{row['arxiv_id']}"
                elif row.get('pmid'):
                    key = f"pmid:{row['pmid']}"
                else:
                    continue
                metadata[key] = row
    return metadata


def _save_metadata_entry(metadata_file: Path, entry: dict):
    """Save a new entry to metadata CSV.
    
    Entry should contain: doi, arxiv_id, pmid, title, filename, source, download_date, manual
    """
    # Ensure directory exists
    metadata_file.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if file exists to determine if we need headers
    file_exists = metadata_file.exists()
    
    fieldnames = ['doi', 'arxiv_id', 'pmid', 'title', 'filename', 'source', 'download_date', 'manual']
    
    with open(metadata_file, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(entry)


def _get_pdf_url_from_unpaywall(doi: str) -> Optional[str]:
    """Try to get direct PDF URL from Unpaywall API using DOI.
    
    Args:
        doi: DOI of the paper (e.g., "10.1038/nature12345")
    
    Returns:
        Direct PDF URL if found, None otherwise
    """
    try:
        # Unpaywall API requires an email in the request
        email = os.getenv("UNPAYWALL_EMAIL", "research@example.com")
        unpaywall_url = f"https://api.unpaywall.org/v2/{doi}?email={email}"
        
        response = requests.get(unpaywall_url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Try best_oa_location first
        best_location = data.get("best_oa_location")
        if best_location and best_location.get("url_for_pdf"):
            return best_location["url_for_pdf"]
        
        # Fallback to first available oa_location
        oa_locations = data.get("oa_locations", [])
        for location in oa_locations:
            if location.get("url_for_pdf"):
                return location["url_for_pdf"]
        
        return None
    except Exception as e:
        print(f"[DEBUG] Unpaywall API failed: {e}", file=sys.stderr)
        return None


def _create_safe_filename(title: str, identifier: str, max_title_len: int = 50) -> str:
    """Create safe filename from title and identifier.
    
    Format: {identifier}_{title_50chars}.pdf
    Example: 10.1038_nature12345_T_Cell_Exhaustion_Mechanisms.pdf
    """
    # Clean title: only alphanumeric, spaces, hyphens, underscores
    clean_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    clean_title = clean_title.replace(' ', '_')
    
    # Truncate to max length
    if len(clean_title) > max_title_len:
        clean_title = clean_title[:max_title_len]
    
    # Clean identifier for filename
    clean_id = identifier.replace('/', '_').replace(':', '_')
    
    return f"{clean_id}_{clean_title}.pdf"


def _clean_question_for_pubmed(question: str) -> str:
    """Clean natural language question for PubMed search.
    
    PubMed's query parser interprets natural language question words
    as author names or misinterprets them as medical terms, causing 
    0 results or irrelevant results. This function removes problematic
    patterns while preserving the actual search terms.
    
    Args:
        question: Natural language question
    
    Returns:
        Cleaned query string suitable for PubMed
    
    Example:
        >>> _clean_question_for_pubmed("What is the mechanism of PARP inhibitors?")
        "mechanism PARP inhibitors"
    """
    # Convert to lowercase for pattern matching
    cleaned = question.lower()
    
    # Step 1: Remove question starters (at beginning of string)
    question_starters = [
        r'^what is the\s+',
        r'^what are the\s+',
        r'^what is\s+',
        r'^what are\s+',
        r'^how does the\s+',
        r'^how do the\s+',
        r'^how does\s+',
        r'^how do\s+',
        r'^why does the\s+',
        r'^why do the\s+',
        r'^why does\s+',
        r'^why do\s+',
        r'^can you\s+',
        r'^please\s+',
        r'^explain\s+',
        r'^describe\s+',
        r'^tell me about\s+',
    ]
    
    for pattern in question_starters:
        cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
    
    # Step 2: Remove filler words/phrases that PubMed misinterprets (anywhere in string)
    # These are interpreted as medical terms or cause overly specific queries
    filler_patterns = [
        r'\bspecifically\s+',  # "specifically" → sensitivity/specificity terms
        r'\bfocusing\s+on\s+',  # "focusing" → ocular accommodation
        r'\bfocusing\s+',
        r'\bfocused\s+on\s+',
        r'\bfocus\s+on\s+',
        r'\bversus\b',  # comparison words
        r'\bvs\b',
        r'\bv\.s\.\b',
        r'\bcompared\s+to\b',
        r'\bcompare\s+to\b',
        r'\bin\s+particular\b',
        r'\bespecially\b',
        r'\bseminal\s+papers?\b',  # "seminal paper(s)" - meta descriptions
        r'\bkey\s+papers?\b',
        r'\bimportant\s+papers?\b',
        r'\bfoundational\s+papers?\b',
        r'\bmajor\s+papers?\b',
        r'\bpapers?\s+for\b',  # "papers for X"
        r'\bpapers?\s+on\b',    # "papers on X"
        r'\bpapers?\s+about\b',
        r'\bliterature\s+on\b',
        r'\bresearch\s+on\b',
        r'\bstudies\s+on\b',
        r'\bstate-of-the-art\b',  # Hyphenated meta-phrase
        r'\bstate\s+of\s+the\s+art\b',  # Same without hyphens
    ]
    
    for pattern in filler_patterns:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # Step 3: Remove stop words that don't add search value
    stop_words = [r'\bof\b', r'\bthe\b', r'\ba\b', r'\ban\b', r'\band\b', r'\bor\b', r'\bin\b', r'\bon\b', r'\bat\b', r'\bto\b', r'\bfor\b']
    for pattern in stop_words:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # Step 4: Remove punctuation and normalize whitespace
    cleaned = re.sub(r'[?,;:\(\)]', ' ', cleaned)  # Remove punctuation
    cleaned = re.sub(r'\s+', ' ', cleaned)  # Collapse multiple spaces
    cleaned = cleaned.strip()
    
    # If cleaning removed everything, return simplified version of original
    if not cleaned or len(cleaned) < 3:
        # Last resort: just remove question words and keep the rest
        simple = re.sub(r'^(what|how|why|when|where|who)\s+(is|are|does|do|can)\s+(the\s+)?', '', question.lower(), flags=re.IGNORECASE)
        return simple.strip() if simple.strip() else question
    
    return cleaned


def _validate_pdf_file(pdf_path: Path) -> tuple[bool, str]:
    """Validate PDF file is complete and readable.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        (is_valid, error_message) tuple
    """
    try:
        # Check file exists and has content
        if not pdf_path.exists():
            return False, "File does not exist"
        
        file_size = pdf_path.stat().st_size
        if file_size < 1024:  # Less than 1KB is suspicious
            return False, f"File too small ({file_size} bytes)"
        
        # Check PDF header
        with open(pdf_path, 'rb') as f:
            header = f.read(4)
            if not header.startswith(b'%PDF'):
                return False, "Not a PDF file (invalid header)"
            
            # Try to read the end of file to check if complete
            # PDF files should end with %%EOF
            f.seek(max(0, file_size - 1024))  # Check last 1KB
            tail = f.read()
            if b'%%EOF' not in tail:
                return False, "Incomplete PDF (missing EOF marker)"
        
        # Try to open with pypdf to verify it's readable
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_path))
            # Try to access first page to ensure PDF is readable
            if len(reader.pages) == 0:
                return False, "PDF has no pages"
        except Exception as e:
            return False, f"PDF corrupted or unreadable: {str(e)[:50]}"
        
        return True, ""
    
    except Exception as e:
        return False, f"Validation error: {str(e)[:50]}"


class ToolResult:
    """Result wrapper for tool execution."""

    def __init__(self, success: bool, output: Any, error: Optional[str] = None):
        self.success = success
        self.output = output
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


class PersistentPythonExecutor:
    """Maintains a persistent Python environment across execute_python calls.

    This allows variables, imports, and state to persist between calls,
    enabling multi-step data analysis without reloading data.
    """

    def __init__(self):
        """Initialize the persistent Python environment."""
        self.globals_dict = {
            '__builtins__': __builtins__,
        }
        self.locals_dict = {}

    def execute(self, code: str, timeout: int = 30) -> tuple[bool, Optional[str], Optional[str]]:
        """Execute code in the persistent environment.

        Args:
            code: Python code to execute
            timeout: Execution timeout in seconds

        Returns:
            Tuple of (success, output, error)
        """
        # Import here to avoid circular dependency
        from src.utils.output_manager import get_current_run_dir

        # Capture stdout/stderr
        old_stdout = sys.stdout
        old_stderr = sys.stderr
        sys.stdout = StringIO()
        sys.stderr = StringIO()

        try:
            # Inject OUTPUT_DIR variable if a run directory is set
            # This allows agents to save files to the correct location without changing cwd
            run_dir = get_current_run_dir()
            if run_dir:
                self.globals_dict['OUTPUT_DIR'] = str(run_dir)
            else:
                # Fallback to current directory if no run directory is set
                self.globals_dict['OUTPUT_DIR'] = os.getcwd()

            # Execute code in persistent namespace
            exec(code, self.globals_dict, self.locals_dict)

            # Get output
            output = sys.stdout.getvalue()
            error = sys.stderr.getvalue()

            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            if error:
                return False, None, error

            return True, output.strip() if output else "Code executed successfully (no output)", None

        except Exception as e:
            # Restore stdout/stderr
            sys.stdout = old_stdout
            sys.stderr = old_stderr

            return False, None, f"Execution error: {type(e).__name__}: {str(e)}"

    def reset(self):
        """Reset the persistent environment (clears all variables)."""
        self.globals_dict = {
            '__builtins__': __builtins__,
        }
        self.locals_dict = {}


# Global persistent executor instance
_persistent_executor = PersistentPythonExecutor()

# ============================================================================
# LITERATURE SEARCH CACHING INFRASTRUCTURE
# ============================================================================
# These module-level caches persist across iterations to avoid re-processing
# papers that have already been indexed and embedded.
# ============================================================================

# Cache for SearchIndex (handles local PDF library with persistent disk storage)
_local_paper_index = None
_local_paper_index_dir = None

# Cache for online papers already downloaded and processed
# Key: (doi or url), Value: dockey
_online_papers_cache = {}

# Persistent Docs object that accumulates all papers (local + online)
_cached_docs = None
_cached_docs_settings_hash = None


def execute_python(code: str, timeout: int = 30, reset: bool = False) -> ToolResult:
    """Execute Python code in a persistent environment.

    Variables, imports, and state persist across calls, allowing multi-step
    analyses without reloading data.

    Args:
        code: Python code to execute
        timeout: Execution timeout in seconds (not strictly enforced in persistent mode)
        reset: If True, reset the persistent environment before execution

    Returns:
        ToolResult with output or error
    """
    global _persistent_executor

    if reset:
        _persistent_executor.reset()

    try:
        success, output, error = _persistent_executor.execute(code, timeout)

        if not success:
            return ToolResult(False, None, error)

        return ToolResult(True, output)

    except Exception as e:
        return ToolResult(False, None, f"Error executing code: {str(e)}")


def search_pubmed(query: str, max_results: int = 10, retmax: int = 100) -> ToolResult:
    """Search PubMed for articles.

    Args:
        query: Search query string
        max_results: Maximum results to return
        retmax: Maximum results to fetch from NCBI

    Returns:
        ToolResult with list of articles containing (title, author, journal, publish_year, doi)
    """
    import xml.etree.ElementTree as ET
    
    try:
        # NCBI E-utilities endpoints
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

        # Search for PMIDs
        search_params = {
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": retmax,
        }

        search_response = requests.get(search_url, params=search_params, timeout=10)
        search_response.raise_for_status()
        search_data = search_response.json()

        pmids = search_data.get("esearchresult", {}).get("idlist", [])[:max_results]

        if not pmids:
            return ToolResult(True, [])

        # Fetch full article details using efetch (includes abstracts)
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }

        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
        fetch_response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(fetch_response.content)

        articles = []
        for article in root.findall(".//PubmedArticle"):
            # Extract PMID
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else "N/A"
            
            # Extract title
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "N/A"
            
            # Extract journal information
            journal = "N/A"
            journal_elem = article.find(".//Journal/Title")
            if journal_elem is None:
                journal_elem = article.find(".//Journal/ISOAbbreviation")
            if journal_elem is not None:
                journal = journal_elem.text
            
            # Extract authors (format: "Author1, Author2, Author3 et al." if more than 3)
            authors = []
            for author in article.findall(".//Author")[:3]:
                last_name = author.find(".//LastName")
                initials = author.find(".//Initials")
                if last_name is not None:
                    author_name = last_name.text
                    if initials is not None:
                        author_name += f" {initials.text}"
                    authors.append(author_name)
            
            # Format author string
            if len(authors) == 0:
                author_str = "N/A"
            elif len(authors) <= 3:
                author_str = ", ".join(authors)
                # Check if there are more authors
                all_authors = article.findall(".//Author")
                if len(all_authors) > 3:
                    author_str += " et al."
            else:
                author_str = ", ".join(authors) + " et al."
            
            # Extract publication year
            publish_year = "N/A"
            pub_date = article.find(".//PubDate")
            if pub_date is not None:
                year = pub_date.find("Year")
                if year is not None:
                    publish_year = year.text
            
            # Extract DOI
            doi = "N/A"
            # Look for DOI in ArticleIdList
            for article_id in article.findall(".//ArticleId"):
                id_type = article_id.get("IdType")
                if id_type == "doi":
                    doi = article_id.text
                    break
            
            # Also check in ELocationID for DOI
            if doi == "N/A":
                for elocation in article.findall(".//ELocationID"):
                    eid_type = elocation.get("EIdType")
                    if eid_type == "doi":
                        doi = elocation.text
                        break
            
            # Extract abstract (for backwards compatibility)
            abstract_parts = []
            for abstract_text in article.findall(".//AbstractText"):
                # Check for labeled sections (e.g., BACKGROUND, METHODS)
                label = abstract_text.get("Label", "")
                text = abstract_text.text or ""
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else "N/A"

            articles.append({
                "title": title,
                "author": author_str,
                "journal": journal,
                "publish_year": publish_year,
                "doi": doi,
                # Keep backwards compatibility fields
                "pmid": pmid,
                "authors": authors,  # Keep original list format for compatibility
                "pubdate": publish_year,  # Alias for backwards compatibility
                "abstract": abstract,
            })

        return ToolResult(True, articles)

    except Exception as e:
        return ToolResult(False, None, f"PubMed search error: {str(e)}")


def _chunked_search(file_path: str, sep: str, column: str, search_value: str, limit: int = 10, chunk_size: int = 10000, max_chunks: int = 50) -> tuple[list, int]:
    """Search a large file in chunks until enough results are found.

    Args:
        file_path: Path to the file
        sep: Delimiter
        column: Column to search in
        search_value: Value to search for
        limit: Maximum results to return
        chunk_size: Rows per chunk
        max_chunks: Maximum chunks to search (safety limit)

    Returns:
        Tuple of (results_list, total_rows_searched)
    """
    import pandas as pd

    results = []
    total_searched = 0

    for chunk in pd.read_csv(file_path, sep=sep, chunksize=chunk_size, low_memory=False):
        total_searched += len(chunk)

        # Search this chunk
        matches = chunk[chunk[column].astype(str).str.contains(search_value, case=False, na=False)]
        results.extend(matches.to_dict('records'))

        # Stop if we have enough results
        if len(results) >= limit:
            return results[:limit], total_searched

        # Safety limit
        if total_searched >= chunk_size * max_chunks:
            break

    return results, total_searched


def query_database(db_name: str, query: str, limit: int = 10, data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data") -> ToolResult:
    """Query a local database file.

    Args:
        db_name: Database name (e.g., 'drugbank', 'bindingdb', 'pharos', 'string', 'gwas')
        query: Query string - can be:
               - Column name to search (e.g., 'Target Name:EGFR')
               - 'info' to get database info (shape, columns, sample)
               - 'all' to get first N rows
        limit: Maximum rows to return (default: 10)
        data_dir: Path to database files

    Returns:
        ToolResult with query results. For searches, includes 'rows_searched' to show coverage.
    """
    try:
        import pandas as pd

        db_name_lower = db_name.lower()
        data_path = Path(data_dir)

        # Handle different databases based on their actual file structure
        if db_name_lower == "bindingdb":
            file_path = data_path / "Drug" / "BindingDB" / "BindingDB_All.tsv"
            if not file_path.exists():
                return ToolResult(False, None, f"BindingDB file not found at {file_path}")

            # For large files, read with chunksize or nrows
            if query.lower() == "info":
                df_sample = pd.read_csv(file_path, sep="\t", nrows=5, low_memory=False)
                return ToolResult(True, {
                    "database": "BindingDB",
                    "file": str(file_path),
                    "columns": df_sample.columns.tolist(),
                    "sample": df_sample.to_dict('records')
                })
            elif ":" in query:
                # Column-based search: "Target Name:EGFR"
                col, value = query.split(":", 1)
                # Use chunked search to iteratively search through file
                results, rows_searched = _chunked_search(file_path, "\t", col, value, limit=limit)
                return ToolResult(True, {
                    "count": len(results),
                    "rows_searched": rows_searched,
                    "results": results,
                    "message": f"Searched {rows_searched:,} rows, found {len(results)} matches"
                })
            else:
                df = pd.read_csv(file_path, sep="\t", nrows=limit, low_memory=False)
                return ToolResult(True, df.to_dict('records'))

        elif db_name_lower == "drugbank":
            drugbank_path = data_path / "Drug" / "DrugBank"
            if not drugbank_path.exists():
                return ToolResult(False, None, f"DrugBank directory not found at {drugbank_path}")

            # List available files
            if query.lower() == "info":
                files = [f.name for f in drugbank_path.glob("*.parquet")]
                return ToolResult(True, {
                    "database": "DrugBank",
                    "available_files": files,
                    "message": "Use query like 'file:interactions' to query specific file"
                })
            elif query.lower().startswith("file:"):
                # Query specific file: "file:interactions"
                file_name = query.split(":", 1)[1].strip()
                file_path = drugbank_path / f"{file_name}.parquet"
                if not file_path.exists():
                    return ToolResult(False, None, f"File {file_name}.parquet not found")
                df = pd.read_parquet(file_path)
                return ToolResult(True, {
                    "file": file_name,
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "sample": df.head(limit).to_dict('records')
                })
            else:
                # Default to interactions file
                file_path = drugbank_path / "interactions.parquet"
                df = pd.read_parquet(file_path)
                return ToolResult(True, {
                    "file": "interactions",
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "sample": df.head(limit).to_dict('records')
                })

        elif db_name_lower == "pharos":
            pharos_path = data_path / "Drug" / "Pharos"
            if not pharos_path.exists():
                return ToolResult(False, None, f"Pharos directory not found at {pharos_path}")

            if query.lower() == "info":
                files = [f.name for f in pharos_path.glob("*.csv")]
                return ToolResult(True, {
                    "database": "Pharos",
                    "available_files": files,
                    "message": "Use query like 'file:pharos_drugs' to query specific file"
                })
            elif query.lower().startswith("file:"):
                file_name = query.split(":", 1)[1].strip()
                file_path = pharos_path / f"{file_name}.csv"
                if not file_path.exists():
                    return ToolResult(False, None, f"File {file_name}.csv not found")
                df = pd.read_csv(file_path, nrows=limit, low_memory=False)
                return ToolResult(True, {
                    "file": file_name,
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "sample": df.to_dict('records')
                })
            else:
                # Default to drugs file
                file_path = pharos_path / "pharos_drugs.csv"
                df = pd.read_csv(file_path, nrows=limit, low_memory=False)
                return ToolResult(True, {
                    "file": "pharos_drugs",
                    "columns": df.columns.tolist(),
                    "sample": df.to_dict('records')
                })

        elif db_name_lower == "gwas":
            file_path = data_path / "GWAS" / "gwas_catalog_association.tsv"
            if not file_path.exists():
                return ToolResult(False, None, f"GWAS file not found at {file_path}")

            if query.lower() == "info":
                df_sample = pd.read_csv(file_path, sep="\t", nrows=5, low_memory=False)
                return ToolResult(True, {
                    "database": "GWAS",
                    "file": str(file_path),
                    "columns": df_sample.columns.tolist(),
                    "sample": df_sample.to_dict('records')
                })
            elif ":" in query:
                # Column-based search with chunked iteration
                col, value = query.split(":", 1)
                results, rows_searched = _chunked_search(file_path, "\t", col, value, limit=limit)
                return ToolResult(True, {
                    "count": len(results),
                    "rows_searched": rows_searched,
                    "results": results,
                    "message": f"Searched {rows_searched:,} rows, found {len(results)} matches"
                })
            else:
                df = pd.read_csv(file_path, sep="\t", nrows=limit, low_memory=False)
                return ToolResult(True, df.to_dict('records'))

        elif db_name_lower == "string" or db_name_lower == "stringdb":
            string_path = data_path / "PPI" / "StringDB"
            if not string_path.exists():
                # Try alternative paths
                alt_path = data_path / "StringDB"
                if alt_path.exists():
                    string_path = alt_path
                else:
                    return ToolResult(False, None,
                        f"STRING directory not found. Searched:\n"
                        f"  - {string_path}\n"
                        f"  - {alt_path}\n"
                        f"Expected structure: {{data_dir}}/PPI/StringDB/")

            if query.lower() == "info":
                files = [f.name for f in string_path.glob("*.txt")]
                return ToolResult(True, {
                    "database": "STRING",
                    "available_files": files,
                    "message": "Use query like 'file:sapiens.9606.protein.info.v12.0' to query specific file"
                })
            elif query.lower().startswith("file:"):
                file_name = query.split(":", 1)[1].strip()
                file_path = string_path / f"{file_name}.txt"
                if not file_path.exists():
                    return ToolResult(False, None, f"File {file_name}.txt not found")
                # STRING files use space delimiter for interactions, tab for others
                sep = " " if "links" in file_name else "\t"
                df = pd.read_csv(file_path, sep=sep, nrows=limit, low_memory=False)
                return ToolResult(True, {
                    "file": file_name,
                    "shape": df.shape,
                    "columns": df.columns.tolist(),
                    "sample": df.to_dict('records')
                })
            else:
                # Default to protein info
                file_path = string_path / "sapiens.9606.protein.info.v12.0.txt"
                df = pd.read_csv(file_path, sep="\t", nrows=limit, low_memory=False)
                return ToolResult(True, {
                    "file": "protein.info",
                    "columns": df.columns.tolist(),
                    "sample": df.to_dict('records')
                })
        else:
            return ToolResult(False, None, f"Unknown database: {db_name}. Available: bindingdb, drugbank, pharos, gwas, string")

    except Exception as e:
        return ToolResult(False, None, f"Database query error: {str(e)}")


def read_file(file_path: str, input_dir: str = "./data") -> ToolResult:
    """Read a file from the input data directory.

    Args:
        file_path: Path to file (relative to input directory)
        input_dir: Base directory for question-specific input data

    Returns:
        ToolResult with file contents
    """
    try:
        data_dir = Path(input_dir)
        target_path = (data_dir / file_path).resolve()

        # Security check: ensure we're reading within data directory
        if not str(target_path).startswith(str(data_dir.resolve())):
            return ToolResult(False, None, "Access denied: path outside input directory")

        if not target_path.exists():
            return ToolResult(False, None, f"File not found: {file_path}")

        # Handle different file types
        if target_path.suffix == ".parquet":
            import pandas as pd
            df = pd.read_parquet(target_path)
            return ToolResult(True, {
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "head": df.head().to_dict('records'),
            })

        elif target_path.suffix in [".csv", ".tsv"]:
            import pandas as pd
            sep = "\t" if target_path.suffix == ".tsv" else ","
            df = pd.read_csv(target_path, sep=sep, low_memory=False)
            return ToolResult(True, {
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "head": df.head().to_dict('records'),
            })

        else:
            # Text file
            with open(target_path, "r") as f:
                content = f.read()
            return ToolResult(True, content)

    except Exception as e:
        return ToolResult(False, None, f"File read error: {str(e)}")


def find_files(
    pattern: Optional[str] = None,
    category: Optional[str] = None,
    extension: Optional[str] = None,
    name_contains: Optional[str] = None,
    question_context: Optional[str] = None,
    workspace_root: str = ".",
    data_dir: Optional[str] = None
) -> ToolResult:
    """Intelligently find relevant files in workspace without repeated directory traversal.
    
    This tool maintains an index of workspace files for efficient discovery.
    Much faster than multiple execute_python + os.listdir() calls.
    
    Args:
        pattern: Glob pattern to match (e.g., '**/Q5/*.csv', '**/*exhaustion*.csv')
        category: Filter by type: 'data', 'config', 'script', 'doc'
        extension: File extension (e.g., 'csv', '.csv', 'parquet')
        name_contains: Find files with this in the name (case-insensitive)
        question_context: Research question - will score files by relevance
        workspace_root: Workspace root directory (default: current directory)
        data_dir: Separate data directory to index (e.g., /path/to/Competition_Data)
        
    Returns:
        ToolResult with list of file paths and metadata
        
    Examples:
        find_files(extension='csv', question_context='T-cell exhaustion')
        find_files(pattern='**/Q5/*.csv')
        find_files(category='data', name_contains='DEG')
    """
    try:
        from src.utils.file_index import get_file_index
        
        # Get or create file index
        index = get_file_index(workspace_root, data_dir)
        
        if question_context:
            # Smart search based on question
            file_metadata = index.get_data_files(question_context=question_context)
        else:
            # Manual search by criteria
            file_metadata = index.find_files(
                pattern=pattern,
                category=category,
                extension=extension,
                name_contains=name_contains
            )
        
        # Format results for readability
        results = []
        for meta in file_metadata:
            results.append({
                "path": meta.path,
                "name": meta.name,
                "type": f"{meta.category}/{meta.subcategory}" if meta.subcategory else meta.category,
                "size_mb": round(meta.size_bytes / (1024 * 1024), 2)
            })
            
        summary = {
            "total_files": len(results),
            "files": results[:50]  # Limit to top 50 to avoid overwhelming output
        }
        
        if len(results) > 50:
            summary["note"] = f"Showing top 50 of {len(results)} files. Refine search if needed."
            
        return ToolResult(True, summary)
        
    except Exception as e:
        return ToolResult(False, None, f"File search error: {str(e)}")


def _simple_pubmed_search(question: str, max_results: int = 5) -> ToolResult:
    """Simple PubMed search that returns abstracts only (lightweight fallback).
    
    Used when no local papers are available to avoid expensive full-text processing.
    """
    try:
        import xml.etree.ElementTree as ET
        import urllib.parse
        
        print("[INFO] Performing lightweight PubMed abstract search", file=sys.stderr)
        
        # Search PubMed
        search_term = urllib.parse.quote(question)
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_term}&retmode=json&retmax={max_results}"
        
        search_response = requests.get(search_url, timeout=30)
        search_response.raise_for_status()
        search_data = search_response.json()
        
        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        
        if not pmids:
            return ToolResult(True, {
                "answer": "No papers found in PubMed for this query.",
                "contexts": [],
                "references": [],
                "sources_used": ["pubmed (0 results)"],
                "mode": "simple_pubmed"
            })
        
        # Fetch paper details
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }
        
        fetch_response = requests.get(fetch_url, params=fetch_params, timeout=15)
        fetch_response.raise_for_status()
        
        root = ET.fromstring(fetch_response.content)
        
        papers = []
        for article in root.findall(".//PubmedArticle"):
            pmid_elem = article.find(".//PMID")
            pmid = pmid_elem.text if pmid_elem is not None else "N/A"
            
            title_elem = article.find(".//ArticleTitle")
            title = title_elem.text if title_elem is not None else "N/A"
            
            # Extract abstract
            abstract_parts = []
            for abstract_text in article.findall(".//AbstractText"):
                text = abstract_text.text or ""
                label = abstract_text.get("Label", "")
                if label:
                    abstract_parts.append(f"{label}: {text}")
                else:
                    abstract_parts.append(text)
            abstract = " ".join(abstract_parts) if abstract_parts else "N/A"
            
            # Extract authors
            authors = []
            for author in article.findall(".//Author")[:3]:
                last_name = author.find(".//LastName")
                initials = author.find(".//Initials")
                if last_name is not None:
                    author_name = last_name.text
                    if initials is not None:
                        author_name += f" {initials.text}"
                    authors.append(author_name)
            
            if len(authors) == 0:
                author_str = "N/A"
            else:
                author_str = ", ".join(authors)
                all_authors = article.findall(".//Author")
                if len(all_authors) > 3:
                    author_str += " et al."
            
            # Extract year
            publish_year = "N/A"
            pub_date = article.find(".//PubDate")
            if pub_date is not None:
                year = pub_date.find("Year")
                if year is not None:
                    publish_year = year.text
            
            papers.append({
                "pmid": pmid,
                "title": title,
                "authors": author_str,
                "year": publish_year,
                "abstract": abstract
            })
        
        # Create a simple answer from the abstracts
        answer_parts = ["Based on PubMed abstracts (no local papers available):\n"]
        references = []
        contexts = []
        
        for i, paper in enumerate(papers, 1):
            answer_parts.append(f"\n{i}. {paper['title']} ({paper['authors']}, {paper['year']})")
            if paper['abstract'] != "N/A":
                answer_parts.append(f"   Abstract: {paper['abstract'][:300]}...")
            
            references.append(f"[{i}] {paper['authors']}. {paper['title']}. PMID: {paper['pmid']} ({paper['year']})")
            contexts.append({
                "text": paper['abstract'],
                "citation": f"{paper['authors']} ({paper['year']})",
                "score": None
            })
        
        return ToolResult(True, {
            "answer": "\n".join(answer_parts),
            "contexts": contexts,
            "references": references,
            "sources_used": [f"pubmed_abstracts ({len(papers)} papers)"],
            "mode": "simple_pubmed"
        })
        
    except Exception as e:
        return ToolResult(False, None, f"PubMed search error: {str(e)}")


def search_literature(
    question: str,
    mode: str = "auto",
    paper_dir: Optional[str] = None,
    max_sources: int = 10
) -> ToolResult:
    """Advanced literature search using PaperQA with local PDFs and/or internet search.

    This tool provides deep literature analysis by:
    - **PRIORITIZING** local PDF library (if available) 
    - Searching online databases (PubMed, arXiv) only if local papers insufficient
    - Reading full-text papers (not just abstracts)
    - Generating cited, evidence-based answers

    Search Strategy (mode='auto', RECOMMENDED):
    1. First queries local PDF library
    2. If local papers provide good answer → returns immediately (faster, more focused)
    3. If local papers insufficient → supplements with online search
    
    This ensures your curated local papers are always checked first!

    Args:
        question: Research question to answer (natural language)
        mode: Search mode:
            - 'auto' (default): Prioritize local, supplement with online if needed
            - 'local': Only local PDFs
            - 'online': Skip local, only internet search
            - 'hybrid': Search both simultaneously (no prioritization)
        paper_dir: Directory containing local PDF papers (uses config default if None)
        max_sources: Maximum number of papers to download and analyze (default: 10)

    Returns:
        ToolResult with:
        - answer: Evidence-based answer with citations
        - contexts: List of relevant text passages from papers
        - references: Bibliography of cited papers
        - sources_used: Information about which sources were queried

    Note: More rigorous than search_pubmed as it reads full papers and synthesizes answers.
    """
    try:
        # Lazy import to avoid loading PaperQA unless needed
        from paperqa import Docs, Settings
        from paperqa.settings import AnswerSettings
        from pathlib import Path

        # Get configuration
        from src.config import get_global_config
        config = get_global_config()

        # IMPORTANT: Check embedding config format
        # PaperQA v5.x expects "st-model-name" for SentenceTransformer models
        # NOT "sentence-transformers/model-name"
        embedding_config = config.paperqa_embedding
        
        # Determine if using local embeddings based on "st-" prefix
        using_local_embeddings = embedding_config.startswith("st-")

        # CRITICAL FIX: Explicitly set API keys in os.environ for LiteLLM
        # LiteLLM checks os.environ at runtime, not just at import
        # For OpenRouter models, LiteLLM uses OpenAI client with custom base_url
        # The OpenAI client looks for OPENAI_API_KEY, so we must set it!
        if config.paperqa_llm.startswith("openrouter/"):
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
            if not api_key:
                return ToolResult(
                    False,
                    None,
                    "OPENROUTER_API_KEY not found. Set it in .env file or environment."
                )
            # Set all API key variants for maximum compatibility
            os.environ["OPENROUTER_API_KEY"] = api_key
            os.environ["OPENROUTER_KEY"] = api_key
            # CRITICAL: For openrouter/ models, LiteLLM uses OpenAI client internally
            # which expects OPENAI_API_KEY to be set!
            os.environ["OPENAI_API_KEY"] = api_key
            print(f"[DEBUG] Set API keys in os.environ (OPENROUTER_API_KEY, OPENAI_API_KEY): {api_key[:15]}...", file=sys.stderr)

        # For non-local embeddings, also need the API key
        if not using_local_embeddings and embedding_config.startswith("openrouter/"):
            api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENROUTER_KEY")
            if not api_key:
                return ToolResult(
                    False,
                    None,
                    "OPENROUTER_API_KEY needed for OpenRouter embeddings. Use local embeddings (st-model-name) to avoid API calls."
                )
            os.environ["OPENROUTER_API_KEY"] = api_key
            os.environ["OPENROUTER_KEY"] = api_key

        # Use provided paper_dir or fall back to config
        if paper_dir is None:
            paper_dir = config.paper_library_dir

        paper_dir_path = Path(paper_dir)
        
        # Create online_papers subdirectory for downloaded papers
        online_papers_dir = paper_dir_path / "online_papers"
        online_papers_dir.mkdir(parents=True, exist_ok=True)

        # Check if papers exist (only in online_papers directory)
        # User indicated they won't use separate local papers
        has_local_papers = online_papers_dir.exists() and any(online_papers_dir.glob("*.pdf"))

        # Adjust mode based on available resources
        if mode == "local" and not has_local_papers:
            return ToolResult(
                False,
                None,
                f"No papers found in {online_papers_dir}. Use mode='online' to download papers."
            )

        if mode == "auto":
            if has_local_papers:
                # Auto mode with papers: prioritize local, supplement with online if needed
                actual_mode = "smart"
            else:
                # Auto mode with no papers: go online directly
                actual_mode = "online"
        else:
            actual_mode = mode

        # embedding_config was already set earlier (before API key checks)
        # No need to process it again here

        # Debug: Print what we're actually using
        print(f"[DEBUG] PaperQA LLM: {config.paperqa_llm}", file=sys.stderr)
        print(f"[DEBUG] PaperQA Embedding: {embedding_config}", file=sys.stderr)
        print(f"[DEBUG] Using local embeddings: {using_local_embeddings}", file=sys.stderr)

        # For local embeddings, verify sentence-transformers is installed
        if using_local_embeddings:
            try:
                import sentence_transformers
                print(f"[DEBUG] sentence-transformers version: {sentence_transformers.__version__}", file=sys.stderr)
            except ImportError:
                return ToolResult(
                    False,
                    None,
                    "Local embeddings require sentence-transformers. Install with: pip install sentence-transformers"
                )

        # Create settings - LiteLLM will automatically use OPENROUTER_KEY from environment
        # CRITICAL: Disable LLM usage during PDF parsing to avoid API calls
        # The LLM will ONLY be used during the query phase (docs.aquery())
        from paperqa.settings import ParsingSettings

        # Determine if we should use LLM during parsing based on model tier
        # For paid models, enable LLM for better document details extraction
        # For free models, disable to avoid rate limits
        use_llm_during_parsing = ":free" not in config.paperqa_llm.lower()

        settings_kwargs = {
            "llm": config.paperqa_llm,
            "summary_llm": config.paperqa_llm,  # Use same LLM for summaries
            "embedding": embedding_config,
            "parsing": ParsingSettings(
                use_doc_details=use_llm_during_parsing,  # Enable LLM for document metadata extraction (paid models only)
                reader_config={
                    "chunk_chars": 3000,  # Standard chunk size (in characters, not tokens)
                    "overlap": 100  # Standard overlap
                },
                multimodal=False,  # Disable image/figure processing for now
                enrichment_llm=config.paperqa_llm,  # Use same LLM for enrichment (vision tasks)
            )
        }

        # Reduce token usage if using free model
        if ":free" in config.paperqa_llm.lower():
            settings_kwargs["answer"] = AnswerSettings(
                answer_max_sources=min(max_sources, 3),  # Reduce sources for free models
                evidence_k=5,  # Reduce evidence contexts
            )
        else:
            settings_kwargs["answer"] = AnswerSettings(
                answer_max_sources=max_sources,
                evidence_k=10
            )

        settings = Settings(**settings_kwargs)
        llm_status = "LLM enabled for metadata extraction" if settings.parsing.use_doc_details else "LLM disabled during PDF loading"
        print(f"[DEBUG] Parsing config: use_doc_details={settings.parsing.use_doc_details} ({llm_status})", file=sys.stderr)

        # Check cache for existing Docs instance (embedding reuse across queries)
        # Cache key = (paper_dir, llm_model, embedding_model)
        # This avoids expensive PDF re-parsing and re-embedding for repeated queries
        cache_key = (str(paper_dir_path), config.paperqa_llm, embedding_config)
        using_cached_docs = False
        print(f"[DEBUG] Cache key: {cache_key}", file=sys.stderr)
        print(f"[DEBUG] Cache has {len(_DOCS_CACHE)} entries", file=sys.stderr)
        print(f"[DEBUG] Cache contains this key: {cache_key in _DOCS_CACHE}", file=sys.stderr)
        if cache_key in _DOCS_CACHE:
            print("[INFO] Reusing cached embeddings from previous queries", file=sys.stderr)
            docs = _DOCS_CACHE[cache_key]
            using_cached_docs = True
        else:
            print("[INFO] Creating new document collection (first time)", file=sys.stderr)
            docs = Docs()

        sources_used = []
        local_answer = None
        should_supplement_online = False

        # STAGE 1: Load existing papers from online_papers directory
        # Skip if using cached docs (already has PDFs loaded)
        if actual_mode in ["local", "hybrid", "local_first", "smart"] and not using_cached_docs:
            import time
            pdf_count = 0
            pdf_errors = []
            # Only search in online_papers directory
            for pdf_file in online_papers_dir.glob("*.pdf"):
                # Validate PDF before attempting to load
                is_valid, error_msg = _validate_pdf_file(pdf_file)
                if not is_valid:
                    print(f"[WARNING] Skipping corrupted PDF: {pdf_file.name}", file=sys.stderr)
                    print(f"[WARNING] Reason: {error_msg}", file=sys.stderr)
                    print(f"[WARNING] Deleting corrupted file: {pdf_file.name}", file=sys.stderr)
                    try:
                        pdf_file.unlink()  # Delete corrupted file
                    except Exception as e:
                        print(f"[ERROR] Failed to delete corrupted file: {e}", file=sys.stderr)
                    pdf_errors.append(f"{pdf_file.name}: {error_msg} (deleted)")
                    continue
                
                # Retry with exponential backoff for rate limit errors
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        print(f"[DEBUG] Loading PDF: {pdf_file.name}...", file=sys.stderr)
                        # Provide a basic citation - LLM may be used for metadata extraction if use_doc_details=True
                        simple_citation = f"{pdf_file.stem}, Local PDF"
                        # Paper-QA v5+ uses async aadd instead of sync add
                        asyncio.run(docs.aadd(str(pdf_file), citation=simple_citation, settings=settings))
                        pdf_count += 1
                        llm_used_msg = "with LLM metadata extraction" if settings.parsing.use_doc_details else "no LLM call"
                        print(f"[DEBUG] Successfully loaded {pdf_file.name} ({llm_used_msg})", file=sys.stderr)
                        break  # Success, move to next PDF
                    except Exception as e:
                        error_str = str(e).lower()
                        # Detailed error logging
                        print(f"[DEBUG] Error loading {pdf_file.name}: {str(e)}", file=sys.stderr)
                        import traceback
                        traceback.print_exc()

                        # Check if it's a rate limit error
                        if "rate" in error_str or "429" in error_str:
                            if attempt < max_retries - 1:
                                # Exponential backoff: 2, 4, 8 seconds
                                wait_time = 2 ** (attempt + 1)
                                print(f"[DEBUG] Rate limit hit, retrying in {wait_time}s...", file=sys.stderr)
                                time.sleep(wait_time)
                                continue  # Retry
                        # Non-rate-limit error or final retry failed
                        # Include more error details for diagnosis
                        error_msg = str(e)
                        if "api_key" in error_str:
                            error_msg = f"API key error: {error_msg}"
                        pdf_errors.append(f"{pdf_file.name}: {error_msg}")
                        break  # Don't retry non-rate-limit errors

            sources_used.append(f"local_library ({pdf_count} PDFs)")
            
            # Save to cache (only if loaded for the first time)
            if cache_key not in _DOCS_CACHE and pdf_count > 0:
                _DOCS_CACHE[cache_key] = docs
                print(f"[INFO] Cached document collection for future queries", file=sys.stderr)

            # Report errors if any PDFs failed to load
            if pdf_errors and pdf_count == 0:
                error_details = '\n'.join(pdf_errors[:3])
                diagnosis = "\n\nDiagnosis:\n"
                if any("api_key" in e.lower() for e in pdf_errors):
                    diagnosis += "- API key not found by LiteLLM during PDF processing\n"
                    diagnosis += f"- OPENROUTER_API_KEY in env: {bool(os.getenv('OPENROUTER_API_KEY'))}\n"
                    diagnosis += f"- OPENROUTER_KEY in env: {bool(os.getenv('OPENROUTER_KEY'))}\n"
                    diagnosis += f"- Using local embeddings: {using_local_embeddings}\n"
                    if using_local_embeddings:
                        diagnosis += "- Local embeddings should NOT require API key\n"
                        diagnosis += "- This suggests PaperQA is making unexpected API calls\n"
                        diagnosis += "- Try: pip install --upgrade paper-qa sentence-transformers\n"

                return ToolResult(
                    False,
                    None,
                    f"Failed to load any PDFs from {paper_dir}.\n\nErrors:\n{error_details}{diagnosis}"
                )
        
        # If using cached docs, still need to set pdf_count for later logic
        elif using_cached_docs and actual_mode in ["local", "hybrid", "local_first", "smart"]:
            pdf_count = len(list(online_papers_dir.glob("*.pdf")))
            sources_used.append(f"local_library ({pdf_count} PDFs, from cache)")
        else:
            pdf_count = 0
            
        # Query local papers (whether newly loaded or from cache)
        if actual_mode in ["local", "hybrid", "local_first", "smart"] and (pdf_count > 0 or using_cached_docs):
                try:
                    print(f"[DEBUG] Querying with LLM: {settings.llm}", file=sys.stderr)
                    print(f"[DEBUG] Querying with embedding: {settings.embedding}", file=sys.stderr)
                    # Paper-QA v5+ uses async aquery instead of sync query
                    local_answer = asyncio.run(docs.aquery(question, settings=settings))

                    # Evaluate local answer quality for smart mode
                    # WHAT IS A CONTEXT?
                    # - Context = a relevant passage/chunk from a paper that was used to answer the question
                    # - Each context represents evidence found in the papers (typically 200-500 words)
                    # - More contexts = more evidence from papers = more comprehensive answer
                    # - PaperQA retrieves multiple contexts and synthesizes them into an answer
                    
                    has_contexts = local_answer and local_answer.contexts and len(local_answer.contexts) > 0
                    cannot_answer = "cannot answer" in local_answer.answer.lower() if local_answer else True
                    
                    # Quality criteria for HIGH QUALITY answer:
                    # 1. contexts >= 3: Found evidence in multiple passages/papers (comprehensive)
                    #    NOTE: This threshold is a heuristic and can be adjusted:
                    #    - For broad topics, may want 5+ contexts
                    #    - For narrow/specific topics, 2+ contexts may suffice
                    #    - Current setting (3) is a balanced default for most scientific queries
                    # 2. answer length >= 100 chars: Detailed explanation, not just a brief sentence
                    # 3. no "cannot answer": Successfully found and synthesized information
                    # 
                    # WHY ANSWER LENGTH MATTERS:
                    # - Short answers (<100 chars) are often incomplete or vague
                    # - Longer answers indicate PaperQA found sufficient evidence to elaborate
                    # - This is a simple heuristic but effective for filtering superficial responses
                    # - Can be adjusted based on query complexity
                    is_high_quality = (
                        has_contexts
                        and len(local_answer.contexts) >= 3  # Multiple evidence sources
                        and len(local_answer.answer) >= 100  # Sufficiently detailed answer
                        and not cannot_answer
                    )
                    
                    # ACCEPTABLE quality (but might benefit from online supplement):
                    # - At least 1 context found (some evidence)
                    # - Can answer the question (not "cannot answer")
                    # - But might be incomplete or lack depth
                    is_acceptable_quality = (
                        has_contexts
                        and len(local_answer.contexts) >= 1
                        and not cannot_answer
                    )
                    
                    # Smart mode decision: evaluate quality and decide if online supplement needed
                    if actual_mode == "smart":
                        if is_high_quality:
                            print("[INFO] Local answer is high quality - no online supplement needed", file=sys.stderr)
                            should_supplement_online = False
                        elif is_acceptable_quality:
                            print("[INFO] Local answer is acceptable but could be improved - will supplement with online", file=sys.stderr)
                            should_supplement_online = True
                        else:
                            print("[INFO] Local answer is insufficient - will supplement with online", file=sys.stderr)
                            should_supplement_online = True
                    
                    # If local_first mode and we have a good answer, return it without online search
                    if actual_mode == "local_first" and is_acceptable_quality:
                        contexts = [
                            {
                                "text": ctx.context,
                                "citation": ctx.text.name if hasattr(ctx.text, 'name') else "Unknown",
                                "score": ctx.score if hasattr(ctx, 'score') else None
                            }
                            for ctx in local_answer.contexts
                        ]
                        
                        return ToolResult(True, {
                            "answer": local_answer.answer,
                            "contexts": contexts,
                            "references": local_answer.references if hasattr(local_answer, 'references') else [],
                            "sources_used": sources_used + ["(local papers sufficient - skipped online search)"],
                            "mode": "local"
                        })
                        
                except Exception as e:
                    # If local query fails, continue to online
                    sources_used.append(f"(local query error: {str(e)[:50]})")

        # STAGE 2: Add online search if needed
        # Online search uses TWO sources in order of priority:
        # 1. Semantic Scholar API - broad scientific coverage, good for general papers
        # 2. PubMed/PMC - biomedical focus, only open access papers
        # Both download full PDFs (not just abstracts) and add to document collection
        # 
        # Smart mode decision: should_supplement_online flag determines if online search runs
        should_do_online = (
            actual_mode in ["online", "hybrid", "local_first"]
            or (actual_mode == "smart" and should_supplement_online)
        )
        
        if should_do_online:
            import requests
            import urllib.parse
            import tempfile
            import xml.etree.ElementTree as ET

            total_papers_added = 0
            
            # Load metadata to check for already downloaded papers
            metadata_file = _get_metadata_file(online_papers_dir)
            existing_metadata = _load_metadata(metadata_file)
            
            # Load failed downloads for retry
            failed_file = _get_failed_downloads_file(online_papers_dir)
            failed_downloads = _load_failed_downloads(failed_file)

            # SOURCE 1: Semantic Scholar (general scientific papers)
            # - Searches across all scientific disciplines
            # - Returns papers with open access PDFs or arXiv links
            # - Fast and comprehensive coverage
            try:
                s2_url = "https://api.semanticscholar.org/graph/v1/paper/search"
                params = {
                    "query": question,
                    "limit": max_sources,
                    "fields": "title,authors,year,abstract,openAccessPdf,externalIds,citationCount"
                }

                headers = {}
                if s2_api_key := os.getenv("SEMANTIC_SCHOLAR_API_KEY"):
                    headers["x-api-key"] = s2_api_key

                response = requests.get(s2_url, params=params, headers=headers, timeout=30.0)
                response.raise_for_status()
                search_data = response.json()

                papers_data = search_data.get("data", [])
                s2_papers_added = 0

                for paper in papers_data[:max_sources]:
                    try:
                        # Extract paper information
                        external_ids = paper.get("externalIds", {})
                        doi = external_ids.get("DOI", "")
                        arxiv_id = external_ids.get("ArXiv", "")
                        title = paper.get("title", "Unknown")
                        year = paper.get("year", "")
                        authors = paper.get("authors", [])
                        author_names = ", ".join([a.get("name", "") for a in authors[:3]])
                        if len(authors) > 3:
                            author_names += " et al."
                        
                        # Check if already in metadata
                        metadata_key = None
                        if doi:
                            metadata_key = f"doi:{doi}"
                        elif arxiv_id:
                            metadata_key = f"arxiv:{arxiv_id}"
                        
                        if metadata_key and metadata_key in existing_metadata:
                            # Already downloaded - use cached file
                            cached_filename = existing_metadata[metadata_key]['filename']
                            local_pdf_path = online_papers_dir / cached_filename
                            
                            if local_pdf_path.exists():
                                print(f"[INFO] Using cached paper from metadata: {cached_filename}", file=sys.stderr)
                                citation = f"{author_names}. {title}. {year}" if year else f"{author_names}. {title}"
                                try:
                                    asyncio.run(docs.aadd(str(local_pdf_path), citation=citation, settings=settings))
                                    s2_papers_added += 1
                                except Exception as e:
                                    print(f"[WARNING] Failed to add cached paper: {e}", file=sys.stderr)
                                continue
                            else:
                                print(f"[WARNING] Metadata exists but file missing: {cached_filename}", file=sys.stderr)
                        
                        # Create filename with title
                        identifier = doi if doi else (f"arxiv_{arxiv_id}" if arxiv_id else "unknown")
                        safe_filename = _create_safe_filename(title, identifier)
                        local_pdf_path = online_papers_dir / safe_filename
                        
                        # Get PDF URL
                        pdf_info = paper.get("openAccessPdf")
                        if not pdf_info or not pdf_info.get("url"):
                            if arxiv_id:
                                pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                            else:
                                continue
                        else:
                            pdf_url = pdf_info["url"]
                            
                            # Handle DOI redirect URLs (not direct PDFs)
                            if pdf_url.startswith("https://doi.org/") or pdf_url.startswith("http://dx.doi.org/"):
                                print(f"[INFO] Semantic Scholar returned DOI redirect for: {title[:60]}...", file=sys.stderr)
                                
                                # Try ArXiv first if available
                                if arxiv_id:
                                    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                                    print(f"[INFO] Using ArXiv instead: {pdf_url}", file=sys.stderr)
                                # Try Unpaywall API to find real PDF URL
                                elif doi:
                                    print(f"[INFO] Trying Unpaywall API to find PDF URL...", file=sys.stderr)
                                    unpaywall_pdf = _get_pdf_url_from_unpaywall(doi)
                                    if unpaywall_pdf:
                                        pdf_url = unpaywall_pdf
                                        print(f"[SUCCESS] Found PDF via Unpaywall: {pdf_url}", file=sys.stderr)
                                    else:
                                        print(f"[WARNING] Unpaywall couldn't find open access PDF", file=sys.stderr)
                                        # Keep DOI link for manual download prompt
                                else:
                                    # No DOI and no ArXiv - skip this paper
                                    print(f"[WARNING] No alternative source found, skipping", file=sys.stderr)
                                    continue

                        citation = f"{author_names}. {title}. {year}" if year else f"{author_names}. {title}"
                        
                        # Try to download PDF
                        download_success = False
                        manual_download = False
                        try:
                            pdf_headers = {
                                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                "Accept": "application/pdf,application/octet-stream,*/*",
                                "Accept-Language": "en-US,en;q=0.9",
                                "Accept-Encoding": "gzip, deflate",
                                "Connection": "keep-alive",
                                "Upgrade-Insecure-Requests": "1"
                            }
                            pdf_response = requests.get(pdf_url, headers=pdf_headers, timeout=60, allow_redirects=True)
                            pdf_response.raise_for_status()

                            # Save to local paper directory (validate after saving)
                            with open(local_pdf_path, 'wb') as f:
                                f.write(pdf_response.content)
                            
                            # Validate the downloaded PDF (comprehensive check)
                            is_valid, error_msg = _validate_pdf_file(local_pdf_path)
                            if not is_valid:
                                local_pdf_path.unlink()  # Delete invalid file
                                raise ValueError(f"Downloaded file is corrupted: {error_msg}")
                            
                            print(f"[SUCCESS] [Semantic Scholar] Downloaded: {safe_filename}", file=sys.stderr)
                            download_success = True
                            
                        except Exception as e:
                            print(f"\n[ERROR] [Semantic Scholar] Failed to download: {title}", file=sys.stderr)
                            print(f"[ERROR] Reason: {str(e)}", file=sys.stderr)
                            print(f"[INFO] URL: {pdf_url}", file=sys.stderr)
                            if doi:
                                print(f"[INFO] DOI: {doi}", file=sys.stderr)
                            if arxiv_id:
                                print(f"[INFO] ArXiv: {arxiv_id}", file=sys.stderr)
                            
                            # Record failed download for later retry
                            failed_entry = {
                                'url': pdf_url,
                                'doi': doi or '',
                                'arxiv_id': arxiv_id or '',
                                'pmid': '',
                                'title': title,
                                'filename': safe_filename,
                                'source': 'semantic_scholar',
                                'reason': str(e)
                            }
                            _save_failed_download(failed_file, failed_entry)
                            print(f"[INFO] Recorded to failed_downloads.json for manual retry", file=sys.stderr)
                            print(f"[INFO] Skipping this paper and continuing...", file=sys.stderr)
                            continue
                        
                        # Add to docs and metadata if download successful
                        if download_success and local_pdf_path.exists():
                            try:
                                asyncio.run(docs.aadd(str(local_pdf_path), citation=citation, settings=settings))
                                s2_papers_added += 1
                                
                                # Save to metadata
                                metadata_entry = {
                                    'doi': doi,
                                    'arxiv_id': arxiv_id,
                                    'pmid': '',
                                    'title': title,
                                    'filename': safe_filename,
                                    'source': 'semantic_scholar',
                                    'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'manual': 'yes' if manual_download else 'no'
                                }
                                _save_metadata_entry(metadata_file, metadata_entry)
                                print(f"[INFO] Added to metadata: {safe_filename}", file=sys.stderr)
                                
                                # Remove from failed downloads if it was previously failed
                                if doi:
                                    _remove_failed_download(failed_file, doi)
                                elif arxiv_id:
                                    _remove_failed_download(failed_file, arxiv_id)
                                
                            except Exception as e:
                                print(f"[ERROR] Failed to add paper to collection: {e}", file=sys.stderr)

                    except Exception as e:
                        print(f"[ERROR] Unexpected error processing paper: {e}", file=sys.stderr)
                        continue

                if s2_papers_added > 0:
                    sources_used.append(f"semantic_scholar ({s2_papers_added} papers)")
                    total_papers_added += s2_papers_added

            except Exception as e:
                print(f"[WARNING] Semantic Scholar search failed: {str(e)}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

            # SOURCE 2: PubMed/PMC (biomedical papers)
            # - PubMed: largest biomedical literature database (35M+ citations)
            # - PMC (PubMed Central): subset with full-text open access articles
            # - Only downloads papers available in PMC (open access requirement)
            # - Excellent for biology, medicine, genetics, immunology topics
            print("[INFO] Trying PubMed/PMC search...", file=sys.stderr)
            try:
                search_term = urllib.parse.quote(question)
                # Use retmax=50 to get more candidates, then filter to max_sources
                search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_term}&retmode=json&retmax=50"
                print(f"[INFO] PubMed query: {question}", file=sys.stderr)

                search_response = requests.get(search_url, timeout=30)
                search_response.raise_for_status()
                search_data = search_response.json()

                pmids = search_data.get("esearchresult", {}).get("idlist", [])
                print(f"[INFO] Found {len(pmids)} PubMed papers", file=sys.stderr)
                pmc_papers_added = 0

                for pmid in pmids[:max_sources]:
                    try:
                        # Check if already in metadata
                        metadata_key = f"pmid:{pmid}"
                        if metadata_key in existing_metadata:
                            # Already downloaded - use cached file
                            cached_filename = existing_metadata[metadata_key]['filename']
                            local_pdf_path = online_papers_dir / cached_filename
                            
                            if local_pdf_path.exists():
                                print(f"[INFO] Using cached paper from metadata: {cached_filename}", file=sys.stderr)
                                # Still need citation, get basic info
                                try:
                                    details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
                                    details_response = requests.get(details_url, timeout=30)
                                    details_data = details_response.json()
                                    paper_info = details_data.get("result", {}).get(pmid, {})
                                    title = paper_info.get("title", "Unknown")
                                    authors = paper_info.get("authors", [])
                                    author_names = ", ".join([a.get("name", "") for a in authors[:3]])
                                    if len(authors) > 3:
                                        author_names += " et al."
                                    citation = f"{author_names}. {title}. PMID: {pmid}"
                                    
                                    asyncio.run(docs.aadd(str(local_pdf_path), citation=citation, settings=settings))
                                    pmc_papers_added += 1
                                except Exception as e:
                                    print(f"[WARNING] Failed to add cached paper: {e}", file=sys.stderr)
                                continue
                            else:
                                print(f"[WARNING] Metadata exists but file missing: {cached_filename}", file=sys.stderr)
                        
                        # Check if paper is available in PMC (open access)
                        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
                        pmc_response = requests.get(pmc_url, timeout=30)
                        pmc_data = pmc_response.json()

                        records = pmc_data.get("records", [])
                        if records and records[0].get("pmcid"):
                            pmcid = records[0]["pmcid"]

                            # Get paper details for citation
                            details_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
                            details_response = requests.get(details_url, timeout=30)
                            details_data = details_response.json()

                            paper_info = details_data.get("result", {}).get(pmid, {})
                            title = paper_info.get("title", "Unknown")
                            authors = paper_info.get("authors", [])
                            author_names = ", ".join([a.get("name", "") for a in authors[:3]])
                            if len(authors) > 3:
                                author_names += " et al."
                            
                            # Create filename with title
                            identifier = f"PMID_{pmid}"
                            safe_filename = _create_safe_filename(title, identifier)
                            local_pdf_path = online_papers_dir / safe_filename

                            # Use PMC OA Web Service to get actual PDF URL
                            # Official API: https://www.ncbi.nlm.nih.gov/pmc/tools/oa-service/
                            print(f"[INFO] Querying PMC OA service for {pmcid}...", file=sys.stderr)
                            oa_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/oa/oa.fcgi?id={pmcid}"
                            
                            try:
                                oa_response = requests.get(oa_url, timeout=10)
                                oa_response.raise_for_status()
                                
                                # Parse XML response to find PDF link
                                import xml.etree.ElementTree as ET_local
                                oa_root = ET_local.fromstring(oa_response.content)
                                
                                # Find link with format="pdf"
                                pdf_link = None
                                for link in oa_root.findall('.//link'):
                                    if link.get('format') == 'pdf':
                                        pdf_link = link.get('href')
                                        break
                                
                                if pdf_link:
                                    pdf_url = pdf_link
                                    print(f"[SUCCESS] Found PDF URL via OA service: {pdf_url}", file=sys.stderr)
                                else:
                                    # Fallback to old method
                                    pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                                    print(f"[WARNING] No PDF link in OA service, using fallback URL", file=sys.stderr)
                            except Exception as e:
                                # Fallback to old method
                                pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/pdf/"
                                print(f"[WARNING] OA service failed ({str(e)}), using fallback URL", file=sys.stderr)
                            
                            citation = f"{author_names}. {title}. PMID: {pmid}"
                            
                            # Try to download PDF
                            download_success = False
                            manual_download = False
                            try:
                                pdf_headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                                    "Accept": "application/pdf,*/*",
                                    "Referer": f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/"
                                }
                                pdf_response = requests.get(pdf_url, headers=pdf_headers, timeout=60, allow_redirects=True)
                                pdf_response.raise_for_status()
                                
                                # Debug info
                                content_type = pdf_response.headers.get("Content-Type", "")
                                content_length = len(pdf_response.content)
                                print(f"[DEBUG] PMC response - Content-Type: {content_type}, Size: {content_length} bytes", file=sys.stderr)
                                
                                # Verify it's actually a PDF (PMC sometimes returns HTML)
                                is_pdf = pdf_response.content.startswith(b"%PDF")
                                is_html = b"<html" in pdf_response.content[:1000].lower() or b"<!doctype" in pdf_response.content[:1000].lower()
                                
                                if is_html:
                                    print(f"[DEBUG] PMC returned HTML instead of PDF. First 200 bytes: {repr(pdf_response.content[:200])}", file=sys.stderr)
                                    raise ValueError(f"PMC returned HTML page, not PDF. The paper may require JavaScript or have access restrictions.")
                                
                                if not is_pdf:
                                    print(f"[DEBUG] Not a PDF. First 50 bytes: {repr(pdf_response.content[:50])}", file=sys.stderr)
                                    raise ValueError(f"Not a valid PDF (Content-Type: {content_type}, starts with: {repr(pdf_response.content[:20])})")
                                
                                # Save to local paper directory
                                with open(local_pdf_path, 'wb') as f:
                                    f.write(pdf_response.content)
                                
                                # Validate the downloaded PDF
                                is_valid, error_msg = _validate_pdf_file(local_pdf_path)
                                if not is_valid:
                                    local_pdf_path.unlink()  # Delete invalid file
                                    raise ValueError(f"Downloaded file is corrupted: {error_msg}")
                                
                                print(f"[SUCCESS] [PubMed/PMC] Downloaded: {safe_filename}", file=sys.stderr)
                                download_success = True
                                
                            except Exception as e:
                                error_type = type(e).__name__
                                print(f"\n[ERROR] [PubMed/PMC] Failed to download ({error_type}): {title}", file=sys.stderr)
                                print(f"[ERROR] Reason: {str(e)}", file=sys.stderr)
                                print(f"[INFO] PMC URL: {pdf_url}", file=sys.stderr)
                                print(f"[INFO] Alternative: https://www.ncbi.nlm.nih.gov/pmc/articles/{pmcid}/", file=sys.stderr)
                                
                                # Record failed download for later retry
                                failed_entry = {
                                    'url': pdf_url,
                                    'doi': '',
                                    'arxiv_id': '',
                                    'pmid': pmid,
                                    'title': title,
                                    'filename': safe_filename,
                                    'source': 'pubmed_pmc',
                                    'reason': str(e)
                                }
                                _save_failed_download(failed_file, failed_entry)
                                print(f"[INFO] Recorded to failed_downloads.json for manual retry", file=sys.stderr)
                                print(f"[INFO] Skipping this paper and continuing...", file=sys.stderr)
                                continue
                            
                            # Add to docs and metadata if download successful
                            if download_success and local_pdf_path.exists():
                                try:
                                    asyncio.run(docs.aadd(str(local_pdf_path), citation=citation, settings=settings))
                                    pmc_papers_added += 1
                                    
                                    # Save to metadata
                                    metadata_entry = {
                                        'doi': '',
                                        'arxiv_id': '',
                                        'pmid': pmid,
                                        'title': title,
                                        'filename': safe_filename,
                                        'source': 'pubmed_pmc',
                                        'download_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'manual': 'yes' if manual_download else 'no'
                                    }
                                    _save_metadata_entry(metadata_file, metadata_entry)
                                    print(f"[INFO] Added to metadata: {safe_filename}", file=sys.stderr)
                                    
                                    # Remove from failed downloads if it was previously failed
                                    _remove_failed_download(failed_file, pmid)
                                    
                                except Exception as e:
                                    print(f"[ERROR] Failed to add paper to collection: {e}", file=sys.stderr)

                    except Exception as e:
                        print(f"[ERROR] Unexpected error processing PMID {pmid}: {e}", file=sys.stderr)
                        continue

                if pmc_papers_added > 0:
                    sources_used.append(f"pubmed_pmc ({pmc_papers_added} papers)")
                    total_papers_added += pmc_papers_added

            except Exception as e:
                print(f"[WARNING] PubMed/PMC search failed: {str(e)}", file=sys.stderr)
                import traceback
                traceback.print_exc(file=sys.stderr)

        # Query the combined document collection
        # Paper-QA v5+ uses async aquery instead of sync query
        answer_obj = asyncio.run(docs.aquery(question, settings=settings))

        # Extract contexts and references
        contexts = [
            {
                "text": ctx.context,
                "citation": ctx.text.name if hasattr(ctx.text, 'name') else "Unknown",
                "score": ctx.score if hasattr(ctx, 'score') else None
            }
            for ctx in answer_obj.contexts
        ]
        
        # Check if there were failed downloads and notify user
        failed_downloads = _load_failed_downloads(failed_file) if should_do_online else []
        if failed_downloads:
            failed_count = len(failed_downloads)
            print(f"\n{'='*80}", file=sys.stderr)
            print(f"[NOTICE] {failed_count} paper(s) failed to download automatically", file=sys.stderr)
            print(f"[NOTICE] Details saved to: {failed_file}", file=sys.stderr)
            print(f"[NOTICE] To manually download:", file=sys.stderr)
            print(f"[NOTICE]   1. Open failed_downloads.json", file=sys.stderr)
            print(f"[NOTICE]   2. Download PDFs from the 'url' field", file=sys.stderr)
            print(f"[NOTICE]   3. Save to the 'filename' path in online_papers/", file=sys.stderr)
            print(f"[NOTICE]   4. Run search_literature again - it will auto-load the new files", file=sys.stderr)
            print(f"{'='*80}\n", file=sys.stderr)

        return ToolResult(True, {
            "answer": answer_obj.answer,
            "contexts": contexts,
            "references": answer_obj.references if hasattr(answer_obj, 'references') else [],
            "sources_used": sources_used,
            "mode": actual_mode,
            "failed_downloads": len(failed_downloads) if failed_downloads else 0
        })

    except ImportError as e:
        return ToolResult(
            False,
            None,
            "PaperQA not installed. Run: pip install paper-qa"
        )
    except Exception as e:
        return ToolResult(False, None, f"Literature search error: {str(e)}")


def get_tool_definitions() -> list[dict[str, Any]]:
    """Get tool definitions for OpenRouter API.

    Returns:
        List of tool definition dicts
    """
    # Check if we should include search_pubmed
    from src.config import get_global_config
    config = get_global_config()

    tools = [
        {
            "type": "function",
            "function": {
                "name": "execute_python",
                "description": "Execute Python code to analyze data, perform calculations, or create visualizations. Use for bioinformatics analysis. IMPORTANT: When saving output files (CSV, plots, etc.), prefix paths with OUTPUT_DIR to organize files properly (e.g., f'{OUTPUT_DIR}/results.csv'). OUTPUT_DIR is automatically available in your code. CRITICAL: When reporting results to other agents in your text response, mention files with {OUTPUT_DIR} prefix so they can find them.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": "Python code to execute. Assume pandas, numpy, biopython are available. ALWAYS use OUTPUT_DIR variable to save files (e.g., df.to_csv(f'{OUTPUT_DIR}/output.csv'), plt.savefig(f'{OUTPUT_DIR}/plot.png')). Never save files without OUTPUT_DIR prefix.",
                        }
                    },
                    "required": ["code"],
                },
            },
        },
    ]

    # Conditionally add search_pubmed
    if not config.use_paperqa_only:
        tools.append({
            "type": "function",
            "function": {
                "name": "search_pubmed",
                "description": "Search PubMed for scientific articles related to a query. Returns titles, abstracts, and author information.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "PubMed search query (e.g., 'SARS-CoV-2 vaccine', 'alzheimer's disease protein')",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum number of results to return (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
        })

    # Continue with remaining tools
    tools.extend([
        {
            "type": "function",
            "function": {
                "name": "query_database",
                "description": "Query one of the competition databases (DrugBank, BindingDB, Pharos, STRING, GWAS). For large databases (BindingDB, GWAS), searches automatically iterate through chunks until finding enough results. Use 'info' query to see database structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "db_name": {
                            "type": "string",
                            "description": "Database name: 'drugbank', 'bindingdb', 'pharos', 'string', or 'gwas'",
                        },
                        "query": {
                            "type": "string",
                            "description": "Query specification: 'info' for database info, 'file:filename' for specific file, 'Column:value' for search (will search iteratively through file), or 'all' for sample rows",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of rows to return (default: 10). For searches, this is the target number of matches to find.",
                            "default": 10,
                        },
                    },
                    "required": ["db_name", "query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a file from the input data directory (question-specific data like gene signatures, expression data). Supports parquet, CSV, TSV, and text files. IMPORTANT: The input directory is already configured - just provide the filename or relative path from that directory. For example, if a file is at './data/Q5/file.csv' and input_dir='./data/Q5', then use file_path='file.csv' (NOT 'data/Q5/file.csv'). Use find_files() first to discover available files and their correct paths.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {
                            "type": "string",
                            "description": "Filename or path relative to the configured input directory. If find_files() returns 'data/Q5/file.csv' but input_dir is './data/Q5', use just 'file.csv'. Use the basename from find_files results.",
                        }
                    },
                    "required": ["file_path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "find_files",
                "description": "Intelligently find relevant files in the workspace without repeated directory traversal. Much more efficient than using execute_python with os.listdir(). Can search by pattern, file type, or question relevance. Use this FIRST before trying to read files - it will help you discover what data is available.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Optional glob pattern to match (e.g., '**/Q5/*.csv', '**/*exhaustion*.csv')",
                        },
                        "category": {
                            "type": "string",
                            "description": "Optional filter by file category: 'data', 'config', 'script', 'doc'",
                            "enum": ["data", "config", "script", "doc"],
                        },
                        "extension": {
                            "type": "string",
                            "description": "Optional file extension filter (e.g., 'csv', 'parquet', 'bam')",
                        },
                        "name_contains": {
                            "type": "string",
                            "description": "Optional: find files with this substring in the name (case-insensitive)",
                        },
                        "question_context": {
                            "type": "string",
                            "description": "Optional: research question text - will intelligently score and rank files by relevance to the question",
                        },
                    },
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_literature",
                "description": "Advanced AI-powered literature search using PaperQA. " + (
                    "**PRIMARY LITERATURE TOOL - USE THIS FOR ALL LITERATURE SEARCHES**. Searches online databases (PubMed, arXiv, Semantic Scholar), downloads papers, reads full-text content, and generates evidence-based answers with citations. If you mention a paper (e.g., 'Philip et al. Nature 2017'), you MUST use this tool with mode='online' to fetch and verify it."
                    if config.use_paperqa_only else
                    "**USE THIS TO VERIFY PAPERS BEFORE CITING THEM**. PRIORITIZES local PDF library first, then supplements with online databases (PubMed, arXiv) if needed. Reads full-text papers and generates evidence-based answers with citations. More rigorous than search_pubmed - use this when you need detailed, cited information from research papers."
                ) + " Default 'auto' mode checks local PDFs first and only searches online if local papers don't provide a good answer.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Research query for literature search. IMPORTANT: Use KEYWORD-BASED queries for better results, NOT full natural language questions. Examples: GOOD: 'AlphaFold protein structure prediction', 'EGFR inhibitor resistance mechanisms', 'RoseTTAFold deep learning'. BAD: 'What are the seminal papers for AlphaFold?', 'How does EGFR resistance work?'. Remove meta-language like 'papers about', 'research on', 'key studies'. Focus on core scientific terms and protein/gene names.",
                        },
                        "mode": {
                            "type": "string",
                            "description": "Search mode: 'local' (only local PDFs), 'online' (skip local, only internet), 'auto' (prioritize local, supplement with online if needed - RECOMMENDED), 'hybrid' (search both simultaneously)",
                            "enum": ["local", "online", "auto", "hybrid"],
                            "default": "auto",
                        },
                        "paper_dir": {
                            "type": "string",
                            "description": "Optional: Override default paper library directory (uses configured default if not provided)",
                        },
                        "max_sources": {
                            "type": "integer",
                            "description": "Maximum number of source contexts to retrieve (default: 5)",
                            "default": 5,
                        },
                    },
                    "required": ["question"],
                },
            },
        },
    ])

    return tools
