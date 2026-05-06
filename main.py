"""Main entry point for paper_agent with improved architecture."""

import time
import shutil
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from core.config import Config
from core.logger import setup_logger, get_logger
from core.api_client import OpenAIClient, DeepXivClient
from core.paper_processor import PaperProcessor
from core.file_utils import safe_filename
from generators.card_generator import CardGenerator
from generators.note_generator import NoteGenerator
from generators.report_generator import ReportGenerator
from generators.figure_analyzer import FigureAnalyzer


def main():
    """Main execution function."""
    # Load configuration
    try:
        config = Config.from_env()
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
        return

    # Setup logging
    log_file = Path("logs") / "paper_agent.log"
    setup_logger(log_file=log_file)
    logger = get_logger(__name__)

    logger.info("=" * 80)
    logger.info("Paper Agent Started")
    logger.info("=" * 80)
    logger.info(f"Search query: {config.search.query}")
    logger.info(f"Limit: {config.search.limit}")
    logger.info(f"Date from: {config.search.date_from}")
    logger.info(f"Categories: {config.search.categories}")
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
    deepxiv_client = DeepXivClient(config.deepxiv)

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

    # Search papers
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
    import json
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    papers = results.get("result", [])
    logger.info(f"Found {len(papers)} papers")

    if not papers:
        logger.warning("No papers found. Exiting.")
        return

    # Process papers in parallel
    logger.info("Processing papers in parallel...")
    processed_results = []

    with ThreadPoolExecutor(max_workers=config.processing.max_workers) as executor:
        futures = {
            executor.submit(
                processor.process,
                paper,
                config.search.query,
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
        report_content = report_gen.generate(materials, config.search.query)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = report_gen.save(report_content, config.search.query, timestamp)

        # Copy materials to report directory
        report_subdir = report_path.parent
        materials_dir = report_subdir / "materials"
        materials_dir.mkdir(exist_ok=True)

        for r in processed_results:
            arxiv_id = r["arxiv_id"]
            src_material = log_dir / f"{safe_filename(arxiv_id)}_material.json"
            dst_material = materials_dir / f"{safe_filename(arxiv_id)}_material.json"

            if src_material.exists():
                shutil.copy2(src_material, dst_material)

        logger.info(f"Copied {len(processed_results)} material files to {materials_dir}")

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
