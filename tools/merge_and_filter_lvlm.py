#!/usr/bin/env python
"""Merge per-venue accepted.jsonl files, dedupe, rank by LVLM/MLLM, take top-N.

Reads outputs/conference_search/{VENUE}/accepted.jsonl for each listed venue,
merges them on arxiv_id, attaches the set of venues each paper was accepted to,
scores LVLM/MLLM relevance (reuses tools/filter_lvlm_papers.score_paper),
and writes:
    {out_dir}/combined_accepted.jsonl   — full merged list, with venues field
    {out_dir}/papers_top.txt            — top-N arxiv IDs for main.py
    {out_dir}/combined_report.md        — score table for sanity checking
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.filter_lvlm_papers import score_paper  # noqa: E402


def load_accepted(path: Path) -> List[Dict]:
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--venues",
        required=True,
        help="Comma-separated venue keys whose accepted.jsonl should be merged.",
    )
    parser.add_argument(
        "--search-dir",
        type=Path,
        default=ROOT / "outputs" / "conference_search",
        help="Root directory containing per-venue subfolders.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=ROOT / "outputs" / "conference_search" / "combined_2026",
        help="Output directory for combined files.",
    )
    parser.add_argument("--top", type=int, default=100)
    args = parser.parse_args()

    venues = [v.strip() for v in args.venues.split(",") if v.strip()]
    by_id: Dict[str, Dict] = {}
    per_venue_counts: Dict[str, int] = {}

    for venue in venues:
        path = args.search_dir / venue / "accepted.jsonl"
        if not path.exists():
            print(f"[warn] missing {path}", file=sys.stderr)
            per_venue_counts[venue] = 0
            continue
        rows = load_accepted(path)
        per_venue_counts[venue] = len(rows)
        for row in rows:
            aid = row.get("arxiv_id")
            if not aid:
                continue
            if aid in by_id:
                by_id[aid].setdefault("venues", []).append(venue)
            else:
                row["venues"] = [venue]
                by_id[aid] = row

    merged = list(by_id.values())

    # Score by LVLM/MLLM relevance; keep only relevant rows.
    scored = []
    for row in merged:
        s = score_paper(row.get("title", ""), row.get("abstract", ""))
        if s > 0:
            row = dict(row)
            row["lvlm_score"] = round(s, 3)
            scored.append(row)

    scored.sort(key=lambda r: (r["lvlm_score"], r.get("updated", "")), reverse=True)
    selected = scored[: args.top] if args.top > 0 else scored

    args.out_dir.mkdir(parents=True, exist_ok=True)
    with (args.out_dir / "combined_accepted.jsonl").open("w", encoding="utf-8") as f:
        for row in scored:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    (args.out_dir / "papers_top.txt").write_text(
        "\n".join(r["arxiv_id"] for r in selected) + ("\n" if selected else ""),
        encoding="utf-8",
    )

    lines = [
        "# Combined LVLM/MLLM top-N across 2026 venues",
        "",
        f"Venues: {', '.join(venues)}",
        "",
        "## Per-venue accepted counts",
        "",
    ]
    for venue in venues:
        lines.append(f"- {venue}: {per_venue_counts.get(venue, 0)}")
    lines += [
        "",
        f"Total unique accepted papers: {len(merged)}",
        f"LVLM/MLLM-relevant: {len(scored)}",
        f"Selected top: {len(selected)}",
        "",
        "## Selected papers",
        "",
        "| # | Score | arXiv ID | Venues | Title |",
        "|---|------:|----------|--------|-------|",
    ]
    for i, row in enumerate(selected, 1):
        title = re.sub(r"\s+", " ", row.get("title", "")).strip()
        venues_str = ",".join(sorted(set(row.get("venues", []))))
        lines.append(
            f"| {i} | {row['lvlm_score']:.1f} | {row['arxiv_id']} | {venues_str} | {title} |"
        )
    (args.out_dir / "combined_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"Per-venue accepted: {per_venue_counts}")
    print(f"Unique papers: {len(merged)}")
    print(f"LVLM/MLLM-relevant: {len(scored)}")
    print(f"Selected top: {len(selected)}")
    print(f"Outputs under: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
