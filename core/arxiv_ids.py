"""Utilities for loading arXiv IDs from text files."""

import re
from pathlib import Path
from typing import List


ARXIV_ID_PATTERN = re.compile(
    r"(?<![\w./-])("
    r"\d{4}\.\d{4,5}(?:v\d+)?"
    r"|"
    r"[a-z-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?"
    r")(?![\w.-])",
    re.IGNORECASE,
)


def extract_arxiv_ids(text: str) -> List[str]:
    """
    Extract arXiv IDs from arbitrary text.

    Supports mixed formats such as:
    - https://arxiv.org/abs/2605.08389
    - https://arxiv.org/pdf/2605.08389.pdf
    - 2605.08389
    - 2605.08389v2
    - cs/9901001
    """
    normalized_text = re.sub(
        r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    normalized_text = re.sub(r"\.pdf\b", " ", normalized_text, flags=re.IGNORECASE)

    ids = []
    seen = set()

    for match in ARXIV_ID_PATTERN.finditer(normalized_text):
        arxiv_id = match.group(1)
        if arxiv_id.lower() in seen:
            continue
        seen.add(arxiv_id.lower())
        ids.append(arxiv_id)

    return ids


def load_arxiv_ids_file(path: Path) -> List[str]:
    """Load and extract unique arXiv IDs from a text file."""
    return extract_arxiv_ids(path.read_text(encoding="utf-8"))
