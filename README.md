# Paper Agent

[English](./README_EN.md) | 简体中文

基于 LLM 的论文阅读助手。自动搜索 arXiv 论文，提取图表，生成结构化阅读笔记。

## 功能

- **论文搜索**：通过 DeepXiv API 按关键词、分类、日期搜索 arXiv 论文
- **会议论文搜索**：扫描本地 arXiv 元数据快照，筛选明确标注被顶会录用的论文（CVPR、ICML、NeurIPS、ICLR、ACL 等）
- **ID 文件导入**：从 txt 批量读取 arXiv ID / URL，跳过关键词搜索直接处理指定论文
- **研究方向判断**：用独立的 `RESEARCH_FOCUS` 评估论文相关性、启发和新论文切入点
- **图表提取**：优先从 LaTeX 源码提取高质量图片，PDF 作为 fallback
- **三层笔记生成**：
  - 10min Card — 快速掌握核心贡献
  - 图表上下文分析 — 结合 LaTeX 引用上下文解读每张图
  - 30min Deep Note — 方法细节、实验可信度、可复现性
- **元数据标注**：自动标注论文类型、顶会录用、开源代码链接
- **批量并行处理**：论文级 + 生成器级双层并行
- **调研报告**：批量处理后自动生成综述

## 快速开始

```bash
git clone https://github.com/sinksilk/paper_agent.git
cd paper_agent
pip install -r requirements.txt
cp .env.example .env  # 编辑填入 API key
python main.py
```

## 配置

编辑 `.env` 文件：

```bash
# LLM API（兼容 OpenAI 接口的任意服务）
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# DeepXiv API（https://deepxiv.com 注册获取）
DEEPXIV_TOKEN=your_token

# 搜索
QUERY="multimodal LVLM jailbreak"       # 只用于关键词搜索
RESEARCH_FOCUS="multimodal LVLM safety" # 用于相关性判断、启发和新论文选题
ARXIV_IDS_FILE=              # 可选：设置后从 txt 读取 ID，跳过关键词搜索
LIMIT=10
DATE_FROM=2025-01-01
CATEGORIES=cs.CV,cs.CL,cs.CR

# 处理
MAX_WORKERS=8              # 并行线程数
DOWNLOAD_PDF=true          # 下载 PDF
EXTRACT_FIGURES=true       # 提取图表
USE_LATEX_SOURCE=true      # 优先 LaTeX 源码提取图片
ANALYZE_FIGURES=true       # 图表上下文分析
GENERATE_DEEP_NOTE=false   # 30min 深度笔记（耗时较长）

# 会议论文搜索（tools/conference_search.py）
ARXIV_METADATA_FILE=       # 本地 arXiv 元数据快照路径
```

### 从 txt 批量处理指定论文

准备一个 txt 文件，内容可以混合 arXiv URL 和裸 ID：

```text
https://arxiv.org/abs/2605.08389
2605.08389
2605.08389v2
https://arxiv.org/pdf/2605.08389.pdf
```

然后运行：

```bash
python main.py --ids-file papers.txt
```

也可以在 `.env` 中设置 `ARXIV_IDS_FILE=papers.txt` 后直接运行 `python main.py`。启用后会跳过关键词搜索，下载并解析 txt 中的所有论文，最后生成本批次的报告。论文相关性、对你的启发和新论文切入点会统一根据 `RESEARCH_FOCUS` 判断；如果 `RESEARCH_FOCUS` 留空，则默认使用 `QUERY`。

### 搜索会议中稿 arXiv 论文并初筛

默认不调用 arXiv 官方 API，而是扫描本地 arXiv metadata 快照（推荐使用 Kaggle/Cornell 的 `arxiv-metadata-oai-snapshot.json`），硬过滤明确写有 `accepted to/at/by` 或 `to appear at/in` 的会议论文，最后把精选 ID 接入现有工作流：

```bash
python tools/conference_search.py --venue CVPR2026 --metadata-file /path/to/arxiv-metadata-oai-snapshot.json --top 50
python tools/conference_search.py --venue ICML2026 --metadata-file /path/to/arxiv-metadata-oai-snapshot.json --top 200
```

也可以在 `.env` 里设置：

```bash
ARXIV_METADATA_FILE=/path/to/arxiv-metadata-oai-snapshot.json
```

之后直接运行：

```bash
python tools/conference_search.py --venue CVPR2026 --top 50
```

`--top` 只控制后续精读数量，不限制搜索数量；如果请求 `--top 200` 但只找到 80 篇 accepted 论文，则 `papers_top.txt` 会包含全部 80 篇。默认扫描完整快照；调试时可用 `--max-records 10000` 限制扫描行数。默认不限制 arXiv category 以提高召回率；需要缩小范围时可加 `--categories cs.CV` 或 `--use-config-categories`。默认排除 workshop/challenge/competition，可用 `--include-workshops` 保留。

如果没有本地快照，也可以临时切到 OpenAlex 或通用搜索引擎发现候选；这些模式同样不使用 arXiv 官方 API，但可复现性和召回率不如本地快照：

```bash
python tools/conference_search.py --venue CVPR2026 --backend openalex --top 50
python tools/conference_search.py --venue CVPR2026 --backend web --search-pages 3 --delay-seconds 5
```

输出目录：

```text
outputs/conference_search/{VENUE}/
├── accepted.jsonl      # 全部通过硬过滤的 arXiv 元数据
├── rejected.jsonl      # 被排除的候选及原因
├── papers_all.txt      # 全部 accepted arXiv IDs
├── papers_top.txt      # 建议进入精读流程的 arXiv IDs
├── trend_report.md     # 基于标题/摘要的非 LLM 方向概览
└── search_log.json
```

确认 `papers_top.txt` 后运行：

```bash
python main.py --ids-file outputs/conference_search/CVPR2026/papers_top.txt
```

也可以一步执行搜索后自动接工作流：

```bash
python tools/conference_search.py --venue CVPR2026 --top 50 --run-workflow
```

## 输出示例

### Card 元数据头部

每张 Card 开头自动生成结构化元数据：

```markdown
# 10min Paper Card：Cross-Modal Obfuscation for Jailbreak Attacks on LVLMs

论文：**Cross-Modal Obfuscation for Jailbreak Attacks on Large Vision-Language Models**
arXiv: **2506.16760**
关键词：LVLM / adversarial jailbreak / black-box / cross-modal obfuscation
类型：**Research**
发表：**NeurIPS 2025**          ← 如果被顶会录用会自动标注
代码：**https://github.com/xxx/xxx**  ← 如果论文提到开源代码会标注
```

### 输出目录结构

```
outputs/
├── cards/              # 10min Paper Cards（含图表分析）
├── deep_notes/         # 30min Deep Notes
├── figure_analysis/    # 图表上下文分析（独立文件）
├── figures/            # 提取的图片
├── pdfs/              # PDF 文件
├── latex_sources/     # LaTeX 源码
└── reports/           # 调研报告
    └── {query}_{timestamp}/
        ├── report.md
        ├── cards/     # 该次查询的所有 card 副本
        └── materials/ # 原始材料 JSON
```

## 笔记格式

### 10min Card

| 章节 | 内容 |
|------|------|
| 一句话结论 | 论文核心贡献 |
| 论文想解决的问题 | 动机和背景 |
| 核心方法 | 技术方案 |
| 和已有工作的区别 | 创新点 |
| 实验设置 | 数据集、Baseline、指标 |
| 关键结果 | 主要实验发现 |
| 可能的问题或漏洞 | 批判性分析 |
| 对我的方向是否有用与启发 | A/B/C/D 评级 + 原因 + 对新论文选题的指导 |
| 30分钟优先读哪些部分 | 阅读建议 |

### 30min Deep Note

深入分析方法细节、训练数据、模型结构、实验可信度、Ablation 充分性、Hidden weakness、可复现性判断、Follow-up 建议。

## 项目结构

```
paper_agent/
├── core/
│   ├── api_client.py        # OpenAI + DeepXiv API 客户端
│   ├── arxiv_ids.py         # arXiv ID 解析
│   ├── conference_search.py # 会议论文搜索核心逻辑
│   ├── config.py            # 配置管理（从 .env 加载）
│   ├── file_utils.py        # 文件工具
│   ├── latex_processor.py   # LaTeX 源码下载、图片提取、上下文提取
│   ├── logger.py            # 日志
│   ├── paper_processor.py   # 论文处理主流程
│   ├── pdf_processor.py     # PDF 下载与图片提取
│   ├── retry.py             # 重试装饰器
│   └── utils.py             # 工具函数
├── generators/
│   ├── card_generator.py    # 10min Card 生成
│   ├── figure_analyzer.py   # 图表上下文分析
│   ├── note_generator.py    # 30min Deep Note 生成
│   └── report_generator.py  # 调研报告生成
├── tools/
│   ├── conference_search.py         # 会议论文搜索 CLI
│   ├── multi_venue_sweep.py         # 多会议一次扫描
│   ├── filter_lvlm_papers.py        # LVLM/MLLM 论文过滤
│   ├── merge_and_filter_lvlm.py     # 跨会议合并去重
│   ├── refresh_arxiv_snapshot.py    # Kaggle arXiv 快照定时刷新
│   ├── survey_synthesis.py          # LLM 综述报告
│   └── survey_synthesis_detailed.py # 分阶段详细综述报告
├── configs/
│   └── conferences.json     # 会议别名、分类、排除词配置
├── tests/                   # 单元测试
├── main.py                  # 入口
├── requirements.txt
├── papers.txt.example       # 论文 ID 列表示例
└── .env.example
```

## 性能

双层并行优化（论文级 + 生成器级）：

| 论文数量 | 串行 | 并行 | 提升 |
|---------|------|------|------|
| 5 篇 | ~13 min | ~4 min | 69% |
| 20 篇 | ~50 min | ~15 min | 70% |

## 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## 依赖

- [DeepXiv](https://deepxiv.com) — 论文搜索与解析 API
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF 处理
- [OpenAI SDK](https://github.com/openai/openai-python) — LLM 调用（兼容任意 OpenAI 接口）

## License

MIT
