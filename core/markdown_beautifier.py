"""Markdown beautifier for fixing LaTeX formulas and formatting."""

import re
from typing import List, Tuple
from core.logger import get_logger

logger = get_logger(__name__)


class MarkdownBeautifier:
    """Beautify markdown content, especially LaTeX formulas."""

    @staticmethod
    def fix_latex_formulas(content: str) -> str:
        """
        Fix LaTeX formulas in markdown content.

        Converts various LaTeX formats to standard $...$ and $$...$$ format.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        original_content = content

        # Pattern 1: \[ ... \] -> $$...$$
        content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)

        # Pattern 2: \( ... \) -> $...$
        content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content, flags=re.DOTALL)

        # Pattern 3: Clean up excessive spaces in display formulas
        def clean_display_formula(match):
            formula = match.group(1)
            formula = re.sub(r'\s+', ' ', formula).strip()
            return f'$${formula}$$'

        content = re.sub(r'\$\$(.*?)\$\$', clean_display_formula, content, flags=re.DOTALL)

        # Pattern 4: $ ... $ with newlines -> $$...$$
        def replace_multiline_inline(match):
            formula = match.group(1)
            if '\n' in formula:
                formula = re.sub(r'\s+', ' ', formula).strip()
                return f'$${formula}$$'
            return match.group(0)

        content = re.sub(r'\$([^\$]+?)\$', replace_multiline_inline, content, flags=re.DOTALL)

        # Pattern 5: Fix spacing around formulas (but not inside)
        # Add space before $ if preceded by alphanumeric
        content = re.sub(r'([a-zA-Z0-9])(\$)', r'\1 \2', content)
        # Add space after $ if followed by alphanumeric (but not another $)
        content = re.sub(r'(\$)([a-zA-Z0-9])', r'\1 \2', content)

        if content != original_content:
            logger.debug("LaTeX formulas beautified")

        return content

    @staticmethod
    def fix_code_blocks(content: str) -> str:
        """
        Fix code blocks formatting.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        # Ensure code blocks have language specified
        content = re.sub(r'```\n', '```text\n', content)

        return content

    @staticmethod
    def fix_headers(content: str) -> str:
        """
        Fix header formatting.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        # Ensure space after # in headers
        content = re.sub(r'^(#{1,6})([^\s#])', r'\1 \2', content, flags=re.MULTILINE)

        # Ensure blank line before headers (except first line)
        lines = content.split('\n')
        result = []
        for i, line in enumerate(lines):
            if i > 0 and line.startswith('#') and result and result[-1].strip():
                result.append('')
            result.append(line)

        return '\n'.join(result)

    @staticmethod
    def fix_lists(content: str) -> str:
        """
        Fix list formatting.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        # Ensure space after list markers
        content = re.sub(r'^(\s*[-*+])([^\s])', r'\1 \2', content, flags=re.MULTILINE)
        content = re.sub(r'^(\s*\d+\.)([^\s])', r'\1 \2', content, flags=re.MULTILINE)

        return content

    @staticmethod
    def fix_emphasis(content: str) -> str:
        """
        Fix emphasis (bold/italic) formatting.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        # Fix bold: ensure no space inside **
        content = re.sub(r'\*\*\s+', '**', content)
        content = re.sub(r'\s+\*\*', '**', content)

        # Fix italic: ensure no space inside *
        content = re.sub(r'(?<!\*)\*\s+(?!\*)', '*', content)
        content = re.sub(r'(?<!\*)\s+\*(?!\*)', '*', content)

        return content

    @classmethod
    def beautify(cls, content: str) -> str:
        """
        Beautify markdown content with all fixes.

        Args:
            content: Markdown content

        Returns:
            Beautified markdown content
        """
        logger.debug("Beautifying markdown content")

        # Apply all fixes in order
        content = cls.fix_latex_formulas(content)
        content = cls.fix_code_blocks(content)
        content = cls.fix_headers(content)
        content = cls.fix_lists(content)
        content = cls.fix_emphasis(content)

        logger.debug("Markdown beautification complete")

        return content

    @staticmethod
    def extract_formulas(content: str) -> List[Tuple[str, str]]:
        """
        Extract all LaTeX formulas from markdown.

        Args:
            content: Markdown content

        Returns:
            List of (formula_type, formula_content) tuples
            formula_type is either 'inline' or 'display'
        """
        formulas = []

        # Extract display formulas ($$...$$)
        for match in re.finditer(r'\$\$(.*?)\$\$', content, flags=re.DOTALL):
            formulas.append(('display', match.group(1).strip()))

        # Extract inline formulas ($...$)
        for match in re.finditer(r'(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)', content, flags=re.DOTALL):
            formula = match.group(1).strip()
            if '\n' not in formula:  # Only single-line inline formulas
                formulas.append(('inline', formula))

        return formulas

    @staticmethod
    def validate_formulas(content: str) -> List[str]:
        """
        Validate LaTeX formulas and return warnings.

        Args:
            content: Markdown content

        Returns:
            List of warning messages
        """
        warnings = []

        # Check for unmatched $ signs
        dollar_count = content.count('$')
        if dollar_count % 2 != 0:
            warnings.append(f"Unmatched $ signs detected (count: {dollar_count})")

        # Check for \[ or \( patterns (should be converted)
        if r'\[' in content or r'\(' in content:
            warnings.append("Found \\[ or \\( patterns - should use $$ or $ instead")

        # Check for formulas with excessive newlines
        for match in re.finditer(r'\$\$(.*?)\$\$', content, flags=re.DOTALL):
            formula = match.group(1)
            if formula.count('\n') > 3:
                warnings.append(f"Formula with excessive newlines: {formula[:50]}...")

        return warnings
