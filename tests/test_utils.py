"""Tests for utility functions."""

import pytest
from core.utils import fix_latex_formulas


def test_fix_latex_display_formulas():
    """Test fixing display formulas \\[ ... \\] to $$...$$"""
    content = r"Some text \[ x = y \] more text"
    result = fix_latex_formulas(content)
    assert result == "Some text $$ x = y $$ more text"


def test_fix_latex_inline_formulas():
    """Test fixing inline formulas \\( ... \\) to $...$"""
    content = r"Some text \( x = y \) more text"
    result = fix_latex_formulas(content)
    assert result == "Some text $ x = y $ more text"


def test_fix_latex_mixed_formulas():
    """Test fixing mixed formulas"""
    content = r"Inline \( a + b \) and display \[ c = d \] formulas"
    result = fix_latex_formulas(content)
    assert result == "Inline $ a + b $ and display $$ c = d $$ formulas"


def test_fix_latex_no_formulas():
    """Test content without formulas remains unchanged"""
    content = "Just plain text with no formulas"
    result = fix_latex_formulas(content)
    assert result == content


def test_fix_latex_multiline_formulas():
    """Test multiline formulas"""
    content = r"""Text before
\[
x = y + z
\]
Text after"""
    result = fix_latex_formulas(content)
    assert "$$" in result
    assert "x = y + z" in result
