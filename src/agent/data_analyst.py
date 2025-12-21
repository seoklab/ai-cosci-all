"""
DS-Star Integration Adapter for ai-cosci-all.

Wraps DS-Star's multi-agent data analysis pipeline into a single ScientificAgent
that can participate in VirtualLab meetings.
"""

import os
import sys
from typing import Optional, List
from pathlib import Path

# Add DS-Star to path
DSSTAR_PATH = Path(__file__).parent.parent.parent / "ext-tools" / "DS-Star"
sys.path.insert(0, str(DSSTAR_PATH))


from dsstar import DS_STAR_Agent, DSConfig
from src.agent.agent import ScientificAgent, AgentPersona


class DataAnalystAgent(ScientificAgent):
    """
    Data Analysis Specialist using DS-Star framework.
    
    This adapter wraps DS-Star's 7-agent pipeline (Analyzer, Planner, Coder,
    Verifier, Router, Debugger, Finalyzer) into VirtualLab's team structure.
    
    Use this agent when:
    - Complex CSV/tabular data analysis is needed
    - Multi-step data processing required
    - Automatic code generation for analysis
    - Expression similarity, correlation analysis, etc.
    
    Example:
        >>> analyst = DataAnalystAgent(api_key="...", input_dir="data/Q1")
        >>> result = analyst.run("Calculate gene expression correlations")
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "openrouter/anthropic/claude-sonnet-4",
        provider: str = "openrouter",
        data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
        input_dir: Optional[str] = None,
        **kwargs
    ):
        """Initialize DataAnalystAgent with DS-Star backend.
        
        Args:
            api_key: API key for LLM provider (uses OPENROUTER_API_KEY env var if not provided)
            model: Model to use (default: OpenRouter Claude 3.5 Sonnet)
            provider: Provider type (default: openrouter)
            data_dir: Database directory path
            input_dir: Question-specific data directory
            **kwargs: Additional arguments passed to ScientificAgent
        """
        # Create persona for this specialist
        persona = AgentPersona(
            title="Data Analysis Specialist (DS-Star)",
            expertise=(
                "Automated multi-step data analysis using DS-Star agentic framework. "
                "Specializes in CSV/tabular data analysis, expression similarity calculations, "
                "correlation analysis, gene clustering, and statistical analysis."
            ),
            goal=(
                "Analyze complex datasets through systematic planning, automated code generation, "
                "execution, verification, and iterative refinement."
            ),
            role=(
                "Execute comprehensive data analysis pipelines when CSV/tabular data analysis "
                "is needed. Automatically generate and debug Python code for data processing."
            )
        )
        
        # Initialize parent ScientificAgent
        super().__init__(
            persona=persona,
            api_key=api_key,
            model=model,
            provider=provider,
            data_dir=data_dir,
            input_dir=input_dir
        )
        
        # Configure DS-Star
        self.dsstar_config = DSConfig(
            model_name=f"openrouter/{model}" if not model.startswith("openrouter/") else model,
            api_key=api_key or os.getenv("OPENROUTER_API_KEY"),
            max_refinement_rounds=5,  
            auto_debug=True,
            debug_attempts=3,  # Prevent infinite loops in meeting
            execution_timeout=1800,  # max 30 minutes
            preserve_artifacts=True,
            data_dir=str(Path(self.input_dir) / "dsstar_temp"),  # Isolated workspace
        )
        
        # Lazy initialization of DS-Star agent
        self._dsstar_agent = None
        
        # Create temp directory for DS-Star outputs
        Path(self.dsstar_config.data_dir).mkdir(parents=True, exist_ok=True)
    
    @property
    def dsstar_agent(self) -> DS_STAR_Agent:
        """Lazy initialization of DS-Star agent."""
        if self._dsstar_agent is None:
            self._dsstar_agent = DS_STAR_Agent(self.dsstar_config)
        return self._dsstar_agent
    
    def run(self, user_question: str, verbose: bool = False) -> str:
        """
        Execute data analysis using DS-Star if applicable, otherwise use standard tools.
        
        Args:
            user_question: The analysis question or task
            verbose: Whether to print detailed execution logs
            
        Returns:
            Analysis result as string
        """
        # Detect if this is a data analysis request that DS-Star should handle
        if self._should_use_dsstar(user_question):
            if verbose:
                print(f"[{self.persona.title}] Using DS-Star pipeline for data analysis")
            return self._run_dsstar_analysis(user_question, verbose)
        else:
            # Fall back to standard ScientificAgent behavior with tools
            if verbose:
                print(f"[{self.persona.title}] Using standard tools for analysis")
            return super().run(user_question, verbose)
    
    def _should_use_dsstar(self, question: str) -> bool:
        """
        Determine if DS-Star should handle this question.
        
        DS-Star is optimal for:
        - Multi-step data analysis workflows
        - Expression/correlation calculations
        - CSV data processing
        - Statistical analysis requiring multiple steps
        
        Args:
            question: The user's question
            
        Returns:
            True if DS-Star should handle it
        """
        # Keywords that indicate DS-Star should be used
        dsstar_keywords = [
            "calculate", "correlation", "similarity", "expression",
            "gene pairs", "clustering", "pairwise", "matrix",
            "csv", "dataframe", "statistical analysis",
            "top genes", "highly expressed", "filter genes"
        ]
        
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in dsstar_keywords)
    
    def _run_dsstar_analysis(self, question: str, verbose: bool) -> str:
        """
        Execute DS-Star pipeline for data analysis.
        
        Args:
            question: Analysis question
            verbose: Detailed logging flag
            
        Returns:
            Formatted analysis result
        """
        try:
            # Discover available CSV files in input directory
            data_files = self._discover_data_files()
            
            if not data_files:
                return (
                    f"[{self.persona.title}] No CSV files found in {self.input_dir}. "
                    "DS-Star requires CSV data files for analysis."
                )
            
            if verbose:
                print(f"[{self.persona.title}] Found data files: {data_files}")
                print(f"[{self.persona.title}] Starting DS-Star pipeline...")
            
            # Copy data files to DS-Star workspace
            self._prepare_dsstar_data(data_files)
            
            # Run DS-Star pipeline
            result = self.dsstar_agent.run_pipeline(
                query=question,
                data_files=[f.name for f in data_files]  # Use just filenames
            )
            
            # Format result for VirtualLab context
            formatted_result = self._format_dsstar_result(result)
            
            if verbose:
                print(f"[{self.persona.title}] DS-Star analysis complete")
            
            return formatted_result
            
        except Exception as e:
            error_msg = (
                f"[{self.persona.title}] DS-Star analysis encountered an error: {str(e)}\n\n"
                "Falling back to standard tool-based analysis..."
            )
            if verbose:
                print(error_msg)
            # Fallback to standard agent behavior
            return super().run(question, verbose)
    
    def _discover_data_files(self) -> List[Path]:
        """
        Discover CSV files in the input directory.
        
        Returns:
            List of Path objects for discovered CSV files
        """
        input_path = Path(self.input_dir)
        csv_files = list(input_path.glob("*.csv"))
        
        # Also check common subdirectories
        for subdir in ["data", "Data", "DATA"]:
            subdir_path = input_path / subdir
            if subdir_path.exists():
                csv_files.extend(subdir_path.glob("*.csv"))
        
        return sorted(set(csv_files))  # Remove duplicates
    
    def _prepare_dsstar_data(self, data_files: List[Path]):
        """
        Copy data files to DS-Star's working directory.
        
        Args:
            data_files: List of data file paths to copy
        """
        import shutil
        
        dsstar_data_dir = Path(self.dsstar_config.data_dir)
        dsstar_data_dir.mkdir(parents=True, exist_ok=True)
        
        for file_path in data_files:
            dest_path = dsstar_data_dir / file_path.name
            if not dest_path.exists():
                shutil.copy2(file_path, dest_path)
    
    def _format_dsstar_result(self, result: dict) -> str:
        """
        Format DS-Star result for VirtualLab meeting context.
        
        Args:
            result: DS-Star pipeline result dictionary
            
        Returns:
            Formatted string for meeting transcript
        """
        output_parts = [
            f"[{self.persona.title} - DS-Star Analysis]",
            ""
        ]
        
        # Add summary
        output_parts.append("**Analysis Complete:**")
        output_parts.append(f"- Run ID: {result['run_id']}")
        output_parts.append(f"- Total Steps: {result['total_steps']}")
        output_parts.append("")
        
        # Add result
        output_parts.append("**Results:**")
        final_result = result.get('final_result', '').strip()
        
        # Truncate if too long (meeting context limitation)
        if len(final_result) > 2000:
            output_parts.append(final_result[:2000] + "...[truncated]")
            output_parts.append("")
            output_parts.append(f"**Full results saved to:** {result['output_file']}")
        else:
            output_parts.append(final_result)
        
        return "\n".join(output_parts)


# Convenience function for creating DataAnalystAgent
def create_data_analyst(
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    provider: str = "openrouter",
    data_dir: str = "/home.galaxy4/sumin/project/aisci/Competition_Data",
    input_dir: Optional[str] = None
) -> DataAnalystAgent:
    """
    Factory function to create a DataAnalystAgent.
    
    Args:
        api_key: API key (defaults to OPENROUTER_API_KEY env var)
        model: Model to use (defaults to Claude 3.5 Sonnet via OpenRouter)
        provider: Provider type
        data_dir: Database directory
        input_dir: Question-specific data directory
        
    Returns:
        DataAnalystAgent instance
    """
    if model is None:
        model = "anthropic/claude-3.5-sonnet"
    
    return DataAnalystAgent(
        api_key=api_key,
        model=model,
        provider=provider,
        data_dir=data_dir,
        input_dir=input_dir
    )

