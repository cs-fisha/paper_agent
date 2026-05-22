#!/usr/bin/env python
"""Single-pass scan of the local arXiv metadata snapshot across multiple venues.

Running tools/conference_search.py once per venue re-reads the 5 GB JSONL each
time. With 7+ venues that is wasteful. This sweeper streams the snapshot once
and routes every record into per-venue accepted/rejected buckets.

Outputs match what conference_search.py writes, so downstream tools
(filter_lvlm_papers.py, main.py, etc.) keep working unchanged:
    outputs/conference_search/{VENUE}/accepted.jsonl
    outputs/conference_search/{VENUE}/rejected.jsonl
    outputs/conference_search/{VENUE}/papers_all.txt
    outputs/conference_search/{VENUE}/search_log.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Load .env before argparse evaluates the ARXIV_METADATA_FILE default.
load_dotenv(dotenv_path=ROOT / ".env")

from core.conference_search import (  # noqa: E402
    ConferenceConfig,
    PaperRecord,
    classify_records,
    filter_records_by_category,
    filter_records_by_date,
    load_conference_configs,
    mentions_any_alias,
    normalize_venue_key,
    paper_record_from_arxiv_metadata,
    write_id_file,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--venues",
        required=True,
        help="Comma-separated venue keys, e.g. CVPR2026,ICML2026,NeurIPS2026.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "conferences.json",
        help="Conferences JSON config.",
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        default=Path(os.getenv("ARXIV_METADATA_FILE", "")) if os.getenv("ARXIV_METADATA_FILE") else None,
        help="Local arXiv snapshot. Defaults to ARXIV_METADATA_FILE in .env.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "conference_search",
        help="Per-venue output root directory.",
    )
    parser.add_argument(
        "--date-from",
        default="",
        help="Global lower-bound YYYY-MM-DD; overrides each venue's date_from.",
    )
    parser.add_argument(
        "--date-to",
        default="",
        help="Global upper-bound YYYY-MM-DD; overrides each venue's date_to.",
    )
    parser.add_argument(
        "--use-config-categories",
        action="store_true",
        help="Restrict to each venue's configured arXiv categories.",
    )
    parser.add_argument(
        "--include-workshops",
        action="store_true",
        help="Keep workshop/challenge/tutorial-flagged records.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Stop after scanning N lines. 0 means scan everything.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=200_000,
        help="Print progress every N lines.",
    )
    return parser.parse_args()


def open_snapshot(path: Path):
    return gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else open(path, "rt", encoding="utf-8")


def sweep_once(
    metadata_file: Path,
    venue_configs: Dict[str, ConferenceConfig],
    *,
    date_from_override: str,
    date_to_override: str,
    use_config_categories: bool,
    include_workshops: bool,
    max_records: int,
    progress_every: int,
) -> Tuple[Dict[str, List[PaperRecord]], Dict[str, List[Dict[str, object]]], Dict[str, object]]:
    """One pass over the JSONL. Returns (accepted_by_venue, rejected_by_venue, stats)."""

    accepted_by_venue: Dict[str, List[PaperRecord]] = {v: [] for v in venue_configs}
    rejected_by_venue: Dict[str, List[Dict[str, object]]] = {v: [] for v in venue_configs}
    per_venue_candidates: Counter = Counter()

    aliases_by_venue = {v: cfg.aliases for v, cfg in venue_configs.items()}
    dates_by_venue: Dict[str, Tuple[Optional[str], Optional[str]]] = {}
    cats_by_venue: Dict[str, Sequence[str]] = {}
    for v, cfg in venue_configs.items():
        dates_by_venue[v] = (
            date_from_override or cfg.date_from,
            date_to_override or cfg.date_to,
        )
        cats_by_venue[v] = cfg.categories if use_config_categories else []

    scanned = 0
    parse_errors = 0
    matched_any = 0
    start = time.time()

    with open_snapshot(metadata_file) as handle:
        for line in handle:
            if max_records and scanned >= max_records:
                break
            scanned += 1
            if progress_every and scanned % progress_every == 0:
                rate = scanned / max(time.time() - start, 1e-6)
                print(
                    f"  scanned={scanned:>10,}  matched_any={matched_any:,}  "
                    f"rate={rate:,.0f}/s",
                    file=sys.stderr,
                )

            if not line.strip():
                continue
            try:
                raw = json.loads(line)
            except json.JSONDecodeError:
                parse_errors += 1
                continue

            # Cheap text-bag prefilter before we even build a PaperRecord.
            # Any venue alias must appear in the relevant fields. We do this
            # once per line by stringifying the fields we care about.
            text_bag = " ".join(
                str(raw.get(key, "") or "")
                for key in ("title", "abstract", "comments", "journal-ref")
            ).lower()
            interested_venues = [
                v
                for v, aliases in aliases_by_venue.items()
                if any(alias.lower() in text_bag for alias in aliases)
            ]
            if not interested_venues:
                continue

            try:
                record = paper_record_from_arxiv_metadata(raw)
            except (TypeError, ValueError):
                parse_errors += 1
                continue
            matched_any += 1

            for venue in interested_venues:
                # Full alias check (case-insensitive). Cheap; we already know
                # at least one alias substring is present, but a different
                # venue's alias may have matched the text bag.
                if not mentions_any_alias(record, aliases_by_venue[venue]):
                    continue
                df, dt = dates_by_venue[venue]
                if not filter_records_by_date([record], date_from=df, date_to=dt):
                    continue
                if not filter_records_by_category([record], cats_by_venue[venue]):
                    continue

                per_venue_candidates[venue] += 1
                one_accepted, one_rejected = classify_records(
                    [record],
                    venue_configs[venue],
                    include_workshops=include_workshops,
                )
                accepted_by_venue[venue].extend(one_accepted)
                rejected_by_venue[venue].extend(one_rejected)

    for venue in accepted_by_venue:
        accepted_by_venue[venue].sort(key=lambda r: r.updated, reverse=True)

    stats = {
        "scanned_records": scanned,
        "parse_errors": parse_errors,
        "matched_any_alias": matched_any,
        "candidate_counts": dict(per_venue_candidates),
        "elapsed_seconds": round(time.time() - start, 1),
    }
    return accepted_by_venue, rejected_by_venue, stats


def write_venue_outputs(
    venue: str,
    config: ConferenceConfig,
    accepted: Sequence[PaperRecord],
    rejected: Sequence[Dict[str, object]],
    candidate_count: int,
    output_dir: Path,
    *,
    date_from: Optional[str],
    date_to: Optional[str],
    categories: Sequence[str],
    include_workshops: bool,
    sweep_stats: Dict[str, object],
) -> None:
    venue_dir = output_dir / venue
    venue_dir.mkdir(parents=True, exist_ok=True)

    write_jsonl(venue_dir / "accepted.jsonl", [r.to_dict() for r in accepted])
    write_jsonl(venue_dir / "rejected.jsonl", list(rejected))
    write_id_file(venue_dir / "papers_all.txt", list(accepted))

    (venue_dir / "search_log.json").write_text(
        json.dumps(
            {
                "venue": venue,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "backend": "metadata-sweep",
                "aliases": config.aliases,
                "configured_categories": config.categories,
                "categories": list(categories),
                "date_from": date_from,
                "date_to": date_to,
                "include_workshops": include_workshops,
                "candidate_count": candidate_count,
                "accepted_count": len(accepted),
                "rejected_count": len(rejected),
                "sweep": sweep_stats,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()

    if not args.metadata_file:
        print("ARXIV_METADATA_FILE or --metadata-file is required.", file=sys.stderr)
        return 2
    if not args.metadata_file.exists():
        print(f"Metadata file not found: {args.metadata_file}", file=sys.stderr)
        return 2

    configs = load_conference_configs(args.config)
    venue_keys = [normalize_venue_key(v) for v in args.venues.split(",") if v.strip()]
    missing = [v for v in venue_keys if v not in configs]
    if missing:
        print(f"Unknown venues: {missing}. Available: {sorted(configs)}", file=sys.stderr)
        return 2
    venue_configs = {v: configs[v] for v in venue_keys}

    print(f"Snapshot: {args.metadata_file}")
    print(f"Venues:   {', '.join(venue_keys)}")
    if args.date_from:
        print(f"Date >=   {args.date_from}  (global override)")
    if args.date_to:
        print(f"Date <=   {args.date_to}  (global override)")
    print(f"Categories filter: {'venue config' if args.use_config_categories else 'all'}")
    print()

    accepted_by_venue, rejected_by_venue, sweep_stats = sweep_once(
        args.metadata_file,
        venue_configs,
        date_from_override=args.date_from,
        date_to_override=args.date_to,
        use_config_categories=args.use_config_categories,
        include_workshops=args.include_workshops,
        max_records=args.max_records,
        progress_every=args.progress_every,
    )

    print()
    print(f"Scanned {sweep_stats['scanned_records']:,} records in "
          f"{sweep_stats['elapsed_seconds']}s; matched_any={sweep_stats['matched_any_alias']:,}; "
          f"parse_errors={sweep_stats['parse_errors']}")
    print()
    print(f"{'VENUE':<12} {'CAND':>8} {'ACCEPT':>8} {'REJECT':>8}")
    for venue in venue_keys:
        cfg = venue_configs[venue]
        candidate_count = sweep_stats["candidate_counts"].get(venue, 0)
        accepted = accepted_by_venue[venue]
        rejected = rejected_by_venue[venue]
        write_venue_outputs(
            venue,
            cfg,
            accepted,
            rejected,
            candidate_count,
            args.output_dir,
            date_from=args.date_from or cfg.date_from,
            date_to=args.date_to or cfg.date_to,
            categories=cfg.categories if args.use_config_categories else [],
            include_workshops=args.include_workshops,
            sweep_stats=sweep_stats,
        )
        print(f"{venue:<12} {candidate_count:>8,} {len(accepted):>8,} {len(rejected):>8,}")

    print(f"\nOutputs under: {args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
