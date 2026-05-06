"""Figure analyzer for detailed figure interpretation."""

import json
from pathlib import Path
from typing import List, Dict, Optional
from core.api_client import OpenAIClient
from core.logger import get_logger
from core.utils import fix_latex_formulas

logger = get_logger(__name__)


class FigureAnalyzer:
    """Generate detailed analysis for each figure."""

    def __init__(self, openai_client: OpenAIClient, analysis_dir: Path):
        self.client = openai_client
        self.analysis_dir = analysis_dir
        self.analysis_dir.mkdir(parents=True, exist_ok=True)

    def analyze_figures(
        self,
        figures: List[Dict],
        contexts: Dict[str, List[Dict]],
        paper_title: str,
        arxiv_id: str
    ) -> str:
        """
        Analyze all figures with their contexts.

        Args:
            figures: List of figure dictionaries with path, caption, label
            contexts: Dictionary mapping labels to context lists
            paper_title: Paper title
            arxiv_id: arXiv paper ID

        Returns:
            Generated analysis content
        """
        if not figures:
            logger.warning("No figures to analyze")
            return ""

        # Build analysis prompt
        figures_info = []
        for fig in figures:
            label = fig.get('label', '')
            caption = fig.get('caption', '')

            # Get contexts for this figure
            fig_contexts = contexts.get(label, []) if label else []

            context_text = ""
            if fig_contexts:
                context_text = "\n引用上下文：\n"
                for idx, ctx in enumerate(fig_contexts[:3], 1):  # Max 3 contexts
                    context_text += f"{idx}. {ctx['text']}\n"

            figures_info.append({
                'index': fig.get('index', 0),
                'caption': caption[:200] if caption else "无caption",
                'label': label,
                'contexts': context_text or "未找到引用"
            })

        prompt = f"""
分析论文中的图表，理解作者意图。

论文标题：{paper_title}
arXiv ID：{arxiv_id}

对每张图表，分析：
1. 图表展示的内容
2. 作者通过这张图想说明什么
3. 这张图在论文中的作用

# 图表分析

{json.dumps(figures_info, ensure_ascii=False, indent=2)}

输出格式（每张图）：

## Figure X: [简短标题]

### 图表内容
描述图表展示了什么（2-3句话）

### 作者意图
作者放这张图的目的，想说明什么问题（2-3句话）

### 论文中的作用
这张图如何支撑论文的核心观点（1-2句话）

### 上下文分析
基于引用上下文，说明图表在论文逻辑中的位置
"""

        logger.info(f"Analyzing {len(figures)} figures")
        analysis_content = self.client.call_llm(prompt)
        logger.debug(f"Analysis generated, length: {len(analysis_content)}")

        # Beautify markdown
        analysis_content = fix_latex_formulas(analysis_content)

        # Add header and figure images
        header = f"# 图表分析：{paper_title}\n\n"
        header += f"**arXiv ID**: {arxiv_id}\n\n"
        header += "---\n\n"

        # Insert figure images
        final_content = header + analysis_content

        return final_content

    def save(self, content: str, arxiv_id: str, title: str) -> Path:
        """
        Save analysis to file.

        Args:
            content: Analysis content
            arxiv_id: arXiv paper ID
            title: Paper title

        Returns:
            Path to saved analysis file
        """
        from core.file_utils import safe_filename

        analysis_path = self.analysis_dir / f"{safe_filename(arxiv_id)}_{safe_filename(title)}_figures.md"
        analysis_path.write_text(content, encoding="utf-8")
        logger.info(f"Figure analysis saved: {analysis_path.name}")

        return analysis_path
