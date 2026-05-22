# Paper Agent

English | [简体中文](./README.md)

LLM-powered paper reading assistant. Automatically searches arXiv papers, extracts figures, and generates structured reading notes.

## Features

- **Paper Search**: Search arXiv via DeepXiv API by keywords, categories, and date
- **Conference Paper Search**: Scan local arXiv metadata snapshot to find papers explicitly accepted at top venues (CVPR, ICML, NeurIPS, ICLR, ACL, etc.)
- **ID File Import**: Load arXiv IDs / URLs from a txt file and process the specified papers directly
- **Research Focus**: Use `RESEARCH_FOCUS` for relevance, inspiration, and new-paper ideas
- **Figure Extraction**: LaTeX source preferred (high quality), PDF as fallback
- **Three-layer Notes**:
  - 10min Card — quick grasp of core contributions
  - Figure Context Analysis — interprets each figure with LaTeX citation context
  - 30min Deep Note — method details, experiment credibility, reproducibility
- **Metadata Annotation**: Auto-labels paper type, top-venue acceptance, open-source code links
- **Parallel Processing**: Paper-level + generator-level dual parallelism
- **Survey Report**: Auto-generated after batch processing

## Quick Start

```bash
git clone https://github.com/sinksilk/paper_agent.git
cd paper_agent
pip install -r requirements.txt
cp .env.example .env  # Edit and fill in API keys
python main.py
```

## Configuration

Edit `.env`:

```bash
# LLM API (any OpenAI-compatible endpoint)
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# DeepXiv API (register at https://deepxiv.com)
DEEPXIV_TOKEN=your_token

# Search
QUERY="multimodal LVLM jailbreak"       # Used only for keyword search
RESEARCH_FOCUS="multimodal LVLM safety" # Used for relevance and new-paper ideas
ARXIV_IDS_FILE=              # Optional: load IDs from txt and skip keyword search
LIMIT=10
DATE_FROM=2025-01-01
CATEGORIES=cs.CV,cs.CL,cs.CR

# Processing
MAX_WORKERS=8              # Parallel threads
DOWNLOAD_PDF=true
EXTRACT_FIGURES=true
USE_LATEX_SOURCE=true      # Prefer LaTeX source for figures
ANALYZE_FIGURES=true       # Figure context analysis
GENERATE_DEEP_NOTE=false   # 30min deep note (slower)

# Conference Search (tools/conference_search.py)
ARXIV_METADATA_FILE=       # Local arXiv metadata snapshot path
```

### Process Papers From a txt File

Create a txt file with mixed arXiv URLs and raw IDs:

```text
https://arxiv.org/abs/2605.08389
2605.08389
2605.08389v2
https://arxiv.org/pdf/2605.08389.pdf
```

Then run:

```bash
python main.py --ids-file papers.txt
```

You can also set `ARXIV_IDS_FILE=papers.txt` in `.env` and run `python main.py`. When enabled, keyword search is skipped; every paper in the txt file is downloaded, parsed, and included in the final report. Relevance, inspiration, and new-paper ideas are judged against `RESEARCH_FOCUS`; if it is empty, `QUERY` is used as the fallback.

### Search Conference-Accepted arXiv Papers

By default this does NOT call the arXiv official API. Instead it scans a local arXiv metadata snapshot (recommended: Kaggle/Cornell `arxiv-metadata-oai-snapshot.json`), hard-filters papers that explicitly state `accepted to/at/by` or `to appear at/in` a venue, then feeds the selected IDs into the existing workflow:

```bash
python tools/conference_search.py --venue CVPR2026 --metadata-file /path/to/arxiv-metadata-oai-snapshot.json --top 50
python tools/conference_search.py --venue ICML2026 --metadata-file /path/to/arxiv-metadata-oai-snapshot.json --top 200
```

You can also set in `.env`:

```bash
ARXIV_METADATA_FILE=/path/to/arxiv-metadata-oai-snapshot.json
```

Then simply run:

```bash
python tools/conference_search.py --venue CVPR2026 --top 50
```

`--top` only controls how many papers enter the deep-read workflow, not the search scope. If you request `--top 200` but only 80 accepted papers are found, `papers_top.txt` will contain all 80. The full snapshot is scanned by default; use `--max-records 10000` for debugging. arXiv categories are unrestricted by default for better recall; narrow with `--categories cs.CV` or `--use-config-categories`. Workshop/challenge/competition papers are excluded by default; use `--include-workshops` to keep them.

If you don't have a local snapshot, you can fall back to OpenAlex or web search for candidate discovery. These modes also avoid the arXiv official API but have lower reproducibility and recall:

```bash
python tools/conference_search.py --venue CVPR2026 --backend openalex --top 50
python tools/conference_search.py --venue CVPR2026 --backend web --search-pages 3 --delay-seconds 5
```

Output directory:

```text
outputs/conference_search/{VENUE}/
├── accepted.jsonl      # All papers passing the hard filter
├── rejected.jsonl      # Excluded candidates with reasons
├── papers_all.txt      # All accepted arXiv IDs
├── papers_top.txt      # IDs suggested for deep-read workflow
├── trend_report.md     # Non-LLM topic overview from titles/abstracts
└── search_log.json
```

After reviewing `papers_top.txt`, run:

```bash
python main.py --ids-file outputs/conference_search/CVPR2026/papers_top.txt
```

Or do search + workflow in one step:

```bash
python tools/conference_search.py --venue CVPR2026 --top 50 --run-workflow
```

## Output Example

### Card Metadata Header

Each card starts with structured metadata:

```markdown
# 10min Paper Card: Cross-Modal Obfuscation for Jailbreak Attacks on LVLMs

Paper: **Cross-Modal Obfuscation for Jailbreak Attacks on Large Vision-Language Models**
arXiv: **2506.16760**
Keywords: LVLM / adversarial jailbreak / black-box / cross-modal obfuscation
Type: **Research**
Venue: **NeurIPS 2025**              ← auto-labeled if accepted at a top venue
Code: **https://github.com/xxx/xxx** ← auto-labeled if mentioned in the paper
```

### Output Directory

```
outputs/
├── cards/              # 10min Paper Cards (with figure analysis)
├── deep_notes/         # 30min Deep Notes
├── figure_analysis/    # Figure context analysis (standalone)
├── figures/            # Extracted figures
├── pdfs/              # PDF files
├── latex_sources/     # LaTeX sources
└── reports/           # Survey reports
    └── {query}_{timestamp}/
        ├── report.md
        ├── cards/
        └── materials/
```

## Note Format

### 10min Card

| Section | Content |
|---------|---------|
| One-sentence conclusion | Core contribution |
| Problem | Motivation and background |
| Method | Technical approach |
| Difference from prior work | Novelty |
| Experiment setup | Datasets, baselines, metrics |
| Key results | Main findings |
| Potential issues | Critical analysis |
| Usefulness to my research | A/B/C/D rating + reason |
| Priority reading sections | Reading guide for 30min |

### 30min Deep Note

In-depth analysis of method details, training data, model architecture, experiment credibility, ablation sufficiency, hidden weaknesses, reproducibility, and follow-up suggestions.

## Project Structure

```
paper_agent/
├── core/
│   ├── api_client.py        # OpenAI + DeepXiv API clients
│   ├── arxiv_ids.py         # arXiv ID parsing
│   ├── conference_search.py # Conference paper search core logic
│   ├── config.py            # Configuration (loads from .env)
│   ├── file_utils.py        # File utilities
│   ├── latex_processor.py   # LaTeX download, figure & context extraction
│   ├── logger.py            # Logging
│   ├── paper_processor.py   # Main processing pipeline
│   ├── pdf_processor.py     # PDF download & figure extraction
│   ├── retry.py             # Retry decorator
│   └── utils.py             # Utilities
├── generators/
│   ├── card_generator.py    # 10min Card generation
│   ├── figure_analyzer.py   # Figure context analysis
│   ├── note_generator.py    # 30min Deep Note generation
│   └── report_generator.py  # Survey report generation
├── tools/
│   ├── conference_search.py         # Conference paper search CLI
│   ├── multi_venue_sweep.py         # Multi-venue single-pass scan
│   ├── filter_lvlm_papers.py        # LVLM/MLLM paper filter
│   ├── merge_and_filter_lvlm.py     # Cross-venue merge & dedup
│   ├── refresh_arxiv_snapshot.py    # Kaggle arXiv snapshot refresh
│   ├── survey_synthesis.py          # LLM survey report
│   └── survey_synthesis_detailed.py # Multi-phase detailed survey report
├── configs/
│   └── conferences.json     # Venue aliases, categories, exclusion terms
├── tests/                   # Unit tests
├── main.py                  # Entry point
├── requirements.txt
├── papers.txt.example       # Example paper ID list
└── .env.example
```

## Performance

Dual-layer parallelism (paper-level + generator-level):

| Papers | Sequential | Parallel | Improvement |
|--------|-----------|----------|-------------|
| 5 | ~13 min | ~4 min | 69% |
| 20 | ~50 min | ~15 min | 70% |

## Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Dependencies

- [DeepXiv](https://deepxiv.com) — Paper search and parsing API
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF processing
- [OpenAI SDK](https://github.com/openai/openai-python) — LLM calls (any OpenAI-compatible endpoint)

## License

MIT
