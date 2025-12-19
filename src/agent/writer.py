from typing import Optional
from src.agent.openrouter_client import OpenRouterClient
from src.agent.anthropic_client import AnthropicClient
from src.config import get_global_config
from src.tools.implementations import search_pubmed
from src.tools.implementations_cached import (
    search_literature_cached as search_literature,
)

import re
import time


class OpenRouterPaperSolver:
    """
    A paper writing agent that integrates with OpenRouter API to generate
    academic papers based on research findings.
    """
    
    def __init__(self, api_key: Optional[str] = None, model: str = "google/gemini-3-pro-preview", provider: str = "openrouter"):
        """
        Initialize the OpenRouter Paper Solver.
        
        Args:
            model (str): The model to use (e.g., "google/gemini-3-pro-preview", "openai/gpt-4o")
            api_key (str, optional): OpenRouter API key. If None, will get from environment.
        """
        if provider == "anthropic":
            self.client = AnthropicClient(api_key=api_key, model=model)
        else:
            self.client = OpenRouterClient(api_key=api_key, model=model)
        
        self.tools = {
            "search_literature": search_literature,
            "search_pubmed": search_pubmed,
        }


    def _create_system_prompt(self) -> str:
        """
        Create a comprehensive system prompt for academic paper writing.
        
        Returns:
            str: Detailed system prompt for the LLM
        """
        return """You are a senior academic researcher writing a high-quality scientific paper. You have access to literature search tools and must use them to provide proper citations for all scientific claims.

CRITICAL REQUIREMENTS:

1. STRUCTURE - Follow this exact structure:
   - Abstract (150-250 words)
   - Introduction (with background, proper citations, and objectives)
   - Methods (ONLY describe data analysis methods used by scientists, NOT experimental procedures)
   - Results (detailed analysis of findings with figure suggestions)
   - Discussion (interpretation and implications with citations)
   - Conclusion (summary and future directions)
   - References (MANDATORY - numbered list of all citations)

2. CITATION REQUIREMENTS - EXTREMELY IMPORTANT:
   - For every scientific claim in the Introduction and Discussion, you MUST search for and cite real academic papers
   - Use the search_pubmed, search_biorxiv, or search_arxiv tools to find relevant papers
   - Use numbered citations in square brackets: [1], [2], etc.
   - NEVER make up citations or reference numbers
   - If you cannot find a citation, omit the claim rather than fabricate
   - The References section is MANDATORY and must contain all cited papers

3. METHODS SECTION RULES:
   - ONLY describe the data analysis methods that the scientists actually performed
   - DO NOT invent or describe experimental procedures (cell culture, transfection, etc.)
   - Focus on computational analysis, statistical methods, and data processing ONLY
   - Base everything on what is explicitly mentioned in the scientist findings

4. LITERATURE SEARCH PROTOCOL:
   - Before writing Introduction, search for 3-5 key papers on the topic
   - Before writing Discussion, search for recent relevant papers
   - Use specific, targeted search terms related to the research question
   - Prioritize recent papers (last 5-10 years) when possible

5. FIGURE INTEGRATION:
   - Insert up to 10 figure suggestions using: [Figure X: Detailed description...]
   - Base figures ONLY on data/results mentioned in scientist findings
   - Do NOT suggest figures for experiments not performed

6. CONTENT ACCURACY:
   - Base paper EXCLUSIVELY on provided scientist findings
   - Use specific numbers, statistics, and results from findings
   - Do NOT add speculative or general knowledge not supported by findings
   - Maintain strict scientific rigor and evidence-based writing

7. FORMATTING:
   - Use proper Markdown formatting with clear section headers
   - Number citations consecutively [1], [2], [3]...
   - Format References section as: [1] Author(s). Title. Journal. Year; Volume: Pages.

SEARCH TOOL USAGE:
- Use search_pubmed("query terms") for biomedical papers
- Use search_literature("query terms") for broader academic literature
- Search before writing Introduction and Discussion sections

Remember: Every scientific claim needs a citation. Use the search tools actively to find real papers to support your statements."""

    def _create_user_prompt(self, research_question: str, scientist_findings: str, target_word_count: int) -> str:
        """
        Create the user prompt with the specific research context.
        
        Args:
            research_question (str): The research question to address
            scientist_findings (str): Findings from the scientist agent
            target_word_count (int): Target word count for the paper
            
        Returns:
            str: Formatted user prompt
        """
        return f"""Please write a complete academic paper based on the following information:

RESEARCH QUESTION:
{research_question}

SCIENTIST FINDINGS:
{scientist_findings}

TARGET WORD COUNT: Approximately {target_word_count} words

Please generate a full academic paper that:
1. Addresses the research question comprehensively
2. Incorporates all relevant findings provided
3. Follows the required structure (Abstract, Introduction, Results, Discussion, Conclusion, References)
4. Includes appropriate figure suggestions using the [Figure X: description] format
5. Maintains scientific accuracy and integrity
6. Uses only verifiable citations or no citations when uncertain

Begin writing the paper now, ensuring it meets all the specified requirements."""

    def _conduct_literature_search(self, research_question: str, scientist_findings: str) -> str:
        """
        Conduct literature searches to gather citations for the paper.
        
        Args:
            research_question (str): The research question
            scientist_findings (str): The scientist's findings
            
        Returns:
            str: Literature search results formatted for inclusion in prompts
        """
        search_results = []
        
        # Extract key terms from research question and findings
        key_terms = []
        
        # Add terms based on content analysis
        if "mRNA" in research_question or "mRNA" in scientist_findings:
            key_terms.extend(["mRNA stability", "mRNA decay", "poly(A) tail"])
        if "virus" in research_question or "viral" in scientist_findings:
            key_terms.extend(["viral RNA", "RNA virus"])
        if "CRE" in scientist_findings or "cis-regulatory" in research_question:
            key_terms.extend(["cis-regulatory element", "RNA regulation"])
        if "nanopore" in research_question or "nanopore" in scientist_findings:
            key_terms.extend(["nanopore sequencing", "direct RNA sequencing"])
        if "poly(A)" in research_question or "poly(A)" in scientist_findings:
            key_terms.extend(["polyadenylation", "deadenylation"])
        
        # Conduct searches with different tools
        search_queries = key_terms[:3]  # Limit to 3 most relevant terms
        
        for query in search_queries:
            try:
                # Search PubMed
                print(f"   Searching PubMed for: {query}")
                pubmed_result = self.tools["search_pubmed"](query)
                if pubmed_result and pubmed_result.success:
                    search_results.append(f"PubMed search for '{query}':\n{pubmed_result.output}\n")
                
                # Search literature (broader search)
                print(f"   Searching literature for: {query}")
                lit_result = self.tools["search_literature"](query)
                if lit_result and lit_result.success:
                    search_results.append(f"Literature search for '{query}':\n{lit_result.output}\n")
                    
            except Exception as e:
                # Continue if search fails
                print(f"   Search failed for '{query}': {e}")
                continue
        
        if search_results:
            return "LITERATURE SEARCH RESULTS:\n" + "\n".join(search_results)
        else:
            return "No literature search results available. Write paper without specific citations but use general academic language."

    def _create_enhanced_user_prompt(self, research_question: str, scientist_findings: str, target_word_count: int, literature_results: str) -> str:
        """
        Create the user prompt with literature search results included.
        
        Args:
            research_question (str): The research question to address
            scientist_findings (str): Findings from the scientist agent
            target_word_count (int): Target word count for the paper
            literature_results (str): Results from literature searches
            
        Returns:
            str: Formatted user prompt with literature context
        """
        return f"""Please write a complete academic paper based on the following information:

RESEARCH QUESTION:
{research_question}

SCIENTIST FINDINGS:
{scientist_findings}

{literature_results}

TARGET WORD COUNT: Approximately {target_word_count} words

WRITING INSTRUCTIONS:
1. Use the literature search results above to provide proper citations in Introduction and Discussion
2. In the Methods section, describe ONLY the data analysis approaches mentioned in the scientist findings
3. Do NOT describe experimental procedures like cell culture, transfection, or RNA extraction
4. Focus Methods on: data processing, statistical analysis, computational methods, visualization
5. Base all Results strictly on the provided scientist findings
6. Include numbered citations [1], [2], [3] throughout the text
7. ALWAYS include a complete References section with all citations
8. Include appropriate figure suggestions using [Figure X: description] format

Begin writing the paper now, ensuring rigorous academic standards with proper citations and evidence-based content."""

    def generate_paper(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int = 3000,
        max_retries: int = 3,
        retry_delay: float = 2.0,
        temperature: float = 0.2
    ) -> str:
        """
        Generate a complete academic paper based on research question and findings.
        
        Args:
            research_question (str): The research question to address
            scientist_findings (str): Output from the Scientist Agent
            target_word_count (int): Target word count for the paper (default: 4000)
            max_retries (int): Maximum number of API call retries (default: 3)
            retry_delay (float): Delay between retries in seconds (default: 2.0)
            temperature (float): Sampling temperature for the model (default: 0.7)
            
        Returns:
            str: Complete academic paper in Markdown format
            
        Raises:
            Exception: If API calls fail after all retries
        """
        
        # Conduct literature searches first
        print("🔍 Conducting literature searches for citations...")
        literature_results = self._conduct_literature_search(research_question, scientist_findings)
        
        # Prepare the prompts with literature context
        system_prompt = self._create_system_prompt()
        user_prompt = self._create_enhanced_user_prompt(research_question, scientist_findings, target_word_count, literature_results)
        
        # Prepare messages for the API call
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        # Attempt API call with retries
        for attempt in range(max_retries):
            try:
                
                response = self.client.create_message(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=30000,  # Allow for long-form content
                )
                
                paper_content = self.client.get_response_text(response)
                
                if paper_content:
                    current_word_count = len(paper_content.split())
                    # Accept papers that are at least 50% of target word count
                    if current_word_count < target_word_count * 0.5:
                        continue
                    return paper_content
                else:
                    raise Exception("Empty response from API")
                    
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    error_msg = f"All {max_retries} API call attempts failed. Last error: {str(e)}"
                    raise Exception(error_msg)
                else:
                    # Wait before retrying
                    time.sleep(retry_delay)
                    retry_delay *= 1.5  # Exponential backoff
        
        # Should not reach here, but just in case
        raise Exception("Unexpected error in paper generation")

    def validate_paper_structure(self, paper_content: str) -> dict:
        """
        Validate that the generated paper has the expected structure.
        
        Args:
            paper_content (str): The generated paper content
            
        Returns:
            dict: Validation results with structure analysis
        """
        required_sections = ['abstract', 'introduction', 'methods', 'results', 'discussion', 'conclusion', 'references']
        found_sections = []
        
        content_lower = paper_content.lower()
        
        for section in required_sections:
            if section in content_lower:
                found_sections.append(section)
        
        # Count figure suggestions
        figure_count = len(re.findall(r'\[Figure \d+:', paper_content))
        
        # Count citations (numbered references like [1], [2], etc.)
        citation_count = len(re.findall(r'\[\d+\]', paper_content))
        
        # Estimate word count
        word_count = len(paper_content.split())
        
        # Check if References section has actual references
        references_content = ""
        if 'references' in content_lower:
            ref_start = content_lower.find('references')
            references_content = paper_content[ref_start:ref_start+1000]  # Check first 1000 chars after References
        
        has_actual_references = bool(re.search(r'\[\d+\].*?\.', references_content))
        
        validation_result = {
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
        
        return validation_result

    def save_paper(self, paper_content: str, filename: str = "generated_paper.md") -> str:
        """
        Save the generated paper to a file.
        
        Args:
            paper_content (str): The paper content to save
            filename (str): Output filename (default: "generated_paper.md")
            
        Returns:
            str: Path to the saved file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(paper_content)
            
            return filename
            
        except Exception as e:
            error_msg = f"Failed to save paper: {str(e)}"
            raise Exception(error_msg)

    def generate_and_validate_paper(
        self, 
        research_question: str, 
        scientist_findings: str, 
        target_word_count: int = 4000,
        save_to_file: bool = True,
        output_filename: str = "generated_paper.md"
    ) -> tuple[str, dict]:
        """
        Generate a paper and validate its structure in one call.
        
        Args:
            research_question (str): The research question to address
            scientist_findings (str): Output from the Scientist Agent
            target_word_count (int): Target word count for the paper
            save_to_file (bool): Whether to save the paper to a file
            output_filename (str): Filename for saving the paper
            
        Returns:
            tuple: (paper_content, validation_results)
        """
        # Generate the paper
        paper_content = self.generate_paper(
            research_question=research_question,
            scientist_findings=scientist_findings,
            target_word_count=target_word_count
        )
        
        # Validate the structure
        validation = self.validate_paper_structure(paper_content)
        
        # Save to file if requested
        if save_to_file:
            self.save_paper(paper_content, output_filename)
        
        return paper_content, validation


# Example usage and testing functions
def test_openrouter_paper_solver():
    """
    Test function to demonstrate usage of the OpenRouterPaperSolver.
    """
    # Example research question and findings
    research_question = "How do T-cell subtype distributions change in response to immune challenges?"
    
    scientist_findings = """
    Our analysis of T-cell populations revealed significant changes in CD4+ and CD8+ subtypes 
    following immune stimulation. Key findings include:
    
    1. CD4+ T-cell populations showed a 35% increase in Th1 cells (p < 0.001)
    2. CD8+ cytotoxic T-cells increased by 42% in activated samples (p < 0.01) 
    3. Regulatory T-cells (Tregs) decreased by 18% during acute response phase
    4. Memory T-cell populations showed enhanced activation markers (CD69, CD25)
    5. Gene expression analysis revealed upregulation of IFN-γ and IL-2 pathways
    
    Statistical analysis was performed using t-tests and ANOVA with multiple comparison correction.
    Sample sizes: Control n=24, Treatment n=26. All experiments performed in triplicate.
    """
    
    try:
        # Initialize the paper solver
        solver = OpenRouterPaperSolver(model="anthropic/claude-3.5-sonnet")
        
        # Generate and validate the paper
        paper, validation = solver.generate_and_validate_paper(
            research_question=research_question,
            scientist_findings=scientist_findings,
            target_word_count=3500,
            save_to_file=True,
            output_filename="example_tcell_paper.md"
        )
        
        print("Paper generation completed successfully!")
        print(f"Paper length: {len(paper)} characters")
        print(f"Structure validation: {validation}")
        
        return paper, validation
        
    except Exception as e:
        print(f"Error during testing: {str(e)}")
        return None, None


if __name__ == "__main__":
    # Run the test if this file is executed directly
    test_openrouter_paper_solver()
