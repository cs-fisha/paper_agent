"""Tests for file utilities."""

import pytest
from core.file_utils import safe_filename


class TestSafeFilename:
    """Test safe_filename function."""

    def test_alphanumeric(self):
        """Test with alphanumeric characters."""
        assert safe_filename("test123") == "test123"

    def test_special_characters(self):
        """Test with special characters."""
        assert safe_filename("test@#$%file") == "test____file"

    def test_spaces(self):
        """Test with spaces."""
        assert safe_filename("test file name") == "test_file_name"

    def test_allowed_characters(self):
        """Test with allowed special characters."""
        assert safe_filename("test-file_name.txt") == "test-file_name.txt"

    def test_long_filename(self):
        """Test with very long filename."""
        long_name = "a" * 200
        result = safe_filename(long_name)
        assert len(result) <= 160

    def test_unicode(self):
        """Test with unicode characters."""
        result = safe_filename("论文标题")
        assert len(result) > 0
        # Unicode characters should be replaced with underscores
        assert "_" in result or result.isalnum()

    def test_empty_string(self):
        """Test with empty string."""
        assert safe_filename("") == ""

    def test_mixed_content(self):
        """Test with mixed content."""
        result = safe_filename("Paper_2024-01-01 (draft).pdf")
        assert result == "Paper_2024-01-01__draft_.pdf"
