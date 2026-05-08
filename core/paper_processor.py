"""Paper processor for handling individual papers."""

import json
import shutil
from pathlib import Path
from typing import Dict, Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from core.api_client import DeepXivClient
from core.pdf_processor import PDFProcessor
from core.latex_processor import LaTeXProcessor
from core.logger import get_logger
from core.file_utils import safe_filename
from generators.card_generator import CardGenerator
from generators.note_generator import NoteGenerator
from generators.figure_analyzer import FigureAnalyzer

logger = get_logger(__name__)


class PaperProcessor:
    """Process individual papers: fetch, extract, generate."""

    def __init__(
        self,
        deepxiv_client: DeepXivClient,
        card_generator: CardGenerator,
        note_generator: NoteGenerator,
        figure_analyzer: Optional[FigureAnalyzer],
        pdf_dir: Path,
        figures_dir: Path,
        latex_dir: Path,
        log_dir: Path,
    ):
        self.deepxiv = deepxiv_client
        self.card_gen = card_generator
        self.note_gen = note_generator
        self.figure_analyzer = figure_analyzer
        self.pdf_dir = pdf_dir
        self.figures_dir = figures_dir
        self.latex_dir = latex_dir
        self.log_dir = log_dir

        # Create directories
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.figures_dir.mkdir(parents=True, exist_ok=True)
        self.latex_dir.mkdir(parents=True, exist_ok=True)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def get_paper_material(self, arxiv_id: str) -> dict:
        """
        Fetch paper material with progressive reading.

        Args:
            arxiv_id: arXiv paper ID

        Returns:
            Paper material dictionary
        """
        material_path = self.log_dir / f"{safe_filename(arxiv_id)}_material.json"

        # Check cache
        if material_path.exists():
            logger.info(f"Loading cached material: {arxiv_id}")
            try:
                return json.loads(material_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Cache read error for {arxiv_id}: {e}, re-fetching...")

        material = {"arxiv_id": arxiv_id}

        # Fetch brief
        try:
            material["brief"] = self.deepxiv.brief(arxiv_id)
        except Exception as e:
            material["brief_error"] = str(e)
            logger.error(f"Error fetching brief for {arxiv_id}: {e}")

        # Fetch head
        try:
            material["head"] = self.deepxiv.head(arxiv_id)
        except Exception as e:
            material["head_error"] = str(e)
            logger.error(f"Error fetching head for {arxiv_id}: {e}")

        # Fetch important sections
        available_sections = []
        if "head" in material and isinstance(material["head"], dict):
            sections_list = material["head"].get("sections", [])
            available_sections = [
                s["name"] for s in sections_list
                if isinstance(s, dict) and "name" in s
            ]

        priority_keywords = [
            ("intro", ["Introduction"]),
            ("related", ["Related Work", "Background"]),
            ("method", ["Method", "Methods", "Methodology", "Approach", "Proposed Method"]),
            ("experiment", ["Experiments", "Results", "Evaluation", "Experimental Results"]),
            ("conclusion", ["Conclusion", "Conclusions", "Discussion"]),
            ("limitation", ["Limitations", "Future Work"]),
        ]

        sections_to_fetch = []
        for _, keywords in priority_keywords:
            for keyword in keywords:
                for avail in available_sections:
                    if keyword.lower() in avail.lower() or avail.lower() in keyword.lower():
                        if avail not in sections_to_fetch:
                            sections_to_fetch.append(avail)
                        break

        sections = {}
        for sec in sections_to_fetch:
            try:
                content = self.deepxiv.section(arxiv_id, sec)
                if content:
                    sections[sec] = content
            except Exception as e:
                logger.warning(f"Error fetching section '{sec}' for {arxiv_id}: {e}")

        material["sections"] = sections

        # Save to cache
        material_path.write_text(
            json.dumps(material, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        logger.info(f"Material cached: {arxiv_id}")

        return material

    def process(
        self,
        paper_info: dict,
        query: str = "",
        download_pdf: bool = True,
        extract_figures: bool = True,
        generate_deep_note: bool = True,
        use_latex_source: bool = True,
        analyze_figures: bool = True,
    ) -> Optional[Dict]:
        """
        Process a single paper.

        Args:
            paper_info: Paper information dictionary
            query: Search query for context
            download_pdf: Whether to download PDF
            extract_figures: Whether to extract figures
            generate_deep_note: Whether to generate deep note
            use_latex_source: Whether to use LaTeX source for figures

        Returns:
            Processing result dictionary or None if failed
        """
        arxiv_id = paper_info.get("arxiv_id") or paper_info.get("id")
        title = paper_info.get("title", "unknown_title")

        if not arxiv_id:
            logger.warning(f"No arxiv_id found for paper: {title}")
            return None

        logger.info(f"Processing paper: {arxiv_id} | {title}")

        try:
            # Fetch material
            material = self.get_paper_material(arxiv_id)

            # Download PDF
            pdf_path = None
            if download_pdf:
                pdf_path = PDFProcessor.download_pdf(arxiv_id, self.pdf_dir)

            # Extract figures
            figures = []
            latex_dir = None
            if extract_figures:
                if use_latex_source:
                    logger.info(f"Trying LaTeX source extraction: {arxiv_id}")
                    latex_dir = LaTeXProcessor.download_latex_source(arxiv_id, self.latex_dir)
                    if latex_dir:
                        figures = LaTeXProcessor.extract_figures_from_latex(
                            latex_dir, arxiv_id, self.figures_dir, max_figures=8
                        )

                    # Fallback to PDF
                    if not figures and pdf_path:
                        logger.info(f"LaTeX extraction failed, falling back to PDF: {arxiv_id}")
                        figures = PDFProcessor.extract_figures_from_pdf(
                            pdf_path, arxiv_id, self.figures_dir, max_figures=5
                        )
                elif pdf_path:
                    figures = PDFProcessor.extract_figures_from_pdf(
                        pdf_path, arxiv_id, self.figures_dir, max_figures=5
                    )

            # Parallel generation of Card, Figure Analysis, and Deep Note
            logger.info(f"Generating notes in parallel: {arxiv_id}")

            card_path = None
            analysis_path = None
            note_path = None

            with ThreadPoolExecutor(max_workers=3) as executor:
                futures = {}

                # Submit card generation
                futures['card'] = executor.submit(
                    self._generate_card, material, query, figures, arxiv_id, title
                )

                # Submit figure analysis if applicable
                if analyze_figures and figures and latex_dir and self.figure_analyzer:
                    futures['analysis'] = executor.submit(
                        self._generate_figure_analysis,
                        figures, latex_dir, title, arxiv_id
                    )

                # Submit deep note if applicable
                if generate_deep_note:
                    futures['note'] = executor.submit(
                        self._generate_deep_note,
                        material, query, figures, pdf_path, arxiv_id, title
                    )

                # Collect results
                for name, future in futures.items():
                    try:
                        result = future.result()
                        if name == 'card':
                            card_path = result
                        elif name == 'analysis':
                            analysis_path = result
                        elif name == 'note':
                            note_path = result
                    except Exception as e:
                        logger.error(f"Error generating {name} for {arxiv_id}: {e}")

            # Append figure analysis to card
            if card_path:
                self._append_figure_analysis_to_card(card_path, analysis_path)

            return {
                "arxiv_id": arxiv_id,
                "title": title,
                "material": material,
                "card_path": card_path,
                "note_path": note_path,
                "pdf_path": pdf_path,
                "figures": figures,
                "analysis_path": analysis_path,
            }

        except Exception as e:
            logger.error(f"Error processing {arxiv_id}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _generate_card(self, material, query, figures, arxiv_id, title) -> Path:
        """Generate card in parallel."""
        logger.info(f"Generating 10min card: {arxiv_id}")
        card_content = self.card_gen.generate(material, query, figures)
        return self.card_gen.save(card_content, arxiv_id, title)

    def _generate_figure_analysis(self, figures, latex_dir, title, arxiv_id) -> Path:
        """Generate figure analysis in parallel."""
        logger.info(f"Generating figure analysis: {arxiv_id}")
        # Extract figure labels
        figure_labels = [fig.get('label', '') for fig in figures if fig.get('label')]

        # Extract contexts
        contexts = {}
        if figure_labels:
            contexts = LaTeXProcessor.extract_figure_contexts(latex_dir, figure_labels)

        # Generate analysis
        analysis_content = self.figure_analyzer.analyze_figures(
            figures, contexts, title, arxiv_id
        )
        return self.figure_analyzer.save(analysis_content, arxiv_id, title)

    def _generate_deep_note(self, material, query, figures, pdf_path, arxiv_id, title) -> Path:
        """Generate deep note in parallel."""
        logger.info(f"Generating 30min deep note: {arxiv_id}")
        note_content = self.note_gen.generate(material, query, figures, pdf_path)
        return self.note_gen.save(note_content, arxiv_id, title)

    def _append_figure_analysis_to_card(self, card_path: Path, analysis_path: Optional[Path]):
        """Append figure analysis content to the end of the card file."""
        import re

        card_content = card_path.read_text(encoding="utf-8")

        if not analysis_path or not analysis_path.exists():
            card_content += "\n\n---\n\n> 图表深度分析未生成（缺少 LaTeX 源码或未提取到图表）。\n"
            card_path.write_text(card_content, encoding="utf-8")
            return

        analysis_content = analysis_path.read_text(encoding="utf-8")

        # Strip the standalone header (title, arxiv id, separator)
        analysis_body = re.sub(
            r'^# 图表分析：.*?\n\n\*\*arXiv ID\*\*:.*?\n\n---\n\n',
            '',
            analysis_content,
            flags=re.DOTALL
        )

        card_content += "\n\n---\n\n## 图表深度分析\n\n"
        card_content += analysis_body.strip() + "\n"
        card_path.write_text(card_content, encoding="utf-8")
        logger.info(f"Figure analysis appended to card: {card_path.name}")
