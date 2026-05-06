"""
Regenerate a paper card with proper figure links in section 7.
"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Import from the main script
from batch_read_deepxiv_with_pdf import (
    make_10min_card,
    make_30min_note,
    safe_filename,
    CARD_DIR,
    DEEP_DIR,
    FIGURES_DIR,
    LOG_DIR,
    PDF_DIR
)

load_dotenv()


def regenerate_card(arxiv_id: str):
    """Regenerate card with proper figure links."""
    print(f"\n[Regenerating card] {arxiv_id}")

    # Load material
    material_path = LOG_DIR / f"{safe_filename(arxiv_id)}_material.json"
    if not material_path.exists():
        print(f"[Error] Material not found: {material_path}")
        return False

    material = json.loads(material_path.read_text(encoding="utf-8"))

    # Find figures
    figures_subdir = FIGURES_DIR / safe_filename(arxiv_id)
    figures = []

    if figures_subdir.exists():
        figure_files = sorted(figures_subdir.glob("*.png"))
        for idx, fig_path in enumerate(figure_files, 1):
            # Extract page number from filename (e.g., fig_1_page2.png)
            parts = fig_path.stem.split("_")
            page_num = int(parts[-1].replace("page", "")) if len(parts) > 2 else 1

            figures.append({
                "path": fig_path,
                "page": page_num,
                "index": idx,
                "size": (0, 0)  # Not needed for card
            })
        print(f"[Found {len(figures)} figures]")
    else:
        print(f"[No figures found]")

    # Find PDF
    pdf_path = PDF_DIR / f"{safe_filename(arxiv_id)}.pdf"
    if not pdf_path.exists():
        pdf_path = None

    # Get query from environment or use default
    query = os.environ.get("QUERY", "multimodal LVLM MLLM")

    # Regenerate card
    print(f"[Generating card...]")
    card_content = make_10min_card(material, query, figures)

    # Find existing card file
    card_files = list(CARD_DIR.glob(f"{safe_filename(arxiv_id)}*.md"))

    if card_files:
        card_path = card_files[0]
    else:
        # Create new filename
        title = material.get("head", {}).get("title", "unknown_title")
        card_path = CARD_DIR / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"

    card_path.write_text(card_content, encoding="utf-8")
    print(f"[Saved card] {card_path}")

    # Regenerate deep note
    print(f"[Generating deep note...]")
    note_content = make_30min_note(material, query, figures, pdf_path)

    note_files = list(DEEP_DIR.glob(f"{safe_filename(arxiv_id)}*.md"))

    if note_files:
        note_path = note_files[0]
    else:
        title = material.get("head", {}).get("title", "unknown_title")
        note_path = DEEP_DIR / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"

    note_path.write_text(note_content, encoding="utf-8")
    print(f"[Saved deep note] {note_path}")

    return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python regenerate_card_with_figures.py <arxiv_id>")
        print("Example: python regenerate_card_with_figures.py 2602.08145")
        sys.exit(1)

    arxiv_id = sys.argv[1]

    success = regenerate_card(arxiv_id)

    if success:
        print("\n[Done] Card and deep note regenerated with figure links")
    else:
        print("\n[Failed] Could not regenerate card")
        sys.exit(1)


if __name__ == "__main__":
    main()
