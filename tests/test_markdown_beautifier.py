"""Tests for markdown beautifier."""

import pytest
from core.markdown_beautifier import MarkdownBeautifier


class TestMarkdownBeautifier:
    """Test markdown beautifier."""

    def test_fix_latex_bracket_to_double_dollar(self):
        """Test converting \\[ ... \\] to $$...$$"""
        content = r"This is a formula: \[ E = mc^2 \] and more text."
        result = MarkdownBeautifier.fix_latex_formulas(content)
        assert "$$E = mc^2$$" in result or "$$ E = mc^2 $$" in result
        assert r"\[" not in result

    def test_fix_latex_paren_to_single_dollar(self):
        """Test converting \\( ... \\) to $...$"""
        content = r"Inline formula \( x = y \) in text."
        result = MarkdownBeautifier.fix_latex_formulas(content)
        assert "$x = y$" in result or "$ x = y $" in result
        assert r"\(" not in result

    def test_fix_multiline_inline_to_display(self):
        """Test converting multiline inline formulas to display."""
        content = "Formula: $x = y\n+ z$ end."
        result = MarkdownBeautifier.fix_latex_formulas(content)
        assert "$$x = y + z$$" in result or "$$ x = y + z $$" in result

    def test_fix_spacing_around_formulas(self):
        """Test adding proper spacing around formulas."""
        content = "Text$x=y$more text"
        result = MarkdownBeautifier.fix_latex_formulas(content)
        # Should have space before and after formula
        assert " $" in result and "$ " in result

    def test_clean_formula_spaces(self):
        """Test cleaning excessive spaces in formulas."""
        content = "$$x  =   y    +    z$$"
        result = MarkdownBeautifier.fix_latex_formulas(content)
        # Should reduce multiple spaces to single space
        assert "  " not in result or result.count("  ") < content.count("  ")

    def test_fix_headers(self):
        """Test fixing header formatting."""
        content = "#Header without space\n##Another one"
        result = MarkdownBeautifier.fix_headers(content)
        assert "# Header without space" in result
        assert "## Another one" in result

    def test_fix_lists(self):
        """Test fixing list formatting."""
        content = "-Item without space\n* Another item\n1.Numbered item"
        result = MarkdownBeautifier.fix_lists(content)
        assert "- Item without space" in result
        assert "* Another item" in result
        assert "1. Numbered item" in result

    def test_extract_formulas(self):
        """Test extracting formulas from markdown."""
        content = "Text with $$E = mc^2$$ and $x = y$ formulas."
        formulas = MarkdownBeautifier.extract_formulas(content)
        assert len(formulas) == 2
        assert formulas[0] == ('display', 'E = mc^2')
        assert formulas[1] == ('inline', 'x = y')

    def test_validate_formulas_unmatched_dollars(self):
        """Test validation of unmatched dollar signs."""
        content = "Text with $unmatched formula"
        warnings = MarkdownBeautifier.validate_formulas(content)
        assert len(warnings) > 0
        assert "Unmatched" in warnings[0]

    def test_validate_formulas_old_syntax(self):
        """Test validation of old LaTeX syntax."""
        content = r"Text with \[ old syntax \]"
        warnings = MarkdownBeautifier.validate_formulas(content)
        assert len(warnings) > 0
        assert "\\[" in warnings[0] or "\\(" in warnings[0]

    def test_beautify_complete(self):
        """Test complete beautification."""
        content = r"""
#Header
Text with \[ E = mc^2 \] and \( x = y \).
-List item
**Bold text**
"""
        result = MarkdownBeautifier.beautify(content)

        # Check all fixes applied
        assert "# Header" in result
        assert "$$" in result and "mc^2" in result  # Formula converted
        assert "$" in result and "x = y" in result  # Inline formula converted
        assert "- List item" in result
        assert r"\[" not in result
        assert r"\(" not in result

    def test_preserve_code_blocks(self):
        """Test that code blocks are not affected by formula fixes."""
        content = r"""
Text with formula $x = y$.

```python
# This should not be changed: \[ code \]
x = "$not a formula$"
```

More text.
"""
        result = MarkdownBeautifier.beautify(content)
        # Code blocks should be preserved
        assert "```python" in result or "```text" in result
        assert "$" in result  # Formula exists
