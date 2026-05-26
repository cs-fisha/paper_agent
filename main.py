"""Main entry point for paper_agent with improved architecture."""

import argparse
import json
import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from core.config import Config
from core.logger import setup_logger, get_logger
from core.api_client import OpenAIClient, DeepXivClient
from core.arxiv_html_fetcher import ArxivHTMLFetcher
from core.arxiv_ids import load_arxiv_ids_file
from core.paper_processor import PaperProcessor
from core.file_utils import safe_filename
from generators.card_generator import CardGenerator
from generators.note_generator import NoteGenerator
from generators.report_generator import ReportGenerator
from generators.figure_analyzer import FigureAnalyzer


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Process arXiv papers and generate reading reports.")
    parser.add_argument(
        "--ids-file",
        type=Path,
        help="Text file containing arXiv IDs or arXiv abs/pdf URLs to process.",
    )
    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()

    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        return

    ids_file = args.ids_file or config.search.arxiv_ids_file
    if ids_file and not ids_file.exists():
        print(f"Configuration error: arXiv IDs file does not exist: {ids_file}")
        return
    research_focus = config.research.focus or config.search.query

    # Setup logging
    log_file = Path("logs") / "paper_agent.log"
    setup_logger(log_file=log_file)
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("Paper Agent Started")
    logger.info("=" * 80)
    if ids_file:
        logger.info(f"Input mode: arXiv IDs file ({ids_file})")
    else:
        logger.info("Input mode: keyword search")
        logger.info(f"Search query: {config.search.query}")
        logger.info(f"Limit: {config.search.limit}")
        logger.info(f"Date from: {config.search.date_from}")
        logger.info(f"Categories: {config.search.categories}")
    logger.info(f"Research focus: {research_focus}")
    logger.info(f"Max workers: {config.processing.max_workers}")
    logger.info(f"Download PDF: {config.processing.download_pdf}")
    logger.info(f"Extract figures: {config.processing.extract_figures}")
    logger.info(f"Generate deep note: {config.processing.generate_deep_note}")
    logger.info(f"Use LaTeX source: {config.processing.use_latex_source}")
    logger.info(f"Analyze figures: {config.processing.analyze_figures}")

    # Setup directories
    out_dir = Path("outputs")
    card_dir = out_dir / "cards"
    deep_dir = out_dir / "deep_notes"
    report_dir = out_dir / "reports"
    analysis_dir = out_dir / "figure_analysis"
    pdf_dir = out_dir / "pdfs"
    figures_dir = out_dir / "figures"
    latex_dir = out_dir / "latex_sources"
    log_dir = Path("logs")

    # Initialize clients
    openai_client = OpenAIClient(config.openai)
    arxiv_fallback = ArxivHTMLFetcher()
    deepxiv_client = DeepXivClient(config.deepxiv, fallback=arxiv_fallback)

    # Initialize generators
    card_gen = CardGenerator(openai_client, card_dir)
    note_gen = NoteGenerator(openai_client, deep_dir)
    report_gen = ReportGenerator(openai_client, report_dir)
    figure_analyzer = FigureAnalyzer(openai_client, analysis_dir) if config.processing.analyze_figures else None

    # Initialize processor
    processor = PaperProcessor(
        deepxiv_client=deepxiv_client,
        card_generator=card_gen,
        note_generator=note_gen,
        figure_analyzer=figure_analyzer,
        pdf_dir=pdf_dir,
        figures_dir=figures_dir,
        latex_dir=latex_dir,
        log_dir=log_dir,
    )

    # Load papers from either an explicit arXiv ID file or keyword search.
    if ids_file:
        logger.info("Loading arXiv IDs from file...")
        arxiv_ids = load_arxiv_ids_file(ids_file)
        input_label = f"ids_{ids_file.stem}"
        report_context = research_focus
        papers = [{"arxiv_id": arxiv_id, "title": arxiv_id} for arxiv_id in arxiv_ids]

        log_path = log_dir / f"ids_{safe_filename(ids_file.stem)}.json"
        log_path.write_text(
            json.dumps({"source_file": str(ids_file), "result": papers}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Loaded {len(papers)} arXiv IDs")
    else:
        logger.info("Searching papers...")
        results = deepxiv_client.search(
            query=config.search.query,
            source="arxiv",
            size=config.search.limit,
            categories=config.search.categories,
            date_search_type="after",
            date_str=config.search.date_from,
        )

        # Save search results
        log_path = log_dir / f"search_{safe_filename(config.search.query)}.json"
        log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

        papers = results.get("result", [])
        input_label = config.search.query
        report_context = research_focus
        logger.info(f"Found {len(papers)} papers")

    if not papers:
        logger.warning("No papers found or loaded. Exiting.")
        return

    # Process papers in parallel
    logger.info("Processing papers in parallel...")
    processed_results = []

    with ThreadPoolExecutor(max_workers=config.processing.max_workers) as executor:
        futures = {
            executor.submit(
                processor.process,
                paper,
                research_focus,
                config.processing.download_pdf,
                config.processing.extract_figures,
                config.processing.generate_deep_note,
                config.processing.use_latex_source,
                config.processing.analyze_figures,
            ): paper
            for paper in papers
        }

        # Use tqdm for progress bar
        with tqdm(total=len(papers), desc="Processing papers") as pbar:
            for future in as_completed(futures):
                result = future.result()
                if result:
                    processed_results.append(result)
                pbar.update(1)

    logger.info(f"Successfully processed {len(processed_results)}/{len(papers)} papers")

    # Generate survey report
    if processed_results:
        logger.info("Generating survey report...")
        materials = [r["material"] for r in processed_results]
        report_content = report_gen.generate(materials, report_context)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = report_gen.save(report_content, input_label, timestamp)

        # Copy materials and cards to report directory
        report_subdir = report_path.parent
        materials_dir = report_subdir / "materials"
        cards_subdir = report_subdir / "cards"
        materials_dir.mkdir(exist_ok=True)
        cards_subdir.mkdir(exist_ok=True)

        for r in processed_results:
            arxiv_id = r["arxiv_id"]
            src_material = log_dir / f"{safe_filename(arxiv_id)}_material.json"
            dst_material = materials_dir / f"{safe_filename(arxiv_id)}_material.json"

            if src_material.exists():
                shutil.copy2(src_material, dst_material)

            # Copy card to query folder with fixed relative paths
            card_path = r.get("card_path")
            if card_path and Path(card_path).exists():
                card_content = Path(card_path).read_text(encoding="utf-8")
                card_content = card_content.replace("](../figures/", "](../../../figures/")
                (cards_subdir / Path(card_path).name).write_text(card_content, encoding="utf-8")

        logger.info(f"Copied {len(processed_results)} material files to {materials_dir}")
        logger.info(f"Copied cards to {cards_subdir}")

    # Summary
    logger.info("=" * 80)
    logger.info("Processing Complete")
    logger.info("=" * 80)
    logger.info(f"Processed: {len(processed_results)}/{len(papers)} papers")
    logger.info(f"Cards: {card_dir}")
    logger.info(f"Deep notes: {deep_dir}")
    if config.processing.analyze_figures:
        logger.info(f"Figure analysis: {analysis_dir}")
    logger.info(f"PDFs: {pdf_dir}")
    logger.info(f"Figures: {figures_dir}")
    logger.info(f"LaTeX sources: {latex_dir}")
    logger.info(f"Reports: {report_dir}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
