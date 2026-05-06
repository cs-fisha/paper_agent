"""Card generator for 10-minute paper summaries."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.utils import fix_latex_formulas

logger = get_logger(__name__)


class CardGenerator:
    """Generate 10-minute paper cards."""

    def __init__(self, openai_client: OpenAIClient, card_dir: Path):
        self.client = openai_client
        self.card_dir = card_dir
        self.card_dir.mkdir(parents=True, exist_ok=True)

    def generate(
        self,
        material: dict,
        query: str = "",
        figures: Optional[List[Dict]] = None
    ) -> str:
        """
        Generate a 10-minute paper card.

        Args:
            material: Paper material dictionary
            query: Search query for context
            figures: List of extracted figures

        Returns:
            Generated card content
        """
        figures_for_section7 = ""
        if figures:
            figures_for_section7 = "\n\n**论文提取的图片**（请在分析时引用这些图片）：\n"
            for fig in figures:
                rel_path = Path(fig["path"]).relative_to(self.card_dir.parent)
                figures_for_section7 += f"- Figure {fig['index']}: 图片路径 `../{rel_path}`\n"

        prompt = f"""
基于论文材料生成 10 分钟阅读笔记（中文 Markdown）。

要求：基于 Introduction/Method/Experiments，不编造，材料不足时说明。{f"重点关注 {query}。" if query else ""}

# 10min Paper Card

## 1. 一句话结论
## 2. 论文想解决的问题
## 3. 核心方法
## 4. 和已有工作的主要区别
## 5. 实验设置
- 数据集、Baseline、指标
## 6. 关键结果
## 7. 最值得看的图/表 ⭐

对每个关键图表：

### Figure X

![Figure X](图片路径)

**说明**：描述图的内容
**创新点**：如何支撑核心贡献
**严密性**：设计是否合理
**可理解度**：约X%

{figures_for_section7}

## 8. 可能的问题或漏洞
## 9. 对我的方向是否有用（A/B/C/D + 原因）
## 10. 30分钟优先读哪些部分

论文材料：
{json.dumps(material, ensure_ascii=False, indent=2)[:120000]}
"""
        logger.info("Generating 10-minute card")
        card_content = self.client.call_llm(prompt)
        logger.debug(f"Card generated, length: {len(card_content)}")

        # Beautify markdown
        card_content = fix_latex_formulas(card_content)
        logger.debug("Card content beautified")

        return card_content

    def save(self, content: str, arxiv_id: str, title: str) -> Path:
        """
        Save card to file.

        Args:
            content: Card content
            arxiv_id: arXiv paper ID
            title: Paper title

        Returns:
            Path to saved card file
        """
        from core.file_utils import safe_filename

        card_path = self.card_dir / f"{safe_filename(arxiv_id)}_{safe_filename(title)}.md"
        card_path.write_text(content, encoding="utf-8")
        logger.info(f"Card saved: {card_path.name}")

        return card_path
