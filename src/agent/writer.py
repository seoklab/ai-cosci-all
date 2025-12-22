"""
Refactored Paper Writer with Global Sentence-Level Citations.

This module implements a clean, streamlined approach to academic paper generation
with sophisticated global citation management across all sections.

Key Features:
- Sentence-level citation classification and extraction
- Global citation deduplication across Introduction and Discussion sections
- Sequential citation numbering with proper References section
- Clean separation of concerns with dedicated classes
"""
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
import re
import time
from pathlib import Path

from src.agent.openrouter_client import OpenRouterClient
from src.agent.anthropic_client import AnthropicClient
from src.tools.implementations import search_literature, search_pubmed


@dataclass
class Citation:
    """Data class for managing citation information with global deduplication."""
    
    key: str
    source: str
    term: str
    result: Any
    section: str
    sentence: str
    final_number: int = None
    
    def get_dedup_key(self) -> str:
        """Generate unique key for global deduplication."""
        result = self.result
        
        # Handle different result formats
        if isinstance(result, list) and result:
            item = result[0] if isinstance(result[0], dict) else {}
        elif isinstance(result, dict):
            item = result
        else:
            item = {}
        
        # Prefer DOI for deduplication (most reliable)
        doi = item.get('doi', '')
        if doi and doi != 'N/A':
            return f"doi:{doi.lower()}"
        
        # Then PMID
        pmid = item.get('pmid', '')
        if pmid and pmid != 'N/A':
            return f"pmid:{pmid}"
        
        # Finally, normalized title
        title = item.get('title', '')
        if title and title != 'N/A':
            normalized_title = re.sub(r'\W+', ' ', title.lower()).strip()[:100]
            return f"title:{normalized_title}"
        
        # Fallback to content hash
        return f"raw:{hash(str(result))}"


class GlobalCitationManager:
    """Manages global citation collection, deduplication, and numbering."""
    
    def __init__(self):
        self.all_citations: List[Citation] = []
        self.unique_citations: List[Citation] = []
        self.citation_map: Dict[str, int] = {}
        
    def add_citation(self, citation: Citation) -> None:
        """Add a citation to the global collection."""
        self.all_citations.append(citation)
    
    def deduplicate_and_number(self) -> None:
        """Deduplicate citations globally and assign sequential numbers."""
        seen_keys = {}
        
        for citation in self.all_citations:
            dedup_key = citation.get_dedup_key()
            
            if dedup_key in seen_keys:
                # Use existing citation number
                citation.final_number = seen_keys[dedup_key]
            else:
                # New citation - assign next sequential number
                final_number = len(seen_keys) + 1
                citation.final_number = final_number
                seen_keys[dedup_key] = final_number
                self.unique_citations.append(citation)
                self.citation_map[dedup_key] = final_number
        
        print(f"   Deduplicated {len(self.all_citations)} citations to {len(self.unique_citations)} unique citations")
    
    def get_citations_for_sentence(self, section: str, sentence: str) -> List[int]:
        """Get sorted citation numbers for a specific sentence."""
        citation_numbers = []
        for citation in self.all_citations:
            if (citation.section == section and 
                citation.sentence == sentence and 
                citation.final_number and 
                citation.final_number not in citation_numbers):
                citation_numbers.append(citation.final_number)
        return sorted(citation_numbers)
    
    def create_references_section(self) -> str:
        """Create formatted References section from unique citations."""
        if not self.unique_citations:
            return "## References\n\nNo references found.\n"

        refs_content = "## References\n\n"
        
        # Sort by final number to ensure proper ordering
        for citation in sorted(self.unique_citations, key=lambda x: x.final_number):
            result = citation.result
            
            # Extract metadata from citation result
            if isinstance(result, list) and result:
                item = result[0] if isinstance(result[0], dict) else {}
            elif isinstance(result, dict):
                item = result
            else:
                item = {}
            
            # Build reference text with proper academic formatting
            parts = []
            
            # Authors
            author = item.get('author', '')
            if not author and 'authors' in item:
                authors = item['authors']
                if isinstance(authors, list):
                    author = ', '.join(authors)
                else:
                    author = str(authors) if authors else ''
            if author and author != 'N/A':
                parts.append(author)
            
            # Title
            title = item.get('title', '')
            if title and title != 'N/A':
                parts.append(title)
            
            # Journal
            journal = item.get('journal', '')
            if journal and journal != 'N/A':
                parts.append(journal)
            
            # Year
            year = item.get('publish_year', '') or item.get('pubdate', '')
            if year and year != 'N/A':
                # Extract year from date string if needed
                year_match = re.search(r'(\d{4})', str(year))
                if year_match:
                    year = year_match.group(1)
                parts.append(year)
            
            # Build reference string
            ref_text = '. '.join(parts) if parts else 'No details available'
            if ref_text and not ref_text.endswith('.'):
                ref_text += '.'
            
            # Add DOI if available
            doi = item.get('doi', '')
            if doi and doi != 'N/A':
                ref_text += f" DOI: {doi}"
            
            refs_content += f"[{citation.final_number}] {ref_text}\n"

        print(f"   Created References section with {len(self.unique_citations)} citations")
        return refs_content


class SentenceCitationProcessor:
    """Handles sentence-level citation processing with LLM assistance."""
    
    def __init__(self, client):
        self.client = client
    
    def classify_sentence_needs_citation(self, sentence: str) -> bool:
        """Use LLM to classify whether a sentence needs a scientific citation."""
        if not sentence.strip() or len(sentence.split()) < 5:
            return False
        
        classification_prompt = f"""Analyze this sentence and determine if it needs a scientific citation. 

A sentence needs a citation if it:
- Makes a factual scientific claim
- Reports specific data, statistics, or findings
- References established scientific knowledge or phenomena  
- Describes mechanisms, pathways, or processes
- States comparative results or relationships

A sentence does NOT need a citation if it:
- Is general methodology description
- Is the author's own interpretation or conclusion
- Is transitional or introductory text
- Describes figures or tables
- Is a general statement without specific claims

Sentence: "{sentence}"

Answer with only "YES" if it needs a citation, or "NO" if it doesn't need a citation.

Answer:"""

        try:
            messages = [{"role": "user", "content": classification_prompt}]
            response = self.client.create_message(
                messages=messages,
                temperature=0.1,
                max_tokens=10
            )
            
            classification = self.client.get_response_text(response).strip().upper()
            return classification == "YES"
            
        except Exception as e:
            print(f"   Failed to classify sentence citation need: {e}")
            return True  # Conservative approach
    
    def extract_key_terms(self, sentence: str) -> List[str]:
        """Extract key scientific terms for literature search."""
        if not sentence.strip() or len(sentence.split()) < 5:
            return []
        
        extraction_prompt = f"""Extract 2-4 key scientific terms from this sentence that would be useful for literature search. Focus on specific concepts, methods, or biological processes mentioned.

Sentence: "{sentence}"

Return only the key terms, separated by commas. Do not include general words like "analysis", "study", "research". Focus on specific scientific concepts.

Examples:
- For "T-cell populations showed increased cytokine production" -> "T-cell populations, cytokine production"
- For "mRNA stability was analyzed using nanopore sequencing" -> "mRNA stability, nanopore sequencing"

Key terms:"""

        try:
            messages = [{"role": "user", "content": extraction_prompt}]
            response = self.client.create_message(
                messages=messages,
                temperature=0.1,
                max_tokens=100
            )
            
            terms_text = self.client.get_response_text(response).strip()
            key_terms = [term.strip() for term in terms_text.split(",") if term.strip()]
            return key_terms[:3]  # Limit to top 3 terms
            
        except Exception as e:
            print(f"   Failed to extract key terms from sentence: {e}")
            return []
    
    def filter_relevant_literature(self, sentence: str, key_terms: List[str], literature_results: List[dict]) -> List[dict]:
        """Filter literature search results for actual relevance to the sentence."""
        if not literature_results:
            return []
        
        relevant_citations = []
        
        for citation_data in literature_results:
            # Extract text for evaluation
            result_data = citation_data['result']
            
            if isinstance(result_data, dict):
                title = result_data.get('title', 'N/A')
                abstract = result_data.get('abstract', 'N/A')
                
                if title != 'N/A' and abstract != 'N/A':
                    result_text = f"title: {title}, abstract: {abstract}"
                else:
                    continue
            else:
                result_text = str(result_data)
            
            filter_prompt = f"""Evaluate if this literature result is actually relevant to the given sentence.

SENTENCE: "{sentence}"
KEY TERMS: {', '.join(key_terms)}

LITERATURE RESULT: "{result_text}"

Is this literature result specifically relevant to the sentence's claims? Consider:
1. Does it address the same biological concepts/processes?
2. Is it from a credible scientific source?
3. Would citing this support or provide evidence for the sentence?

Answer with only "RELEVANT" or "NOT_RELEVANT".

Answer:"""

            try:
                messages = [{"role": "user", "content": filter_prompt}]
                response = self.client.create_message(
                    messages=messages,
                    temperature=0.1,
                    max_tokens=20
                )
                
                relevance = self.client.get_response_text(response).strip().upper()
                if relevance == "RELEVANT":
                    relevant_citations.append(citation_data)
                    
            except Exception as e:
                print(f"   Failed to filter citation relevance: {e}")
                # Conservative approach - include if filtering fails
                relevant_citations.append(citation_data)
        
        return relevant_citations


class PaperSolver:
    """Main class for generating academic papers with global sentence-level citations."""
    
    def __init__(self, 
                 api_key: Optional[str] = None, 
                 model: str = "google/gemini-3-flash-preview", 
                 provider: str = "openrouter",
                 citation: Optional[Path] = None,
                 use_global_citations: bool = True):
        """Initialize the paper solver with specified model and provider."""
        if provider == "anthropic":
            self.client = AnthropicClient(api_key=api_key, model=model)
        else:
            self.client = OpenRouterClient(api_key=api_key, model=model)
        
        self.tools = {
            "search_literature": search_literature,
            "search_pubmed": search_pubmed,
        }
        
        self.citation_processor = SentenceCitationProcessor(self.client)

        self.citation_file = citation
        self.use_global_citations = use_global_citations
    
    def generate_paper(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int = 3000,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        temperature: float = 0.2,
    ) -> str:
        """Generate a complete academic paper with optional global citations."""
        
        print(f"🔬 Generating {target_word_count}-word academic paper...")
        
        if self.use_global_citations:
            return self._generate_with_global_citations(
                research_question, scientist_findings, target_word_count, 
                max_retries, retry_delay, temperature
            )
        else:
            draft = self._generate_draft(
            research_question, scientist_findings, target_word_count, 
            max_retries, retry_delay, temperature
            )
            references = self._generate_references_section(self.citation_file)

            final_paper = f"{draft}\n\n{references}"
            return final_paper
        
    def _generate_references_section(self, citation_file: Optional[Path]) -> str:
        """Generate References section from CSV file with journal information."""
        if not citation_file or not citation_file.exists():
            return "\n## References\n\nNo references file provided.\n"
        
        try:
            import pandas as pd
        except ImportError:
            print("Warning: pandas not available. Cannot process CSV file.")
            return "\n## References\n\nError: pandas required to process citations CSV file.\n"
        
        try:
            # Read CSV file
            df = pd.read_csv(citation_file)
            
            if df.empty:
                return "\n## References\n\nNo citations found in file.\n"
            
            references_content = "## References\n\n"
            
            # Process each row to create formatted references
            for idx, row in df.iterrows():
                ref_number = idx + 1
                
                # Extract fields with fallback handling
                author = self._clean_field(row.get('author', ''))
                title = self._clean_field(row.get('title', ''))
                journal = self._clean_field(row.get('journal', ''))
                volume = self._clean_field(row.get('volume', ''))
                page = self._clean_field(row.get('page', ''))
                year = self._clean_field(row.get('year', ''))
                doi = self._clean_field(row.get('doi', ''))
                pmid = self._clean_field(row.get('pmid', ''))
                arxiv_id = self._clean_field(row.get('arxiv_id', ''))
                
                # Build reference in academic format
                ref_parts = []
                
                # Authors
                if author:
                    # Handle multiple authors - format properly
                    if ',' in author and ' and ' not in author.lower():
                        # Assume comma-separated authors
                        authors = [a.strip() for a in author.split(',')]
                        if len(authors) > 3:
                            formatted_author = f"{authors[0]} et al."
                        else:
                            formatted_author = ', '.join(authors[:-1]) + f" and {authors[-1]}" if len(authors) > 1 else authors[0]
                    else:
                        formatted_author = author
                    ref_parts.append(formatted_author)
                
                # Title
                if title:
                    # Ensure title ends with period if it doesn't already
                    title_formatted = title if title.endswith('.') else f"{title}."
                    ref_parts.append(title_formatted)
                
                # Journal, Volume, Pages, Year
                journal_info = []
                if journal:
                    journal_info.append(journal)
                
                # Add volume and pages if available
                if volume:
                    if page:
                        journal_info.append(f"{volume}, {page}")
                    else:
                        journal_info.append(f"{volume}")
                elif page:
                    journal_info.append(page)
                
                # Add year
                if year:
                    journal_info.append(f"({year})")
                
                if journal_info:
                    ref_parts.append(' '.join(journal_info))
                
                # Build complete reference string
                if ref_parts:
                    reference_text = ' '.join(ref_parts)
                    if not reference_text.endswith('.'):
                        reference_text += '.'
                else:
                    reference_text = "Reference information incomplete."
                
                # Add DOI if available
                if doi:
                    if doi.startswith('http'):
                        reference_text += f" {doi}"
                    else:
                        reference_text += f" DOI: {doi}"
                
                # Add PMID if available and no DOI
                elif pmid:
                    reference_text += f" PMID: {pmid}"
                
                # Add arXiv ID if available and no DOI/PMID
                elif arxiv_id:
                    reference_text += f" arXiv: {arxiv_id}"
                
                # Add formatted reference to content
                references_content += f"[{ref_number}] {reference_text}\n\n"
            
            print(f"   Generated References section with {len(df)} citations")
            return references_content
            
        except Exception as e:
            print(f"Error processing citation file {citation_file}: {e}")
            return f"\n## References\n\nError processing citations: {str(e)}\n"
    
    def _clean_field(self, field_value) -> str:
        """Clean and validate a field value from CSV."""
        try:
            import pandas as pd
            if pd.isna(field_value):
                return ""
        except (ImportError, TypeError):
            # Handle case where pandas not available or field_value is not pandas-compatible
            if field_value is None:
                return ""
        
        field_str = str(field_value).strip()
        
        # Remove common placeholder values
        if field_str.lower() in ['n/a', 'na', 'null', 'none', '']:
            return ""
        
        return field_str

    def _generate_with_global_citations(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int,
        max_retries: int,
        retry_delay: float,
        temperature: float
    ) -> str:
        """Generate paper with global sentence-level citations."""
        
        # Step 1: Generate initial draft without citations
        print("📝 Generating initial draft...")
        draft_paper = self._generate_draft(
            research_question, scientist_findings, target_word_count, 
            max_retries, retry_delay, temperature
        )
        
        # Step 2: Parse draft into sections
        print("📋 Parsing sections...")
        sections = self._parse_sections(draft_paper)
        
        # Step 3: Collect citations globally
        print("🔍 Collecting global citations...")
        citation_manager = GlobalCitationManager()
        
        for section_name, section_content in sections.items():
            if section_name.lower() in ['introduction', 'discussion']:
                self._collect_citations_from_section(
                    section_content, section_name, citation_manager
                )
        
        # Step 4: Deduplicate and number citations
        print("🔄 Deduplicating citations...")
        citation_manager.deduplicate_and_number()
        
        # Step 5: Apply citations to sections
        print("📝 Applying citations...")
        enhanced_sections = {}
        
        for section_name, section_content in sections.items():
            if section_name.lower() in ['introduction', 'discussion']:
                enhanced_sections[section_name] = self._apply_citations_to_section(
                    section_content, section_name, citation_manager
                )
            else:
                enhanced_sections[section_name] = section_content
        
        # Step 6: Create References section
        print("📚 Creating References...")
        references_section = citation_manager.create_references_section()
        
        # Step 7: Format final paper
        print("📑 Formatting final paper...")
        final_paper = self._format_final_paper(enhanced_sections, references_section)
        
        final_word_count = len(final_paper.split())
        print(f"✅ Paper generation completed! Final length: {final_word_count} words (target: {target_word_count})")
        
        if final_word_count >= target_word_count * 0.8:
            print("   ✓ Successfully met target word count")
        elif final_word_count >= target_word_count * 0.6:
            print("   ⚠ Close to target word count")
        else:
            print("   ⚠ Below target word count - consider regenerating with higher targets")
        
        return final_paper
    
    def _generate_draft(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int,
        max_retries: int,
        retry_delay: float,
        temperature: float
    ) -> str:
        """Generate initial draft by creating sections step by step to meet word count."""
        print("   Generating paper sections step by step...")
        
        # Calculate word count distribution
        section_word_counts = self._calculate_section_word_counts(target_word_count)
        
        # Generate each section individually in proper academic order
        sections = {}
        
        # 0. Title (first, then add to sections)
        print("   - Generating Title...")
        sections['Title'] = self._generate_title(research_question, scientist_findings, max_retries, retry_delay, temperature)
        
        # 1. Abstract (150-250 words)
        print(f"   - Generating Abstract ({section_word_counts['abstract']} words)...")
        sections['Abstract'] = self._generate_abstract(
            research_question, scientist_findings, section_word_counts['abstract'], 
            max_retries, retry_delay, temperature
        )
        
        # 2. Introduction (background and objectives)
        print(f"   - Generating Introduction ({section_word_counts['introduction']} words)...")
        sections['Introduction'] = self._generate_introduction(
            research_question, scientist_findings, section_word_counts['introduction'],
            max_retries, retry_delay, temperature
        )
        
        # 3. Methods (data analysis methods)
        print(f"   - Generating Methods ({section_word_counts['methods']} words)...")
        sections['Methods'] = self._generate_methods(
            scientist_findings, section_word_counts['methods'],
            max_retries, retry_delay, temperature
        )
        
        # 4. Results (detailed findings)
        print(f"   - Generating Results ({section_word_counts['results']} words)...")
        sections['Results'] = self._generate_results(
            scientist_findings, section_word_counts['results'],
            max_retries, retry_delay, temperature
        )
        
        # 5. Discussion (interpretation)
        print(f"   - Generating Discussion ({section_word_counts['discussion']} words)...")
        sections['Discussion'] = self._generate_discussion(
            research_question, scientist_findings, section_word_counts['discussion'],
            max_retries, retry_delay, temperature
        )
        
        # 6. Conclusion (summary)
        print(f"   - Generating Conclusion ({section_word_counts['conclusion']} words)...")
        sections['Conclusion'] = self._generate_conclusion(
            research_question, scientist_findings, section_word_counts['conclusion'],
            max_retries, retry_delay, temperature
        )
        
        # Combine all sections in proper academic order
        print("   - Assembling complete paper...")
        section_order = ['Title', 'Abstract', 'Introduction', 'Methods', 'Results', 'Discussion', 'Conclusion']
        paper_parts = []
        
        for section_name in section_order:
            if section_name in sections:
                content = sections[section_name].strip()
                print(section_name)
                print(sections[section_name])
                if content:
                    paper_parts.append(content)
                    print(f"     ✓ Added {section_name} ({len(content.split())} words)")
                else:
                    print(f"     ⚠ Empty {section_name} section")
        
        full_draft = '\n\n'.join(paper_parts)
        actual_word_count = len(full_draft.split())
        print(f"   Generated complete draft with {actual_word_count} words (target: {target_word_count})")
        
        return full_draft
    
    def _calculate_section_word_counts(self, target_word_count: int) -> Dict[str, int]:
        """Calculate optimal word count distribution across sections."""
        # Standard academic paper proportions
        proportions = {
            'abstract': 0.08,      # 8% - 150-250 words
            'introduction': 0.20,  # 20% - background and context
            'methods': 0.15,       # 15% - data analysis methods
            'results': 0.25,       # 25% - detailed findings
            'discussion': 0.25,    # 25% - interpretation and implications
            'conclusion': 0.07     # 7% - summary and future work
        }
        
        word_counts = {}
        for section, proportion in proportions.items():
            word_counts[section] = max(100, int(target_word_count * proportion))
        
        # Ensure Abstract stays within academic norms
        word_counts['abstract'] = min(250, max(150, word_counts['abstract']))
        
        return word_counts
    
    def _generate_title(self, research_question: str, scientist_findings: str,
                       max_retries: int, retry_delay: float, temperature: float) -> str:
        """Generate Title for the paper."""
        system_prompt = """You are writing the Title for an academic paper.

The Title should:
- Be concise and informative (8-15 words typically)
- Clearly convey the main research focus
- Include key scientific terms and concepts
- Be specific and descriptive
- Follow academic title conventions

Avoid:
- Generic phrases like "A Study of" or "Investigation into"
- Overly long or complex titles
- Jargon that might confuse readers"""

        user_prompt = f"""Write a compelling Title for this research paper:

RESEARCH QUESTION: {research_question}

SCIENTIST FINDINGS: {scientist_findings}

Create a clear, informative title that captures the essence of this research. The title should be specific and engaging while maintaining academic standards."""

        return self._generate_section_content(
            "# ", system_prompt, user_prompt, 15,  # Short target for title
            max_retries, retry_delay, temperature
        )

    def _generate_abstract(self, research_question: str, scientist_findings: str, 
                          word_count: int, max_retries: int, retry_delay: float, 
                          temperature: float) -> str:
        """Generate Abstract section."""
        system_prompt = """You are writing the Abstract section of an academic paper. 

The Abstract should:
- Provide a concise summary of the entire study
- Include background context (1-2 sentences)
- State the research objective clearly
- Summarize key methods used
- Present main findings with specific results
- Conclude with implications or significance

Use past tense for completed work and present tense for general statements."""

        user_prompt = f"""Write an Abstract section for this research:

RESEARCH QUESTION: {research_question}

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words (150-250 words typical for abstracts)

Write a comprehensive abstract that summarizes the entire study including background, methods, results, and conclusions."""

        return self._generate_section_content(
            "## Abstract", system_prompt, user_prompt, word_count, 
            max_retries, retry_delay, temperature
        )
    
    def _generate_system_prompt(self) -> str:
        return """You are a senior academic researcher writing a formal paper. 
Your task is to write a comprehensive analysis on the topic provided below.

**CONTENT ACCURACY**
   1. Base paper EXCLUSIVELY on provided scientist findings
   2. Use specific numbers, statistics, and results from findings
   3. Maintain strict scientific rigor and evidence-based writing


**FORMATTING**
1. Use proper Markdown formatting with clear section headers
2. Include figure suggestions using [Figure X: description] format
3. No bullet points or lists: Do not use bullet points, numbered lists, or outline formats under any circumstances. Every idea must be expressed in full, complete sentences.
4. Minimal or no headings: Avoid using subheadings to separate sections. Instead, use smooth transitional phrases (e.g., "Furthermore," "Conversely," "Consequently," "In addition to...") to guide the reader from one paragraph to the next naturally.
5. Paragraph structure: Write in a continuous narrative flow. Organize the text into multiple substantial paragraphs:
   - Begin with a strong introductory paragraph setting the context.
   - Develop the argument through several body paragraphs, each focusing on a specific aspect of the topic.
   - Conclude with a synthesizing paragraph that summarizes the implications.
6. Tone: Maintain a sophisticated, objective, and formal academic tone.
"""
    
    def _generate_introduction(self, research_question: str, scientist_findings: str,
                              word_count: int, max_retries: int, retry_delay: float,
                              temperature: float) -> str:
        """Generate Introduction section."""
        system_prompt = """You are writing the Introduction section of an academic paper.

The Introduction should:
- Provide relevant background and context
- Review existing knowledge and identify gaps
- Establish the significance of the research question
- State objectives and hypotheses clearly
- Outline the approach taken

Structure: Background → Knowledge Gap → Research Question → Objectives → Approach"""

        user_prompt = f"""Write a comprehensive Introduction section for this research:

RESEARCH QUESTION: {research_question}

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words

Create a detailed introduction that provides proper context, establishes significance, and clearly states the research objectives. Include relevant background information that leads logically to the research question."""

        return self._generate_section_content(
            "## Introduction", system_prompt, user_prompt, word_count,
            max_retries, retry_delay, temperature
        )
    
    def _generate_methods(self, scientist_findings: str, word_count: int,
                         max_retries: int, retry_delay: float, temperature: float) -> str:
        """Generate Methods section."""
        system_prompt = """You are writing the Methods section of an academic paper.

CRITICAL: Describe ONLY the data analysis methods that were actually performed according to the scientist findings. 

The Methods should:
- Describe data processing and analysis approaches
- Detail statistical methods used
- Explain computational approaches
- Describe visualization methods
- Include any quality control measures

DO NOT include:
- Experimental procedures (cell culture, transfection, etc.)
- Sample collection methods
- Laboratory protocols

Focus exclusively on data analysis methodology."""

        user_prompt = f"""Write a detailed Methods section based on the data analysis performed:

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words

Describe in detail the data analysis methods, statistical approaches, and computational techniques that were used according to the scientist findings. Focus on methodology that can be reproduced by other researchers."""

        return self._generate_section_content(
            "## Methods", system_prompt, user_prompt, word_count,
            max_retries, retry_delay, temperature
        )
    
    def _generate_results(self, scientist_findings: str, word_count: int,
                         max_retries: int, retry_delay: float, temperature: float) -> str:
        """Generate Results section."""
        system_prompt = """You are writing the Results section of an academic paper.

The Results should:
- Present findings in logical order
- Include specific numbers, statistics, and quantitative results
- Describe patterns and trends observed
- Reference figures and tables using [Figure X: description] format
- Present results objectively without interpretation
- Use past tense for completed analyses

Focus on what was found, not what it means (save interpretation for Discussion)."""

        user_prompt = f"""Write a comprehensive Results section based on:

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words

Present all findings in detail with specific results, statistics, and quantitative data. Include figure suggestions using [Figure X: description] format. Focus on comprehensive presentation of results without interpretation."""

        return self._generate_section_content(
            "## Results", system_prompt, user_prompt, word_count,
            max_retries, retry_delay, temperature
        )
    
    def _generate_discussion(self, research_question: str, scientist_findings: str,
                           word_count: int, max_retries: int, retry_delay: float,
                           temperature: float) -> str:
        """Generate Discussion section."""
        system_prompt = """You are writing the Discussion section of an academic paper.

The Discussion should:
- Interpret the results in context of the research question
- Compare findings with existing literature
- Explain biological or scientific significance
- Address limitations of the study
- Discuss implications for the field
- Suggest future research directions

Structure: Interpretation → Literature Context → Significance → Limitations → Implications → Future Work"""

        user_prompt = f"""Write a comprehensive Discussion section for this research:

RESEARCH QUESTION: {research_question}

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words

Provide detailed interpretation of the results, discuss their significance in the broader scientific context, address limitations, and suggest future research directions. This should be the most analytical section of the paper."""

        return self._generate_section_content(
            "## Discussion", system_prompt, user_prompt, word_count,
            max_retries, retry_delay, temperature
        )
    
    def _generate_conclusion(self, research_question: str, scientist_findings: str,
                           word_count: int, max_retries: int, retry_delay: float,
                           temperature: float) -> str:
        """Generate Conclusion section."""
        system_prompt = """You are writing the Conclusion section of an academic paper.

The Conclusion should:
- Summarize the main findings concisely
- Restate how the research question was answered
- Highlight the most significant contributions
- Present final implications for the field
- Suggest specific future research directions
- End with a strong closing statement

Keep it focused and impactful - this is the reader's final impression."""

        user_prompt = f"""Write a strong Conclusion section for this research:

RESEARCH QUESTION: {research_question}

SCIENTIST FINDINGS: {scientist_findings}

TARGET WORD COUNT: {word_count} words

Provide a compelling conclusion that summarizes key findings, emphasizes contributions to the field, and suggests future research directions. Make it memorable and impactful."""

        return self._generate_section_content(
            "## Conclusion", system_prompt, user_prompt, word_count,
            max_retries, retry_delay, temperature
        )
    
    def _generate_section_content(self, section_header: str, system_prompt: str,
                                 user_prompt: str, target_words: int,
                                 max_retries: int, retry_delay: float,
                                 temperature: float) -> str:
        """Generate content for a specific section with word count control."""

        common_system_prompt = self._generate_system_prompt()
        messages = [
            {"role": "system", "content": common_system_prompt + "\n" + system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(max_retries):
            try:
                response = self.client.create_message(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=min(8000, target_words * 2)  # Allow room for detailed content
                )
                
                content = self.client.get_response_text(response)
                
                if content:
                    # Handle title differently - no header needed, just clean title
                    if section_header == "# ":
                        # For titles, clean and format properly
                        content = content.strip()
                        # Remove any unwanted prefixes
                        content = re.sub(r'^(Title:|#\s*)', '', content, flags=re.IGNORECASE).strip()
                        content = f"# {content}"
                    else:
                        # Add section header if not present for other sections
                        if not content.strip().startswith('#'):
                            content = f"{section_header}\n\n{content}"
                    
                    word_count = len(content.split())
                    
                    # For title, accept any reasonable content
                    if section_header == "# " and content.strip():
                        return content
                    # For other sections, check word count
                    elif word_count >= target_words * 0.5:
                        return content
                    else:
                        print(f"     Section too short ({word_count} words), retrying...")
                        # Modify prompt to encourage more detail
                        user_prompt += f"\n\nNote: Please provide more comprehensive detail to reach approximately {target_words} words."
                
            except Exception as e:
                print(f"     Section generation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    raise Exception(f"Section generation failed after {max_retries} attempts: {e}")
                time.sleep(retry_delay * (attempt + 1))
        
        raise Exception("Section generation failed unexpectedly")
    
    def _collect_citations_from_section(
        self, 
        section_content: str, 
        section_name: str, 
        citation_manager: GlobalCitationManager
    ) -> None:
        """Collect citations from a section and add to global manager."""
        print(f"   Processing {section_name}...")
        
        # Extract content (skip header line)
        lines = section_content.split('\n')
        content_text = '\n'.join(lines[1:] if len(lines) > 1 else [])
        
        # Process sentences for citations
        sentences = re.split(r'[.!?]+', content_text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 5]
        
        for sentence in sentences:
            # Skip figure captions or sentences with existing citations
            if sentence.startswith('[Figure') or '[' in sentence and ']' in sentence:
                continue
            
            # Check if sentence needs citation
            if not self.citation_processor.classify_sentence_needs_citation(sentence):
                continue
            
            # Extract key terms
            key_terms = self.citation_processor.extract_key_terms(sentence)
            if not key_terms:
                continue
            
            # Search for citations
            citations = self._search_for_citations(sentence, key_terms)
            
            # Add citations to global manager
            for citation_data in citations:
                citation = Citation(
                    key=f"{section_name}_{sentence[:50]}_{citation_data.get('term', '')}",
                    source=citation_data.get('source', ''),
                    term=citation_data.get('term', ''),
                    result=citation_data.get('result'),
                    section=section_name,
                    sentence=sentence
                )
                citation_manager.add_citation(citation)
    
    def _search_for_citations(self, sentence: str, key_terms: List[str]) -> List[dict]:
        """Search for citations and filter for relevance."""
        citations = []
        
        for term in key_terms:
            try:
                # Search PubMed first
                pubmed_result = self.tools["search_pubmed"](term)
                if pubmed_result and pubmed_result.success and pubmed_result.output:
                    citations.append({
                        'term': term,
                        'source': 'pubmed',
                        'result': pubmed_result.output
                    })
                
                # Search broader literature
                lit_result = self.tools["search_literature"](term)
                if lit_result and lit_result.success and lit_result.output:
                    citations.append({
                        'term': term,
                        'source': 'literature',
                        'result': lit_result.output
                    })
                    
            except Exception as e:
                print(f"   Citation search failed for '{term}': {e}")
                continue
        
        # Filter for relevance
        return self.citation_processor.filter_relevant_literature(sentence, key_terms, citations)
    
    def _apply_citations_to_section(
        self, 
        section_content: str, 
        section_name: str, 
        citation_manager: GlobalCitationManager
    ) -> str:
        """Apply global citation numbers to a section."""
        print(f"   Applying citations to {section_name}...")
        
        # Split content preserving header
        lines = section_content.split('\n')
        header_line = lines[0] if lines else ""
        content_text = '\n'.join(lines[1:] if len(lines) > 1 else [])
        
        # Process sentences
        sentences = re.split(r'[.!?]+', content_text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 5]
        
        enhanced_content = content_text
        
        for sentence in sentences:
            # Skip figure captions
            if sentence.startswith('[Figure') or '[' in sentence and ']' in sentence:
                continue
            
            # Get citation numbers for this sentence
            citation_numbers = citation_manager.get_citations_for_sentence(section_name, sentence)
            
            if citation_numbers:
                # Apply citations
                citation_text = ', '.join([f"[{num}]" for num in citation_numbers])
                enhanced_sentence = f"{sentence} {citation_text}"
                enhanced_content = enhanced_content.replace(sentence, enhanced_sentence)
        
        # Reconstruct with header
        return f"{header_line}\n{enhanced_content}"
    
    def _parse_sections(self, draft_paper: str) -> Dict[str, str]:
        """Parse draft paper into sections."""
        sections = {}
        lines = draft_paper.split('\n')
        current_section = None
        current_content = []
        
        # Include title in section headers
        section_headers = ['title', 'abstract', 'introduction', 'methods', 'results', 'discussion', 'conclusion']
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check for section header
            is_section_header = False
            
            # Special handling for title (starts with single #)
            if line.strip().startswith('# ') and not line.strip().startswith('## '):
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = '\n'.join(current_content)
                
                # Start title section
                current_section = 'Title'
                current_content = [line]
                is_section_header = True
            else:
                # Check for other section headers
                for header in section_headers:
                    if header != 'title' and ((line_lower.startswith('##') and header in line_lower) or line_lower == header):
                        # Save previous section
                        if current_section and current_content:
                            sections[current_section] = '\n'.join(current_content)
                        
                        # Start new section
                        current_section = header.capitalize()
                        current_content = [line]
                        is_section_header = True
                        break
            
            if not is_section_header:
                if current_section:
                    current_content.append(line)
                else:
                    # Handle content before any section (shouldn't happen with new structure)
                    if 'Header' not in sections:
                        current_section = 'Header'
                        current_content = []
                    current_content.append(line)
        
        # Don't forget last section
        if current_section and current_content:
            sections[current_section] = '\n'.join(current_content)
        
        print(f"   Parsed {len(sections)} sections: {list(sections.keys())}")
        return sections
    
    def _format_final_paper(self, sections: Dict[str, str], references_section: str) -> str:
        """Format final paper with all sections in correct academic order."""
        # Academic paper structure: Title, Abstract, Introduction, Methods, Results, Discussion, Conclusion, References
        section_order = ['Title', 'Abstract', 'Introduction', 'Methods', 'Results', 'Discussion', 'Conclusion']
        
        paper_parts = []
        
        # Add all sections in academic order
        for section_name in section_order:
            if section_name in sections:
                content = sections[section_name].strip()
                if content:
                    paper_parts.append(content)
                    print(f"     ✓ Added {section_name} to final paper")
                else:
                    print(f"     ⚠ Warning: Empty {section_name} section")
            else:
                print(f"     ⚠ Warning: Missing {section_name} section")
        
        # Add References section at the end
        if references_section and references_section.strip():
            paper_parts.append(references_section.strip())
            print("     ✓ Added References section")
        else:
            print("     ⚠ Warning: Empty References section")
        
        final_paper = '\n\n'.join(paper_parts)
        print(f"   Final paper assembled with {len(final_paper.split())} words")
        
        return final_paper
    
    
    def validate_paper_structure(self, paper_content: str) -> Dict[str, Any]:
        """Validate paper structure and return analysis."""
        required_sections = ['abstract', 'introduction', 'methods', 'results', 'discussion', 'conclusion', 'references']
        found_sections = []
        
        content_lower = paper_content.lower()
        
        for section in required_sections:
            if section in content_lower:
                found_sections.append(section)
        
        # Count metrics
        figure_count = len(re.findall(r'\[Figure \d+:', paper_content))
        citation_count = len(re.findall(r'\[\d+\]', paper_content))
        word_count = len(paper_content.split())
        
        # Check References section quality
        has_actual_references = False
        if 'references' in content_lower:
            ref_start = content_lower.find('references')
            references_content = paper_content[ref_start:ref_start+1000]
            has_actual_references = bool(re.search(r'\[\d+\].*?\.', references_content))
        
        return {
            'required_sections': required_sections,
            'found_sections': found_sections,
            'missing_sections': [s for s in required_sections if s not in found_sections],
            'figure_suggestions': figure_count,
            'citation_count': citation_count,
            'has_actual_references': has_actual_references,
            'word_count': word_count,
            'structure_complete': len(found_sections) == len(required_sections),
            'citations_present': citation_count > 0,
            'references_populated': has_actual_references
        }
    
    def generate_and_validate_paper(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int = 3000,
        save_to_file: bool = True,
        output_filename: str = "generated_paper.md"
    ) -> Tuple[str, Dict[str, Any]]:
        """Generate paper and validate its structure."""
        # Generate paper
        paper_content = self.generate_paper(
            research_question=research_question,
            scientist_findings=scientist_findings,
            target_word_count=target_word_count
        )
        
        # Validate structure
        validation = self.validate_paper_structure(paper_content)
        
        # Save if requested
        if save_to_file:
            with open(output_filename, 'w', encoding='utf-8') as f:
                f.write(paper_content)
        
        return paper_content, validation
