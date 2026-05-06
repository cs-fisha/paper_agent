# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-05-06

### Added
- 🎉 Initial release
- 🔍 Automatic paper search from arXiv via DeepXiv API
- 📄 Automatic PDF download
- 🖼️ Intelligent figure extraction from PDFs (with captions)
- 📝 Dual-layer note generation:
  - 10min Paper Card for quick overview
  - 30min Deep Note for in-depth analysis
- 🎯 Detailed figure analysis in Section 7:
  - What the figure shows
  - How it demonstrates novelty
  - Logical rigor assessment
  - Comprehension percentage
- ⚡ Fully parallelized Card and Deep Note generation (70% faster)
- 📊 Automatic survey report generation for batch processing
- 🛠️ Utility scripts:
  - `regenerate_card_with_figures.py` - Regenerate single paper
  - `batch_regenerate_cards.py` - Batch regenerate all papers
  - `fix_figure_links.py` - Alternative solution using vision API
- 📚 Comprehensive documentation:
  - Chinese and English README
  - Parallel optimization guide
  - Figure link fix explanation
  - Quick start guide
  - Contributing guide
  - Project structure documentation

### Features
- Smart column layout detection (single/double column)
- Figure region detection with caption matching
- Material caching to avoid redundant API calls
- Configurable parallel processing (MAX_WORKERS)
- Flexible output control (GENERATE_DEEP_NOTE flag)
- Support for multiple arXiv categories

### Performance
- 70% faster processing with parallel Card + Deep Note generation
- 5 papers: 13 min → 4 min
- 20 papers: 50 min → 15 min

### Documentation
- Detailed environment variable explanations
- Step-by-step installation guide
- Usage examples and best practices
- Performance benchmarks
- Troubleshooting tips

## [Unreleased]

### Planned
- [ ] Vision API integration for direct figure analysis
- [ ] Improved figure numbering accuracy
- [ ] Table extraction support
- [ ] Image quality checking
- [ ] Smart figure matching with OCR
- [ ] Multi-language support for generated notes
- [ ] Web UI for easier interaction
- [ ] Docker support for easy deployment

---

[1.0.0]: https://github.com/yourusername/paper_agent/releases/tag/v1.0.0
