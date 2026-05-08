"""API clients for OpenAI and DeepXiv."""

from typing import Optional
from openai import OpenAI
from deepxiv_sdk import Reader
from core.config import OpenAIConfig, DeepXivConfig
from core.retry import retry_on_exception
from core.logger import get_logger

logger = get_logger(__name__)


class OpenAIClient:
    """Wrapper for OpenAI API with retry logic."""

    def __init__(self, config: OpenAIConfig):
        self.config = config
        self.client = OpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
        )
        logger.info(f"Initialized OpenAI client with model: {config.model_name}")

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Call LLM with retry logic.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt

        Returns:
            LLM response text
        """
        if system_prompt is None:
            system_prompt = (
                "You are a senior researcher in large language models and multimodal models. "
                "You read papers critically, focusing on method novelty, experiments, limitations, "
                "and reproducibility."
            )

        logger.debug(f"Calling LLM with prompt length: {len(prompt)}")

        response = self.client.chat.completions.create(
            model=self.config.model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
        )

        result = response.choices[0].message.content
        logger.debug(f"LLM response length: {len(result)}")

        return result


class DeepXivClient:
    """Wrapper for DeepXiv API with retry logic."""

    def __init__(self, config: DeepXivConfig):
        self.config = config
        self.reader = Reader(token=config.token)
        logger.info("Initialized DeepXiv client")

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def search(
        self,
        query: str,
        source: str = "arxiv",
        size: int = 5,
        categories: list = None,
        date_search_type: str = "after",
        date_str: str = "2025-06-01",
    ) -> dict:
        """
        Search papers with retry logic.

        Args:
            query: Search query
            source: Source to search (default: arxiv)
            size: Number of results
            categories: List of arXiv categories
            date_search_type: Date filter type
            date_str: Date string

        Returns:
            Search results dictionary
        """
        logger.info(f"Searching: query='{query}', size={size}, categories={categories}")

        results = self.reader.search(
            query,
            source=source,
            size=size,
            categories=categories or [],
            date_search_type=date_search_type,
            date_str=date_str,
        )

        num_results = len(results.get("result", []))
        logger.info(f"Found {num_results} papers")

        return results

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def brief(self, arxiv_id: str) -> dict:
        """Get paper brief with retry logic."""
        logger.debug(f"Fetching brief for {arxiv_id}")
        return self.reader.brief(arxiv_id)

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def head(self, arxiv_id: str) -> dict:
        """Get paper head with retry logic."""
        logger.debug(f"Fetching head for {arxiv_id}")
        return self.reader.head(arxiv_id)

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def section(self, arxiv_id: str, section_name: str) -> str:
        """Get paper section with retry logic."""
        logger.debug(f"Fetching section '{section_name}' for {arxiv_id}")
        return self.reader.section(arxiv_id, section_name)
