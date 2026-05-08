"""Logging configuration for paper_agent."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logger(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """
    Setup root logger with console and optional file output.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file

    Returns:
        Configured root logger instance
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers
    if root_logger.handlers:
        return root_logger

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Format with timestamp and level
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler if specified
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str = "paper_agent") -> logging.Logger:
    """Get existing logger or create new one."""
    return logging.getLogger(name)
