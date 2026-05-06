"""Report generator for survey reports."""

import json
from pathlib import Path
from typing import List
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.utils import fix_latex_formulas

logger = get_logger(__name__)


class ReportGenerator:
    """Generate survey reports from multiple papers."""

    def __init__(self, openai_client: OpenAIClient, report_dir: Path):
        self.client = openai_client
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, materials: List[dict], query: str) -> str:
        """
        Generate a survey report.

        Args:
            materials: List of paper material dictionaries
            query: Search query

        Returns:
            Generated report content
        """
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
基于论文材料生成调研报告（中文 Markdown）。

搜索查询：{query}
论文数量：{len(materials)}

# 调研报告：{query}

## 1. 整体概览
论文总数、主要方向分布、时间跨度

## 2. 核心技术趋势
列出3-5个主要技术方向：代表论文、核心思路、优缺点

## 3. 重点论文推荐
按优先级列出最值得读的3-5篇，说明理由

## 4. 方法对比与差异
对比关键维度差异（数据、模型、训练、评估）

## 5. 研究空白与机会
可能的研究空白或改进方向

## 6. 对我的科研方向的启发
结合 {query} 的研究视角

论文摘要：
{json.dumps(summaries, ensure_ascii=False, indent=2)[:80000]}

完整材料（供参考）：
{json.dumps(materials, ensure_ascii=False, indent=2)[:200000]}
"""
        logger.info(f"Generating survey report for query: {query}")
        report_content = self.client.call_llm(prompt)
        logger.debug(f"Report generated, length: {len(report_content)}")

        # Beautify markdown
        report_content = fix_latex_formulas(report_content)
        logger.debug("Report content beautified")

        return report_content

    def save(self, content: str, query: str, timestamp: str) -> Path:
        """
        Save report to file.

        Args:
            content: Report content
            query: Search query
            timestamp: Timestamp string

        Returns:
            Path to saved report file
        """
        from core.file_utils import safe_filename

        report_subdir = self.report_dir / f"{safe_filename(query)}_{timestamp}"
        report_subdir.mkdir(parents=True, exist_ok=True)

        report_path = report_subdir / "survey_report.md"
        report_path.write_text(content, encoding="utf-8")
        logger.info(f"Report saved: {report_path}")

        return report_path
