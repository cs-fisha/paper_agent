# Paper Agent

English | [简体中文](./README.md)

An intelligent paper reading assistant powered by LLM that automatically searches papers from arXiv, downloads PDFs, extracts figures, and generates structured reading notes.

## ✨ Features

- 🔍 **Smart Search**: Search arXiv papers via DeepXiv API
- 📄 **Auto Download**: Automatically download paper PDFs
- 🖼️ **Figure Extraction**: Intelligently extract key figures and tables from PDFs (with captions)
- 📝 **Dual-Layer Notes**:
  - **10min Card**: Quick overview of paper essentials
  - **30min Deep Note**: In-depth analysis of paper details
- 🎯 **Figure Analysis**: Detailed analysis for each figure (content, novelty, logic)
- ⚡ **Parallel Processing**: Card and Deep Note generation fully parallelized, 70% faster
- 📊 **Survey Report**: Automatically generate comprehensive survey reports after batch processing

## 📦 Installation

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Main dependencies:
- `openai` - OpenAI API client
- `deepxiv-sdk` - DeepXiv API client
- `PyMuPDF` (fitz) - PDF processing
- `Pillow` - Image processing
- `python-dotenv` - Environment variable management

### 3. Configure Environment Variables

Copy `.env.example` to `.env` and fill in the configuration:

```bash
cp .env.example .env
```

Then edit the `.env` file:

```bash
# OpenAI API Configuration
OPENAI_API_KEY=your_api_key_here          # Your API Key
OPENAI_BASE_URL=https://api.openai.com/v1 # API Base URL
MODEL_NAME=gpt-4                           # Model name

# DeepXiv API Configuration
DEEPXIV_TOKEN=your_deepxiv_token_here     # DeepXiv Token

# Search Configuration
QUERY="multimodal LVLM MLLM"              # Search keywords
LIMIT=5                                    # Number of papers
DATE_FROM=2025-01-01                       # Start date
CATEGORIES=cs.CV,cs.CL                     # arXiv categories

# Processing Configuration
MAX_WORKERS=8                              # Parallel threads
DOWNLOAD_PDF=true                          # Download PDFs
EXTRACT_FIGURES=true                       # Extract figures
GENERATE_DEEP_NOTE=true                    # Generate Deep Notes
```

## 🚀 Usage

### Basic Usage

```bash
python batch_read_deepxiv_with_pdf.py
```

This will:
1. Search arXiv papers based on `QUERY`
2. Download PDF files
3. Extract key figures
4. Generate Cards and Deep Notes in parallel
5. Generate comprehensive survey report

### Advanced Usage

#### Generate Cards Only (Quick Preview)

```bash
export GENERATE_DEEP_NOTE=false
python batch_read_deepxiv_with_pdf.py
```

#### Regenerate Single Paper

```bash
python regenerate_card_with_figures.py 2602.08145
```

#### Batch Regenerate All Papers

```bash
python batch_regenerate_cards.py
```

## 📊 Environment Variables Explained

### OpenAI API Configuration

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `OPENAI_API_KEY` | ✅ | OpenAI API Key | `sk-...` |
| `OPENAI_BASE_URL` | ✅ | API Base URL | `https://api.openai.com/v1` |
| `MODEL_NAME` | ✅ | Model to use | `gpt-4`, `gpt-3.5-turbo` |

**How to get**:
- Official OpenAI: Visit https://platform.openai.com/api-keys
- Third-party proxy: Get from your API provider

### DeepXiv API Configuration

| Variable | Required | Description | Example |
|----------|----------|-------------|---------|
| `DEEPXIV_TOKEN` | ✅ | DeepXiv API Token | `ilY0FVk...` |

**How to get**:
1. Visit https://deepxiv.com
2. Register an account
3. Get API Token from personal settings

### Search Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QUERY` | ❌ | `"multimodal LVLM MLLM"` | Search keywords, supports multiple terms |
| `LIMIT` | ❌ | `5` | Number of papers to retrieve |
| `DATE_FROM` | ❌ | `2025-06-01` | Paper publication start date (YYYY-MM-DD) |
| `CATEGORIES` | ❌ | `cs.CV,cs.CL` | arXiv categories, comma-separated |

**Common arXiv Categories**:
- `cs.CV` - Computer Vision
- `cs.CL` - Computation and Language (NLP)
- `cs.AI` - Artificial Intelligence
- `cs.LG` - Machine Learning
- `cs.CR` - Cryptography and Security
- `cs.RO` - Robotics
- `cs.NE` - Neural and Evolutionary Computing

Full category list: https://arxiv.org/category_taxonomy

### Processing Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MAX_WORKERS` | ❌ | `8` | Number of parallel threads |
| `DOWNLOAD_PDF` | ❌ | `true` | Whether to download PDF files |
| `EXTRACT_FIGURES` | ❌ | `true` | Whether to extract figures from PDFs |
| `GENERATE_DEEP_NOTE` | ❌ | `true` | Whether to generate Deep Notes |

**MAX_WORKERS Recommendations**:

| Paper Count | Recommended | Notes |
|-------------|-------------|-------|
| 1-5         | 4-8         | Full parallelization |
| 6-20        | 8-12        | Balance speed and resources |
| 20+         | 8-16        | Avoid API rate limits |

⚠️ **Notes**:
- If you encounter API rate limit errors, reduce `MAX_WORKERS`
- Each worker consumes memory, adjust based on your machine
- Set `GENERATE_DEEP_NOTE=false` to only generate Cards for faster processing

## 📁 Output Structure

```
outputs/
├── cards/              # 10min Paper Cards
│   └── 2602.08145_Paper_Title.md
├── deep_notes/         # 30min Deep Notes
│   └── 2602.08145_Paper_Title.md
├── pdfs/              # Downloaded PDF files
│   └── 2602.08145.pdf
├── figures/           # Extracted figures
│   └── 2602.08145/
│       ├── fig_1_page2.png
│       ├── fig_2_page2.png
│       └── ...
└── reports/           # Survey reports
    └── query_timestamp/
        ├── survey_report.md
        └── materials/
```

## 📝 Output Format

### 10min Paper Card

Contains:
1. One-sentence conclusion
2. Problem the paper addresses
3. Core method
4. Main differences from existing work
5. Experimental setup
6. Key results
7. **Most valuable figures/tables/experiments** ⭐ (with image links and detailed analysis)
8. Potential issues or weaknesses
9. Relevance to my research direction
10. Priority reading sections for 30-minute reading

### 30min Deep Note

Contains:
1. Paper claims vs. actual contributions
2. Method details breakdown
3. Training data / preference data / annotation methods
4. Model architecture or pipeline
5. Credibility of experimental results
6. Sufficiency of ablation / analysis
7. **Most valuable figures/tables/experiments** ⭐
8. Potential hidden weaknesses
9. Relationship to my research direction
10. Reproducibility assessment
11. How to follow up on this work

### Figure Analysis Format

Each figure includes:
- **What the figure shows**: 2-3 sentences describing the content
- **How it demonstrates novelty**: 2-3 sentences on how it supports the paper's core contribution
- **Logical rigor**: 1-2 sentences evaluating the design
- **Comprehension from figure alone**: Percentage with brief explanation

## ⚡ Performance

### Parallel Processing Optimization

Fully parallelized Card and Deep Note generation achieves significant performance improvements:

| Paper Count | Before | After | Improvement |
|-------------|--------|-------|-------------|
| 5 papers    | 13 min | 4 min | **69% ⬇️** |
| 20 papers   | 50 min | 15 min | **70% ⬇️** |

See [docs/PARALLEL_OPTIMIZATION.md](./docs/PARALLEL_OPTIMIZATION.md) for details

## 📚 Documentation

- [docs/EXAMPLE_OUTPUT.md](./docs/EXAMPLE_OUTPUT.md) - Example outputs showcase
- [docs/SUMMARY.md](./docs/SUMMARY.md) - Complete feature summary
- [docs/PARALLEL_OPTIMIZATION.md](./docs/PARALLEL_OPTIMIZATION.md) - Parallel optimization details
- [docs/FIGURE_LINKS_FIX.md](./docs/FIGURE_LINKS_FIX.md) - Figure link fix explanation
- [docs/QUICK_START.md](./docs/QUICK_START.md) - Quick start guide
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - Project structure
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Contributing guide
- [CHANGELOG.md](./CHANGELOG.md) - Changelog

## 🛠️ Utility Scripts

- `batch_read_deepxiv_with_pdf.py` - Main program
- `regenerate_card_with_figures.py` - Regenerate single paper
- `batch_regenerate_cards.py` - Batch regenerate all papers
- `fix_figure_links.py` - Alternative solution using vision API

## 🤝 Contributing

Issues and Pull Requests are welcome!

## 📄 License

MIT License

## 🙏 Acknowledgments

- [DeepXiv](https://deepxiv.com) - Paper search and parsing API
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing library
- [OpenAI](https://openai.com) - LLM API

## ⚠️ Important Notes

1. **API Costs**: Using OpenAI API incurs costs, control `LIMIT` and `MAX_WORKERS` carefully
2. **Figure Numbering**: Auto-extracted figure numbers may not perfectly match paper numbering
3. **Network Requirements**: Stable internet connection required for arXiv and API access
4. **Storage Space**: PDFs and figures consume storage, periodically clean `outputs/` directory

## 📮 Contact

For questions or suggestions, please submit an Issue or contact the author.
