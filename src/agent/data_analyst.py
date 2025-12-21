"""
DS-Star Integration Adapter for ai-cosci-all.

Wraps DS-Star's multi-agent data analysis pipeline into a single ScientificAgent
that can participate in VirtualLab meetings.
"""

import os
import sys
import traceback
import yaml
import datetime
from typing import Optional, List
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add DS-Star to path
DSSTAR_PATH = Path(__file__).parent.parent.parent / "ext-tools" / "DS-Star"
sys.path.insert(0, str(DSSTAR_PATH))

from dsstar import DS_STAR_Agent, DSConfig
from src.agent.agent import ScientificAgent, AgentPersona
from src.utils.logger import get_logger


def load_dsstar_config(config_path: Path) -> dict:
    """Load DS-Star config.yaml if exists."""
    if config_path.exists():
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    return {}


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
        
        super().__init__(
            persona=persona,
            api_key=api_key,
            model=model,
            provider=provider,
            data_dir=data_dir,
            input_dir=input_dir
        )
        
        self.logger = get_logger()
        
        dsstar_config_path = DSSTAR_PATH / "config.yaml"
        dsstar_yaml_config = load_dsstar_config(dsstar_config_path)
        agent_models = dsstar_yaml_config.get('agent_models', {})
        
        resolved_api_key = (
            api_key or 
            os.getenv("OPENROUTER_API_KEY") or 
            os.getenv("OPENROUTER_KEY")
        )
        
        if not resolved_api_key:
            self.logger.warning(
                "No API key found! DS-Star will fail. Set OPENROUTER_API_KEY in .env or pass api_key parameter",
                indent=2
            )
        
        self.dsstar_base_config = {
            'model_name': f"openrouter/{model}" if not model.startswith("openrouter/") else model,
            'api_key': resolved_api_key,
            'max_refinement_rounds': dsstar_yaml_config.get('max_refinement_rounds', 5),
            'auto_debug': dsstar_yaml_config.get('auto_debug', True),
            'debug_attempts': dsstar_yaml_config.get('debug_attempts', 3),
            'execution_timeout': dsstar_yaml_config.get('execution_timeout', 1800),
            'preserve_artifacts': True,
            'agent_models': agent_models
        }
        
        self.input_dir_path = Path(self.input_dir)
        
        if agent_models:
            self.logger.info(f"Loaded {len(agent_models)} specialized models from DS-Star config.yaml", indent=2)
    
    def create_dsstar_agent(self) -> DS_STAR_Agent:
        """Create an isolated DS-Star agent for each analysis.
        
        Uses original data location with unique runs_dir per execution.
        
        Returns:
            DS_STAR_Agent with isolated runs_dir and shared data_dir
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:20]
        project_root = Path(__file__).parent.parent.parent
        unique_runs_dir = project_root / "outputs" / "dsstar_runs" / timestamp
        unique_runs_dir.mkdir(parents=True, exist_ok=True)
        
        original_data_dir = self.input_dir_path.resolve()
        
        self.logger.info(f"DS-Star data_dir (original): {original_data_dir}", indent=4)
        self.logger.info(f"DS-Star runs_dir (isolated): {unique_runs_dir}", indent=4)
        
        config = DSConfig(
            data_dir=str(original_data_dir),
            runs_dir=str(unique_runs_dir),
            **self.dsstar_base_config
        )
        
        return DS_STAR_Agent(config)
    
    def run(self, user_question: str, verbose: bool = False) -> str:
        """
        Execute data analysis using DS-Star if applicable, otherwise use standard tools.
        
        Args:
            user_question: The analysis question or task
            verbose: Whether to print detailed execution logs
            
        Returns:
            Analysis result as string
        """
        self.logger.progress(f"[{self.persona.title}] Evaluating DS-Star applicability...")
        
        should_use = self._should_use_dsstar(user_question)
        
        if should_use:
            self.logger.info(f"[{self.persona.title}] DS-Star pipeline SELECTED for data analysis", indent=2)
            return self._run_dsstar_analysis(user_question, verbose)
        else:
            self.logger.warning(f"[{self.persona.title}] DS-Star NOT selected - using standard tools", indent=2)
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
        dsstar_keywords = [
            "calculate", "correlation", "similarity", "expression",
            "gene pairs", "clustering", "pairwise", "matrix",
            "csv", "dataframe", "statistical analysis",
            "top genes", "highly expressed", "filter genes",
            "process", "tpm", "analyze", "quantif"
        ]
        
        question_lower = question.lower()
        matched = [kw for kw in dsstar_keywords if kw in question_lower]
        
        if matched:
            self.logger.verbose(f"DS-Star keywords matched: {matched}", indent=4)
            return True
        else:
            self.logger.verbose(f"No DS-Star keywords matched in question", indent=4)
            return False
    
    def _run_dsstar_analysis(self, question: str, verbose: bool) -> str:
        """Execute DS-Star pipeline via subprocess.
        
        Args:
            question: Analysis question
            verbose: Detailed logging flag
            
        Returns:
            Formatted analysis result
        """
        self.logger.progress(f"[{self.persona.title}] Starting DS-Star subprocess...")
        
        try:
            import subprocess
            import shutil
            
            # Discover CSV files
            self.logger.info(f"Discovering CSV files in: {self.input_dir}", indent=2)
            data_files = self._discover_data_files()
            
            if not data_files:
                error_msg = f"[{self.persona.title}] No CSV files found in {self.input_dir}"
                self.logger.error(error_msg, indent=2)
                return error_msg
            
            self.logger.success(f"Found {len(data_files)} CSV files", indent=2)
            
            # Create config for subprocess
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            run_id = f"dsstar_{timestamp}"
            
            project_root = Path(__file__).parent.parent.parent
            runs_dir = project_root / "outputs" / "dsstar_runs" / run_id
            runs_dir.mkdir(parents=True, exist_ok=True)
            
            config_data = dict(self.dsstar_base_config)
            config_data.update({
                'run_id': run_id,
                'runs_dir': str(runs_dir),
                'data_dir': str(Path(self.input_dir).resolve()),
                'query': question,
                'data_files': [f.name for f in data_files],
                'interactive': False,
                'preserve_artifacts': True
            })
            
            config_path = runs_dir / f"config_{timestamp}.yaml"
            with open(config_path, 'w') as f:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            
            self.logger.info(f"Config saved: {config_path}", indent=2)
            self.logger.verbose(f"  - Data dir: {config_data['data_dir']}", indent=2)
            self.logger.verbose(f"  - Runs dir: {config_data['runs_dir']}", indent=2)
            self.logger.verbose(f"  - Data files: {len(config_data['data_files'])} files", indent=2)
            self.logger.verbose(f"  - Max refinement rounds: {config_data.get('max_refinement_rounds', 'N/A')}", indent=2)
            self.logger.verbose(f"  - Debug attempts: {config_data.get('debug_attempts', 'N/A')}", indent=2)
            self.logger.verbose(f"  - Agent models: {len(config_data.get('agent_models', {}))}", indent=2)
            self.logger.progress("Launching DS-Star subprocess...", indent=2)
            
            # Execute subprocess
            result = subprocess.run(
                [sys.executable, "dsstar.py", "--config", str(config_path)],
                cwd=str(DSSTAR_PATH),
                capture_output=True,
                text=True,
                timeout=3600
            )
            
            if result.returncode != 0:
                self.logger.error(f"DS-Star failed: {result.stderr[:200]}", indent=2)
                return super().run(question, verbose)
            
            self.logger.success("DS-Star completed", indent=2)
            
            # Collect results
            output_dir = runs_dir / run_id / "final_output"
            output_files = {}
            if output_dir.exists():
                for f in output_dir.glob("*"):
                    if f.is_file():
                        output_files[f.stem] = str(f)
            
            # Format result
            parts = [f"[{self.persona.title} - DS-Star Subprocess]", "", f"Run: {run_id}"]
            if output_files:
                parts.append("Files:")
                for name, path in output_files.items():
                    parts.append(f"- {Path(path).name}")
            
            # Try to read result
            result_file = output_files.get('result')
            if result_file and Path(result_file).exists():
                with open(result_file) as f:
                    content = f.read().strip()
                    if len(content) > 2000:
                        parts.append("")
                        parts.append("Results (truncated):")
                        parts.append(content[:2000] + "...")
                    else:
                        parts.append("")
                        parts.append("Results:")
                        parts.append(content)
            
            return "\n".join(parts)
            
        except subprocess.TimeoutExpired:
            self.logger.error("DS-Star timeout", indent=2)
            return super().run(question, verbose)
        except Exception as e:
            self.logger.error(f"DS-Star error: {e}", indent=2)
            return super().run(question, verbose)

    def _discover_data_files(self) -> List[Path]:
        """
        Discover CSV files in the input directory.
        
        Returns:
            List of Path objects for discovered CSV files
        """
        input_path = Path(self.input_dir)
        csv_files = list(input_path.glob("*.csv"))
        
        for subdir in ["data", "Data", "DATA"]:
            subdir_path = input_path / subdir
            if subdir_path.exists():
                csv_files.extend(subdir_path.glob("*.csv"))
        
        return sorted(set(csv_files))
    
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
        
        output_parts.append("**Analysis Complete:**")
        output_parts.append(f"- Run ID: {result['run_id']}")
        output_parts.append(f"- Total Steps: {result['total_steps']}")
        output_parts.append("")
        
        output_parts.append("**Results:**")
        final_result = result.get('final_result', '').strip()
        
        if len(final_result) > 2000:
            output_parts.append(final_result[:2000] + "...[truncated]")
            output_parts.append("")
            output_parts.append(f"**Full results saved to:** {result['output_file']}")
        else:
            output_parts.append(final_result)
        
        return "\n".join(output_parts)


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
