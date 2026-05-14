"""Tests for paper processor helpers."""

import sys
import types


deepxiv_sdk = types.ModuleType("deepxiv_sdk")
deepxiv_sdk.Reader = object
sys.modules.setdefault("deepxiv_sdk", deepxiv_sdk)

from core.paper_processor import PaperProcessor


def test_resolve_title_prefers_deepxiv_head_title():
    paper_info = {"arxiv_id": "2605.07209", "title": "2605.07209"}
    material = {"head": {"title": "Real Paper Title"}}

    assert PaperProcessor._resolve_title(paper_info, material) == "Real Paper Title"


def test_resolve_title_falls_back_to_paper_info_title():
    paper_info = {"arxiv_id": "2605.07209", "title": "Search Result Title"}
    material = {"head": {}}

    assert PaperProcessor._resolve_title(paper_info, material) == "Search Result Title"


def test_resolve_title_falls_back_to_arxiv_id():
    paper_info = {"arxiv_id": "2605.07209"}
    material = {"head": {}}

    assert PaperProcessor._resolve_title(paper_info, material) == "2605.07209"
