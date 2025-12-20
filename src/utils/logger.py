"""Enhanced logging utility for CoScientist with timestamps and progress tracking."""

import sys
from datetime import datetime
from typing import Optional
from enum import Enum


class LogLevel(Enum):
    """Log levels for different types of messages."""
    INFO = "INFO"
    SUCCESS = "✓"
    WARNING = "⚠"
    ERROR = "✗"
    PROGRESS = "→"
    SECTION = "═"


class Logger:
    """Enhanced logger with timestamps, colors, and structured output."""

    # ANSI color codes
    COLORS = {
        'RESET': '\033[0m',
        'BOLD': '\033[1m',
        'DIM': '\033[2m',
        'GREEN': '\033[92m',
        'BLUE': '\033[94m',
        'YELLOW': '\033[93m',
        'RED': '\033[91m',
        'CYAN': '\033[96m',
        'MAGENTA': '\033[95m',
    }

    def __init__(self, verbose: bool = False, use_colors: bool = True):
        """Initialize logger.

        Args:
            verbose: If True, show all messages. If False, only show important ones.
            use_colors: If True, use ANSI colors for output.
        """
        self.verbose_mode = verbose  # Renamed to avoid collision with verbose() method
        self.use_colors = use_colors and sys.stdout.isatty()
        self.start_time = None
        self.last_event_time = None

    def _color(self, text: str, color: str) -> str:
        """Apply color to text if colors are enabled."""
        if not self.use_colors:
            return text
        return f"{self.COLORS.get(color, '')}{text}{self.COLORS['RESET']}"

    def _timestamp(self) -> str:
        """Get current timestamp string."""
        now = datetime.now()
        time_str = now.strftime("%H:%M:%S")

        # Add elapsed time if start_time is set
        if self.start_time:
            elapsed = (now - self.start_time).total_seconds()
            if elapsed < 60:
                elapsed_str = f"{elapsed:.1f}s"
            elif elapsed < 3600:
                mins = int(elapsed // 60)
                secs = int(elapsed % 60)
                elapsed_str = f"{mins}m{secs}s"
            else:
                hours = int(elapsed // 3600)
                mins = int((elapsed % 3600) // 60)
                elapsed_str = f"{hours}h{mins}m"
            time_str = f"{time_str} (+{elapsed_str})"

        return self._color(f"[{time_str}]", 'DIM')

    def start_timer(self):
        """Start the global timer."""
        self.start_time = datetime.now()
        self.last_event_time = self.start_time

    def get_elapsed_time(self) -> tuple[int, int, int]:
        """Get elapsed time since start.

        Returns:
            Tuple of (hours, minutes, seconds)
        """
        if not self.start_time:
            return (0, 0, 0)

        elapsed = (datetime.now() - self.start_time).total_seconds()
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        return (hours, minutes, seconds)

    def section(self, title: str, width: int = 70):
        """Print a section header."""
        print()
        print(self._color("=" * width, 'BOLD'))
        print(self._color(title.center(width), 'BOLD'))
        print(self._color("=" * width, 'BOLD'))

    def subsection(self, title: str, width: int = 70):
        """Print a subsection header."""
        print()
        print(self._color("-" * width, 'CYAN'))
        print(self._color(f"  {title}", 'CYAN'))
        print(self._color("-" * width, 'CYAN'))

    def info(self, message: str, indent: int = 0):
        """Print an info message."""
        prefix = " " * indent
        print(f"{self._timestamp()} {prefix}{message}")

    def success(self, message: str, indent: int = 0):
        """Print a success message."""
        prefix = " " * indent
        symbol = self._color("✓", 'GREEN')
        print(f"{self._timestamp()} {symbol} {prefix}{message}")

    def warning(self, message: str, indent: int = 0):
        """Print a warning message."""
        prefix = " " * indent
        symbol = self._color("⚠", 'YELLOW')
        print(f"{self._timestamp()} {symbol} {prefix}{message}")

    def error(self, message: str, indent: int = 0):
        """Print an error message."""
        prefix = " " * indent
        symbol = self._color("✗", 'RED')
        print(f"{self._timestamp()} {symbol} {prefix}{message}")

    def progress(self, message: str, indent: int = 0):
        """Print a progress/action message."""
        prefix = " " * indent
        symbol = self._color("→", 'BLUE')
        print(f"{self._timestamp()} {symbol} {prefix}{message}")

    def verbose(self, message: str, indent: int = 0):
        """Print a verbose message (only if verbose mode is on)."""
        if self.verbose_mode:
            prefix = " " * indent
            print(f"{self._timestamp()} {self._color('[V]', 'DIM')} {prefix}{message}")

    def agent_action(self, agent_name: str, action: str, indent: int = 0):
        """Print an agent action message."""
        prefix = " " * indent
        agent_colored = self._color(agent_name, 'MAGENTA')
        print(f"{self._timestamp()} {prefix}{agent_colored}: {action}")

    def subtask(self, subtask_id: str, description: str, assigned: list[str]):
        """Print a subtask header."""
        print()
        print(self._color(f"┌─ Subtask {subtask_id}", 'CYAN'))
        print(self._color(f"│  {description}", 'CYAN'))
        print(self._color(f"│  Assigned: {', '.join(assigned)}", 'CYAN'))
        print(self._color(f"└─", 'CYAN'))

    def result_summary(self, title: str, content: str, max_lines: int = 5):
        """Print a result summary with truncation."""
        print()
        print(self._color(f"  {title}:", 'BOLD'))
        lines = content.split('\n')
        if len(lines) > max_lines:
            for line in lines[:max_lines]:
                print(f"    {line}")
            remaining = len(lines) - max_lines
            print(self._color(f"    ... ({remaining} more lines)", 'DIM'))
        else:
            for line in lines:
                print(f"    {line}")

    def print_elapsed_time(self):
        """Print total elapsed time."""
        if not self.start_time:
            return

        hours, minutes, seconds = self.get_elapsed_time()

        print()
        print(self._color("=" * 70, 'BOLD'))

        if hours > 0:
            time_str = f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            time_str = f"{minutes}m {seconds}s"
        else:
            time_str = f"{seconds}s"

        message = f"Total Time: {time_str}"
        print(self._color(message.center(70), 'GREEN'))
        print(self._color("=" * 70, 'BOLD'))


# Global logger instance
_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Get the global logger instance."""
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger


def init_logger(verbose: bool = False, use_colors: bool = True) -> Logger:
    """Initialize the global logger with specific settings."""
    global _logger
    _logger = Logger(verbose=verbose, use_colors=use_colors)
    return _logger
