"""PDF processing utilities."""

import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Optional
from core.logger import get_logger
from core.retry import retry_on_exception
import requests

logger = get_logger(__name__)


class PDFProcessor:
    """Handle PDF download and processing."""

    @staticmethod
    @retry_on_exception(max_attempts=3, delay=2.0, exceptions=(requests.RequestException,))
    def download_pdf(arxiv_id: str, output_dir: Path) -> Optional[Path]:
        """
        Download PDF from arXiv.

        Args:
            arxiv_id: arXiv paper ID
            output_dir: Directory to save PDF

        Returns:
            Path to downloaded PDF or None if failed
        """
        from core.file_utils import safe_filename

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        pdf_path = output_dir / f"{safe_filename(arxiv_id)}.pdf"

        if pdf_path.exists():
            logger.info(f"PDF already exists: {pdf_path.name}")
            return pdf_path

        logger.info(f"Downloading PDF: {arxiv_id}")
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        pdf_path.write_bytes(response.content)
        logger.info(f"PDF saved: {pdf_path.name}")
        return pdf_path

    @staticmethod
    def detect_column_layout(page) -> str:
        """
        Detect if page is single or double column.

        Args:
            page: PyMuPDF page object

        Returns:
            'single', 'double', or 'unknown'
        """
        try:
            text_blocks = page.get_text("dict")["blocks"]
            text_rects = []

            for block in text_blocks:
                if block.get("type") == 0:  # Text block
                    bbox = block["bbox"]
                    page_height = page.rect.height
                    # Filter out headers/footers
                    if bbox[1] > page_height * 0.1 and bbox[3] < page_height * 0.9:
                        text_rects.append(bbox)

            if not text_rects:
                return "unknown"

            page_width = page.rect.width
            left_blocks = sum(1 for r in text_rects if r[2] < page_width * 0.55)
            right_blocks = sum(1 for r in text_rects if r[0] > page_width * 0.45)

            if left_blocks > 3 and right_blocks > 3:
                return "double"
            else:
                return "single"
        except Exception as e:
            logger.warning(f"Error detecting column layout: {e}")
            return "unknown"

    @staticmethod
    def find_figure_regions(page, column_layout: str) -> List[Dict]:
        """
        Find figure regions including captions.

        Args:
            page: PyMuPDF page object
            column_layout: Layout type ('single', 'double', 'unknown')

        Returns:
            List of figure region dictionaries
        """
        page_width = page.rect.width
        page_height = page.rect.height

        # Get all image blocks
        image_blocks = []
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") == 1:  # Image block
                image_blocks.append(block["bbox"])

        if not image_blocks:
            return []

        text_blocks = page.get_text("dict")["blocks"]
        figure_regions = []

        for img_bbox in image_blocks:
            x0, y0, x1, y1 = img_bbox
            img_width = x1 - x0
            img_height = y1 - y0

            # Filter out very small images
            if img_width < page_width * 0.15 or img_height < page_height * 0.08:
                continue

            is_full_width = img_width > page_width * 0.7

            if column_layout == "double" and not is_full_width:
                if img_width < page_width * 0.35:
                    continue

            # Look for caption below the image
            caption_bbox = None
            caption_search_area = (x0 - 20, y1, x1 + 20, min(y1 + 100, page_height))

            for block in text_blocks:
                if block.get("type") == 0:  # Text block
                    bbox = block["bbox"]
                    if (bbox[1] >= caption_search_area[1] and
                        bbox[3] <= caption_search_area[3] and
                        bbox[0] >= caption_search_area[0] - 50 and
                        bbox[2] <= caption_search_area[2] + 50):

                        text = block.get("lines", [])
                        block_text = ""
                        for line in text:
                            for span in line.get("spans", []):
                                block_text += span.get("text", "")

                        if "Figure" in block_text or "Fig" in block_text or "图" in block_text:
                            if caption_bbox is None:
                                caption_bbox = list(bbox)
                            else:
                                caption_bbox[1] = min(caption_bbox[1], bbox[1])
                                caption_bbox[3] = max(caption_bbox[3], bbox[3])

            # Create final region
            if caption_bbox:
                final_bbox = (
                    min(x0, caption_bbox[0]) - 5,
                    y0 - 5,
                    max(x1, caption_bbox[2]) + 5,
                    caption_bbox[3] + 5
                )
            else:
                final_bbox = (x0 - 5, y0 - 5, x1 + 5, y1 + 5)

            figure_regions.append({
                "bbox": final_bbox,
                "has_caption": caption_bbox is not None,
                "is_full_width": is_full_width,
                "size": (img_width, img_height)
            })

        return figure_regions

    @classmethod
    def extract_figures_from_pdf(
        cls,
        pdf_path: Path,
        arxiv_id: str,
        output_dir: Path,
        max_figures: int = 5
    ) -> List[Dict]:
        """
        Extract figures from PDF by rendering page regions.

        Args:
            pdf_path: Path to PDF file
            arxiv_id: arXiv paper ID
            output_dir: Directory to save figures
            max_figures: Maximum number of figures to extract

        Returns:
            List of extracted figure dictionaries
        """
        from core.file_utils import safe_filename

        if not pdf_path or not pdf_path.exists():
            logger.warning(f"PDF not found: {pdf_path}")
            return []

        figures_subdir = output_dir / safe_filename(arxiv_id)
        figures_subdir.mkdir(parents=True, exist_ok=True)

        extracted_figures = []

        try:
            doc = fitz.open(pdf_path)
            logger.info(f"Extracting figures from {pdf_path.name} ({len(doc)} pages)")

            figure_count = 0
            for page_num in range(min(len(doc), 10)):  # First 10 pages
                if figure_count >= max_figures:
                    break

                page = doc[page_num]
                column_layout = cls.detect_column_layout(page)
                logger.debug(f"Page {page_num + 1} layout: {column_layout}")

                figure_regions = cls.find_figure_regions(page, column_layout)

                for region in figure_regions:
                    if figure_count >= max_figures:
                        break

                    try:
                        bbox = region["bbox"]
                        mat = fitz.Matrix(2.0, 2.0)  # 2x zoom
                        pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(bbox))

                        fig_filename = f"fig_{figure_count + 1}_page{page_num + 1}.png"
                        fig_path = figures_subdir / fig_filename
                        pix.save(str(fig_path))

                        extracted_figures.append({
                            "path": fig_path,
                            "page": page_num + 1,
                            "size": (int(region["size"][0]), int(region["size"][1])),
                            "index": figure_count + 1,
                            "has_caption": region["has_caption"],
                            "is_full_width": region["is_full_width"]
                        })

                        caption_info = "with caption" if region["has_caption"] else "no caption"
                        width_info = "full-width" if region["is_full_width"] else "partial-width"
                        logger.info(f"Extracted {fig_filename} ({width_info}, {caption_info})")
                        figure_count += 1

                    except Exception as e:
                        logger.error(f"Error extracting figure from page {page_num}: {e}")
                        continue

            doc.close()
            logger.info(f"Extracted {len(extracted_figures)} figures from {arxiv_id}")

        except Exception as e:
            logger.error(f"Error processing PDF {arxiv_id}: {e}")
            import traceback
            traceback.print_exc()

        return extracted_figures
