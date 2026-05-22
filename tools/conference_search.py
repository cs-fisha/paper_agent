#!/usr/bin/env python
"""Search arXiv for papers explicitly marked accepted by a conference."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.conference_search import (  # noqa: E402
    annotate_and_select,
    build_openalex_queries,
    build_search_queries,
    build_web_search_queries,
    classify_records,
    fetch_arxiv_abs_records,
    fetch_arxiv_records,
    fetch_openalex_candidates,
    fetch_web_candidates,
    filter_records_by_category,
    filter_records_by_date,
    generate_trend_report,
    load_conference_configs,
    normalize_venue_key,
    scan_arxiv_metadata_file,
    write_id_file,
    write_jsonl,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find arXiv papers explicitly marked accepted/to-appear at a conference."
    )
    parser.add_argument("--venue", required=True, help="Conference key, e.g. CVPR2026 or ICML2026.")
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "configs" / "conferences.json",
        help="JSON config with venue aliases, categories, and exclusion terms.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "outputs" / "conference_search",
        help="Directory for conference search outputs.",
    )
    parser.add_argument(
        "--backend",
        choices=["metadata", "openalex", "web", "arxiv-api"],
        default="metadata",
        help="Search backend. Default avoids the official arXiv API.",
    )
    parser.add_argument(
        "--metadata-file",
        type=Path,
        default=Path(os.getenv("ARXIV_METADATA_FILE", "")) if os.getenv("ARXIV_METADATA_FILE") else None,
        help="Local arXiv metadata JSONL file, e.g. arxiv-metadata-oai-snapshot.json. Can also be set with ARXIV_METADATA_FILE.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=50,
        help="Number of papers to pass to deep workflow. If fewer exist, all are used. Use 0 to skip.",
    )
    parser.add_argument(
        "--categories",
        default="",
        help="Comma-separated arXiv categories to restrict search, e.g. cs.CV,cs.LG. Default: all categories.",
    )
    parser.add_argument(
        "--use-config-categories",
        action="store_true",
        help="Restrict search to the categories configured for this venue.",
    )
    parser.add_argument(
        "--query-field",
        choices=["all", "co", "both"],
        default="both",
        help="arXiv API backend only: metadata field to query. 'co' is comments, 'all' is all fields.",
    )
    parser.add_argument(
        "--search-pages",
        type=int,
        default=2,
        help="Web backend only: search result pages to inspect for each exact phrase query.",
    )
    parser.add_argument(
        "--mailto",
        default=os.getenv("OPENALEX_MAILTO", "paper_agent@example.com"),
        help="OpenAlex polite-pool email. Can also be set with OPENALEX_MAILTO.",
    )
    parser.add_argument("--page-size", type=int, default=100, help="OpenAlex/arXiv API page size.")
    parser.add_argument(
        "--max-results",
        type=int,
        default=5000,
        help="Network backend safety cap, not the final top-N size.",
    )
    parser.add_argument(
        "--max-records",
        type=int,
        default=0,
        help="Metadata backend scan cap. Default 0 means scan the full snapshot.",
    )
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=3.1,
        help="Delay between network requests for non-metadata backends.",
    )
    parser.add_argument(
        "--date-from",
        default="",
        help="Published date lower bound YYYY-MM-DD. Defaults to the venue config.",
    )
    parser.add_argument(
        "--date-to",
        default="",
        help="Published date upper bound YYYY-MM-DD. Defaults to the venue config if set.",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=3,
        help="Retries for each arXiv API request when rate-limited or temporarily unavailable.",
    )
    parser.add_argument(
        "--include-workshops",
        action="store_true",
        help="Keep workshop/challenge/competition papers instead of excluding them.",
    )
    parser.add_argument(
        "--focus",
        default="",
        help="Optional research focus for lightweight ranking. Defaults to RESEARCH_FOCUS in .env.",
    )
    parser.add_argument(
        "--run-workflow",
        action="store_true",
        help="After search, run python main.py --ids-file papers_top.txt.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    load_dotenv(dotenv_path=ROOT / ".env")

    if args.top < 0:
        print("Configuration error: --top must be >= 0", file=sys.stderr)
        return 2
    if args.page_size < 1 or args.page_size > 2000:
        print("Configuration error: --page-size must be between 1 and 2000", file=sys.stderr)
        return 2
    if args.max_results < 1:
        print("Configuration error: --max-results must be >= 1", file=sys.stderr)
        return 2
    if args.max_records < 0:
        print("Configuration error: --max-records must be >= 0", file=sys.stderr)
        return 2
    if args.retries < 0:
        print("Configuration error: --retries must be >= 0", file=sys.stderr)
        return 2
    if args.search_pages < 1:
        print("Configuration error: --search-pages must be >= 1", file=sys.stderr)
        return 2

    configs = load_conference_configs(args.config)
    venue_key = normalize_venue_key(args.venue)
    if venue_key not in configs:
        available = ", ".join(sorted(configs))
        print(f"Unknown venue '{args.venue}'. Available: {available}", file=sys.stderr)
        return 2

    config = configs[venue_key]
    if args.categories:
        categories = parse_csv(args.categories)
    elif args.use_config_categories:
        categories = config.categories
    else:
        categories = []
    focus = args.focus.strip() or os.getenv("RESEARCH_FOCUS", "").strip()
    date_from = args.date_from.strip() or config.date_from
    date_to = args.date_to.strip() or config.date_to

    output_dir = args.output_dir / venue_key
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Venue: {venue_key}")
    print(f"Backend: {args.backend}")
    print(f"Categories: {', '.join(categories) if categories else 'all'}")
    print(f"Date filter: {date_from or 'none'} to {date_to or 'none'}")

    queries = []
    fetched_candidates = []
    candidates = []

    if args.backend == "metadata":
        if not args.metadata_file:
            print(
                "Configuration error: --metadata-file or ARXIV_METADATA_FILE is required for metadata backend.",
                file=sys.stderr,
            )
            return 2
        if not args.metadata_file.exists():
            print(f"Configuration error: metadata file does not exist: {args.metadata_file}", file=sys.stderr)
            return 2
        print(f"Scanning local arXiv metadata: {args.metadata_file}")
        accepted, rejected, scan_log = scan_arxiv_metadata_file(
            args.metadata_file,
            config,
            date_from=date_from,
            date_to=date_to,
            categories=categories,
            include_workshops=args.include_workshops,
            max_records=args.max_records,
        )
        query_logs = {"metadata_scan": scan_log}
    elif args.backend == "openalex":
        queries = build_openalex_queries(config)
        print(f"Generated OpenAlex queries: {len(queries)}")
        print("Discovering arXiv candidates via OpenAlex...")
        candidate_urls, search_logs = fetch_openalex_candidates(
            queries,
            date_from=date_from,
            date_to=date_to,
            per_page=args.page_size,
            max_results=args.max_results,
            delay_seconds=args.delay_seconds,
            mailto=args.mailto,
        )
        print(f"Candidate URLs discovered: {len(candidate_urls)}")
        print("Fetching candidate arXiv abs pages...")
        fetched_candidates, fetch_logs = fetch_arxiv_abs_records(
            candidate_urls,
            delay_seconds=args.delay_seconds,
        )
        query_logs = {
            "openalex_search": search_logs,
            "abs_fetch": fetch_logs,
        }
    elif args.backend == "web":
        queries = build_web_search_queries(config)
        print(f"Generated web-search queries: {len(queries)}")
        print("Discovering arXiv candidates via web search...")
        candidate_urls, search_logs = fetch_web_candidates(
            queries,
            search_pages=args.search_pages,
            max_results=args.max_results,
            delay_seconds=args.delay_seconds,
        )
        print(f"Candidate URLs discovered: {len(candidate_urls)}")
        print("Fetching candidate arXiv abs pages...")
        fetched_candidates, fetch_logs = fetch_arxiv_abs_records(
            candidate_urls,
            delay_seconds=args.delay_seconds,
        )
        query_logs = {
            "web_search": search_logs,
            "abs_fetch": fetch_logs,
        }
    else:
        queries = build_search_queries(config, query_fields=args.query_field, categories=categories)
        print(f"Generated arXiv API queries: {len(queries)}")
        print("Fetching arXiv API metadata...")
        fetched_candidates, query_logs = fetch_arxiv_records(
            queries,
            page_size=args.page_size,
            max_results=args.max_results,
            delay_seconds=args.delay_seconds,
            retries=args.retries,
        )

    if args.backend != "metadata":
        dated_candidates = filter_records_by_date(fetched_candidates, date_from=date_from, date_to=date_to)
        candidates = filter_records_by_category(dated_candidates, categories)
        accepted, rejected = classify_records(
            candidates,
            config,
            include_workshops=args.include_workshops,
        )
    selected = annotate_and_select(accepted, top_n=args.top, focus=focus)
    candidate_count = (
        query_logs.get("metadata_scan", {}).get("candidate_count", len(candidates))
        if args.backend == "metadata"
        else len(candidates)
    )

    write_jsonl(output_dir / "accepted.jsonl", [record.to_dict() for record in accepted])
    write_jsonl(output_dir / "rejected.jsonl", rejected)
    write_id_file(output_dir / "papers_all.txt", accepted)
    write_id_file(output_dir / "papers_top.txt", selected)
    (output_dir / "trend_report.md").write_text(
        generate_trend_report(
            venue_key,
            accepted,
            selected,
            top_n=args.top,
            focus=focus,
            include_workshops=args.include_workshops,
        ),
        encoding="utf-8",
    )
    (output_dir / "search_log.json").write_text(
        json.dumps(
            {
                "venue": venue_key,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "aliases": config.aliases,
                "categories": categories,
                "configured_categories": config.categories,
                "date_from": date_from,
                "date_to": date_to,
                "backend": args.backend,
                "query_field": args.query_field,
                "search_pages": args.search_pages,
                "mailto": args.mailto if args.backend == "openalex" else "",
                "top_requested": args.top,
                "fetched_candidate_count": len(fetched_candidates),
                "candidate_count": candidate_count,
                "accepted_count": len(accepted),
                "selected_count": len(selected),
                "include_workshops": args.include_workshops,
                "queries": queries,
                "query_logs": query_logs,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Candidates fetched: {candidate_count}")
    print(f"Accepted after hard filter: {len(accepted)}")
    print(f"Selected for deep workflow: {len(selected)}")
    print(f"Output: {output_dir}")

    if args.run_workflow:
        if not selected:
            print("No selected papers; skipping main.py workflow.")
            return 0
        print("Running existing paper_agent workflow on papers_top.txt...")
        subprocess.run(
            [sys.executable, str(ROOT / "main.py"), "--ids-file", str(output_dir / "papers_top.txt")],
            cwd=ROOT,
            check=True,
        )

    return 0


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
