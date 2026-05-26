"""Fallback fetcher that scrapes arxiv abs/HTML pages when DeepXiv has no data."""

import re
import time
import requests
from typing import Dict, List, Optional
from lxml import html as lxml_html
from core.retry import retry_on_exception
from core.logger import get_logger

logger = get_logger(__name__)

_HEADERS = {
    "User-Agent": "paper_agent/1.0 (academic research tool; +https://github.com)"
}
_REQUEST_INTERVAL = 1.0


class ArxivHTMLFetcher:
    """Fetches paper metadata and content from arxiv.org HTML pages."""

    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self._last_request_time = 0.0

    def _throttle(self):
        elapsed = time.time() - self._last_request_time
        if elapsed < _REQUEST_INTERVAL:
            time.sleep(_REQUEST_INTERVAL - elapsed)
        self._last_request_time = time.time()

    @retry_on_exception(max_attempts=3, delay=2.0, backoff=2.0)
    def _get(self, url: str) -> str:
        self._throttle()
        logger.debug(f"Fetching {url}")
        resp = requests.get(url, headers=_HEADERS, timeout=self.timeout)
        resp.raise_for_status()
        return resp.text

    def _parse_abs_meta(self, arxiv_id: str) -> Dict:
        """Parse metadata from arxiv abs page meta tags."""
        page = self._get(f"https://arxiv.org/abs/{arxiv_id}")
        tree = lxml_html.fromstring(page)

        def meta(name: str) -> Optional[str]:
            el = tree.xpath(f'//meta[@name="{name}"]/@content')
            return el[0] if el else None

        def meta_all(name: str) -> List[str]:
            return tree.xpath(f'//meta[@name="{name}"]/@content')

        title = meta("citation_title") or ""
        authors = meta_all("citation_author")
        abstract = meta("citation_abstract") or ""
        date = meta("citation_date") or ""
        pdf_url = meta("citation_pdf_url") or f"https://arxiv.org/pdf/{arxiv_id}"

        # Categories from abs page
        categories = []
        primary = tree.xpath('//span[@class="primary-subject"]/text()')
        if primary:
            cat_match = re.search(r'\(([^)]+)\)', primary[0])
            if cat_match:
                categories.append(cat_match.group(1))

        # Normalize date from "2026/05/22" to "2026-05-22"
        if date:
            date = date.replace("/", "-")

        return {
            "title": title,
            "authors": authors,
            "abstract": abstract,
            "publish_at": date,
            "pdf_url": pdf_url,
            "categories": categories,
        }

    def _parse_html_sections(self, arxiv_id: str) -> List[Dict]:
        """Parse section list from arxiv HTML full text page."""
        try:
            page = self._get(f"https://arxiv.org/html/{arxiv_id}")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                logger.warning(f"HTML full text not available for {arxiv_id}")
                return []
            raise

        tree = lxml_html.fromstring(page)
        self._cached_html_tree = (arxiv_id, tree)

        sections = []
        headings = tree.xpath(
            '//*[contains(@class, "ltx_title") and contains(@class, "ltx_title_section")]'
        )
        for idx, h in enumerate(headings):
            text = h.text_content().strip()
            # Remove leading number like "1 " or "1. "
            name = re.sub(r'^\d+\.?\s*', '', text)
            if name:
                sections.append({"name": name, "idx": idx, "token_count": 0})

        return sections

    def _extract_section_content(self, tree, section_idx: int) -> str:
        """Extract text content of a section by its index."""
        section_id = f"S{section_idx + 1}"
        elements = tree.xpath(f'//section[@id="{section_id}"]')
        if not elements:
            return ""
        text = elements[0].text_content()
        # Clean up excessive whitespace
        text = re.sub(r'\n[ \t]+', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    def fetch_brief(self, arxiv_id: str) -> Dict:
        """Fetch brief info compatible with DeepXiv brief() output."""
        logger.info(f"[arxiv HTML fallback] Fetching brief for {arxiv_id}")
        meta = self._parse_abs_meta(arxiv_id)
        return {
            "arxiv_id": arxiv_id,
            "title": meta["title"],
            "src_url": meta["pdf_url"],
            "publish_at": meta["publish_at"],
            "tldr": None,
            "keywords": [],
            "citations": 0,
        }

    def fetch_head(self, arxiv_id: str) -> Dict:
        """Fetch head info compatible with DeepXiv head() output."""
        logger.info(f"[arxiv HTML fallback] Fetching head for {arxiv_id}")
        meta = self._parse_abs_meta(arxiv_id)
        sections = self._parse_html_sections(arxiv_id)

        authors = [{"name": a, "orgs": []} for a in meta["authors"]]

        return {
            "arxiv_id": arxiv_id,
            "title": meta["title"],
            "abstract": meta["abstract"],
            "authors": authors,
            "categories": meta["categories"],
            "sections": sections,
            "token_count": 0,
            "publish_at": meta["publish_at"],
        }

    def fetch_section(self, arxiv_id: str, section_name: str) -> str:
        """Fetch a specific section's content from HTML full text."""
        logger.info(f"[arxiv HTML fallback] Fetching section '{section_name}' for {arxiv_id}")

        # Reuse cached tree if available
        if hasattr(self, '_cached_html_tree') and self._cached_html_tree[0] == arxiv_id:
            tree = self._cached_html_tree[1]
        else:
            try:
                page = self._get(f"https://arxiv.org/html/{arxiv_id}")
            except requests.HTTPError:
                return ""
            tree = lxml_html.fromstring(page)
            self._cached_html_tree = (arxiv_id, tree)

        # Find matching section
        headings = tree.xpath(
            '//*[contains(@class, "ltx_title") and contains(@class, "ltx_title_section")]'
        )
        section_lower = section_name.lower()
        for idx, h in enumerate(headings):
            text = h.text_content().strip()
            name = re.sub(r'^\d+\.?\s*', '', text).lower()
            if name == section_lower or section_lower in name or name in section_lower:
                return self._extract_section_content(tree, idx)

        logger.warning(f"Section '{section_name}' not found in HTML for {arxiv_id}")
        return ""
