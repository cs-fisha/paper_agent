"""Tests for configuration management."""

import pytest
import os
from core.config import (
    OpenAIConfig,
    DeepXivConfig,
    SearchConfig,
    ResearchConfig,
    ProcessingConfig,
    Config,
)


class TestOpenAIConfig:
    """Test OpenAI configuration."""

    def test_valid_config(self):
        """Test with valid configuration."""
        config = OpenAIConfig(
            api_key="test_key",
            base_url="https://api.openai.com/v1",
            model_name="gpt-4"
        )
        assert config.api_key == "test_key"
        assert config.base_url == "https://api.openai.com/v1"
        assert config.model_name == "gpt-4"

    def test_missing_api_key(self):
        """Test with missing API key."""
        with pytest.raises(ValueError, match="OPENAI_API_KEY is required"):
            OpenAIConfig(api_key="", base_url="https://api.openai.com/v1", model_name="gpt-4")

    def test_missing_base_url(self):
        """Test with missing base URL."""
        with pytest.raises(ValueError, match="OPENAI_BASE_URL is required"):
            OpenAIConfig(api_key="test_key", base_url="", model_name="gpt-4")

    def test_missing_model_name(self):
        """Test with missing model name."""
        with pytest.raises(ValueError, match="MODEL_NAME is required"):
            OpenAIConfig(api_key="test_key", base_url="https://api.openai.com/v1", model_name="")


class TestDeepXivConfig:
    """Test DeepXiv configuration."""

    def test_valid_config(self):
        """Test with valid configuration."""
        config = DeepXivConfig(token="test_token")
        assert config.token == "test_token"

    def test_missing_token(self):
        """Test with missing token."""
        with pytest.raises(ValueError, match="DEEPXIV_TOKEN is required"):
            DeepXivConfig(token="")


class TestSearchConfig:
    """Test search configuration."""

    def test_default_config(self):
        """Test with default configuration."""
        config = SearchConfig()
        assert config.query == "multimodal LVLM MLLM"
        assert config.limit == 5
        assert config.date_from == "2025-06-01"
        assert config.categories == ["cs.CV", "cs.CL"]
        assert config.arxiv_ids_file is None

    def test_custom_config(self):
        """Test with custom configuration."""
        config = SearchConfig(
            query="test query",
            limit=10,
            date_from="2024-01-01",
            categories=["cs.AI"],
            arxiv_ids_file=None,
        )
        assert config.query == "test query"
        assert config.limit == 10
        assert config.date_from == "2024-01-01"
        assert config.categories == ["cs.AI"]

    def test_arxiv_ids_file(self, tmp_path):
        """Test with arXiv IDs file."""
        ids_file = tmp_path / "papers.txt"
        ids_file.write_text("2605.08389\n", encoding="utf-8")

        config = SearchConfig(arxiv_ids_file=ids_file)

        assert config.arxiv_ids_file == ids_file

    def test_invalid_limit_too_low(self):
        """Test with limit too low."""
        with pytest.raises(ValueError, match="LIMIT must be at least 1"):
            SearchConfig(limit=0)

    def test_invalid_limit_too_high(self):
        """Test with limit too high."""
        with pytest.raises(ValueError, match="LIMIT should not exceed 100"):
            SearchConfig(limit=101)


class TestProcessingConfig:
    """Test processing configuration."""

    def test_default_config(self):
        """Test with default configuration."""
        config = ProcessingConfig()
        assert config.max_workers == 8
        assert config.download_pdf is True
        assert config.extract_figures is True
        assert config.generate_deep_note is False  # Changed: default to False
        assert config.use_latex_source is True
        assert config.analyze_figures is True  # Default to True

    def test_custom_config(self):
        """Test with custom configuration."""
        config = ProcessingConfig(
            max_workers=4,
            download_pdf=False,
            extract_figures=False,
            generate_deep_note=False,
            use_latex_source=False
        )
        assert config.max_workers == 4
        assert config.download_pdf is False
        assert config.extract_figures is False
        assert config.generate_deep_note is False
        assert config.use_latex_source is False

    def test_invalid_max_workers_too_low(self):
        """Test with max_workers too low."""
        with pytest.raises(ValueError, match="MAX_WORKERS must be at least 1"):
            ProcessingConfig(max_workers=0)

    def test_invalid_max_workers_too_high(self):
        """Test with max_workers too high."""
        with pytest.raises(ValueError, match="MAX_WORKERS should not exceed 32"):
            ProcessingConfig(max_workers=33)


class TestResearchConfig:
    """Test research focus configuration."""

    def test_default_config(self):
        """Test with default configuration."""
        config = ResearchConfig()
        assert config.focus == ""

    def test_custom_config(self):
        """Test with custom research focus."""
        config = ResearchConfig(focus="multimodal LVLM jailbreak")
        assert config.focus == "multimodal LVLM jailbreak"
