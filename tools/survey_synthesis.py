"""One-shot survey synthesis for LVLM/MLLM CVPR/ICML 2026 papers.

Reads all generated 10-min Cards (and optionally Deep Notes / materials JSON)
from outputs/, extracts structured highlights per paper, then asks the LLM
to produce a single accessible Chinese briefing that answers:
  - 学界目前关注哪些方向
  - 大家都在做什么
  - 大家感兴趣的问题与难解决的问题是什么

Re-uses the project's OpenAIClient so it picks up OPENAI_API_KEY,
OPENAI_BASE_URL and MODEL_NAME from .env automatically.

Run from project root inside the paper_agent conda env:
    python tools/survey_synthesis.py \
        --cards-dir outputs/cards \
        --output outputs/reports/lvlm_mllm_briefing.md
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

from core.api_client import OpenAIClient  # noqa: E402
from core.config import Config  # noqa: E402
from core.logger import setup_logger, get_logger  # noqa: E402


EXTRACTION_SYSTEM = (
    "你是一位资深的多模态大模型方向研究综述员，擅长把一篇论文 Card 浓缩成"
    "可被聚合的结构化要点。只输出 JSON，不要寒暄、不要解释。"
)

EXTRACTION_PROMPT_TEMPLATE = """\
下面是一篇 CVPR2026 或 ICML2026 多模态视觉语言大模型相关论文的 10min Card（Markdown）。
请抽取结构化亮点，用于跨论文聚合分析。严格输出如下 JSON（不加 ```），字段都用中文：

{{
  "arxiv_id": "{arxiv_id}",
  "title": "<论文标题>",
  "方向标签": ["最多 3 个，例如：视觉幻觉、Token压缩、视觉指令对齐、安全越狱、视频理解、视觉推理、Agent、3D视觉理解 等"],
  "想解决的问题": "<一句话，关键>",
  "为什么难": "<一句话，论文揭示的难点>",
  "核心方法一句话": "<核心思路>",
  "关键发现或贡献": "<一句话，可量化最好>",
  "局限或未解决问题": "<论文自己承认或留下的问题>"
}}

只输出 JSON 对象本体。论文 Card 内容如下：

{card_text}
"""


SYNTHESIS_SYSTEM = (
    "你是一位刚读完 50–100 篇 CVPR2026/ICML2026 多模态视觉语言大模型论文的"
    "资深研究助理。现在要为一次调研汇报写讲稿。读者是同行研究生，希望快速"
    "搞清楚“目前学界关心什么、在做什么、什么是难题”。要求语言通俗易懂、"
    "口语化但不啰嗦，能直接念出来；不要堆术语；具体观点必须有论文支撑，"
    "在句末用 [arxiv_id] 形式给出 1–3 篇代表论文作为证据。"
)


SYNTHESIS_PROMPT_TEMPLATE = """\
我们刚汇总了 {num_papers} 篇 CVPR2026 / ICML2026 大会接收的、与
大型视觉语言模型（LVLM / MLLM）密切相关的论文。下面是按论文逐篇抽取的
结构化亮点 JSON 数组（每条对应一篇）：

{highlights_json}

请基于上面这些论文亮点，写一份**面向口头汇报**的中文调研稿（Markdown，
不要 code fence）。结构如下，但每节都要写得像在跟同事聊天，避免学术八股：

# CVPR2026 与 ICML2026 多模态视觉语言大模型方向调研汇报

## 1. 一句话总览
- 用一句话告诉听众：现在这个领域整体处于什么阶段，最热闹的几条线是什么。

## 2. 当前学界最关注的几个大方向
请你自己归纳出 5–8 个高频方向（不要照抄方向标签，要合并同类项），每个方向写：
- **方向名 + 一句口语化解释**：是什么、为什么大家在做
- **大家具体在做什么**：典型做法/技术路线，用 2–4 个代表论文 [arxiv_id] 举例
- **真正难的地方**：这个方向当前最卡住的问题，引 1–2 篇 [arxiv_id]

## 3. 大家共同感兴趣、但都没彻底解决的“硬骨头”
横向梳理 3–5 个跨方向反复出现的难题（例如幻觉、推理可靠性、视频长上下文、
评测可信度、安全对齐、效率与部署等），每个难题：
- 描述这个难题为什么棘手
- 当前主流缓解思路与各自局限
- 引用 2–4 篇代表论文 [arxiv_id]

## 4. 比较新颖、值得多关注的尝试
挑 5–8 篇你认为方法路线特别新、或者揭示了之前没被认真讨论过的问题的论文，
每篇用 1–2 句话告诉听众“新在哪里、为什么值得追”。

## 5. 给做 LVLM/MLLM 方向同学的几点建议
- 哪些方向已经开始“卷指标”，新人入场要谨慎
- 哪些是低垂果实、当前论文还没怎么覆盖
- 想找新选题，可以从哪几篇论文交叉点切入

写作约束：
- 全文以**讲稿**口吻写，可以用“咱们”“听上去……”“其实……”这种连接词。
- 每个具体观点末尾必须用 [arxiv_id] 列出至少一篇支撑论文，最多三篇。
- 不要复述上面的 JSON 数据，要总结成自然语言。
- 不要使用表格，多用项目符号。
- 全文控制在 2500–4500 字。
"""


def load_card_file(card_path: Path) -> Optional[Dict[str, str]]:
    """Extract arxiv_id (from filename or front matter) and the card text."""

    text = card_path.read_text(encoding="utf-8", errors="ignore")
    # Cards usually contain a line like: arXiv: **2604.13074**
    m = re.search(r"arXiv:\s*\**\s*([\d.]+(?:v\d+)?)", text)
    arxiv_id = m.group(1) if m else card_path.stem
    return {"arxiv_id": arxiv_id, "card_text": text, "path": str(card_path)}


def parse_extracted_json(raw: str) -> Optional[Dict]:
    """Robustly parse JSON object even when model adds extra prose or fences."""

    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    # Some models still wrap with leading commentary; grab first {...} block.
    if not raw.startswith("{"):
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        raw = raw[start : end + 1]
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def extract_highlights(
    client: OpenAIClient,
    card: Dict[str, str],
    logger,
) -> Optional[Dict]:
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        arxiv_id=card["arxiv_id"],
        card_text=card["card_text"][:12000],  # plenty for a 10min card
    )
    try:
        raw = client.call_llm(prompt, system_prompt=EXTRACTION_SYSTEM)
    except Exception as exc:
        logger.warning(f"Extraction failed for {card['arxiv_id']}: {exc}")
        return None

    parsed = parse_extracted_json(raw)
    if parsed is None:
        logger.warning(f"Could not parse JSON for {card['arxiv_id']}: {raw[:200]}")
        return None
    parsed.setdefault("arxiv_id", card["arxiv_id"])
    return parsed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cards-dir",
        type=Path,
        default=ROOT / "outputs" / "cards",
        help="Directory containing 10min Paper Cards (.md).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "outputs" / "reports" / "lvlm_mllm_briefing.md",
        help="Path to write the final accessible briefing markdown.",
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help="Optional arXiv IDs txt. If given, only cards for these IDs are kept.",
    )
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument(
        "--highlights-cache",
        type=Path,
        default=None,
        help="Cache file for per-paper highlights JSON. Reuses already-extracted ones.",
    )
    args = parser.parse_args()

    log_file = ROOT / "logs" / "survey_synthesis.log"
    setup_logger(log_file=log_file)
    logger = get_logger("survey_synthesis")

    cfg = Config.from_env()
    client = OpenAIClient(cfg.openai)

    if not args.cards_dir.exists():
        logger.error(f"Cards dir not found: {args.cards_dir}")
        sys.exit(1)

    # Collect cards
    card_paths = sorted(args.cards_dir.glob("*.md"))
    cards = [c for c in (load_card_file(p) for p in card_paths) if c]
    logger.info(f"Found {len(cards)} cards under {args.cards_dir}")

    if args.ids_file and args.ids_file.exists():
        wanted_ids = {
            line.strip().split("/")[-1].replace(".pdf", "").split("v")[0]
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
        before = len(cards)
        cards = [c for c in cards if c["arxiv_id"].split("v")[0] in wanted_ids]
        logger.info(f"Filtered cards by --ids-file: {before} -> {len(cards)}")

    if not cards:
        logger.error("No cards to process.")
        sys.exit(1)

    # Load highlights cache if any
    cache: Dict[str, Dict] = {}
    if args.highlights_cache and args.highlights_cache.exists():
        try:
            cached_list = json.loads(args.highlights_cache.read_text(encoding="utf-8"))
            cache = {h["arxiv_id"]: h for h in cached_list if "arxiv_id" in h}
            logger.info(f"Loaded {len(cache)} cached highlights")
        except Exception as exc:
            logger.warning(f"Failed to load cache: {exc}")

    todo = [c for c in cards if c["arxiv_id"] not in cache]
    logger.info(f"Need to extract highlights for {len(todo)} new cards (cached: {len(cache)})")

    if todo:
        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {pool.submit(extract_highlights, client, c, logger): c for c in todo}
            done = 0
            for fut in as_completed(futures):
                card = futures[fut]
                result = fut.result()
                done += 1
                if result:
                    cache[result["arxiv_id"]] = result
                if done % 5 == 0 or done == len(todo):
                    logger.info(f"Extraction progress: {done}/{len(todo)}")
                # Persist cache eagerly so failures don't lose progress
                if args.highlights_cache:
                    args.highlights_cache.parent.mkdir(parents=True, exist_ok=True)
                    args.highlights_cache.write_text(
                        json.dumps(list(cache.values()), ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

    highlights = [cache[c["arxiv_id"]] for c in cards if c["arxiv_id"] in cache]
    logger.info(f"Final highlights count: {len(highlights)}")

    if not highlights:
        logger.error("No highlights extracted; aborting synthesis.")
        sys.exit(1)

    prompt = SYNTHESIS_PROMPT_TEMPLATE.format(
        num_papers=len(highlights),
        highlights_json=json.dumps(highlights, ensure_ascii=False, indent=2),
    )

    logger.info("Calling LLM to synthesize final briefing...")
    t0 = time.time()
    briefing = client.call_llm(prompt, system_prompt=SYNTHESIS_SYSTEM)
    logger.info(f"Synthesis done in {time.time() - t0:.1f}s, length={len(briefing)}")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(briefing, encoding="utf-8")
    logger.info(f"Final briefing written to {args.output}")
    print(f"Done: {args.output}")


if __name__ == "__main__":
    main()
