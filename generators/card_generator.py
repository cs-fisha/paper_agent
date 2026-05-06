"""Card generator for 10-minute paper summaries."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.markdown_beautifier import MarkdownBeautifier

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
        logger.info("Generating 10-minute card")
        card_content = self.client.call_llm(prompt)
        logger.debug(f"Card generated, length: {len(card_content)}")

        # Beautify markdown
        card_content = MarkdownBeautifier.beautify(card_content)
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
