"""LaTeX source processing utilities."""

import re
import shutil
import tarfile
import requests
import fitz
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from core.logger import get_logger
from core.retry import retry_on_exception

logger = get_logger(__name__)


class LaTeXProcessor:
    """Handle LaTeX source download and figure extraction."""

    @staticmethod
    @retry_on_exception(max_attempts=3, delay=2.0, exceptions=(requests.RequestException,))
    def download_latex_source(arxiv_id: str, output_dir: Path) -> Optional[Path]:
        """
        Download LaTeX source from arXiv.

        Args:
            arxiv_id: arXiv paper ID
            output_dir: Directory to save source

        Returns:
            Path to extracted source directory or None if failed
        """
        from core.file_utils import safe_filename

        source_url = f"https://arxiv.org/e-print/{arxiv_id}"
        source_dir = output_dir / safe_filename(arxiv_id)

        if source_dir.exists() and any(source_dir.iterdir()):
            logger.info(f"LaTeX source already exists: {source_dir.name}")
            return source_dir

        source_dir.mkdir(parents=True, exist_ok=True)

        try:
            logger.info(f"Downloading LaTeX source: {arxiv_id}")
            response = requests.get(source_url, timeout=30)
            response.raise_for_status()

            tar_path = source_dir / "source.tar.gz"
            tar_path.write_bytes(response.content)

            try:
                with tarfile.open(tar_path, 'r:gz') as tar:
                    tar.extractall(source_dir)
                tar_path.unlink()
                logger.info(f"LaTeX source extracted: {source_dir.name}")
                return source_dir
            except tarfile.ReadError:
                # Not a tar file, might be a single .tex file
                tex_path = source_dir / "main.tex"
                tex_path.write_bytes(response.content)
                logger.info(f"LaTeX source saved as single file: {tex_path.name}")
                return source_dir

        except Exception as e:
            logger.error(f"Error downloading LaTeX source for {arxiv_id}: {e}")
            return None

    @staticmethod
    def extract_figures_from_latex(
        latex_dir: Path,
        arxiv_id: str,
        output_dir: Path,
        max_figures: int = 8
    ) -> List[Dict]:
        """
        Extract figures from LaTeX source.

        Args:
            latex_dir: Directory containing LaTeX source
            arxiv_id: arXiv paper ID
            output_dir: Directory to save figures
            max_figures: Maximum number of figures to extract

        Returns:
            List of extracted figure dictionaries
        """
        from core.file_utils import safe_filename

        if not latex_dir or not latex_dir.exists():
            logger.warning(f"LaTeX directory not found: {latex_dir}")
            return []

        figures_subdir = output_dir / safe_filename(arxiv_id)
        figures_subdir.mkdir(parents=True, exist_ok=True)

        extracted_figures = []

        try:
            tex_files = list(latex_dir.rglob("*.tex"))
            if not tex_files:
                logger.warning(f"No .tex files found in {latex_dir}")
                return []

            logger.info(f"Processing {len(tex_files)} .tex files")

            # Patterns to match LaTeX figure commands
            include_pattern = re.compile(r'\\includegraphics(?:\[.*?\])?\{([^}]+)\}')
            figure_pattern = re.compile(
                r'\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}',
                re.DOTALL
            )

            figure_info = []

            for tex_file in tex_files:
                try:
                    content = tex_file.read_text(encoding='utf-8', errors='ignore')

                    for fig_match in figure_pattern.finditer(content):
                        fig_content = fig_match.group(1)

                        img_match = include_pattern.search(fig_content)
                        if not img_match:
                            continue

                        img_filename = img_match.group(1).strip()

                        caption_match = re.search(r'\\caption\{(.*?)\}', fig_content, re.DOTALL)
                        caption = caption_match.group(1) if caption_match else ""

                        label_match = re.search(r'\\label\{(.*?)\}', fig_content)
                        label = label_match.group(1) if label_match else ""

                        figure_info.append({
                            'filename': img_filename,
                            'caption': caption,
                            'label': label,
                            'tex_file': tex_file.name
                        })

                except Exception as e:
                    logger.error(f"Error reading {tex_file.name}: {e}")
                    continue

            logger.info(f"Found {len(figure_info)} figure references in LaTeX")

            # Find actual image files
            figure_count = 0
            for idx, fig in enumerate(figure_info):
                if figure_count >= max_figures:
                    break

                img_filename = fig['filename']
                possible_extensions = ['', '.pdf', '.png', '.jpg', '.jpeg', '.eps', '.PDF', '.PNG', '.JPG']
                img_path = None

                for ext in possible_extensions:
                    search_name = img_filename if img_filename.endswith(tuple(possible_extensions[1:])) else img_filename + ext
                    matches = list(latex_dir.rglob(search_name))
                    if matches:
                        img_path = matches[0]
                        break

                if not img_path or not img_path.exists():
                    logger.debug(f"Image not found: {img_filename}")
                    continue

                try:
                    output_filename = f"fig_{figure_count + 1}.png"
                    output_path = figures_subdir / output_filename

                    if img_path.suffix.lower() in ['.png', '.jpg', '.jpeg']:
                        shutil.copy2(img_path, output_path)
                    elif img_path.suffix.lower() == '.pdf':
                        # Convert PDF to PNG
                        doc = fitz.open(img_path)
                        page = doc[0]
                        mat = fitz.Matrix(2.0, 2.0)
                        pix = page.get_pixmap(matrix=mat)
                        pix.save(str(output_path))
                        doc.close()
                    else:
                        logger.warning(f"Unsupported format: {img_path.suffix}")
                        continue

                    extracted_figures.append({
                        'path': output_path,
                        'index': figure_count + 1,
                        'caption': fig['caption'][:200] if fig['caption'] else "",
                        'label': fig['label'],
                        'source_file': img_path.name
                    })

                    logger.info(f"Extracted {output_filename} from {img_path.name}")
                    figure_count += 1

                except Exception as e:
                    logger.error(f"Error converting {img_path.name}: {e}")
                    continue

            logger.info(f"Extracted {len(extracted_figures)} figures from LaTeX for {arxiv_id}")

        except Exception as e:
            logger.error(f"Error processing LaTeX for {arxiv_id}: {e}")
            import traceback
            traceback.print_exc()

        return extracted_figures

    @staticmethod
    def extract_figure_contexts(
        latex_dir: Path,
        figure_labels: List[str]
    ) -> Dict[str, List[Dict]]:
        """
        Extract contexts where figures are referenced in LaTeX source.

        Args:
            latex_dir: Directory containing LaTeX source
            figure_labels: List of figure labels (e.g., ['fig:overview', 'fig:results'])

        Returns:
            Dictionary mapping label to list of context dictionaries
        """
        if not latex_dir or not latex_dir.exists():
            logger.warning(f"LaTeX directory not found: {latex_dir}")
            return {}

        contexts = {label: [] for label in figure_labels}

        try:
            tex_files = list(latex_dir.rglob("*.tex"))
            if not tex_files:
                return contexts

            # Patterns for figure references
            ref_patterns = [
                re.compile(r'\\ref\{(' + '|'.join(re.escape(l) for l in figure_labels) + r')\}'),
                re.compile(r'Figure~?\\ref\{(' + '|'.join(re.escape(l) for l in figure_labels) + r')\}', re.IGNORECASE),
                re.compile(r'Fig\.?~?\\ref\{(' + '|'.join(re.escape(l) for l in figure_labels) + r')\}', re.IGNORECASE),
            ]

            for tex_file in tex_files:
                try:
                    content = tex_file.read_text(encoding='utf-8', errors='ignore')

                    # Remove comments
                    content = re.sub(r'(?<!\\)%.*$', '', content, flags=re.MULTILINE)

                    # Split into sentences (simple approach)
                    sentences = re.split(r'(?<=[.!?])\s+', content)

                    for i, sentence in enumerate(sentences):
                        for pattern in ref_patterns:
                            matches = pattern.finditer(sentence)
                            for match in matches:
                                label = match.group(1)
                                if label in contexts:
                                    # Extract context: 2 sentences before and after
                                    start_idx = max(0, i - 2)
                                    end_idx = min(len(sentences), i + 3)
                                    context_text = ' '.join(sentences[start_idx:end_idx])

                                    # Clean up LaTeX commands for readability
                                    context_text = re.sub(r'\\cite\{[^}]+\}', '[citation]', context_text)
                                    context_text = re.sub(r'\\[a-zA-Z]+\{([^}]+)\}', r'\1', context_text)
                                    context_text = re.sub(r'\\[a-zA-Z]+', '', context_text)
                                    context_text = re.sub(r'\s+', ' ', context_text).strip()

                                    if len(context_text) > 50:  # Meaningful context
                                        contexts[label].append({
                                            'text': context_text,
                                            'file': tex_file.name,
                                            'sentence_index': i
                                        })

                except Exception as e:
                    logger.error(f"Error reading {tex_file.name}: {e}")
                    continue

            # Log results
            for label, ctx_list in contexts.items():
                logger.info(f"Found {len(ctx_list)} contexts for {label}")

        except Exception as e:
            logger.error(f"Error extracting figure contexts: {e}")
            import traceback
            traceback.print_exc()

        return contexts
