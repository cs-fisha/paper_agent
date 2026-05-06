"""Utility functions for markdown and LaTeX processing."""

import re


def fix_latex_formulas(content: str) -> str:
    """
    Fix LaTeX formulas in markdown content.

    Converts various LaTeX formats to standard $...$ and $$...$$ format.

    Args:
        content: Markdown content with LaTeX formulas

    Returns:
        Content with fixed LaTeX formulas
    """
    # \[ ... \] -> $$...$$
    content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)

    # \( ... \) -> $...$
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content, flags=re.DOTALL)

    return content
