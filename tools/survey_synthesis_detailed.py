"""Detailed survey synthesis for LVLM/MLLM papers — 20-30K character report.

Multi-phase parallel pipeline that avoids 524 timeouts by breaking the work
into many small LLM calls instead of one 200KB-prompt monolith.

Phases:
  1. Extract per-paper highlights (reuses survey_synthesis logic + cache)
  2. Cluster papers into themes via one LLM call
  3. Generate per-theme deep-dive sections in parallel
  4. Generate cross-cutting analysis (硬骨头 / 新颖工作 / 选题建议)
  5. Generate intro + outro
  6. Assemble locally (no final monolith LLM call)

Run:
    python tools/survey_synthesis_detailed.py \
        --cards-dir outputs/cards \
        --ids-file outputs/conference_search/combined_2026/papers_top.txt \
        --output outputs/reports/lvlm_mllm_detailed_briefing.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import random  # noqa: E402 (used for clustering shuffle)
import numpy as np  # noqa: E402
from sklearn.cluster import KMeans  # noqa: E402
from core.config import Config  # noqa: E402
from core.api_client import OpenAIClient  # noqa: E402
from core.logger import setup_logger, get_logger  # noqa: E402


# ─── Phase 1: Extraction ──────────────────────────────────────────────────────

EXTRACTION_SYSTEM = (
    "你是一位资深的多模态大模型方向研究综述员，擅长把一篇论文 Card 浓缩成"
    "可被聚合的结构化要点。只输出 JSON，不要寒暄、不要解释。"
)

EXTRACTION_PROMPT_TEMPLATE = """\
下面是一篇 2026 年顶会（ICLR/CVPR/ICML/ACL/AAAI 等）多模态视觉语言大模型相关论文的 10min Card（Markdown）。
请抽取结构化亮点，用于跨论文聚合分析。严格输出如下 JSON（不加 ```），字段都用中文：

{{
  "arxiv_id": "{arxiv_id}",
  "title": "<论文标题>",
  "venue": "<接收会议，如 CVPR2026>",
  "方向标签": ["最多 3 个，例如：视觉幻觉、Token压缩、视觉指令对齐、安全越狱、视频理解、视觉推理、Agent、3D视觉理解、评测基准、训练范式、多模态检索、文档理解 等"],
  "想解决的问题": "<一句话，关键>",
  "为什么难": "<一句话，论文揭示的难点>",
  "核心方法一句话": "<核心思路>",
  "关键发现或贡献": "<一句话，可量化最好>",
  "局限或未解决问题": "<论文自己承认或留下的问题>"
}}

只输出 JSON 对象本体。论文 Card 内容如下：

{card_text}
"""


# ─── Phase 2: Theme clustering ───────────────────────────────────────────────

CLUSTERING_SYSTEM = (
    "你是一位资深 AI 研究综述员，正在把一批论文聚类为可独立分析的研究主题。"
    "只输出 JSON。"
)

CLUSTERING_PROMPT = """\
下面是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文的结构化亮点摘要。
请将它们聚类为 **{theme_range}** 研究主题（cluster）。

聚类要求：
- 主题粒度适中：每个主题应该有 {per_theme_range} 篇论文。避免太粗（如"多模态"）或太细（如"某个具体数据集"）。
- 主题名简短（2-8 字中文）。
- 一篇论文应**主要分配到 1 个主题**，跨主题论文最多出现在 2 个主题里。
- 按论文数量从多到少排列。
- 必须覆盖所有论文：所有 arxiv_id 必须至少出现在一个主题里。

输出严格 JSON 数组（不加 ```）：
[
  {{
    "theme": "<主题名>",
    "description": "<一句话描述这个主题在做什么>",
    "paper_ids": ["arxiv_id_1", "arxiv_id_2", ...]
  }},
  ...
]

论文亮点（简化版）：
{slim_highlights_json}
"""


# ─── Phase 3: Per-theme deep dive ────────────────────────────────────────────

THEME_SYSTEM = (
    "你是一位资深 AI 研究综述员，正在为一份详细调研报告撰写某个主题的深度分析章节。"
    "语言通俗易懂、口语化但凝练，像在跟同行研究生聊天。"
    "每个具体观点必须用 [arxiv_id] 标注 1-3 篇支撑论文。"
    "禁止使用表格，禁止堆砌论文罗列，要有自己的归纳和判断。"
)

THEME_PROMPT = """\
现在请你深度分析一个主题，目标长度 **1500-2500 字**（不含标题与空行）。

主题名：{theme_name}
主题描述：{theme_desc}
该主题下共有 {num_papers} 篇论文，亮点数据如下：

{theme_highlights_json}

请严格按以下结构输出 Markdown（用 ## 开头，**不要**加最外层的 # 大标题）：

## {section_index}. {theme_name}

### 一句话定调
（写 1-2 句话，把这个方向当前所处的阶段说清楚，要有判断而不是流水账。）

### 大家在解决什么 & 为什么现在做
（200-350 字，讲清楚问题动机和驱动力，引 1-3 篇 [arxiv_id]）

### 主流技术路线
（梳理出 **2-4 条** 不同的路线/流派，每条用一个加粗子标题。
每条路线写：核心思路是什么、最具代表性的 1-3 个工作 [arxiv_id]、它的优势和明显短板。
不要简单列举论文，要讲清楚不同路线在思路上的关键差别。）

### 关键发现与最有意思的几个观察
（300-500 字，挑 3-5 个让你眼前一亮的结果或发现，每个用 [arxiv_id] 标注。
重点放在"改变了我们对问题的认知"的发现，而不是榜单分数。）

### 共同的局限与还没被认真做的事
（200-400 字，指出该方向多篇论文共有的盲区或还没解决的难点。
要有具体的、可继续研究的开口，引 [arxiv_id]。）

写作约束：
- 每段都要有 [arxiv_id]，平均每 80-120 字至少一处。
- 用"咱们"、"其实"、"听上去……但是……"这种口语化连接词。
- 禁止表格、禁止 code fence、禁止堆术语。
- 不要在末尾加总结性废话（"综上所述……"）。
"""


# ─── Phase 4: Cross-cutting analysis ─────────────────────────────────────────

CROSSCUT_SYSTEM = (
    "你是一位资深 AI 研究综述员，正在撰写跨主题的横向分析。"
    "语言通俗易懂但有深度。每个观点用 [arxiv_id] 标注来源。"
    "不要堆砌论文，要有自己的判断。"
)

CROSSCUT_HARD_PROBLEMS_PROMPT = """\
以下是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文的全部亮点数据：

{slim_highlights_json}

请撰写一节《跨方向的共性难题》（目标 1800-2800 字），结构如下：

## N. 跨方向的共性难题

写一段 80-120 字的引子，说明为什么要单独看这些跨主题的问题。

然后梳理 **5-7 个**反复出现在多个主题中的"硬骨头"问题。每个问题用 `### N.x 难题名` 作为子标题，包含：

- **为什么棘手**：不是"还没做好"这种废话，而是要点出结构性原因（语言先验、模态错位、长上下文、评测信号噪音、视觉解码偏置、训练数据稀缺、跨模态对齐目标本身有歧义等）
- **当前主流缓解思路与各自局限**：要把不同思路分类对比，引 3-5 篇 [arxiv_id]
- **你认为可能的突破方向**：要具体（"沿着 X 方向做 Y"），不要"加大模型规模"这种空话

写作约束：
- 每个观点用 [arxiv_id] 标注 1-3 篇支撑论文
- 用口语化但凝练的中文
- 不要表格、不要 code fence
- 每个难题之间用空行分隔
- 不要复述论文标题，要总结成自己的语言
"""


CROSSCUT_NOVELTY_PROMPT = """\
以下是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文的全部亮点数据：

{slim_highlights_json}

请撰写一节《特别值得关注的新颖工作》（目标 1500-2500 字），结构如下：

## N. 特别值得关注的新颖工作

写一段 60-100 字的引子，说明你的"新颖"判定标准（不是看分数高低，而是看思路是否真的不同）。

然后从全部论文里**精选 10-14 篇**你认为最有新意的工作。每篇用 `### N.x 论文短名（arxiv_id）` 作为子标题，包含：

- **新在哪里**：用 1-2 句话讲清楚它跟主流做法的关键差异
- **为什么值得追**：可能开辟新方向、可能改变某个子方向的研究范式、提出了之前没人系统问过的问题等
- **可能的后续发展**：你认为接下来沿着这个思路应该做什么

写作约束：
- 选论文时要覆盖至少 5 个不同主题（不要全集中在某一两个方向）
- 不要选你已经在前面章节讲过太多的那几篇代表作，要补充挖出来一些"次主流但有意思"的工作
- 每段都要凝练，避免空话
- 不要表格、不要 code fence
"""


CROSSCUT_ADVICE_PROMPT = """\
以下是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文的全部亮点数据：

{slim_highlights_json}

请撰写一节《选题建议与趋势判断》（目标 1500-2500 字），面向正在找选题的研究生：

## N. 选题建议与趋势判断

写一段 80-120 字的引子。

然后写以下三个子节（用 `### N.x` 子标题）：

### N.1 已经过度拥挤的方向
列出 3-5 个已经"卷指标"的方向，**具体**说明为什么不建议新人入场（不是因为难，而是因为收益不再显著），引 [arxiv_id] 为证。

### N.2 低垂果实
列出 4-6 个还没被认真做但有明确价值的子方向（新场景 × 新指标的交叉点最常见）。每个：
- 为什么是低垂果实
- 入场可能的方法路径
- 引相关 [arxiv_id]

### N.3 5-8 个具体的交叉选题建议
每个建议写成 `**选题：X + Y → 解决 Z**` 的形式，然后 100-150 字解释为什么这个交叉点可行、可以怎么做、引相关 [arxiv_id]。

最后写一段 150-250 字的"未来 1-2 年趋势判断"作为子节 `### N.4 趋势预判`，要有具体的判断而不是空话。

写作约束：
- 整体像资深研究者在给学生做选题指导，凝练但有针对性
- 每个观点用 [arxiv_id] 标注 1-3 篇相关论文
- 不要表格，不要堆砌
"""


# ─── Phase 5: Intro + Outro ──────────────────────────────────────────────────

INTRO_PROMPT = """\
以下是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文聚类后的主题列表：

{themes_summary}

请撰写一份**调研报告的总览章节**（350-600 字），面向同行研究生读者，包含：

1. 一句话定调：用一句口语化的话告诉听众，**现在这个领域整体处于什么阶段**。
2. 用 4-6 句话归纳：当前学界最热闹的几条主线、哪些问题大家有共识、哪些还在分歧。
3. 用 2-3 句话点出：哪些是这一批论文里最值得关注的转折信号或新现象。

写作约束：
- 完全口语化，像跟同事聊天那样
- 不要罗列主题列表，要有归纳和判断
- 不要使用 [arxiv_id]（这是总览，不需要详细引用）
- 不要写成"本报告将……"这种八股开头
- 直接以判断性句子开头
- 不要加 Markdown 标题
"""


OUTRO_PROMPT = """\
以下是 {num_papers} 篇 2026 年顶会 LVLM/MLLM 论文聚类后的主题列表：

{themes_summary}

请撰写一份**调研报告的结尾收束**（200-400 字），不要重复正文已经说过的细节。
要点：
- 用 1-2 句话提炼整份报告的核心判断（不是 summary，是 takeaway）
- 用 2-3 句话点出：对于做 LVLM/MLLM 的研究者，**接下来最应该关注什么**
- 用 1-2 句话指出：这个领域可能在 1-2 年内出现什么变化

写作约束：
- 口语化，凝练
- 不要"综上所述"、"总而言之"这种废话开头
- 不要加 Markdown 标题
"""


# ─── Helpers ──────────────────────────────────────────────────────────────────


def load_card_file(card_path: Path) -> Optional[Dict[str, str]]:
    text = card_path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"arXiv:\s*\**\s*([\d.]+(?:v\d+)?)", text)
    arxiv_id = m.group(1) if m else card_path.stem
    return {"arxiv_id": arxiv_id, "card_text": text, "path": str(card_path)}


def parse_json_blob(raw: str) -> Optional[object]:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    if not raw:
        return None
    if raw[0] not in "{[":
        for open_c, close_c in [("[", "]"), ("{", "}")]:
            start = raw.find(open_c)
            end = raw.rfind(close_c)
            if start != -1 and end != -1 and end > start:
                raw = raw[start : end + 1]
                break
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract_highlights(client: OpenAIClient, card: Dict[str, str], logger) -> Optional[Dict]:
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        arxiv_id=card["arxiv_id"],
        card_text=card["card_text"][:12000],
    )
    try:
        raw = client.call_llm(prompt, system_prompt=EXTRACTION_SYSTEM)
    except Exception as exc:
        logger.warning(f"Extraction failed for {card['arxiv_id']}: {exc}")
        return None
    parsed = parse_json_blob(raw)
    if not isinstance(parsed, dict):
        logger.warning(f"Could not parse JSON for {card['arxiv_id']}: {raw[:200]}")
        return None
    parsed.setdefault("arxiv_id", card["arxiv_id"])
    return parsed


def slim_highlights(highlights: List[Dict]) -> List[Dict]:
    """Trim each highlight to the fields needed for clustering/cross-cut prompts."""

    out = []
    for h in highlights:
        out.append(
            {
                "arxiv_id": h.get("arxiv_id", ""),
                "title": (h.get("title") or "")[:140],
                "venue": h.get("venue", ""),
                "方向标签": h.get("方向标签", []),
                "想解决的问题": (h.get("想解决的问题") or "")[:160],
                "核心方法": (h.get("核心方法一句话") or "")[:160],
                "关键贡献": (h.get("关键发现或贡献") or "")[:160],
                "局限": (h.get("局限或未解决问题") or "")[:160],
            }
        )
    return out


def ultra_slim_highlights(highlights: List[Dict]) -> List[Dict]:
    """Smallest representation suitable for clustering only (~12 KB for 100 papers)."""

    out = []
    for h in highlights:
        out.append(
            {
                "id": h.get("arxiv_id", ""),
                "title": (h.get("title") or "")[:90],
                "tags": h.get("方向标签", []),
                "q": (h.get("想解决的问题") or "")[:90],
            }
        )
    return out


def cluster_papers(client: OpenAIClient, highlights: List[Dict], logger) -> List[Dict]:
    n = len(highlights)
    if n <= 120:
        k = 8
    elif n <= 300:
        k = 9
    else:
        k = 10

    # Build embedding texts: title + problem + core method
    texts = []
    for h in highlights:
        parts = [
            (h.get("title") or "").strip(),
            (h.get("想解决的问题") or "").strip(),
            (h.get("核心方法一句话") or "").strip(),
        ]
        texts.append(" | ".join(p for p in parts if p))

    # Get embeddings in batches of 512
    logger.info(f"Getting embeddings for {n} papers...")
    all_embeddings = []
    batch_size = 512
    for i in range(0, n, batch_size):
        batch = texts[i : i + batch_size]
        embs = client.get_embeddings(batch)
        all_embeddings.extend(embs)
        if i + batch_size < n:
            logger.info(f"  embeddings: {i + len(batch)}/{n}")

    X = np.array(all_embeddings)
    logger.info(f"Running KMeans (k={k}) on {X.shape} matrix...")
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    # Group papers by cluster
    clusters: Dict[int, List[str]] = {}
    for idx, label in enumerate(labels):
        clusters.setdefault(int(label), []).append(highlights[idx]["arxiv_id"])

    # Sort clusters by size (largest first)
    sorted_clusters = sorted(clusters.items(), key=lambda x: len(x[1]), reverse=True)

    # Ask LLM to name each cluster based on its papers
    cluster_summaries = []
    for cluster_id, paper_ids in sorted_clusters:
        sample_papers = []
        for pid in paper_ids[:15]:
            h = next((x for x in highlights if x["arxiv_id"] == pid), None)
            if h:
                sample_papers.append(
                    f"- {h.get('title', '')}: {h.get('想解决的问题', '')}"
                )
        cluster_summaries.append({
            "paper_count": len(paper_ids),
            "sample": "\n".join(sample_papers),
            "paper_ids": paper_ids,
        })

    naming_prompt = "下面是通过 embedding 聚类得到的论文分组，请为每组起一个简短的中文主题名（2-8字）并写一句话描述。\n\n"
    for i, cs in enumerate(cluster_summaries):
        naming_prompt += f"### 组 {i+1}（{cs['paper_count']} 篇）\n{cs['sample']}\n\n"
    naming_prompt += (
        "输出严格 JSON 数组（不加 ```），按输入顺序：\n"
        '[{"theme": "<主题名>", "description": "<一句话描述>"},...]\n'
    )

    logger.info(f"Naming {k} clusters via LLM (prompt {len(naming_prompt)} chars)...")
    raw = client.call_llm(naming_prompt, system_prompt=CLUSTERING_SYSTEM)
    names = parse_json_blob(raw)
    if not isinstance(names, list) or len(names) < len(sorted_clusters):
        logger.warning(f"Naming returned {len(names) if names else 0} items, expected {len(sorted_clusters)}")
        names = names or []
        while len(names) < len(sorted_clusters):
            names.append({"theme": f"主题{len(names)+1}", "description": ""})

    themes = []
    for i, (cluster_id, paper_ids) in enumerate(sorted_clusters):
        themes.append({
            "theme": names[i]["theme"],
            "description": names[i].get("description", ""),
            "paper_ids": paper_ids,
        })

    return themes


def themes_summary_text(themes: List[Dict]) -> str:
    return "\n".join(
        f"- **{t['theme']}**（{len(t.get('paper_ids', []))} 篇）：{t.get('description', '')}"
        for t in themes
    )


def render_theme_section(
    client: OpenAIClient,
    section_index: int,
    theme: Dict,
    highlights_by_id: Dict[str, Dict],
    logger,
) -> str:
    paper_ids = theme.get("paper_ids", [])
    theme_highlights = [highlights_by_id[i] for i in paper_ids if i in highlights_by_id]
    if not theme_highlights:
        logger.warning(f"Theme '{theme['theme']}' has no resolvable papers")
        return ""
    prompt = THEME_PROMPT.format(
        section_index=section_index,
        theme_name=theme["theme"],
        theme_desc=theme.get("description", ""),
        num_papers=len(theme_highlights),
        theme_highlights_json=json.dumps(theme_highlights, ensure_ascii=False, indent=1),
    )
    t0 = time.time()
    logger.info(
        f"  [theme {section_index}] '{theme['theme']}' "
        f"({len(theme_highlights)} papers, prompt {len(prompt)} chars)..."
    )
    text = client.call_llm(prompt, system_prompt=THEME_SYSTEM)
    logger.info(
        f"  [theme {section_index}] '{theme['theme']}' done in {time.time()-t0:.1f}s "
        f"({len(text)} chars)"
    )
    return text.strip()


def render_crosscut_section(
    client: OpenAIClient,
    prompt_template: str,
    highlights: List[Dict],
    section_label: str,
    logger,
    max_papers: int = 200,
) -> str:
    subset = highlights[:max_papers] if len(highlights) > max_papers else highlights
    slim = slim_highlights(subset)
    prompt = prompt_template.format(
        num_papers=len(slim),
        slim_highlights_json=json.dumps(slim, ensure_ascii=False, indent=1),
    )
    t0 = time.time()
    logger.info(f"  [{section_label}] {len(subset)}/{len(highlights)} papers, prompt {len(prompt)} chars, calling LLM...")
    text = client.call_llm(prompt, system_prompt=CROSSCUT_SYSTEM)
    logger.info(f"  [{section_label}] done in {time.time()-t0:.1f}s ({len(text)} chars)")
    return text.strip()


def render_intro(client: OpenAIClient, themes: List[Dict], num_papers: int, logger) -> str:
    prompt = INTRO_PROMPT.format(
        num_papers=num_papers,
        themes_summary=themes_summary_text(themes),
    )
    return client.call_llm(prompt, system_prompt=THEME_SYSTEM).strip()


def render_outro(client: OpenAIClient, themes: List[Dict], num_papers: int, logger) -> str:
    prompt = OUTRO_PROMPT.format(
        num_papers=num_papers,
        themes_summary=themes_summary_text(themes),
    )
    return client.call_llm(prompt, system_prompt=THEME_SYSTEM).strip()


def fix_section_numbering(text: str, target_idx: int) -> str:
    """Replace the leading `## X.` with the desired index. Best-effort."""

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if line.startswith("## "):
            if re.match(r"^##\s+\d+\.", line):
                lines[i] = re.sub(r"^##\s+\d+\.", f"## {target_idx}.", line, count=1)
            else:
                lines[i] = f"## {target_idx}. " + line[3:].lstrip()
            break
    text = "\n".join(lines)
    # Renumber subheadings ### N.x or ### <digit>.x → ### {target_idx}.x
    text = re.sub(
        r"(?m)^###\s+(?:N|\d+)\.(\d+)",
        lambda m: f"### {target_idx}.{m.group(1)}",
        text,
    )
    return text


def build_toc(theme_titles: List[str], crosscut_titles: List[str]) -> str:
    lines = ["## 目录", ""]
    n = 1
    lines.append(f"{n}. 总览")
    for title in theme_titles:
        n += 1
        lines.append(f"{n}. {title}")
    for title in crosscut_titles:
        n += 1
        lines.append(f"{n}. {title}")
    n += 1
    lines.append(f"{n}. 结语")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cards-dir", type=Path, default=ROOT / "outputs" / "cards")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "reports" / "lvlm_mllm_detailed_briefing.md",
    )
    parser.add_argument("--ids-file", type=Path, default=None)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument(
        "--highlights-cache",
        type=Path,
        default=ROOT / "outputs" / "reports" / "lvlm_mllm_detailed_highlights.json",
    )
    parser.add_argument(
        "--themes-cache",
        type=Path,
        default=ROOT / "outputs" / "reports" / "lvlm_mllm_detailed_themes.json",
    )
    parser.add_argument(
        "--reuse-themes",
        action="store_true",
        help="If themes-cache exists, skip the clustering LLM call and reuse it.",
    )
    parser.add_argument(
        "--max-crosscut-papers",
        type=int,
        default=200,
        help="Max papers fed to cross-cutting prompts (top by score). Prevents 524 timeout.",
    )
    parser.add_argument(
        "--combined-accepted",
        type=Path,
        default=ROOT / "outputs" / "conference_search" / "combined_2026" / "combined_accepted.jsonl",
        help="Authoritative per-paper venue mapping; used for the header line.",
    )
    args = parser.parse_args()

    log_file = ROOT / "logs" / "survey_synthesis_detailed.log"
    setup_logger(log_file=log_file)
    logger = get_logger("survey_detailed")

    cfg = Config.from_env()
    client = OpenAIClient(cfg.openai)

    # ── Phase 1: load cards ──
    if not args.cards_dir.exists():
        logger.error(f"Cards dir not found: {args.cards_dir}")
        sys.exit(1)
    card_paths = sorted(args.cards_dir.glob("*.md"))
    cards = [c for c in (load_card_file(p) for p in card_paths) if c]
    logger.info(f"Loaded {len(cards)} cards")

    if args.ids_file and args.ids_file.exists():
        wanted_ids = {
            line.strip().split("/")[-1].replace(".pdf", "").split("v")[0]
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        before = len(cards)
        cards = [c for c in cards if c["arxiv_id"].split("v")[0] in wanted_ids]
        logger.info(f"Filtered by --ids-file: {before} -> {len(cards)}")

    if not cards:
        logger.error("No cards to process.")
        sys.exit(1)

    # ── Phase 1b: extraction with cache ──
    cache: Dict[str, Dict] = {}
    if args.highlights_cache and args.highlights_cache.exists():
        try:
            cached_list = json.loads(args.highlights_cache.read_text(encoding="utf-8"))
            cache = {h["arxiv_id"]: h for h in cached_list if "arxiv_id" in h}
            logger.info(f"Loaded {len(cache)} cached highlights")
        except Exception as exc:
            logger.warning(f"Failed to load highlights cache: {exc}")

    todo = [c for c in cards if c["arxiv_id"] not in cache]
    logger.info(f"Need to extract {len(todo)} new highlights (cached: {len(cache)})")
    if todo:
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {pool.submit(extract_highlights, client, c, logger): c for c in todo}
            done = 0
            for fut in as_completed(futures):
                result = fut.result()
                done += 1
                if result:
                    cache[result["arxiv_id"]] = result
                if done % 5 == 0 or done == len(todo):
                    logger.info(f"  extraction progress: {done}/{len(todo)}")
                if args.highlights_cache:
                    args.highlights_cache.parent.mkdir(parents=True, exist_ok=True)
                    args.highlights_cache.write_text(
                        json.dumps(list(cache.values()), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    highlights = [cache[c["arxiv_id"]] for c in cards if c["arxiv_id"] in cache]
    highlights_by_id = {h["arxiv_id"]: h for h in highlights}
    logger.info(f"Phase 1 done: {len(highlights)} highlights")

    # ── Phase 2: clustering ──
    themes: List[Dict]
    if args.reuse_themes and args.themes_cache and args.themes_cache.exists():
        themes = json.loads(args.themes_cache.read_text(encoding="utf-8"))
        logger.info(f"Reusing {len(themes)} themes from cache")
    else:
        themes = cluster_papers(client, highlights, logger)
        args.themes_cache.parent.mkdir(parents=True, exist_ok=True)
        args.themes_cache.write_text(
            json.dumps(themes, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Phase 2 done: {len(themes)} themes")
        for t in themes:
            logger.info(f"  - {t['theme']}: {len(t.get('paper_ids', []))} papers")

    # ── Phase 3: per-theme deep dive (parallel) ──
    theme_sections: Dict[int, str] = {}
    with ThreadPoolExecutor(max_workers=min(args.max_workers, len(themes))) as pool:
        futures = {
            pool.submit(
                render_theme_section,
                client,
                idx + 2,  # 1 is overview, themes start at 2
                theme,
                highlights_by_id,
                logger,
            ): idx
            for idx, theme in enumerate(themes)
        }
        for fut in as_completed(futures):
            idx = futures[fut]
            try:
                theme_sections[idx] = fut.result()
            except Exception as exc:
                logger.error(f"Theme #{idx} ({themes[idx]['theme']}) failed: {exc}")
                theme_sections[idx] = f"## {idx + 2}. {themes[idx]['theme']}\n\n（本节生成失败：{exc}）"

    # ── Phase 4: cross-cutting (parallel) ──
    crosscut_specs = [
        ("hard_problems", CROSSCUT_HARD_PROBLEMS_PROMPT, "跨方向的共性难题"),
        ("novelty", CROSSCUT_NOVELTY_PROMPT, "特别值得关注的新颖工作"),
        ("advice", CROSSCUT_ADVICE_PROMPT, "选题建议与趋势判断"),
    ]
    crosscut_results: Dict[str, str] = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {
            pool.submit(
                render_crosscut_section,
                client,
                template,
                highlights,
                label,
                logger,
                args.max_crosscut_papers,
            ): label
            for label, template, _ in crosscut_specs
        }
        for fut in as_completed(futures):
            label = futures[fut]
            try:
                crosscut_results[label] = fut.result()
            except Exception as exc:
                logger.error(f"Cross-cut '{label}' failed: {exc}")
                crosscut_results[label] = f"（{label} 章节生成失败：{exc}）"

    # ── Phase 5: intro + outro (parallel) ──
    intro_text = outro_text = ""
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_intro = pool.submit(render_intro, client, themes, len(highlights), logger)
        fut_outro = pool.submit(render_outro, client, themes, len(highlights), logger)
        try:
            intro_text = fut_intro.result()
        except Exception as exc:
            logger.error(f"Intro failed: {exc}")
            intro_text = "（总览生成失败）"
        try:
            outro_text = fut_outro.result()
        except Exception as exc:
            logger.error(f"Outro failed: {exc}")
            outro_text = "（结语生成失败）"

    # ── Phase 6: assemble locally ──
    theme_titles = [t["theme"] for t in themes]
    crosscut_titles = [label for _, _, label in crosscut_specs]

    sections: List[str] = []

    # Header
    venue_counts: Dict[str, int] = {}
    if args.combined_accepted and args.combined_accepted.exists():
        wanted_ids = {h["arxiv_id"].split("v")[0] for h in highlights}
        with args.combined_accepted.open("r", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row.get("arxiv_id", "").split("v")[0] not in wanted_ids:
                    continue
                for v in row.get("venues", []):
                    venue_counts[v] = venue_counts.get(v, 0) + 1
    if venue_counts:
        venues_line = ", ".join(
            f"{v}（{c}）" for v, c in sorted(venue_counts.items(), key=lambda kv: -kv[1])
        )
    else:
        venues_line = "ICLR/CVPR/ICML/ACL/AAAI 2026"
    sections.append(
        "# 2026 年顶会 LVLM/MLLM 方向深度调研报告\n\n"
        f"涵盖会议：{venues_line}\n"
        f"论文数量：{len(highlights)} 篇（综合 LVLM/MLLM 相关性排序后 top-{len(highlights)}）\n"
        f"主题数：{len(themes)}\n"
    )

    # TOC
    sections.append(build_toc(theme_titles, [title for _, _, title in crosscut_specs]))

    # Overview (section 1)
    sections.append("## 1. 总览\n\n" + intro_text)

    # Theme sections (already numbered 2..N+1 by section_index)
    for idx in range(len(themes)):
        body = theme_sections.get(idx, "")
        if not body.strip().startswith("##"):
            body = f"## {idx + 2}. {themes[idx]['theme']}\n\n{body}"
        else:
            body = fix_section_numbering(body, idx + 2)
        sections.append(body)

    # Cross-cutting sections
    crosscut_start = len(themes) + 2
    for offset, (label, _, title) in enumerate(crosscut_specs):
        section_idx = crosscut_start + offset
        body = crosscut_results.get(label, "")
        if not body.strip().startswith("##"):
            body = f"## {section_idx}. {title}\n\n{body}"
        else:
            body = fix_section_numbering(body, section_idx)
        sections.append(body)

    # Outro
    outro_idx = crosscut_start + len(crosscut_specs)
    sections.append(f"## {outro_idx}. 结语\n\n{outro_text}")

    # Appendix: theme→papers index for transparency
    appendix_lines = [f"## {outro_idx + 1}. 附录：主题与论文映射", ""]
    for i, theme in enumerate(themes, start=2):
        appendix_lines.append(f"### {i}. {theme['theme']}")
        appendix_lines.append(f"_{theme.get('description', '')}_")
        appendix_lines.append("")
        for aid in theme.get("paper_ids", []):
            h = highlights_by_id.get(aid)
            if h:
                title = (h.get("title") or "").strip()
                appendix_lines.append(f"- [{aid}](https://arxiv.org/abs/{aid}) — {title}")
            else:
                appendix_lines.append(f"- {aid}")
        appendix_lines.append("")
    sections.append("\n".join(appendix_lines))

    final = "\n\n".join(sections).rstrip() + "\n"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(final, encoding="utf-8")
    logger.info(f"Final report written: {args.output}  ({len(final):,} chars)")
    print(f"Done: {args.output}  ({len(final):,} chars)")


if __name__ == "__main__":
    main()
