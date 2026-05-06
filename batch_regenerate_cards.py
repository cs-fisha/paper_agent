"""
Batch regenerate all cards with proper figure links.
"""

import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from regenerate_card_with_figures import regenerate_card
from batch_read_deepxiv_with_pdf import CARD_DIR, safe_filename

def extract_arxiv_id_from_filename(filename: str) -> str:
    """Extract arxiv_id from card filename."""
    # Format: arxiv_id_title.md
    parts = filename.split("_")
    if len(parts) >= 1:
        # arxiv_id is usually like 2602.08145
        arxiv_id = parts[0]
        return arxiv_id
    return None


def main():
    max_workers = int(os.environ.get("MAX_WORKERS", "4"))

    # Find all card files
    card_files = list(CARD_DIR.glob("*.md"))
    print(f"[Found {len(card_files)} card files]")

    arxiv_ids = []
    for card_file in card_files:
        arxiv_id = extract_arxiv_id_from_filename(card_file.stem)
        if arxiv_id:
            arxiv_ids.append(arxiv_id)

    print(f"[Extracted {len(arxiv_ids)} arxiv IDs]")

    # Regenerate in parallel
    success_count = 0
    failed_count = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(regenerate_card, arxiv_id): arxiv_id
            for arxiv_id in arxiv_ids
        }

        for future in as_completed(futures):
            arxiv_id = futures[future]
            try:
                success = future.result()
                if success:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                print(f"[Error] {arxiv_id}: {e}")
                failed_count += 1

    print(f"\n[Done] Success: {success_count}, Failed: {failed_count}")


if __name__ == "__main__":
    main()
