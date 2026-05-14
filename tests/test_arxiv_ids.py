"""Tests for loading arXiv IDs from text."""

from core.arxiv_ids import extract_arxiv_ids, load_arxiv_ids_file


def test_extract_mixed_arxiv_id_formats():
    content = """
    https://arxiv.org/abs/2605.08389
    2605.08390
    https://arxiv.org/pdf/2605.08391.pdf
    2605.08392v2
    """

    assert extract_arxiv_ids(content) == [
        "2605.08389",
        "2605.08390",
        "2605.08391",
        "2605.08392v2",
    ]


def test_extract_arxiv_ids_deduplicates_preserving_order():
    content = "2605.08389 https://arxiv.org/abs/2605.08389 2605.08390 2605.08389"

    assert extract_arxiv_ids(content) == ["2605.08389", "2605.08390"]


def test_extract_legacy_arxiv_ids():
    content = "https://arxiv.org/abs/cs/9901001 and math.GT/0309136v1"

    assert extract_arxiv_ids(content) == ["cs/9901001", "math.GT/0309136v1"]


def test_extract_arxiv_ids_ignores_invalid_text():
    assert extract_arxiv_ids("not-an-id 1234.12 2605.abcde") == []


def test_load_arxiv_ids_file(tmp_path):
    ids_file = tmp_path / "papers.txt"
    ids_file.write_text("https://arxiv.org/abs/2605.08389\n2605.08390\n", encoding="utf-8")

    assert load_arxiv_ids_file(ids_file) == ["2605.08389", "2605.08390"]
