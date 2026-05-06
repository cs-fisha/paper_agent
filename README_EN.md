# Paper Agent

English | [简体中文](./README.md)

An intelligent paper reading assistant powered by LLM that automatically searches, downloads, extracts figures, and generates structured notes.

## ✨ Core Features

- 🔍 **Smart Search**: Search arXiv papers via DeepXiv API
- 📄 **Auto Download**: PDF + LaTeX source
- 🖼️ **Figure Extraction**: LaTeX source first (high quality) → PDF fallback
- 📝 **Dual-layer Notes**:
  - **10min Card**: Quick overview
  - **30min Deep Note**: In-depth analysis
- 🎯 **Figure Analysis**: Detailed interpretation of each figure
- ⚡ **Parallel Processing**: 70% performance boost
- 📊 **Survey Report**: Auto-generated after batch processing

## 📦 Quick Start

### 1. Installation

```bash
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent
pip install -r requirements.txt
```

### 2. Configuration

Copy `.env.example` to `.env` and fill in:

```bash
# OpenAI API
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# DeepXiv API
DEEPXIV_TOKEN=your_token

# Search Config
QUERY="multimodal LVLM MLLM"
LIMIT=5
DATE_FROM=2025-01-01
CATEGORIES=cs.CV,cs.CL

# Processing Config
MAX_WORKERS=8
DOWNLOAD_PDF=true
EXTRACT_FIGURES=true
GENERATE_DEEP_NOTE=true
```

### 3. Run

```bash
python main.py
```

## 📁 Output Structure

```
outputs/
├── cards/              # 10min Paper Cards
├── deep_notes/         # 30min Deep Notes
├── pdfs/              # PDF files
├── figures/           # Extracted figures
│   └── {arxiv_id}/
├── latex_sources/     # LaTeX sources
└── reports/           # Survey reports
    └── {query}_{timestamp}/
```

## 📝 Output Format

### 10min Card

- One-sentence conclusion
- Core problem & method
- Experiment setup & results
- **Key figures/tables** ⭐ (with detailed analysis)
- Potential issues
- Usefulness rating (A/B/C/D)
- Reading suggestions

### 30min Deep Note

- Claims vs. real contributions
- Method details breakdown
- Training data / model structure
- Experiment credibility
- Ablation sufficiency
- **Key figures/tables** ⭐
- Hidden weaknesses
- Reproducibility assessment
- Follow-up suggestions

## ⚡ Performance

| Papers | Before | After | Improvement |
|--------|--------|-------|-------------|
| 5      | 13 min | 4 min | **69% ⬇️** |
| 20     | 50 min | 15 min | **70% ⬇️** |

## 🏗️ Project Structure

```
paper_agent/
├── core/              # Core modules
│   ├── api_client.py
│   ├── config.py
│   ├── paper_processor.py
│   ├── pdf_processor.py
│   ├── latex_processor.py
│   └── ...
├── generators/        # Generators
│   ├── card_generator.py
│   ├── note_generator.py
│   └── report_generator.py
├── tests/            # Unit tests
└── main.py           # Main entry
```

## 🧪 Testing

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## 📄 License

MIT License

## 🙏 Acknowledgments

- [DeepXiv](https://deepxiv.com) - Paper search and parsing API
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF processing
- [OpenAI](https://openai.com) - LLM API

## ⚠️ Notes

1. **API Costs**: Using OpenAI API incurs costs
2. **Network**: Requires stable internet connection
3. **Storage**: PDFs and figures consume storage space
