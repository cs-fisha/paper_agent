import os
import json
import time
import shutil
import requests
import fitz  # PyMuPDF
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image
from io import BytesIO

from dotenv import load_dotenv
from openai import OpenAI
from deepxiv_sdk import Reader

load_dotenv()

BASE_URL = os.getenv("OPENAI_BASE_URL")
API_KEY = os.getenv("OPENAI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")

if not BASE_URL or not API_KEY or not MODEL_NAME:
    raise RuntimeError("Please set OPENAI_BASE_URL, OPENAI_API_KEY, MODEL_NAME in .env")

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

reader = Reader(token=os.getenv("DEEPXIV_TOKEN"))

OUT_DIR = Path("outputs")
CARD_DIR = OUT_DIR / "cards"
DEEP_DIR = OUT_DIR / "deep_notes"
REPORT_DIR = OUT_DIR / "reports"
PDF_DIR = OUT_DIR / "pdfs"
FIGURES_DIR = OUT_DIR / "figures"
LOG_DIR = Path("logs")

CARD_DIR.mkdir(parents=True, exist_ok=True)
DEEP_DIR.mkdir(parents=True, exist_ok=True)
REPORT_DIR.mkdir(parents=True, exist_ok=True)
PDF_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


def call_llm(prompt: str, temperature: float = 0.2) -> str:
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a senior researcher in large language models and multimodal models. "
                    "You read papers critically, focusing on method novelty, experiments, limitations, "
                    "and reproducibility."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=temperature,
    )
    return resp.choices[0].message.content


def safe_filename(text: str) -> str:
    keep = []
    for ch in text:
        if ch.isalnum() or ch in "-_.":
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep)[:160]


def download_pdf(arxiv_id: str, output_dir: Path) -> Path:
    """Download PDF from arXiv."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    pdf_path = output_dir / f"{safe_filename(arxiv_id)}.pdf"

    if pdf_path.exists():
        print(f"[PDF exists] {pdf_path}")
        return pdf_path

    try:
        print(f"[Downloading PDF] {pdf_url}")
        response = requests.get(pdf_url, timeout=30)
        response.raise_for_status()

        pdf_path.write_bytes(response.content)
        print(f"[PDF saved] {pdf_path}")
        return pdf_path
    except Exception as e:
        print(f"[PDF download error] {arxiv_id}: {e}")
        return None


def detect_column_layout(page) -> str:
    """Detect if page is single or double column by analyzing text blocks."""
    try:
        text_blocks = page.get_text("dict")["blocks"]
        text_rects = []

        for block in text_blocks:
            if block.get("type") == 0:  # Text block
                bbox = block["bbox"]
                # Filter out headers/footers (top 10% and bottom 10%)
                page_height = page.rect.height
                if bbox[1] > page_height * 0.1 and bbox[3] < page_height * 0.9:
                    text_rects.append(bbox)

        if not text_rects:
            return "unknown"

        # Calculate average x-coordinates
        page_width = page.rect.width
        left_blocks = sum(1 for r in text_rects if r[2] < page_width * 0.55)  # Right edge in left half
        right_blocks = sum(1 for r in text_rects if r[0] > page_width * 0.45)  # Left edge in right half

        # If significant blocks on both sides, likely double column
        if left_blocks > 3 and right_blocks > 3:
            return "double"
        else:
            return "single"
    except:
        return "unknown"


def find_figure_regions(page, column_layout: str) -> list:
    """Find figure regions including captions by analyzing page layout."""
    page_width = page.rect.width
    page_height = page.rect.height

    # Get all image blocks
    image_blocks = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") == 1:  # Image block
            image_blocks.append(block["bbox"])

    if not image_blocks:
        return []

    # Get text blocks to find captions
    text_blocks = page.get_text("dict")["blocks"]

    figure_regions = []
    for img_bbox in image_blocks:
        x0, y0, x1, y1 = img_bbox
        img_width = x1 - x0
        img_height = y1 - y0

        # Filter out very small images (icons, logos)
        if img_width < page_width * 0.15 or img_height < page_height * 0.08:
            continue

        # Determine if this is a full-width figure
        is_full_width = img_width > page_width * 0.7

        # For double column layout, check if figure spans both columns
        if column_layout == "double" and not is_full_width:
            # Half-width figure in double column - might be part of a multi-part figure
            # Skip very narrow figures
            if img_width < page_width * 0.35:
                continue

        # Look for caption below the image (within 100 points)
        caption_bbox = None
        caption_search_area = (x0 - 20, y1, x1 + 20, min(y1 + 100, page_height))

        for block in text_blocks:
            if block.get("type") == 0:  # Text block
                bbox = block["bbox"]
                # Check if text block is in caption search area
                if (bbox[1] >= caption_search_area[1] and
                    bbox[3] <= caption_search_area[3] and
                    bbox[0] >= caption_search_area[0] - 50 and
                    bbox[2] <= caption_search_area[2] + 50):

                    # Check if it contains "Figure" or "Fig"
                    text = block.get("lines", [])
                    block_text = ""
                    for line in text:
                        for span in line.get("spans", []):
                            block_text += span.get("text", "")

                    if "Figure" in block_text or "Fig" in block_text or "图" in block_text:
                        if caption_bbox is None:
                            caption_bbox = list(bbox)
                        else:
                            # Extend caption bbox
                            caption_bbox[1] = min(caption_bbox[1], bbox[1])
                            caption_bbox[3] = max(caption_bbox[3], bbox[3])

        # Create final region including image and caption
        if caption_bbox:
            final_bbox = (
                min(x0, caption_bbox[0]) - 5,
                y0 - 5,
                max(x1, caption_bbox[2]) + 5,
                caption_bbox[3] + 5
            )
        else:
            # No caption found, just use image bbox with padding
            final_bbox = (x0 - 5, y0 - 5, x1 + 5, y1 + 5)

        figure_regions.append({
            "bbox": final_bbox,
            "has_caption": caption_bbox is not None,
            "is_full_width": is_full_width,
            "size": (img_width, img_height)
        })

    return figure_regions


def extract_figures_from_pdf(pdf_path: Path, arxiv_id: str, output_dir: Path, max_figures: int = 5) -> list:
    """Extract figures from PDF by rendering page regions (includes captions)."""
    if not pdf_path or not pdf_path.exists():
        return []

    figures_subdir = output_dir / safe_filename(arxiv_id)
    figures_subdir.mkdir(parents=True, exist_ok=True)

    extracted_figures = []

    try:
        doc = fitz.open(pdf_path)
        print(f"[Extracting figures] {pdf_path.name} ({len(doc)} pages)")

        figure_count = 0
        for page_num in range(min(len(doc), 10)):  # Only check first 10 pages
            if figure_count >= max_figures:
                break

            page = doc[page_num]

            # Detect column layout
            column_layout = detect_column_layout(page)
            print(f"[Page {page_num + 1}] Layout: {column_layout}")

            # Find figure regions
            figure_regions = find_figure_regions(page, column_layout)

            for region in figure_regions:
                if figure_count >= max_figures:
                    break

                try:
                    bbox = region["bbox"]

                    # Render this region at high resolution
                    mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better quality
                    pix = page.get_pixmap(matrix=mat, clip=fitz.Rect(bbox))

                    # Save as PNG
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
                    print(f"[Figure extracted] {fig_filename} ({width_info}, {caption_info})")
                    figure_count += 1

                except Exception as e:
                    print(f"[Figure extraction error] page {page_num}, region: {e}")
                    continue

        doc.close()
        print(f"[Extracted {len(extracted_figures)} figures] {arxiv_id}")

    except Exception as e:
        print(f"[PDF processing error] {arxiv_id}: {e}")
        import traceback
        traceback.print_exc()

    return extracted_figures


def get_paper_material(arxiv_id: str) -> dict:
    """
    Progressive reading:
    1. Check local cache first
    2. brief: quick judgement
    3. head: structure / sections
    4. important sections: Introduction / Method / Experiments / Conclusion
    """
    material_path = LOG_DIR / f"{safe_filename(arxiv_id)}_material.json"
    if material_path.exists():
        print(f"[Cache hit] {arxiv_id}")
        try:
            return json.loads(material_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[Cache read error] {arxiv_id}: {e}, re-fetching...")

    material = {"arxiv_id": arxiv_id}

    try:
        material["brief"] = reader.brief(arxiv_id)
    except Exception as e:
        material["brief_error"] = str(e)

    try:
        material["head"] = reader.head(arxiv_id)
    except Exception as e:
        material["head_error"] = str(e)

    available_sections = []
    if "head" in material and isinstance(material["head"], dict):
        sections_list = material["head"].get("sections", [])
        available_sections = [s["name"] for s in sections_list if isinstance(s, dict) and "name" in s]

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
            content = reader.section(arxiv_id, sec)
            if content:
                sections[sec] = content
        except Exception:
            pass

    material["sections"] = sections
    return material


def make_10min_card(material: dict, query: str = "", figures: list = None) -> str:
    # Build figure references for section 7
    figures_for_section7 = ""
    if figures:
        figures_for_section7 = "\n\n**论文提取的图片**（请在分析时引用这些图片）：\n"
        for fig in figures:
            rel_path = Path(fig["path"]).relative_to(CARD_DIR.parent)
            figures_for_section7 += f"- Figure {fig['index']} (Page {fig['page']}): 图片路径 `{rel_path}`\n"

    prompt = f"""
请基于下面的论文材料，生成一份适合我 10 分钟内读完的 paper card。

要求：
- 不要只复述 abstract，要尽可能利用 Introduction / Method / Experiments / Results 等信息。
- 假如材料不足，请明确写"材料不足"，不要编造。
- 用中文输出。
- 输出 Markdown。
{f"- 重点关注与 {query} 相关的内容。" if query else ""}
- **重点**：在"最值得看的图/表/实验"部分，必须插入图片链接并详细分析。

输出结构必须如下：

# 10min Paper Card

## 1. 一句话结论
## 2. 论文想解决的问题
## 3. 核心方法
## 4. 和已有工作的主要区别
## 5. 实验设置
- 数据集：
- Baseline：
- 指标：
## 6. 关键结果
## 7. 最值得看的图/表/实验 ⭐

**这是最重要的部分！** 对于每个关键图表，必须按以下格式输出：

### Figure X（图的标题）

![Figure X](图片路径)

**图片说明了什么**：
（2-3句话描述图的内容）

**如何体现论文创新**：
（2-3句话说明这个图如何支撑论文的核心贡献）

**逻辑严密性**：
（1-2句话评价图的设计是否合理、是否有明显问题）

**只看图能理解多少**：约X%（给出百分比并简要说明）

---

请至少分析2-3个最关键的图表。{figures_for_section7}

## 8. 可能的问题或漏洞
## 9. 对我的科研方向是否有用
给出 A/B/C/D 评级，并说明原因。
## 10. 如果只读 30 分钟，应该优先读哪些部分

论文材料如下：
{json.dumps(material, ensure_ascii=False, indent=2)[:120000]}
"""
    card_content = call_llm(prompt)

    return card_content


def make_30min_note(material: dict, query: str = "", figures: list = None, pdf_path: Path = None) -> str:
    figures_info = ""
    if figures:
        figures_info = "\n\n## 论文关键图表详解\n\n"
        figures_info += "> **提示**：以下是从论文中提取的关键图表，结合正文理解效果更佳。\n\n"
        for fig in figures:
            rel_path = Path(fig["path"]).relative_to(DEEP_DIR.parent)
            figures_info += f"### Figure {fig['index']} (Page {fig['page']})\n\n"
            figures_info += f"![Figure {fig['index']}]({rel_path})\n\n"
            figures_info += f"**位置**：第 {fig['page']} 页\n\n"
            figures_info += "---\n\n"

    pdf_info = ""
    if pdf_path and pdf_path.exists():
        rel_pdf_path = pdf_path.relative_to(DEEP_DIR.parent)
        pdf_info = f"\n\n## PDF 文件\n\n[查看完整 PDF]({rel_pdf_path})\n\n"

    prompt = f"""
请基于下面的论文材料，生成一份适合我 30 分钟内细读完的 deep reading note。

要求：
- 用中文输出，尽量浅显易懂。
- 必须区分"论文明确说的内容"和"你的推断/评价"。
- 必须指出实验是否足以支撑 claim。
- 如果材料缺失，不要编造。
{f"- 重点关注与 {query} 相关的内容。" if query else ""}

输出结构：

# 30min Deep Reading Note

## 1. 论文主张与真实贡献
## 2. 方法细节拆解
## 3. 训练数据 / 偏好数据 / 标注方式
## 4. 模型结构或 pipeline
## 5. 实验结果是否可信
## 6. Ablation / Analysis 是否充分
## 7. 最值得看的图/表/实验 ⭐

**重要**：请详细分析论文中的关键图表，对每个图表说明：
- 图表展示了什么内容
- 如何支撑论文观点
- 是否逻辑严密
- 是否有明显问题

## 8. 可能的 hidden weakness
## 9. 和我的方向的关系
## 10. 可复现性判断
## 11. 我如果要 follow，可以怎么做
- 最小复现实验：
- 可以改进的点：
- 可能能写成论文的切入点：

论文材料如下：
{json.dumps(material, ensure_ascii=False, indent=2)[:160000]}
"""
    note_content = call_llm(prompt)

    # Append PDF link and figures at the end
    if pdf_info:
        note_content += pdf_info
    if figures_info:
        note_content += figures_info

    return note_content


def make_survey_report(materials: list[dict], query: str) -> str:
    """Generate a survey report based on all processed papers."""
    summaries = []
    for mat in materials:
        arxiv_id = mat.get("arxiv_id", "unknown")
        head = mat.get("head", {})
        title = head.get("title", "unknown") if isinstance(head, dict) else "unknown"
        abstract = head.get("abstract", "") if isinstance(head, dict) else ""
        tldr = head.get("tldr", "") if isinstance(head, dict) else ""

        summaries.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "tldr": tldr,
        })

    prompt = f"""
你是一位资深的研究员。请基于下面这批论文的材料，生成一份调研报告。

搜索查询：{query}
论文数量：{len(materials)}

要求：
- 用中文输出
- 重点关注与 {query} 相关的内容
- 识别这批论文的共同趋势、技术路线、关键差异
- 指出哪些论文最值得深读，哪些可以略过
- 输出 Markdown 格式

输出结构：

# 调研报告：{query}

## 1. 整体概览
- 论文总数：
- 主要研究方向分布：
- 时间跨度：

## 2. 核心技术趋势
列出 3-5 个主要技术方向或方法类别，每个方向包括：
- 代表论文
- 核心思路
- 优缺点

## 3. 重点论文推荐
按优先级列出最值得读的 3-5 篇论文，说明推荐理由。

## 4. 方法对比与差异
对比不同论文在关键维度上的差异（数据、模型、训练方式、评估等）

## 5. 研究空白与机会
基于这批论文，指出可能的研究空白或改进方向

## 6. 对我的科研方向的启发
结合 {query} 的研究视角

论文摘要列表：
{json.dumps(summaries, ensure_ascii=False, indent=2)[:80000]}

完整材料（供参考）：
{json.dumps(materials, ensure_ascii=False, indent=2)[:200000]}
"""
    return call_llm(prompt, temperature=0.3)


def process_paper(paper_info: dict, total: int, index: int, query: str = "", download_pdf_flag: bool = True, extract_figures_flag: bool = True, generate_deep_note: bool = True) -> dict:
    """Process a single paper: fetch material, download PDF, extract figures, generate card and deep note."""
    arxiv_id = paper_info.get("arxiv_id") or paper_info.get("id")
    title = paper_info.get("title", "unknown_title")

    if not arxiv_id:
        print(f"[Skip] no arxiv_id: {title}")
        return None

    print(f"\n[{index}/{total}] {arxiv_id} | {title}")

    try:
        material = get_paper_material(arxiv_id)

        material_path = LOG_DIR / f"{safe_filename(arxiv_id)}_material.json"
        material_path.write_text(json.dumps(material, ensure_ascii=False, indent=2), encoding="utf-8")

        # Download PDF
        pdf_path = None
        if download_pdf_flag:
            pdf_path = download_pdf(arxiv_id, PDF_DIR)

        # Extract figures
        figures = []
        if extract_figures_flag and pdf_path:
            figures = extract_figures_from_pdf(pdf_path, arxiv_id, FIGURES_DIR, max_figures=5)

        # Generate card
        card = make_10min_card(material, query, figures)
        card_path = CARD_DIR / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"
        card_path.write_text(card, encoding="utf-8")
        print(f"[Saved card] {card_path}")

        # Generate deep note (in parallel with other papers)
        note_path = None
        if generate_deep_note:
            print(f"[Generating deep note] {arxiv_id}")
            note = make_30min_note(material, query, figures, pdf_path)
            note_path = DEEP_DIR / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"
            note_path.write_text(note, encoding="utf-8")
            print(f"[Saved deep note] {note_path}")

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "material": material,
            "card_path": card_path,
            "note_path": note_path,
            "pdf_path": pdf_path,
            "figures": figures,
        }
    except Exception as e:
        print(f"[Error] {arxiv_id}: {e}")
        import traceback
        traceback.print_exc()
        return None


def main():
    query = os.environ.get("QUERY", "multimodal LVLM MLLM")
    limit = int(os.environ.get("LIMIT", "5"))
    date_from = os.environ.get("DATE_FROM", "2025-06-01")
    categories = os.environ.get("CATEGORIES", "cs.CV,cs.CL").split(",")
    max_workers = int(os.environ.get("MAX_WORKERS", "8"))
    download_pdf_flag = os.environ.get("DOWNLOAD_PDF", "true").lower() == "true"
    extract_figures_flag = os.environ.get("EXTRACT_FIGURES", "true").lower() == "true"
    generate_deep_note_flag = os.environ.get("GENERATE_DEEP_NOTE", "true").lower() == "true"

    print(f"[Search] query={query}, limit={limit}, date_from={date_from}, categories={categories}")
    print(f"[Config] max_workers={max_workers}, download_pdf={download_pdf_flag}, extract_figures={extract_figures_flag}, generate_deep_note={generate_deep_note_flag}")

    results = reader.search(
        query,
        source="arxiv",
        size=limit,
        categories=categories,
        date_search_type="after",
        date_str=date_from,
    )

    log_path = LOG_DIR / f"search_{safe_filename(query)}.json"
    log_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")

    papers = results.get("result", [])
    print(f"[Search] got {len(papers)} papers")

    # Parallel processing - now includes deep note generation
    print(f"\n[Processing papers in parallel (card + deep note)]")
    processed_results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_paper, p, len(papers), i, query, download_pdf_flag, extract_figures_flag, generate_deep_note_flag): i
            for i, p in enumerate(papers, start=1)
        }

        for future in as_completed(futures):
            result = future.result()
            if result:
                processed_results.append(result)

    # Generate survey report
    if processed_results:
        print(f"\n[Generating survey report]")
        materials = [r["material"] for r in processed_results]
        report = make_survey_report(materials, query)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_subdir = REPORT_DIR / f"{safe_filename(query)}_{timestamp}"
        report_subdir.mkdir(parents=True, exist_ok=True)

        report_path = report_subdir / "survey_report.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"[Saved report] {report_path}")

        # Copy materials to report directory
        materials_dir = report_subdir / "materials"
        materials_dir.mkdir(exist_ok=True)

        for r in processed_results:
            arxiv_id = r["arxiv_id"]
            src_material = LOG_DIR / f"{safe_filename(arxiv_id)}_material.json"
            dst_material = materials_dir / f"{safe_filename(arxiv_id)}_material.json"

            if src_material.exists():
                shutil.copy2(src_material, dst_material)

        print(f"[Copied materials] {len(processed_results)} files to {materials_dir}")

    print(f"\n[Done] Processed {len(processed_results)}/{len(papers)} papers")
    print(f"[Output locations]")
    print(f"  - Cards: {CARD_DIR}")
    print(f"  - Deep notes: {DEEP_DIR}")
    print(f"  - PDFs: {PDF_DIR}")
    print(f"  - Figures: {FIGURES_DIR}")
    print(f"  - Reports: {REPORT_DIR}")


if __name__ == "__main__":
    main()
