# Paper Agent

[English](./README_EN.md) | 简体中文

基于 LLM 的智能论文阅读助手，自动搜索、下载、提取图片并生成结构化笔记。

## ✨ 核心功能

- 🔍 **智能搜索**：基于 DeepXiv API 搜索 arXiv 论文
- 📄 **自动下载**：PDF + LaTeX 源码
- 🖼️ **图片提取**：LaTeX 源码优先（高质量）→ PDF fallback
- 📝 **三层笔记**（按顺序生成）：
  1. **10min Card**：快速了解核心内容（默认开启）
  2. **图表分析**：每张图的深度解读（默认开启）
  3. **30min Deep Note**：深度分析方法细节（默认关闭）
- ⚡ **并行处理**：70% 性能提升
- 📊 **调研报告**：批量处理后自动生成

## 📦 快速开始

### 1. 安装

```bash
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 到 `.env` 并填写：

```bash
# OpenAI API
OPENAI_API_KEY=your_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4

# DeepXiv API
DEEPXIV_TOKEN=your_token

# 搜索配置
QUERY="multimodal LVLM MLLM"
LIMIT=5
DATE_FROM=2025-01-01
CATEGORIES=cs.CV,cs.CL

# 处理配置
MAX_WORKERS=8
DOWNLOAD_PDF=true
EXTRACT_FIGURES=true
GENERATE_DEEP_NOTE=false  # 30min深度笔记（默认关闭）
ANALYZE_FIGURES=true      # 图表分析（默认开启）
```

### 3. 运行

```bash
python main.py
```

## 📁 输出结构

```
outputs/
├── cards/              # 10min Paper Cards
├── deep_notes/         # 30min Deep Notes
├── figure_analysis/    # 图表上下文分析（NEW）
├── pdfs/              # PDF 文件
├── figures/           # 提取的图片
│   └── {arxiv_id}/
├── latex_sources/     # LaTeX 源码
└── reports/           # 调研报告
    └── {query}_{timestamp}/
```

## 📝 输出格式

### 10min Card

- 一句话结论
- 核心问题与方法
- 实验设置与结果
- **最值得看的图/表** ⭐（带详细分析）
- 可能的问题
- 对我的方向是否有用（A/B/C/D）
- 阅读建议

### 30min Deep Note

- 论文主张与真实贡献
- 方法细节拆解
- 训练数据/模型结构
- 实验可信度
- Ablation 充分性
- **最值得看的图/表** ⭐
- Hidden weakness
- 可复现性判断
- Follow-up 建议

### 图表上下文分析（NEW）

对每张图表：
- **图表内容**：描述图表展示了什么
- **作者意图**：作者放这张图的目的
- **论文中的作用**：如何支撑核心观点
- **上下文分析**：基于 LaTeX 源码中的引用上下文分析

## ⚡ 性能

| 论文数量 | 优化前 | 优化后 | 提升 |
|---------|-------|-------|------|
| 5 篇    | 13 分钟 | 4 分钟 | **69% ⬇️** |
| 20 篇   | 50 分钟 | 15 分钟 | **70% ⬇️** |

## 🏗️ 项目结构

```
paper_agent/
├── core/              # 核心模块
│   ├── api_client.py      # API 客户端
│   ├── config.py          # 配置管理
│   ├── paper_processor.py # 论文处理
│   ├── pdf_processor.py   # PDF 处理
│   ├── latex_processor.py # LaTeX 处理（含上下文提取）
│   └── ...
├── generators/        # 生成器
│   ├── card_generator.py
│   ├── note_generator.py
│   ├── report_generator.py
│   └── figure_analyzer.py  # 图表分析器（NEW）
├── tests/            # 单元测试
└── main.py           # 主程序
```

## 🧪 测试

```bash
pip install -r requirements-dev.txt
pytest tests/ -v
```

## 📄 许可证

MIT License

## 🙏 致谢

- [DeepXiv](https://deepxiv.com) - 论文搜索和解析 API
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF 处理
- [OpenAI](https://openai.com) - LLM API

## ⚠️ 注意

1. **API 费用**：使用 OpenAI API 会产生费用
2. **网络要求**：需要稳定的网络连接
3. **存储空间**：PDF 和图片会占用存储空间
