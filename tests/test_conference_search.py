"""Tests for conference accepted-paper search helpers."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from core.conference_search import (
    ConferenceConfig,
    PaperRecord,
    annotate_and_select,
    build_openalex_queries,
    build_search_queries,
    classify_records,
    extract_arxiv_abs_urls,
    extract_arxiv_urls_from_openalex_work,
    filter_records_by_category,
    filter_records_by_date,
    is_accepted_record,
    normalize_venue_key,
    paper_record_from_arxiv_metadata,
    parse_arxiv_abs_html,
    scan_arxiv_metadata_file,
)


def make_record(arxiv_id: str = "2601.00001", comment: str = "", title: str = "A Useful Paper") -> PaperRecord:
    return PaperRecord(
        arxiv_id=arxiv_id,
        title=title,
        abstract="We propose a useful multimodal benchmark for robust reasoning.",
        authors=["Ada Lovelace"],
        categories=["cs.CV"],
        published="2026-01-01T00:00:00Z",
        updated="2026-01-02T00:00:00Z",
        url=f"https://arxiv.org/abs/{arxiv_id}",
        comment=comment,
    )


def test_normalize_venue_key():
    assert normalize_venue_key("cvpr-2026") == "CVPR2026"
    assert normalize_venue_key("ICML 2026") == "ICML2026"


def test_build_search_queries_for_aliases_and_categories():
    config = ConferenceConfig(
        venue="CVPR2026",
        aliases=["CVPR 2026", "CVPR2026"],
        categories=["cs.CV"],
    )

    queries = build_search_queries(config, query_fields="both")

    assert 'all:"CVPR 2026" AND cat:cs.CV' in queries
    assert 'co:"CVPR2026" AND cat:cs.CV' in queries


def test_build_openalex_queries_include_accepted_phrases():
    config = ConferenceConfig(venue="CVPR2026", aliases=["CVPR 2026"])

    queries = build_openalex_queries(config)

    assert "accepted to CVPR 2026" in queries
    assert "to appear in CVPR 2026" in queries


def test_accepted_record_matches_common_phrases():
    aliases = ["CVPR 2026", "CVPR2026"]

    for phrase in [
        "Accepted to CVPR 2026.",
        "Accepted at CVPR2026.",
        "Accepted by CVPR 2026.",
        "To appear in CVPR 2026.",
    ]:
        accepted, _, alias = is_accepted_record(make_record(comment=phrase), aliases)
        assert accepted is True
        assert alias in aliases


def test_classify_records_excludes_workshop_by_default():
    config = ConferenceConfig(
        venue="CVPR2026",
        aliases=["CVPR 2026"],
        categories=["cs.CV"],
        exclude=["workshop", "challenge"],
    )
    main = make_record("2601.00001", "Accepted to CVPR 2026.")
    workshop = make_record("2601.00002", "Accepted to CVPR 2026 Workshop.")

    accepted, rejected = classify_records([main, workshop], config)

    assert [record.arxiv_id for record in accepted] == ["2601.00001"]
    assert rejected[0]["arxiv_id"] == "2601.00002"
    assert "workshop" in rejected[0]["reject_reason"]


def test_classify_records_can_include_workshops():
    config = ConferenceConfig(
        venue="CVPR2026",
        aliases=["CVPR 2026"],
        categories=["cs.CV"],
        exclude=["workshop"],
    )
    workshop = make_record("2601.00002", "Accepted to CVPR 2026 Workshop.")

    accepted, rejected = classify_records([workshop], config, include_workshops=True)

    assert [record.arxiv_id for record in accepted] == ["2601.00002"]
    assert rejected == []


def test_top_n_larger_than_available_returns_all():
    records = [
        make_record("2601.00001", "Accepted to CVPR 2026.", title="Video Reasoning"),
        make_record("2601.00002", "Accepted to CVPR 2026.", title="3D Reconstruction"),
    ]

    selected = annotate_and_select(records, top_n=200)

    assert {record.arxiv_id for record in selected} == {"2601.00001", "2601.00002"}


def test_top_zero_selects_none():
    records = [make_record("2601.00001", "Accepted to CVPR 2026.")]

    assert annotate_and_select(records, top_n=0) == []


def test_filter_records_by_date_uses_published_date():
    old = make_record("2401.00001", "Accepted to CVPR 2026.")
    old.published = "2024-01-01T00:00:00Z"
    old.updated = "2024-01-02T00:00:00Z"
    new = make_record("2601.00001", "Accepted to CVPR 2026.")
    new.published = "2026-01-01T00:00:00Z"
    new.updated = "2026-01-02T00:00:00Z"

    filtered = filter_records_by_date([old, new], date_from="2025-01-01")

    assert [record.arxiv_id for record in filtered] == ["2601.00001"]


def test_extract_arxiv_abs_urls_from_search_links():
    html = """
    <a href="/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F2601.12345">result</a>
    <a href="https://arxiv.org/abs/2601.12345v2">duplicate</a>
    <a href="https://example.com/not-arxiv">ignore</a>
    """

    assert extract_arxiv_abs_urls(html) == ["https://arxiv.org/abs/2601.12345"]


def test_extract_arxiv_urls_from_openalex_work_handles_pdf_locations():
    work = {
        "locations": [
            {
                "landing_page_url": "https://arxiv.org/abs/2601.12345",
                "pdf_url": "https://arxiv.org/pdf/2601.12345v2.pdf",
            }
        ]
    }

    assert extract_arxiv_urls_from_openalex_work(work) == ["https://arxiv.org/abs/2601.12345"]


def test_parse_arxiv_abs_html_extracts_comment_and_categories():
    html = """
    <html>
      <head>
        <meta name="citation_title" content="A Useful Vision Paper">
        <meta name="citation_author" content="Ada Lovelace">
        <meta name="citation_arxiv_id" content="2601.12345">
        <meta name="citation_date" content="2026/01/15">
      </head>
      <body>
        <blockquote class="abstract mathjax">
          <span class="descriptor">Abstract:</span> We propose a benchmark.
        </blockquote>
        <td class="tablecell comments mathjax">Accepted to CVPR 2026.</td>
        <td class="tablecell subjects">Computer Vision and Pattern Recognition (cs.CV); Machine Learning (cs.LG)</td>
      </body>
    </html>
    """

    record = parse_arxiv_abs_html(html, fallback_url="https://arxiv.org/abs/2601.12345")

    assert record.arxiv_id == "2601.12345"
    assert record.title == "A Useful Vision Paper"
    assert record.comment == "Accepted to CVPR 2026."
    assert record.categories == ["cs.CV", "cs.LG"]
    assert record.published == "2026-01-15T00:00:00Z"


def test_paper_record_from_kaggle_arxiv_metadata():
    record = paper_record_from_arxiv_metadata(
        {
            "id": "2601.12345",
            "title": "A Useful Paper",
            "abstract": "Abstract text",
            "authors_parsed": [["Lovelace", "Ada", ""]],
            "categories": "cs.CV cs.LG",
            "comments": "Accepted to CVPR 2026.",
            "journal-ref": "",
            "versions": [{"version": "v1", "created": "Thu, 15 Jan 2026 00:00:00 GMT"}],
            "update_date": "2026-02-01",
        }
    )

    assert record.arxiv_id == "2601.12345"
    assert record.authors == ["Lovelace Ada"]
    assert record.categories == ["cs.CV", "cs.LG"]
    assert record.published == "2026-01-15"
    assert record.updated == "2026-02-01"


def test_scan_arxiv_metadata_file_filters_accepted_records():
    config = ConferenceConfig(
        venue="CVPR2026",
        aliases=["CVPR 2026"],
        categories=["cs.CV"],
        exclude=["workshop"],
    )
    rows = [
        {
            "id": "2601.00001",
            "title": "Main Paper",
            "abstract": "Vision work",
            "authors": "Ada Lovelace",
            "categories": "cs.CV",
            "comments": "Accepted to CVPR 2026.",
            "versions": [{"created": "Thu, 15 Jan 2026 00:00:00 GMT"}],
            "update_date": "2026-02-01",
        },
        {
            "id": "2601.00002",
            "title": "Workshop Paper",
            "abstract": "Vision work",
            "authors": "Ada Lovelace",
            "categories": "cs.CV",
            "comments": "Accepted to CVPR 2026 workshop.",
            "versions": [{"created": "Thu, 15 Jan 2026 00:00:00 GMT"}],
            "update_date": "2026-02-01",
        },
    ]

    with TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "arxiv-metadata-oai-snapshot.json"
        path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
        accepted, rejected, log = scan_arxiv_metadata_file(path, config, date_from="2025-01-01")

    assert [record.arxiv_id for record in accepted] == ["2601.00001"]
    assert rejected[0]["arxiv_id"] == "2601.00002"
    assert log["scanned_records"] == 2
    assert log["candidate_count"] == 2


def test_filter_records_by_category_keeps_overlaps():
    cv = make_record("2601.00001")
    lg = make_record("2601.00002")
    lg.categories = ["cs.LG"]

    filtered = filter_records_by_category([cv, lg], ["cs.CV"])

    assert [record.arxiv_id for record in filtered] == ["2601.00001"]
