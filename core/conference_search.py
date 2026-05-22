"""Conference accepted-paper search helpers for arXiv metadata."""

from __future__ import annotations

import json
import math
import re
import time
import xml.etree.ElementTree as ET
import gzip
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import requests


ARXIV_API_URL = "https://export.arxiv.org/api/query"
DUCKDUCKGO_HTML_URL = "https://html.duckduckgo.com/html/"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"
OPENALEX_ARXIV_SOURCE_ID = "S4306400194"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"
OPENSEARCH_NS = "{http://a9.com/-/spec/opensearch/1.1/}"


@dataclass
class ConferenceConfig:
    """Search settings for a conference edition."""

    venue: str
    aliases: List[str]
    categories: List[str] = field(default_factory=list)
    exclude: List[str] = field(default_factory=list)
    date_from: str = "2025-01-01"
    date_to: Optional[str] = None


@dataclass
class PaperRecord:
    """arXiv metadata used by the conference search pipeline."""

    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    categories: List[str]
    published: str
    updated: str
    url: str
    comment: str = ""
    journal_ref: str = ""
    doi: str = ""
    matched_alias: str = ""
    match_reason: str = ""
    score: float = 0.0
    topics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "arxiv_id": self.arxiv_id,
            "title": self.title,
            "abstract": self.abstract,
            "authors": self.authors,
            "categories": self.categories,
            "published": self.published,
            "updated": self.updated,
            "url": self.url,
            "comment": self.comment,
            "journal_ref": self.journal_ref,
            "doi": self.doi,
            "matched_alias": self.matched_alias,
            "match_reason": self.match_reason,
            "score": round(self.score, 4),
            "topics": self.topics,
        }


DEFAULT_EXCLUDE_TERMS = [
    "workshop",
    "challenge",
    "competition",
    "shared task",
    "tutorial",
    "demo track",
    "in conjunction with",
]


DEFAULT_CONFERENCES: Dict[str, ConferenceConfig] = {
    "CVPR2026": ConferenceConfig(
        venue="CVPR2026",
        aliases=[
            "CVPR 2026",
            "CVPR2026",
            "IEEE/CVF Conference on Computer Vision and Pattern Recognition 2026",
            "Computer Vision and Pattern Recognition 2026",
        ],
        categories=["cs.CV", "cs.AI", "cs.LG", "cs.RO"],
        exclude=DEFAULT_EXCLUDE_TERMS,
        date_from="2025-01-01",
    ),
    "ICML2026": ConferenceConfig(
        venue="ICML2026",
        aliases=[
            "ICML 2026",
            "ICML2026",
            "International Conference on Machine Learning 2026",
        ],
        categories=["cs.LG", "cs.AI", "cs.CL", "stat.ML", "cs.CV"],
        exclude=DEFAULT_EXCLUDE_TERMS,
        date_from="2025-01-01",
    ),
    "NeurIPS2026": ConferenceConfig(
        venue="NeurIPS2026",
        aliases=[
            "NeurIPS 2026",
            "NeurIPS2026",
            "Neural Information Processing Systems 2026",
            "Conference on Neural Information Processing Systems 2026",
        ],
        categories=["cs.LG", "cs.AI", "cs.CL", "cs.CV", "stat.ML"],
        exclude=DEFAULT_EXCLUDE_TERMS,
        date_from="2025-01-01",
    ),
    "ICLR2026": ConferenceConfig(
        venue="ICLR2026",
        aliases=[
            "ICLR 2026",
            "ICLR2026",
            "International Conference on Learning Representations 2026",
        ],
        categories=["cs.LG", "cs.AI", "cs.CL", "cs.CV", "stat.ML"],
        exclude=DEFAULT_EXCLUDE_TERMS,
        date_from="2025-01-01",
    ),
    "ACL2026": ConferenceConfig(
        venue="ACL2026",
        aliases=[
            "ACL 2026",
            "ACL2026",
            "Annual Meeting of the Association for Computational Linguistics 2026",
        ],
        categories=["cs.CL", "cs.AI", "cs.LG"],
        exclude=DEFAULT_EXCLUDE_TERMS,
        date_from="2025-01-01",
    ),
}


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "via",
    "we",
    "with",
    "using",
    "towards",
    "toward",
    "based",
    "learning",
    "model",
    "models",
    "data",
    "method",
    "methods",
    "paper",
    "new",
    "large",
    "deep",
    "neural",
}


TOPIC_KEYWORDS: Dict[str, Sequence[str]] = {
    "multimodal": ["multimodal", "multi-modal", "vision-language", "vlm", "vllm", "cross-modal"],
    "llm-agents": ["llm", "large language", "agent", "agents", "tool", "reasoning"],
    "video": ["video", "temporal", "motion", "tracking", "streaming"],
    "3d": ["3d", "point cloud", "nerf", "gaussian", "rendering", "reconstruction"],
    "generation": ["diffusion", "generative", "generation", "image synthesis", "text-to-image"],
    "segmentation-detection": ["segmentation", "detection", "detector", "object", "instance"],
    "robotics-autonomy": ["robot", "robotics", "autonomous", "driving", "navigation", "planning"],
    "medical": ["medical", "clinical", "radiology", "mri", "ct", "healthcare"],
    "efficiency": ["efficient", "compression", "quantization", "pruning", "distillation", "latency"],
    "safety-alignment": ["safety", "alignment", "jailbreak", "robustness", "adversarial", "trustworthy"],
    "rl": ["reinforcement", "policy", "reward", "rl", "offline rl"],
    "optimization-theory": ["optimization", "generalization", "theory", "bound", "convergence"],
    "evaluation-data": ["benchmark", "dataset", "evaluation", "metric", "annotation"],
    "interpretability": ["interpretability", "interpretable", "explainable", "mechanistic"],
    "audio-speech": ["audio", "speech", "music", "sound"],
    "graph": ["graph", "gnn", "network"],
    "time-series": ["time series", "forecasting", "temporal"],
}


def load_conference_configs(config_path: Optional[Path] = None) -> Dict[str, ConferenceConfig]:
    """Load conference configs from JSON, falling back to built-in defaults."""

    configs = dict(DEFAULT_CONFERENCES)
    if not config_path or not config_path.exists():
        return configs

    raw = json.loads(config_path.read_text(encoding="utf-8"))
    for venue, payload in raw.items():
        configs[normalize_venue_key(venue)] = ConferenceConfig(
            venue=normalize_venue_key(venue),
            aliases=list(payload.get("aliases", [])),
            categories=list(payload.get("categories", [])),
            exclude=list(payload.get("exclude", DEFAULT_EXCLUDE_TERMS)),
            date_from=payload.get("date_from", "2025-01-01"),
            date_to=payload.get("date_to"),
        )
    return configs


def normalize_venue_key(venue: str) -> str:
    """Normalize CLI venue names such as 'cvpr-2026' to 'CVPR2026'."""

    return re.sub(r"[^A-Za-z0-9]", "", venue).upper()


def quote_arxiv_value(value: str) -> str:
    escaped = value.replace('"', '\\"')
    return f'"{escaped}"'


def build_search_queries(
    config: ConferenceConfig,
    query_fields: str = "both",
    categories: Optional[Sequence[str]] = None,
) -> List[str]:
    """Build arXiv API query strings for aliases and configured categories."""

    fields = ["all", "co"] if query_fields == "both" else [query_fields]
    category_terms = list(categories if categories is not None else config.categories)
    queries: List[str] = []

    for alias in config.aliases:
        for field in fields:
            base = f"{field}:{quote_arxiv_value(alias)}"
            if category_terms:
                for category in category_terms:
                    queries.append(f"{base} AND cat:{category}")
            else:
                queries.append(base)

    seen = set()
    unique = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def build_web_search_queries(config: ConferenceConfig) -> List[str]:
    """Build exact web-search queries that discover candidate arXiv abs pages."""

    phrase_templates = [
        "accepted to {alias}",
        "accepted at {alias}",
        "accepted by {alias}",
        "accepted in {alias}",
        "accepted for {alias}",
        "to appear at {alias}",
        "to appear in {alias}",
        "appearing at {alias}",
        "forthcoming at {alias}",
    ]
    queries = []
    for alias in config.aliases:
        for template in phrase_templates:
            queries.append(f'site:arxiv.org/abs "{template.format(alias=alias)}"')

    seen = set()
    unique = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def build_openalex_queries(config: ConferenceConfig) -> List[str]:
    """Build OpenAlex search queries for accepted/to-appear venue phrases."""

    phrase_templates = [
        "accepted to {alias}",
        "accepted at {alias}",
        "accepted by {alias}",
        "accepted in {alias}",
        "accepted for {alias}",
        "to appear at {alias}",
        "to appear in {alias}",
        "appearing at {alias}",
        "{alias} accepted",
    ]
    queries = []
    for alias in config.aliases:
        for template in phrase_templates:
            queries.append(template.format(alias=alias))

    seen = set()
    unique = []
    for query in queries:
        if query not in seen:
            seen.add(query)
            unique.append(query)
    return unique


def fetch_web_candidates(
    queries: Sequence[str],
    *,
    search_pages: int = 2,
    max_results: int = 1000,
    delay_seconds: float = 5.0,
    session: Optional[requests.Session] = None,
) -> Tuple[List[str], List[Dict[str, object]]]:
    """Find arXiv abs URLs from general web-search result pages."""

    client = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; paper-agent-conference-search/1.0)",
    }
    seen = set()
    urls: List[str] = []
    logs: List[Dict[str, object]] = []

    for query in queries:
        for page in range(search_pages):
            if len(urls) >= max_results:
                return urls, logs
            offset = page * 30
            try:
                response = client.get(
                    DUCKDUCKGO_HTML_URL,
                    params={"q": query, "s": offset},
                    headers=headers,
                    timeout=45,
                )
                response.raise_for_status()
            except requests.RequestException as exc:
                logs.append(
                    {
                        "query": query,
                        "page": page,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break

            page_urls = extract_arxiv_abs_urls(response.text)
            added = 0
            for url in page_urls:
                if url in seen:
                    continue
                seen.add(url)
                urls.append(url)
                added += 1
                if len(urls) >= max_results:
                    break
            logs.append(
                {
                    "query": query,
                    "page": page,
                    "offset": offset,
                    "returned_urls": len(page_urls),
                    "added_urls": added,
                }
            )
            time.sleep(delay_seconds)
    return urls, logs


def fetch_openalex_candidates(
    queries: Sequence[str],
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    per_page: int = 100,
    max_results: int = 1000,
    delay_seconds: float = 1.0,
    mailto: str = "paper_agent@example.com",
    session: Optional[requests.Session] = None,
) -> Tuple[List[str], List[Dict[str, object]]]:
    """Find arXiv abs URLs from OpenAlex works that have an arXiv location."""

    client = session or requests.Session()
    headers = {
        "User-Agent": "paper-agent-conference-search/1.0 (mailto:paper_agent@example.com)",
    }
    filter_parts = [f"locations.source.id:{OPENALEX_ARXIV_SOURCE_ID}"]
    if date_from:
        filter_parts.append(f"from_publication_date:{date_from}")
    if date_to:
        filter_parts.append(f"to_publication_date:{date_to}")

    seen = set()
    urls: List[str] = []
    logs: List[Dict[str, object]] = []

    for query in queries:
        cursor = "*"
        while len(urls) < max_results:
            try:
                response = client.get(
                    OPENALEX_WORKS_URL,
                    params={
                        "search": query,
                        "filter": ",".join(filter_parts),
                        "per-page": min(max(per_page, 1), 200),
                        "cursor": cursor,
                        "mailto": mailto,
                    },
                    headers=headers,
                    timeout=45,
                )
                response.raise_for_status()
                payload = response.json()
            except requests.RequestException as exc:
                logs.append(
                    {
                        "query": query,
                        "cursor": cursor,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break

            results = payload.get("results", [])
            added = 0
            for work in results:
                for url in extract_arxiv_urls_from_openalex_work(work):
                    if url in seen:
                        continue
                    seen.add(url)
                    urls.append(url)
                    added += 1
                    if len(urls) >= max_results:
                        break
                if len(urls) >= max_results:
                    break

            meta = payload.get("meta", {})
            logs.append(
                {
                    "query": query,
                    "cursor": cursor,
                    "returned_works": len(results),
                    "added_urls": added,
                    "count": meta.get("count"),
                }
            )
            next_cursor = meta.get("next_cursor")
            if not results or not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
            time.sleep(delay_seconds)
        time.sleep(delay_seconds)
        if len(urls) >= max_results:
            break

    return urls, logs


def scan_arxiv_metadata_file(
    metadata_file: Path,
    config: ConferenceConfig,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    categories: Optional[Sequence[str]] = None,
    include_workshops: bool = False,
    max_records: int = 0,
) -> Tuple[List[PaperRecord], List[Dict[str, object]], Dict[str, object]]:
    """Scan a local arXiv metadata JSONL snapshot without using network APIs."""

    accepted: List[PaperRecord] = []
    rejected: List[Dict[str, object]] = []
    scanned = 0
    candidate_count = 0
    parse_errors = 0
    open_func = gzip.open if metadata_file.suffix == ".gz" else open

    with open_func(metadata_file, "rt", encoding="utf-8") as handle:
        for line in handle:
            if max_records and scanned >= max_records:
                break
            scanned += 1
            if not line.strip():
                continue
            try:
                raw = json.loads(line)
                record = paper_record_from_arxiv_metadata(raw)
            except (json.JSONDecodeError, TypeError, ValueError):
                parse_errors += 1
                continue

            if not mentions_any_alias(record, config.aliases):
                continue
            if not filter_records_by_date([record], date_from=date_from, date_to=date_to):
                continue
            if not filter_records_by_category([record], categories):
                continue

            candidate_count += 1
            one_accepted, one_rejected = classify_records(
                [record],
                config,
                include_workshops=include_workshops,
            )
            accepted.extend(one_accepted)
            rejected.extend(one_rejected)

    accepted.sort(key=lambda item: item.updated, reverse=True)
    return accepted, rejected, {
        "metadata_file": str(metadata_file),
        "scanned_records": scanned,
        "candidate_count": candidate_count,
        "accepted_count": len(accepted),
        "rejected_count": len(rejected),
        "parse_errors": parse_errors,
        "max_records": max_records,
    }


def paper_record_from_arxiv_metadata(raw: Dict[str, object]) -> PaperRecord:
    """Convert Kaggle/Cornell arXiv metadata JSONL row to PaperRecord."""

    arxiv_id = str(raw.get("id", "")).strip()
    if not arxiv_id:
        raise ValueError("missing arXiv id")
    categories = str(raw.get("categories", "")).split()
    authors_value = raw.get("authors_parsed") or raw.get("authors") or []
    authors = normalize_metadata_authors(authors_value)
    updated = str(raw.get("update_date", "")).strip()
    published = first_version_created(raw.get("versions")) or updated
    return PaperRecord(
        arxiv_id=arxiv_id,
        title=compact_ws(str(raw.get("title", ""))),
        abstract=compact_ws(str(raw.get("abstract", ""))),
        authors=authors,
        categories=categories,
        published=published,
        updated=updated,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=compact_ws(str(raw.get("comments", "") or "")),
        journal_ref=compact_ws(str(raw.get("journal-ref", "") or "")),
        doi=compact_ws(str(raw.get("doi", "") or "")),
    )


def normalize_metadata_authors(authors_value: object) -> List[str]:
    """Normalize Kaggle arXiv author fields to a list of display names."""

    if isinstance(authors_value, str):
        return [compact_ws(part) for part in authors_value.split(",") if compact_ws(part)]
    if isinstance(authors_value, list):
        names = []
        for author in authors_value:
            if isinstance(author, list):
                names.append(compact_ws(" ".join(str(part) for part in author if part)))
            else:
                names.append(compact_ws(str(author)))
        return [name for name in names if name]
    return []


def first_version_created(versions: object) -> str:
    """Return the first arXiv version date as ISO-like text when available."""

    if not isinstance(versions, list) or not versions:
        return ""
    first = versions[0]
    if not isinstance(first, dict):
        return ""
    created = str(first.get("created", "")).strip()
    if not created:
        return ""
    try:
        return parsedate_to_datetime(created).date().isoformat()
    except (TypeError, ValueError, IndexError, OverflowError):
        return created[:10]


def mentions_any_alias(record: PaperRecord, aliases: Sequence[str]) -> bool:
    """Cheap prefilter before the stricter accepted/to-appear regex pass."""

    text = " ".join([record.comment, record.journal_ref, record.title, record.abstract]).lower()
    return any(alias.lower() in text for alias in aliases)


def extract_arxiv_urls_from_openalex_work(work: Dict[str, object]) -> List[str]:
    """Extract arXiv abs URLs from OpenAlex work locations and URL fields."""

    blob = json.dumps(work, ensure_ascii=False)
    urls = []
    seen = set()
    for match in re.finditer(r"https?://(?:[^\s\"<>/]+\.)?arxiv\.org/[^\s\"<>]+", blob, flags=re.IGNORECASE):
        url = normalize_arxiv_abs_url(match.group(0))
        if url and url not in seen:
            seen.add(url)
            urls.append(url)
    return urls


def fetch_arxiv_abs_records(
    urls: Sequence[str],
    *,
    delay_seconds: float = 5.0,
    session: Optional[requests.Session] = None,
) -> Tuple[List[PaperRecord], List[Dict[str, object]]]:
    """Fetch candidate arXiv abs pages and parse metadata from HTML."""

    client = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; paper-agent-conference-search/1.0)",
    }
    records: List[PaperRecord] = []
    logs: List[Dict[str, object]] = []

    for url in urls:
        try:
            response = client.get(url, headers=headers, timeout=45)
            response.raise_for_status()
            records.append(parse_arxiv_abs_html(response.text, fallback_url=url))
            logs.append({"url": url, "status": "ok"})
        except Exception as exc:
            logs.append({"url": url, "error": f"{type(exc).__name__}: {exc}"})
        time.sleep(delay_seconds)
    return records, logs


def extract_arxiv_abs_urls(html_text: str) -> List[str]:
    """Extract canonical arXiv abs URLs from a search result page."""

    parser = LinkExtractor()
    parser.feed(html_text)
    urls: List[str] = []
    seen = set()
    for href in parser.links:
        resolved = normalize_arxiv_abs_url(href)
        if resolved and resolved not in seen:
            seen.add(resolved)
            urls.append(resolved)
    return urls


def normalize_arxiv_abs_url(url: str) -> str:
    """Return a canonical https://arxiv.org/abs/<id> URL when possible."""

    if not url:
        return ""
    url = unescape(url)
    parsed = urlparse(url)
    if (parsed.netloc.endswith("duckduckgo.com") or not parsed.netloc) and parsed.path.startswith("/l/"):
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        if target:
            url = unquote(target)
            parsed = urlparse(url)
    match = re.search(
        r"https?://(?:www\.)?arxiv\.org/(?:abs|html|pdf)/([A-Za-z\-]+(?:\.[A-Z]{2})?/\d{7}|\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?",
        url,
        flags=re.IGNORECASE,
    )
    if not match:
        return ""
    return f"https://arxiv.org/abs/{match.group(1)}"


class LinkExtractor(HTMLParser):
    """Collect links from a small search result page."""

    def __init__(self) -> None:
        super().__init__()
        self.links: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag != "a":
            return
        attr_map = dict(attrs)
        href = attr_map.get("href")
        if href:
            self.links.append(href)


def parse_arxiv_abs_html(html_text: str, *, fallback_url: str = "") -> PaperRecord:
    """Parse arXiv abs-page HTML into a PaperRecord without using the arXiv API."""

    parser = ArxivAbsParser()
    parser.feed(html_text)
    metadata = parser.metadata
    arxiv_id = (
        metadata.get("citation_arxiv_id", "")
        or extract_arxiv_id_from_url(fallback_url)
        or extract_arxiv_id_from_url(parser.canonical_url)
    )
    if not arxiv_id:
        raise ValueError("Could not parse arXiv ID from abs page")

    categories = parse_subject_categories(parser.subjects)
    published = normalize_citation_date(metadata.get("citation_date", ""))
    title = compact_ws(metadata.get("citation_title", "") or parser.title)
    abstract = compact_ws(metadata.get("citation_abstract", "") or parser.abstract)
    return PaperRecord(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=parser.authors,
        categories=categories,
        published=published,
        updated=published,
        url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=compact_ws(parser.comments),
        journal_ref=compact_ws(parser.journal_ref),
        doi=compact_ws(metadata.get("citation_doi", "")),
    )


class ArxivAbsParser(HTMLParser):
    """Small arXiv abs-page parser for metadata, abstract, comments, and subjects."""

    def __init__(self) -> None:
        super().__init__()
        self.metadata: Dict[str, str] = {}
        self.authors: List[str] = []
        self.title = ""
        self.abstract = ""
        self.comments = ""
        self.journal_ref = ""
        self.subjects = ""
        self.canonical_url = ""
        self._title_depth = 0
        self._abstract_depth = 0
        self._td_depth = 0
        self._active_td_label = ""
        self._buffer: List[str] = []

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        if tag == "meta":
            name = attr_map.get("name", "")
            content = attr_map.get("content", "")
            if name == "citation_author":
                self.authors.append(compact_ws(content))
            elif name.startswith("citation_"):
                self.metadata[name] = content
        elif tag == "link" and attr_map.get("rel") == "canonical":
            self.canonical_url = attr_map.get("href", "")
        elif tag == "h1" and "title" in attr_map.get("class", "").split():
            self._title_depth = 1
            self._buffer = []
        elif tag == "blockquote" and "abstract" in attr_map.get("class", "").split():
            self._abstract_depth = 1
            self._buffer = []
        elif tag == "td":
            self._td_depth = 1
            self._active_td_label = ""
            self._buffer = []
            classes = attr_map.get("class", "")
            if "comments" in classes:
                self._active_td_label = "comments"
            elif "jref" in classes:
                self._active_td_label = "journal_ref"
            elif "subjects" in classes:
                self._active_td_label = "subjects"
        elif self._title_depth:
            self._title_depth += 1
        elif self._abstract_depth:
            self._abstract_depth += 1
        elif self._td_depth:
            self._td_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self._title_depth:
            self._title_depth -= 1
            if self._title_depth == 0:
                self.title = strip_descriptor("".join(self._buffer), "Title:")
                self._buffer = []
            return
        if self._abstract_depth:
            self._abstract_depth -= 1
            if self._abstract_depth == 0:
                self.abstract = strip_descriptor("".join(self._buffer), "Abstract:")
                self._buffer = []
            return
        if self._td_depth:
            self._td_depth -= 1
            if self._td_depth == 0:
                value = compact_ws("".join(self._buffer))
                if self._active_td_label == "comments":
                    self.comments = value
                elif self._active_td_label == "journal_ref":
                    self.journal_ref = value
                elif self._active_td_label == "subjects":
                    self.subjects = value
                self._active_td_label = ""
                self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._title_depth or self._abstract_depth or self._td_depth:
            self._buffer.append(data)


def strip_descriptor(text: str, descriptor: str) -> str:
    text = compact_ws(text)
    if text.lower().startswith(descriptor.lower()):
        return compact_ws(text[len(descriptor) :])
    return text


def extract_arxiv_id_from_url(url: str) -> str:
    normalized = normalize_arxiv_abs_url(url)
    return normalized.rstrip("/").split("/")[-1] if normalized else ""


def normalize_citation_date(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    if re.fullmatch(r"\d{4}/\d{1,2}/\d{1,2}", value):
        year, month, day = value.split("/")
        return f"{year}-{int(month):02d}-{int(day):02d}T00:00:00Z"
    return value


def parse_subject_categories(subjects: str) -> List[str]:
    return re.findall(r"\(([a-z\-]+\.[A-Z]{2})\)", subjects)


def fetch_arxiv_query(
    query: str,
    *,
    start: int = 0,
    max_results: int = 100,
    sort_by: str = "submittedDate",
    sort_order: str = "descending",
    session: Optional[requests.Session] = None,
    timeout: int = 45,
    retries: int = 3,
    retry_delay_seconds: float = 10.0,
) -> Tuple[int, List[PaperRecord]]:
    """Fetch one page from the arXiv API."""

    client = session or requests.Session()
    params = {
        "search_query": query,
        "start": start,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    last_error: Optional[Exception] = None
    for attempt in range(retries + 1):
        try:
            response = client.get(ARXIV_API_URL, params=params, timeout=timeout)
            if response.status_code == 429 or response.status_code >= 500:
                retry_after = response.headers.get("Retry-After")
                wait_seconds = float(retry_after) if retry_after else retry_delay_seconds * (attempt + 1)
                if attempt < retries:
                    time.sleep(wait_seconds)
                    continue
            response.raise_for_status()
            return parse_arxiv_feed(response.text)
        except requests.RequestException as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(retry_delay_seconds * (attempt + 1))
                continue
            raise
    if last_error:
        raise last_error
    raise RuntimeError("arXiv request failed without an exception")


def fetch_arxiv_records(
    queries: Sequence[str],
    *,
    page_size: int = 100,
    max_results: int = 5000,
    delay_seconds: float = 3.1,
    retries: int = 3,
    session: Optional[requests.Session] = None,
) -> Tuple[List[PaperRecord], List[Dict[str, object]]]:
    """Fetch and de-duplicate records for several arXiv API queries."""

    client = session or requests.Session()
    by_id: Dict[str, PaperRecord] = {}
    logs: List[Dict[str, object]] = []

    for query in queries:
        fetched_for_query = 0
        total = 0
        start = 0
        while fetched_for_query < max_results:
            page_limit = min(page_size, max_results - fetched_for_query)
            try:
                total, records = fetch_arxiv_query(
                    query,
                    start=start,
                    max_results=page_limit,
                    session=client,
                    retries=retries,
                    retry_delay_seconds=max(delay_seconds, 1.0),
                )
            except requests.RequestException as exc:
                logs.append(
                    {
                        "query": query,
                        "start": start,
                        "max_results": page_limit,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                break
            logs.append(
                {
                    "query": query,
                    "start": start,
                    "max_results": page_limit,
                    "total": total,
                    "returned": len(records),
                }
            )
            if not records:
                break
            for record in records:
                by_id.setdefault(record.arxiv_id, record)
            fetched_for_query += len(records)
            start += len(records)
            if start >= total:
                break
            time.sleep(delay_seconds)
        time.sleep(delay_seconds)

    return sorted(by_id.values(), key=lambda item: item.updated, reverse=True), logs


def parse_arxiv_feed(xml_text: str) -> Tuple[int, List[PaperRecord]]:
    """Parse an arXiv Atom feed into paper records."""

    root = ET.fromstring(xml_text)
    total_node = root.find(f"{OPENSEARCH_NS}totalResults")
    total = int(total_node.text or "0") if total_node is not None else 0
    records = [parse_arxiv_entry(entry) for entry in root.findall(f"{ATOM_NS}entry")]
    return total, records


def parse_arxiv_entry(entry: ET.Element) -> PaperRecord:
    """Parse one arXiv Atom entry."""

    entry_id = text_of(entry, f"{ATOM_NS}id")
    arxiv_id = entry_id.rstrip("/").split("/")[-1]
    title = compact_ws(text_of(entry, f"{ATOM_NS}title"))
    abstract = compact_ws(text_of(entry, f"{ATOM_NS}summary"))
    authors = [
        compact_ws(text_of(author, f"{ATOM_NS}name"))
        for author in entry.findall(f"{ATOM_NS}author")
    ]
    categories = [
        category.attrib.get("term", "")
        for category in entry.findall(f"{ATOM_NS}category")
        if category.attrib.get("term")
    ]
    return PaperRecord(
        arxiv_id=arxiv_id,
        title=title,
        abstract=abstract,
        authors=authors,
        categories=categories,
        published=text_of(entry, f"{ATOM_NS}published"),
        updated=text_of(entry, f"{ATOM_NS}updated"),
        url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=compact_ws(text_of(entry, f"{ARXIV_NS}comment")),
        journal_ref=compact_ws(text_of(entry, f"{ARXIV_NS}journal_ref")),
        doi=compact_ws(text_of(entry, f"{ARXIV_NS}doi")),
    )


def text_of(element: ET.Element, path: str) -> str:
    node = element.find(path)
    return node.text.strip() if node is not None and node.text else ""


def compact_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def classify_records(
    records: Iterable[PaperRecord],
    config: ConferenceConfig,
    *,
    include_workshops: bool = False,
) -> Tuple[List[PaperRecord], List[Dict[str, object]]]:
    """Split records into hard-accepted and rejected candidates."""

    accepted: List[PaperRecord] = []
    rejected: List[Dict[str, object]] = []
    exclude_terms = config.exclude or DEFAULT_EXCLUDE_TERMS

    for record in records:
        is_accepted, reason, alias = is_accepted_record(record, config.aliases)
        if not is_accepted:
            rejected.append(
                {
                    **record.to_dict(),
                    "reject_reason": "missing explicit accepted/to-appear venue phrase",
                }
            )
            continue

        excluded, exclude_reason = has_excluded_context(record, exclude_terms)
        if excluded and not include_workshops:
            rejected.append({**record.to_dict(), "reject_reason": exclude_reason})
            continue

        record.matched_alias = alias
        record.match_reason = reason
        accepted.append(record)

    accepted.sort(key=lambda item: item.updated, reverse=True)
    return accepted, rejected


def filter_records_by_date(
    records: Iterable[PaperRecord],
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[PaperRecord]:
    """Filter records by published date using YYYY-MM-DD string comparison."""

    filtered: List[PaperRecord] = []
    for record in records:
        date_value = (record.updated or record.published)[:10]
        if date_from and date_value and date_value < date_from:
            continue
        if date_to and date_value and date_value > date_to:
            continue
        filtered.append(record)
    return filtered


def filter_records_by_category(
    records: Iterable[PaperRecord],
    categories: Optional[Sequence[str]] = None,
) -> List[PaperRecord]:
    """Keep records that overlap the requested arXiv categories."""

    if not categories:
        return list(records)
    wanted = set(categories)
    return [record for record in records if wanted & set(record.categories)]


def is_accepted_record(record: PaperRecord, aliases: Sequence[str]) -> Tuple[bool, str, str]:
    """Return whether a paper explicitly states accepted/to-appear at the venue."""

    fields = [
        ("comment", record.comment),
        ("journal_ref", record.journal_ref),
        ("title", record.title),
        ("abstract", record.abstract),
    ]
    for alias in aliases:
        alias_re = alias_to_regex(alias)
        patterns = [
            rf"\baccepted\s+(?:to|at|by|in|for)\s+(?:the\s+)?{alias_re}\b",
            rf"\bto\s+appear\s+(?:at|in)\s+(?:the\s+)?{alias_re}\b",
            rf"\bappearing\s+(?:at|in)\s+(?:the\s+)?{alias_re}\b",
            rf"\bforthcoming\s+(?:at|in)\s+(?:the\s+)?{alias_re}\b",
            rf"\b{alias_re}\s+(?:accepted|acceptance)\b",
        ]
        for field_name, value in fields:
            if not value:
                continue
            for pattern in patterns:
                if re.search(pattern, value, flags=re.IGNORECASE):
                    return True, f"{field_name} matched '{pattern}'", alias
    return False, "", ""


def alias_to_regex(alias: str) -> str:
    """Convert a venue alias into a case-insensitive regex fragment."""

    tokens = re.split(r"(\W+)", alias)
    parts = []
    for token in tokens:
        if not token:
            continue
        if token.isspace() or re.fullmatch(r"\W+", token):
            parts.append(r"[\s\-/]*")
        else:
            parts.append(re.escape(token))
    return "".join(parts)


def has_excluded_context(record: PaperRecord, exclude_terms: Sequence[str]) -> Tuple[bool, str]:
    """Detect workshop/challenge-like accepted papers when main-track only is desired."""

    text = " ".join([record.comment, record.journal_ref, record.title]).lower()
    for term in exclude_terms:
        term_re = re.escape(term.lower()).replace(r"\ ", r"\s+")
        if re.search(rf"\b{term_re}\b", text):
            return True, f"excluded by term '{term}'"
    return False, ""


def annotate_and_select(
    records: Sequence[PaperRecord],
    *,
    top_n: int,
    focus: str = "",
) -> List[PaperRecord]:
    """Score papers and return a diverse top-N subset. If fewer exist, return all."""

    if top_n < 0:
        raise ValueError("top_n must be >= 0")
    if top_n == 0 or not records:
        return []

    term_weights = corpus_term_weights(records)
    focus_tokens = set(tokenize(focus))
    scored: List[PaperRecord] = []
    for record in records:
        record.topics = detect_topics(record)
        record.score = score_record(record, term_weights, focus_tokens)
        scored.append(record)

    scored.sort(key=lambda item: (item.score, item.updated), reverse=True)
    limit = min(top_n, len(scored))
    return diverse_round_robin(scored, limit)


def corpus_term_weights(records: Sequence[PaperRecord]) -> Counter:
    counter: Counter = Counter()
    for record in records:
        counter.update(tokenize(f"{record.title} {record.abstract}"))
    return counter


def tokenize(text: str) -> List[str]:
    return [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", text.lower())
        if token not in STOPWORDS and not token.isdigit()
    ]


def detect_topics(record: PaperRecord) -> List[str]:
    text = f"{record.title} {record.abstract}".lower()
    hits = []
    for topic, keywords in TOPIC_KEYWORDS.items():
        if any(keyword.lower() in text for keyword in keywords):
            hits.append(topic)
    return hits or ["other"]


def score_record(record: PaperRecord, term_weights: Counter, focus_tokens: set) -> float:
    text = f"{record.title} {record.abstract}".lower()
    tokens = tokenize(text)
    focus_score = 0.0
    if focus_tokens:
        title_tokens = set(tokenize(record.title))
        body_tokens = set(tokens)
        focus_score = 4.0 * len(focus_tokens & title_tokens) + 1.5 * len(focus_tokens & body_tokens)

    topic_score = 1.2 * len(record.topics)
    keyword_score = sum(math.log1p(term_weights[token]) for token in set(tokens[:120])) / 20.0
    recency_score = parse_year(record.updated) / 10000.0
    return focus_score + topic_score + keyword_score + recency_score


def parse_year(value: str) -> int:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).year
    except ValueError:
        return 0


def diverse_round_robin(scored: Sequence[PaperRecord], limit: int) -> List[PaperRecord]:
    """Prefer topical diversity while preserving score order within each topic."""

    buckets: Dict[str, List[PaperRecord]] = defaultdict(list)
    for record in scored:
        buckets[record.topics[0] if record.topics else "other"].append(record)

    ordered_topics = sorted(
        buckets,
        key=lambda topic: sum(item.score for item in buckets[topic]) / max(len(buckets[topic]), 1),
        reverse=True,
    )
    selected: List[PaperRecord] = []
    seen = set()
    while len(selected) < limit:
        progressed = False
        for topic in ordered_topics:
            while buckets[topic]:
                candidate = buckets[topic].pop(0)
                if candidate.arxiv_id in seen:
                    continue
                selected.append(candidate)
                seen.add(candidate.arxiv_id)
                progressed = True
                break
            if len(selected) >= limit:
                break
        if not progressed:
            break
    return selected


def write_jsonl(path: Path, rows: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_id_file(path: Path, records: Sequence[PaperRecord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(record.arxiv_id for record in records) + ("\n" if records else ""), encoding="utf-8")


def generate_trend_report(
    venue: str,
    accepted: Sequence[PaperRecord],
    selected: Sequence[PaperRecord],
    *,
    top_n: int,
    focus: str = "",
    include_workshops: bool = False,
) -> str:
    """Generate a lightweight non-LLM trend report from metadata."""

    category_counts = Counter(category for record in accepted for category in record.categories)
    topic_counts = Counter(topic for record in accepted for topic in detect_topics(record))
    term_counts = corpus_term_weights(accepted)
    month_counts = Counter((record.published or record.updated)[:7] for record in accepted if record.published or record.updated)

    top_terms = [term for term, _ in term_counts.most_common(30)]
    lines = [
        f"# {venue} arXiv Accepted Search",
        "",
        "## Summary",
        "",
        f"- Accepted papers found: {len(accepted)}",
        f"- Suggested papers for deep workflow: {len(selected)} (requested top={top_n})",
        f"- Workshop/challenge papers included: {'yes' if include_workshops else 'no'}",
    ]
    if focus:
        lines.append(f"- Research focus used for ranking: {focus}")

    lines.extend(["", "## Categories", ""])
    lines.extend([f"- {category}: {count}" for category, count in category_counts.most_common(20)] or ["- No category data"])

    lines.extend(["", "## Topics", ""])
    lines.extend([f"- {topic}: {count}" for topic, count in topic_counts.most_common(20)] or ["- No topic data"])

    lines.extend(["", "## Submission Months", ""])
    lines.extend([f"- {month}: {count}" for month, count in sorted(month_counts.items())] or ["- No date data"])

    lines.extend(["", "## Frequent Terms", ""])
    lines.append(", ".join(top_terms) if top_terms else "No terms found.")

    lines.extend(["", "## Suggested Deep-Read Papers", ""])
    if selected:
        for idx, record in enumerate(selected, 1):
            topics = ", ".join(record.topics or detect_topics(record))
            lines.append(
                f"{idx}. {record.title} ({record.arxiv_id}) - score={record.score:.2f}; topics={topics}"
            )
    else:
        lines.append("No papers selected for deep workflow.")

    return "\n".join(lines) + "\n"
