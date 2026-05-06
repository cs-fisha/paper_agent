"""Configuration management with validation."""

import os
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    base_url: str
    model_name: str

    def __post_init__(self):
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required")
        if not self.base_url:
            raise ValueError("OPENAI_BASE_URL is required")
        if not self.model_name:
            raise ValueError("MODEL_NAME is required")


@dataclass
class DeepXivConfig:
    """DeepXiv API configuration."""
    token: str

    def __post_init__(self):
        if not self.token:
            raise ValueError("DEEPXIV_TOKEN is required")


@dataclass
class SearchConfig:
    """Search parameters configuration."""
    query: str = "multimodal LVLM MLLM"
    limit: int = 5
    date_from: str = "2025-06-01"
    categories: List[str] = field(default_factory=lambda: ["cs.CV", "cs.CL"])

    def __post_init__(self):
        if self.limit < 1:
            raise ValueError("LIMIT must be at least 1")
        if self.limit > 100:
            raise ValueError("LIMIT should not exceed 100")


@dataclass
class ProcessingConfig:
    """Processing parameters configuration."""
    max_workers: int = 8
    download_pdf: bool = True
    extract_figures: bool = True
    generate_deep_note: bool = True
    use_latex_source: bool = True
    analyze_figures: bool = True  # New: Generate figure analysis

    def __post_init__(self):
        if self.max_workers < 1:
            raise ValueError("MAX_WORKERS must be at least 1")
        if self.max_workers > 32:
            raise ValueError("MAX_WORKERS should not exceed 32")


@dataclass
class Config:
    """Main configuration container."""
    openai: OpenAIConfig
    deepxiv: DeepXivConfig
    search: SearchConfig
    processing: ProcessingConfig

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        openai = OpenAIConfig(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", ""),
            model_name=os.getenv("MODEL_NAME", ""),
        )

        deepxiv = DeepXivConfig(
            token=os.getenv("DEEPXIV_TOKEN", ""),
        )

        search = SearchConfig(
            query=os.getenv("QUERY", "multimodal LVLM MLLM"),
            limit=int(os.getenv("LIMIT", "5")),
            date_from=os.getenv("DATE_FROM", "2025-06-01"),
            categories=os.getenv("CATEGORIES", "cs.CV,cs.CL").split(","),
        )

        processing = ProcessingConfig(
            max_workers=int(os.getenv("MAX_WORKERS", "8")),
            download_pdf=os.getenv("DOWNLOAD_PDF", "true").lower() == "true",
            extract_figures=os.getenv("EXTRACT_FIGURES", "true").lower() == "true",
            generate_deep_note=os.getenv("GENERATE_DEEP_NOTE", "true").lower() == "true",
            use_latex_source=os.getenv("USE_LATEX_SOURCE", "true").lower() == "true",
            analyze_figures=os.getenv("ANALYZE_FIGURES", "true").lower() == "true",
        )

        return cls(
            openai=openai,
            deepxiv=deepxiv,
            search=search,
            processing=processing,
        )
