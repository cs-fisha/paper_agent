# Paper Agent

[English](./README_EN.md) | 简体中文

一个基于 LLM 的智能论文阅读助手，可以自动从 arXiv 搜索论文、下载 PDF、提取图片，并生成结构化的阅读笔记。

## ✨ 特性

- 🔍 **智能搜索**：基于 DeepXiv API 搜索 arXiv 论文
- 📄 **自动下载**：自动下载论文 PDF 文件
- 🖼️ **图片提取**：从 PDF 中智能提取关键图表（包含 caption）
- 📝 **双层笔记**：
  - **10min Card**：快速了解论文核心内容
  - **30min Deep Note**：深度分析论文细节
- 🎯 **图表分析**：对每张图进行详细分析（内容、创新点、逻辑严密性）
- ⚡ **并行处理**：Card 和 Deep Note 完全并行生成，速度提升 70%
- 📊 **调研报告**：批量处理后自动生成综合调研报告

## 📦 安装

### 1. 克隆仓库

```bash
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

需要的主要依赖：
- `openai` - OpenAI API 客户端
- `deepxiv-sdk` - DeepXiv API 客户端
- `PyMuPDF` (fitz) - PDF 处理
- `Pillow` - 图像处理
- `python-dotenv` - 环境变量管理

### 3. 配置环境变量

复制 `.env.example` 到 `.env` 并填写配置：

```bash
cp .env.example .env
```

然后编辑 `.env` 文件：

```bash
# OpenAI API 配置
OPENAI_API_KEY=your_api_key_here          # 你的 API Key
OPENAI_BASE_URL=https://api.openai.com/v1 # API 基础 URL
MODEL_NAME=gpt-4                           # 使用的模型名称

# DeepXiv API 配置
DEEPXIV_TOKEN=your_deepxiv_token_here     # DeepXiv Token

# 搜索配置
QUERY="multimodal LVLM MLLM"              # 搜索关键词
LIMIT=5                                    # 论文数量
DATE_FROM=2025-01-01                       # 起始日期
CATEGORIES=cs.CV,cs.CL                     # arXiv 分类

# 处理配置
MAX_WORKERS=8                              # 并行线程数
DOWNLOAD_PDF=true                          # 是否下载 PDF
EXTRACT_FIGURES=true                       # 是否提取图片
GENERATE_DEEP_NOTE=true                    # 是否生成 Deep Note
```

## 🚀 使用方法

### 基本用法

```bash
python batch_read_deepxiv_with_pdf.py
```

这将：
1. 根据 `QUERY` 搜索 arXiv 论文
2. 下载 PDF 文件
3. 提取关键图表
4. 并行生成 Card 和 Deep Note
5. 生成综合调研报告

### 高级用法

#### 只生成 Card（快速预览）

```bash
export GENERATE_DEEP_NOTE=false
python batch_read_deepxiv_with_pdf.py
```

#### 重新生成单个论文

```bash
python regenerate_card_with_figures.py 2602.08145
```

#### 批量重新生成所有论文

```bash
python batch_regenerate_cards.py
```

## 📊 环境变量详解

### OpenAI API 配置

| 变量 | 必填 | 说明 | 示例 |
|-----|------|------|------|
| `OPENAI_API_KEY` | ✅ | OpenAI API Key | `sk-...` |
| `OPENAI_BASE_URL` | ✅ | API 基础 URL | `https://api.openai.com/v1` |
| `MODEL_NAME` | ✅ | 使用的模型 | `gpt-4`, `gpt-3.5-turbo` |

**获取方式**：
- 官方 OpenAI：访问 https://platform.openai.com/api-keys
- 第三方代理：从你的 API 提供商获取

### DeepXiv API 配置

| 变量 | 必填 | 说明 | 示例 |
|-----|------|------|------|
| `DEEPXIV_TOKEN` | ✅ | DeepXiv API Token | `ilY0FVk...` |

**获取方式**：
1. 访问 https://deepxiv.com
2. 注册账号
3. 在个人设置中获取 API Token

### 搜索配置

| 变量 | 必填 | 默认值 | 说明 |
|-----|------|--------|------|
| `QUERY` | ❌ | `"multimodal LVLM MLLM"` | 搜索关键词，支持多个词组合 |
| `LIMIT` | ❌ | `5` | 搜索返回的论文数量 |
| `DATE_FROM` | ❌ | `2025-06-01` | 论文发布日期起始点（YYYY-MM-DD） |
| `CATEGORIES` | ❌ | `cs.CV,cs.CL` | arXiv 分类，逗号分隔 |

**常用 arXiv 分类**：
- `cs.CV` - Computer Vision（计算机视觉）
- `cs.CL` - Computation and Language（自然语言处理）
- `cs.AI` - Artificial Intelligence（人工智能）
- `cs.LG` - Machine Learning（机器学习）
- `cs.CR` - Cryptography and Security（密码学与安全）
- `cs.RO` - Robotics（机器人）
- `cs.NE` - Neural and Evolutionary Computing（神经与进化计算）

完整分类列表：https://arxiv.org/category_taxonomy

### 处理配置

| 变量 | 必填 | 默认值 | 说明 |
|-----|------|--------|------|
| `MAX_WORKERS` | ❌ | `8` | 并行处理的线程数 |
| `DOWNLOAD_PDF` | ❌ | `true` | 是否下载 PDF 文件 |
| `EXTRACT_FIGURES` | ❌ | `true` | 是否从 PDF 提取图片 |
| `GENERATE_DEEP_NOTE` | ❌ | `true` | 是否生成 Deep Note |

**MAX_WORKERS 设置建议**：

| 论文数量 | 推荐值 | 说明 |
|---------|-------|------|
| 1-5     | 4-8   | 充分利用并行 |
| 6-20    | 8-12  | 平衡速度和资源 |
| 20+     | 8-16  | 避免 API 限流 |

⚠️ **注意**：
- 如果遇到 API 限流错误，降低 `MAX_WORKERS`
- 每个 worker 会占用内存，根据机器配置调整
- 设置 `GENERATE_DEEP_NOTE=false` 可以只生成 Card，速度更快

## 📁 输出结构

```
outputs/
├── cards/              # 10min Paper Cards
│   └── 2602.08145_Paper_Title.md
├── deep_notes/         # 30min Deep Notes
│   └── 2602.08145_Paper_Title.md
├── pdfs/              # 下载的 PDF 文件
│   └── 2602.08145.pdf
├── figures/           # 提取的图片
│   └── 2602.08145/
│       ├── fig_1_page2.png
│       ├── fig_2_page2.png
│       └── ...
└── reports/           # 调研报告
    └── query_timestamp/
        ├── survey_report.md
        └── materials/
```

## 📝 输出格式

### 10min Paper Card

包含以下部分：
1. 一句话结论
2. 论文想解决的问题
3. 核心方法
4. 和已有工作的主要区别
5. 实验设置
6. 关键结果
7. **最值得看的图/表/实验** ⭐（包含图片链接和详细分析）
8. 可能的问题或漏洞
9. 对我的科研方向是否有用
10. 如果只读 30 分钟，应该优先读哪些部分

### 30min Deep Note

包含以下部分：
1. 论文主张与真实贡献
2. 方法细节拆解
3. 训练数据 / 偏好数据 / 标注方式
4. 模型结构或 pipeline
5. 实验结果是否可信
6. Ablation / Analysis 是否充分
7. **最值得看的图/表/实验** ⭐
8. 可能的 hidden weakness
9. 和我的方向的关系
10. 可复现性判断
11. 我如果要 follow，可以怎么做

### 图表分析格式

每张图都包含：
- **图片说明了什么**：2-3 句话描述图的内容
- **如何体现论文创新**：2-3 句话说明这个图如何支撑论文的核心贡献
- **逻辑严密性**：1-2 句话评价图的设计是否合理
- **只看图能理解多少**：给出百分比并简要说明

## ⚡ 性能

### 并行处理优化

通过完全并行化 Card 和 Deep Note 生成，实现了显著的性能提升：

| 论文数量 | 优化前 | 优化后 | 提升 |
|---------|-------|-------|------|
| 5 篇    | 13 分钟 | 4 分钟 | **69% ⬇️** |
| 20 篇   | 50 分钟 | 15 分钟 | **70% ⬇️** |

详见 [docs/PARALLEL_OPTIMIZATION.md](./docs/PARALLEL_OPTIMIZATION.md)

## 📚 文档

- [docs/EXAMPLE_OUTPUT.md](./docs/EXAMPLE_OUTPUT.md) - 示例输出展示
- [docs/SUMMARY.md](./docs/SUMMARY.md) - 完整功能总结
- [docs/PARALLEL_OPTIMIZATION.md](./docs/PARALLEL_OPTIMIZATION.md) - 并行优化详解
- [docs/FIGURE_LINKS_FIX.md](./docs/FIGURE_LINKS_FIX.md) - 图片链接修复说明
- [docs/QUICK_START.md](./docs/QUICK_START.md) - 快速开始指南
- [PROJECT_STRUCTURE.md](./PROJECT_STRUCTURE.md) - 项目结构说明
- [CONTRIBUTING.md](./CONTRIBUTING.md) - 贡献指南
- [CHANGELOG.md](./CHANGELOG.md) - 更新日志

## 🛠️ 工具脚本

- `batch_read_deepxiv_with_pdf.py` - 主程序
- `regenerate_card_with_figures.py` - 重新生成单个论文
- `batch_regenerate_cards.py` - 批量重新生成
- `fix_figure_links.py` - 使用 vision API 的备用方案

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License

## 🙏 致谢

- [DeepXiv](https://deepxiv.com) - 提供论文搜索和解析 API
- [PyMuPDF](https://pymupdf.readthedocs.io/) - PDF 处理库
- [OpenAI](https://openai.com) - LLM API

## ⚠️ 注意事项

1. **API 费用**：使用 OpenAI API 会产生费用，请注意控制 `LIMIT` 和 `MAX_WORKERS`
2. **图片编号**：自动提取的图片编号可能与论文实际编号不完全对应
3. **网络要求**：需要稳定的网络连接来访问 arXiv 和 API
4. **存储空间**：PDF 和图片会占用存储空间，定期清理 `outputs/` 目录

## 📮 联系方式

如有问题或建议，请提交 Issue 或联系作者。
