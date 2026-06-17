"""Filter conference accepted.jsonl down to top LVLM/MLLM papers.

Reads accepted.jsonl produced by tools/conference_search.py, ranks papers by
LVLM/MLLM relevance (title + abstract keyword density), and writes the top-N
arxiv IDs to a target text file ready to feed `python main.py --ids-file`.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List

# Title hits weight 3x abstract hits. Phrases also override unrelated meanings
# (e.g. "vlm" alone is risky, but "vision-language model" is unambiguous).
TITLE_WEIGHT = 3.0
ABSTRACT_WEIGHT = 1.0

# Phrases must appear as substrings (lowercased) in title or abstract.
STRONG_TERMS = [
    "lvlm",
    "mllm",
    "lmm ",  # avoid matching "llm "
    "large multimodal model",
    "multimodal large language model",
    "multimodal llm",
    "vision-language model",
    "vision language model",
    "vision-language large",
    "visual language model",
    "visual instruction tuning",
    "visual instruction-tuned",
    "vision-language pre-train",
    "multimodal language model",
    "video-language model",
    "vision-language reasoning",
    # LLM Agent terms
    "llm agent",
    "llm-based agent",
    "language model agent",
    "language agent",
    "multimodal agent",
    "tool-augmented llm",
    "agentic llm",
    "multi-agent llm",
    "autonomous agent",
    "agent framework",
]

# Weaker signals — count only if at least one STRONG term already matched, to
# avoid dragging in unrelated multimodal (audio/3D/robotic) work.
WEAK_TERMS = [
    "multimodal",
    "vision-language",
    "vision and language",
    "visual question answering",
    "vqa",
    "image-text",
    "image text",
    "vlm",
    # LLM Agent weak signals
    "agent",
    "tool calling",
    "function calling",
    "web agent",
    "gui agent",
    "code agent",
    "reasoning agent",
]


def score_paper(title: str, abstract: str) -> float:
    title_l = (title or "").lower()
    abs_l = (abstract or "").lower()

    strong_title = sum(1 for term in STRONG_TERMS if term in title_l)
    strong_abs = sum(1 for term in STRONG_TERMS if term in abs_l)

    if strong_title == 0 and strong_abs == 0:
        return 0.0

    weak_title = sum(1 for term in WEAK_TERMS if term in title_l)
    weak_abs = sum(1 for term in WEAK_TERMS if term in abs_l)

    return (
        TITLE_WEIGHT * strong_title
        + ABSTRACT_WEIGHT * strong_abs
        + 0.5 * weak_title
        + 0.2 * weak_abs
    )


def load_accepted(path: Path) -> List[Dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted", required=True, type=Path, help="Path to accepted.jsonl")
    parser.add_argument("--out", required=True, type=Path, help="Output IDs txt path")
    parser.add_argument("--top", type=int, default=50)
    parser.add_argument(
        "--debug-report",
        type=Path,
        default=None,
        help="Optional: write a markdown table of selected papers with scores",
    )
    args = parser.parse_args()

    records = load_accepted(args.accepted)
    scored = []
    for r in records:
        s = score_paper(r.get("title", ""), r.get("abstract", ""))
        if s > 0:
            scored.append((s, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[: args.top]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as f:
        for _, r in selected:
            f.write(r["arxiv_id"] + "\n")

    print(f"Source: {args.accepted}  total={len(records)}  lvlm/mllm-related={len(scored)}")
    print(f"Wrote top {len(selected)} arXiv IDs to {args.out}")

    if args.debug_report:
        lines = [
            f"# LVLM/MLLM filter result — {args.accepted.parent.name}",
            "",
            f"Total accepted: {len(records)}  |  LVLM/MLLM hits: {len(scored)}  |  Selected: {len(selected)}",
            "",
            "| # | Score | arXiv ID | Title |",
            "|---|------:|----------|-------|",
        ]
        for i, (s, r) in enumerate(selected, 1):
            title = re.sub(r"\s+", " ", r.get("title", "")).strip()
            lines.append(f"| {i} | {s:.1f} | {r['arxiv_id']} | {title} |")
        args.debug_report.parent.mkdir(parents=True, exist_ok=True)
        args.debug_report.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"Debug report: {args.debug_report}")


if __name__ == "__main__":
    main()
