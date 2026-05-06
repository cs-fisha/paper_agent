"""Note generator for 30-minute deep reading notes."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.markdown_beautifier import MarkdownBeautifier

logger = get_logger(__name__)


class NoteGenerator:
    """Generate 30-minute deep reading notes."""

    def __init__(self, openai_client: OpenAIClient, note_dir: Path):
        self.client = openai_client
        self.note_dir = note_dir
        self.note_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        material: dict,
        query: str = "",
        figures: Optional[List[Dict]] = None,
        pdf_path: Optional[Path] = None
    ) -> str:
        """
        Generate a 30-minute deep reading note.

        Args:
            material: Paper material dictionary
            query: Search query for context
            figures: List of extracted figures
            pdf_path: Path to PDF file

        Returns:
            Generated note content
        """
        figures_info = ""
        if figures:
            figures_info = "\n\n## 论文关键图表详解\n\n"
            figures_info += "> **提示**：以下是从论文中提取的关键图表，结合正文理解效果更佳。\n\n"
            for fig in figures:
                rel_path = Path(fig["path"]).relative_to(self.note_dir.parent)
                figures_info += f"### Figure {fig['index']}\n\n"
                figures_info += f"![Figure {fig['index']}](../{rel_path})\n\n"
                if fig.get('caption'):
                    figures_info += f"**Caption**: {fig['caption']}\n\n"
                figures_info += "---\n\n"

        pdf_info = ""
        if pdf_path and pdf_path.exists():
            rel_pdf_path = pdf_path.relative_to(self.note_dir.parent)
            pdf_info = f"\n\n## PDF 文件\n\n[查看完整 PDF](../{rel_pdf_path})\n\n"

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
        logger.info("Generating 30-minute deep note")
        note_content = self.client.call_llm(prompt)
        logger.debug(f"Note generated, length: {len(note_content)}")

        # Beautify markdown
        note_content = MarkdownBeautifier.beautify(note_content)
        logger.debug("Note content beautified")

        # Append PDF link and figures
        if pdf_info:
            note_content += pdf_info
        if figures_info:
            note_content += figures_info

        return note_content

    def save(self, content: str, arxiv_id: str, title: str) -> Path:
        """
        Save note to file.

        Args:
            content: Note content
            arxiv_id: arXiv paper ID
            title: Paper title

        Returns:
            Path to saved note file
        """
        from core.file_utils import safe_filename

        note_path = self.note_dir / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"
        note_path.write_text(content, encoding="utf-8")
        logger.info(f"Note saved: {note_path.name}")

        return note_path
