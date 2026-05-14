"""Note generator for 30-minute deep reading notes."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.utils import fix_latex_formulas

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
基于论文材料生成 30 分钟深度阅读笔记（中文 Markdown）。

要求：区分"论文明确内容"和"推断/评价"，指出实验是否支撑claim，材料缺失不编造。{f"以我的研究方向为评判视角：{query}。" if query else ""}

# 30min Deep Reading Note

## 1. 论文主张与真实贡献
## 2. 方法细节拆解
## 3. 训练数据/标注方式
## 4. 模型结构或pipeline
## 5. 实验结果是否可信
## 6. Ablation/Analysis是否充分
## 7. 最值得看的图/表 ⭐
详细分析关键图表：展示内容、如何支撑观点、逻辑严密性、明显问题
## 8. Hidden weakness
## 9. 和我的方向的关系
说明相关性、可迁移部分、不能直接借鉴的边界，以及能如何启发新论文选题。
## 10. 可复现性判断
## 11. Follow方向
- 最小复现实验
- 改进点
- 论文切入点

论文材料：
{json.dumps(material, ensure_ascii=False, indent=2)[:160000]}
"""
        logger.info("Generating 30-minute deep note")
        note_content = self.client.call_llm(prompt)
        logger.debug(f"Note generated, length: {len(note_content)}")

        # Beautify markdown
        note_content = fix_latex_formulas(note_content)
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
