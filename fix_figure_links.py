"""
Fix figure links in generated markdown files by:
1. Analyzing extracted figures with vision API to identify their captions
2. Matching extracted figures to paper figure numbers
3. Inserting figure links with detailed explanations into section 7
"""

import os
import json
import base64
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)

OUT_DIR = Path("outputs")
CARD_DIR = OUT_DIR / "cards"
DEEP_DIR = OUT_DIR / "deep_notes"
FIGURES_DIR = OUT_DIR / "figures"


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def identify_figure_caption(image_path: Path) -> dict:
    """Use vision API to identify figure caption and number."""
    base64_image = encode_image(image_path)

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": """请分析这张图片，识别：
1. 图片编号（如 Figure 1, Fig. 2, 图1等）
2. 图片标题/caption的完整文本
3. 这张图的主要内容是什么（用一句话概括）

请以JSON格式返回：
{
    "figure_number": "识别到的图号，如 '1', '2', '3'等，如果无法识别返回null",
    "caption": "完整的caption文本",
    "description": "图片主要内容的一句话描述"
}"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=0.1
    )

    try:
        result = json.loads(response.choices[0].message.content)
        return result
    except:
        return {
            "figure_number": None,
            "caption": "",
            "description": ""
        }


def analyze_figure_with_context(image_path: Path, material: dict) -> str:
    """Use vision API to analyze figure in context of the paper."""
    base64_image = encode_image(image_path)

    # Extract paper context
    paper_title = material.get("head", {}).get("title", "")
    paper_abstract = material.get("head", {}).get("abstract", "")

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": "你是一位资深研究员，擅长分析论文图表。"
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": f"""论文标题：{paper_title}

论文摘要：{paper_abstract[:500]}

请详细分析这张图：
1. 这张图展示了什么内容？
2. 这张图如何支撑论文的核心观点或方法？
3. 从这张图能看出论文的novelty吗？
4. 这张图的逻辑是否严密？有没有明显的问题？

请用中文回答，每个问题2-3句话。"""
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        temperature=0.2
    )

    return response.choices[0].message.content


def process_figures_for_paper(arxiv_id: str, material: dict) -> list:
    """Process all figures for a paper and return figure info with analysis."""
    figures_subdir = FIGURES_DIR / arxiv_id.replace("/", "_")

    if not figures_subdir.exists():
        print(f"[No figures] {arxiv_id}")
        return []

    figure_files = sorted(figures_subdir.glob("*.png"))

    if not figure_files:
        print(f"[No figure files] {arxiv_id}")
        return []

    print(f"[Processing {len(figure_files)} figures] {arxiv_id}")

    figures_info = []
    for fig_path in figure_files:
        print(f"  [Analyzing] {fig_path.name}")

        # Identify caption
        caption_info = identify_figure_caption(fig_path)

        # Analyze in context
        analysis = analyze_figure_with_context(fig_path, material)

        figures_info.append({
            "path": fig_path,
            "filename": fig_path.name,
            "figure_number": caption_info.get("figure_number"),
            "caption": caption_info.get("caption", ""),
            "description": caption_info.get("description", ""),
            "analysis": analysis
        })

    return figures_info


def insert_figures_into_section7(card_content: str, figures_info: list, base_dir: Path) -> str:
    """Insert figure links and analysis into section 7."""

    # Find section 7
    lines = card_content.split("\n")
    section7_start = -1
    section8_start = -1

    for i, line in enumerate(lines):
        if line.startswith("## 7. 最值得看的图/表/实验"):
            section7_start = i
        elif section7_start > 0 and line.startswith("## 8."):
            section8_start = i
            break

    if section7_start == -1:
        print("[Warning] Section 7 not found")
        return card_content

    # Build new section 7 content
    new_section7 = [lines[section7_start]]
    new_section7.append("")

    for fig_info in figures_info:
        rel_path = fig_info["path"].relative_to(base_dir.parent)
        fig_num = fig_info["figure_number"] or "?"

        new_section7.append(f"### Figure {fig_num}")
        new_section7.append("")
        new_section7.append(f"![Figure {fig_num}]({rel_path})")
        new_section7.append("")

        if fig_info["caption"]:
            new_section7.append(f"**Caption**: {fig_info['caption']}")
            new_section7.append("")

        new_section7.append(f"**分析**：")
        new_section7.append("")
        new_section7.append(fig_info["analysis"])
        new_section7.append("")

    # Reconstruct content
    if section8_start > 0:
        new_lines = lines[:section7_start] + new_section7 + lines[section8_start:]
    else:
        new_lines = lines[:section7_start] + new_section7

    return "\n".join(new_lines)


def fix_card(card_path: Path, arxiv_id: str, material: dict):
    """Fix a single card file."""
    print(f"\n[Fixing card] {card_path.name}")

    # Process figures
    figures_info = process_figures_for_paper(arxiv_id, material)

    if not figures_info:
        print(f"[Skip] No figures to process")
        return

    # Read card
    card_content = card_path.read_text(encoding="utf-8")

    # Insert figures into section 7
    new_content = insert_figures_into_section7(card_content, figures_info, CARD_DIR)

    # Save
    card_path.write_text(new_content, encoding="utf-8")
    print(f"[Updated] {card_path}")


def fix_deep_note(note_path: Path, arxiv_id: str, material: dict):
    """Fix a single deep note file."""
    print(f"\n[Fixing deep note] {note_path.name}")

    # Process figures
    figures_info = process_figures_for_paper(arxiv_id, material)

    if not figures_info:
        print(f"[Skip] No figures to process")
        return

    # Read note
    note_content = note_path.read_text(encoding="utf-8")

    # Append figures at the end with analysis
    figures_section = ["\n\n## 论文关键图表详解\n"]

    for fig_info in figures_info:
        rel_path = fig_info["path"].relative_to(DEEP_DIR.parent)
        fig_num = fig_info["figure_number"] or "?"

        figures_section.append(f"\n### Figure {fig_num}\n")
        figures_section.append(f"\n![Figure {fig_num}]({rel_path})\n")

        if fig_info["caption"]:
            figures_section.append(f"\n**Caption**: {fig_info['caption']}\n")

        figures_section.append(f"\n**详细分析**：\n")
        figures_section.append(f"\n{fig_info['analysis']}\n")

    new_content = note_content + "\n".join(figures_section)

    # Save
    note_path.write_text(new_content, encoding="utf-8")
    print(f"[Updated] {note_path}")


def main():
    import sys

    if len(sys.argv) < 2:
        print("Usage: python fix_figure_links.py <arxiv_id>")
        print("Example: python fix_figure_links.py 2602.08145")
        sys.exit(1)

    arxiv_id = sys.argv[1]

    # Load material
    from batch_read_deepxiv_with_pdf import safe_filename, LOG_DIR
    material_path = LOG_DIR / f"{safe_filename(arxiv_id)}_material.json"

    if not material_path.exists():
        print(f"[Error] Material not found: {material_path}")
        sys.exit(1)

    material = json.loads(material_path.read_text(encoding="utf-8"))

    # Find card and note files
    card_files = list(CARD_DIR.glob(f"{safe_filename(arxiv_id)}*.md"))
    note_files = list(DEEP_DIR.glob(f"{safe_filename(arxiv_id)}*.md"))

    if not card_files and not note_files:
        print(f"[Error] No card or note files found for {arxiv_id}")
        sys.exit(1)

    # Fix card
    if card_files:
        fix_card(card_files[0], arxiv_id, material)

    # Fix deep note
    if note_files:
        fix_deep_note(note_files[0], arxiv_id, material)

    print("\n[Done]")


if __name__ == "__main__":
    main()
