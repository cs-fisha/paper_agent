"""File utility functions."""

from pathlib import Path


def safe_filename(text: str) -> str:
    """
    Convert text to safe filename.

    Args:
        text: Input text

    Returns:
        Safe filename string
    """
    keep = []
    for ch in text:
        if ch.isalnum() or ch in "-_.":
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)[:160]
