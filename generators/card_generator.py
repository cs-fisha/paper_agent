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
        prompt = f"""
基于论文材料生成 10 分钟阅读笔记（中文 Markdown）。

要求：基于 Introduction/Method/Experiments，不编造，材料不足时说明。{f"重点关注 {query}。" if query else ""}

输出格式如下（严格按照此结构）：

# 10min Paper Card：{{论文标题}}

论文：**{{论文标题}}**
arXiv: **{{arxiv_id}}**
关键词：{{从材料中提取 3-6 个核心关键词，用 " / " 分隔}}
类型：**{{判断论文类型：Research / Survey / Benchmark / Position Paper / Workshop Paper 等}}**
{{如果 venue/journal_name 不为空且不是 "arXiv.org"，输出：发表：**{{venue/journal_name}}**（这表示被顶会/期刊录用，务必标注）}}
{{如果论文材料中提到了 GitHub 开源链接或代码仓库地址，输出：代码：**{{GitHub URL}}**}}

---

## 1. 一句话结论
## 2. 论文想解决的问题
## 3. 核心方法
## 4. 和已有工作的主要区别
## 5. 实验设置
- 数据集、Baseline、指标
## 6. 关键结果
## 7. 可能的问题或漏洞
## 8. 对我的方向是否有用（A/B/C/D + 原因）
## 9. 30分钟优先读哪些部分

注意事项：
- 元数据头部必须放在最前面，紧跟标题之后
- venue/journal_name 字段在 material["head"] 中，如果有值且不是 "arXiv.org"，说明论文已被顶会/期刊录用，一定要标出
- GitHub 链接可能出现在 abstract、introduction 或 conclusion 中，如果找到请标注
- 关键词应反映论文的核心技术贡献，不要照搬搜索 query

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
