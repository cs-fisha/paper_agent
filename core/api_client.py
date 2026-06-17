"""API clients for OpenAI and DeepXiv."""

from typing import Optional, List
from openai import OpenAI
from deepxiv_sdk import Reader
from deepxiv_sdk.reader import NotFoundError
from core.config import OpenAIConfig, DeepXivConfig
from core.arxiv_html_fetcher import ArxivHTMLFetcher
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

    @retry_on_exception(max_attempts=3, delay=30.0, backoff=2.0)
    def get_embeddings(self, texts: List[str], model: str = "text-embedding-3-large") -> List[List[float]]:
        """Get embeddings for a batch of texts (max 2048 per call)."""
        response = self.client.embeddings.create(model=model, input=texts)
        return [item.embedding for item in response.data]


class DeepXivClient:
    """Wrapper for DeepXiv API with retry logic and arxiv HTML fallback."""

    def __init__(self, config: DeepXivConfig, fallback: Optional[ArxivHTMLFetcher] = None):
        self.config = config
        self.reader = Reader(token=config.token)
        self.fallback = fallback
        logger.info("Initialized DeepXiv client" + (" (with HTML fallback)" if fallback else ""))

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
        """Get paper brief with retry logic. Falls back to arxiv HTML on NotFoundError."""
        logger.debug(f"Fetching brief for {arxiv_id}")
        try:
            return self.reader.brief(arxiv_id)
        except NotFoundError:
            if self.fallback:
                logger.info(f"DeepXiv 404 for {arxiv_id}, using arxiv HTML fallback")
                return self.fallback.fetch_brief(arxiv_id)
            raise

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def head(self, arxiv_id: str) -> dict:
        """Get paper head with retry logic. Falls back to arxiv HTML on NotFoundError."""
        logger.debug(f"Fetching head for {arxiv_id}")
        try:
            return self.reader.head(arxiv_id)
        except NotFoundError:
            if self.fallback:
                logger.info(f"DeepXiv 404 for {arxiv_id}, using arxiv HTML fallback")
                return self.fallback.fetch_head(arxiv_id)
            raise

    @retry_on_exception(max_attempts=3, delay=60.0, backoff=2.0)
    def section(self, arxiv_id: str, section_name: str) -> str:
        """Get paper section with retry logic. Falls back to arxiv HTML on NotFoundError."""
        logger.debug(f"Fetching section '{section_name}' for {arxiv_id}")
        try:
            return self.reader.section(arxiv_id, section_name)
        except NotFoundError:
            if self.fallback:
                logger.info(f"DeepXiv 404 for section '{section_name}' of {arxiv_id}, using arxiv HTML fallback")
                return self.fallback.fetch_section(arxiv_id, section_name)
            raise
