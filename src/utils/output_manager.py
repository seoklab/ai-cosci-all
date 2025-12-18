"""Output directory management for organizing run-specific files.

This module provides utilities to organize all outputs (answer files, CSV files,
plots, etc.) into question/run-specific directories instead of cluttering the cwd.
"""

import os
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager


class OutputManager:
    """Manages output directories for each run."""

    def __init__(self, base_dir: str = "outputs"):
        """Initialize the output manager.

        Args:
            base_dir: Base directory for all outputs (default: "outputs/")
        """
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._current_run_dir: Optional[Path] = None

    def create_run_directory(
        self,
        question: str,
        mode: str = "single",
        custom_name: Optional[str] = None
    ) -> Path:
        """Create a new run-specific directory.

        Args:
            question: The research question (used for hashing)
            mode: The execution mode (single, virtual-lab, etc.)
            custom_name: Optional custom directory name

        Returns:
            Path to the created directory
        """
        if custom_name:
            dir_name = custom_name
        else:
            # Create directory name: YYYYMMDD_HHMMSS_<mode>_<question_hash>
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            question_hash = hashlib.md5(question.encode()).hexdigest()[:8]
            dir_name = f"{timestamp}_{mode}_{question_hash}"

        run_dir = self.base_dir / dir_name
        run_dir.mkdir(parents=True, exist_ok=True)

        # Save question to metadata file
        metadata_file = run_dir / "QUESTION.txt"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            f.write(f"Mode: {mode}\n")
            f.write(f"Timestamp: {datetime.now().isoformat()}\n")
            f.write(f"\n{'='*60}\n")
            f.write(f"RESEARCH QUESTION:\n")
            f.write(f"{'='*60}\n\n")
            f.write(question)

        self._current_run_dir = run_dir
        return run_dir

    def get_current_run_dir(self) -> Optional[Path]:
        """Get the current run directory."""
        return self._current_run_dir

    def get_output_path(self, filename: str, subdir: Optional[str] = None) -> Path:
        """Get full path for an output file in the current run directory.

        Args:
            filename: Name of the output file
            subdir: Optional subdirectory within the run directory

        Returns:
            Full path to the output file
        """
        if self._current_run_dir is None:
            raise RuntimeError("No run directory set. Call create_run_directory() first.")

        if subdir:
            output_dir = self._current_run_dir / subdir
            output_dir.mkdir(parents=True, exist_ok=True)
            return output_dir / filename

        return self._current_run_dir / filename

    def reset(self):
        """Reset the current run directory."""
        self._current_run_dir = None


# Global output manager instance
_global_output_manager: Optional[OutputManager] = None


def get_output_manager() -> OutputManager:
    """Get the global output manager instance."""
    global _global_output_manager
    if _global_output_manager is None:
        _global_output_manager = OutputManager()
    return _global_output_manager


def set_output_manager(manager: OutputManager):
    """Set the global output manager instance."""
    global _global_output_manager
    _global_output_manager = manager


@contextmanager
def run_context(question: str, mode: str = "single", custom_name: Optional[str] = None):
    """Context manager for a run with automatic directory management.

    Usage:
        with run_context(question, mode="virtual-lab") as run_dir:
            # All operations in this block will use run_dir
            result = run_virtual_lab(question)
            save_answer(result, run_dir)

    Args:
        question: Research question
        mode: Execution mode
        custom_name: Optional custom directory name

    Yields:
        Path to the run directory
    """
    manager = get_output_manager()
    run_dir = manager.create_run_directory(question, mode, custom_name)

    # Store original working directory
    original_cwd = Path.cwd()

    try:
        yield run_dir
    finally:
        # Reset on exit (don't change cwd back - let caller decide)
        pass


def get_run_output_path(filename: str, subdir: Optional[str] = None) -> Path:
    """Get output path for a file in the current run.

    This is a convenience function that uses the global output manager.

    Args:
        filename: Output filename
        subdir: Optional subdirectory

    Returns:
        Full path to the output file
    """
    return get_output_manager().get_output_path(filename, subdir)


def get_current_run_dir() -> Optional[Path]:
    """Get the current run directory from global output manager.

    Returns:
        Path to current run directory, or None if not set
    """
    return get_output_manager().get_current_run_dir()
