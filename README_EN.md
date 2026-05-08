# Paper Agent

English | [简体中文](./README.md)

LLM-powered paper reading assistant. Automatically searches arXiv papers, extracts figures, and generates structured reading notes.

## Features

- **Paper Search**: Search arXiv via DeepXiv API by keywords, categories, and date
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
QUERY="multimodal LVLM jailbreak"
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
│   ├── config.py            # Configuration (loads from .env)
│   ├── paper_processor.py   # Main processing pipeline
│   ├── pdf_processor.py     # PDF download & figure extraction
│   ├── latex_processor.py   # LaTeX download, figure & context extraction
│   ├── retry.py             # Retry decorator
│   └── utils.py             # Utilities
├── generators/
│   ├── card_generator.py    # 10min Card generation
│   ├── note_generator.py    # 30min Deep Note generation
│   ├── report_generator.py  # Survey report generation
│   └── figure_analyzer.py   # Figure context analysis
├── tests/
├── main.py
├── requirements.txt
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
