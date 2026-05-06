# 项目结构 / Project Structure

```
paper_agent/
├── README.md                           # 项目说明（中文）
├── README_EN.md                        # 项目说明（英文）
├── LICENSE                             # MIT 许可证
├── CONTRIBUTING.md                     # 贡献指南
├── requirements.txt                    # Python 依赖
├── .env.example                        # 环境变量示例
├── .gitignore                          # Git 忽略文件
│
├── batch_read_deepxiv_with_pdf.py     # 主程序：批量处理论文
├── regenerate_card_with_figures.py    # 工具：重新生成单个论文
├── batch_regenerate_cards.py          # 工具：批量重新生成所有论文
├── fix_figure_links.py                # 工具：使用 vision API 修复图片链接（备用）
│
├── docs/                               # 文档目录
│   ├── SUMMARY.md                      # 完整功能总结
│   ├── PARALLEL_OPTIMIZATION.md        # 并行优化详解
│   ├── FIGURE_LINKS_FIX.md            # 图片链接修复说明
│   └── QUICK_START.md                  # 快速开始指南
│
├── outputs/                            # 输出目录（自动生成）
│   ├── cards/                          # 10min Paper Cards
│   ├── deep_notes/                     # 30min Deep Notes
│   ├── pdfs/                           # 下载的 PDF 文件
│   ├── figures/                        # 提取的图片
│   │   └── {arxiv_id}/                 # 每篇论文的图片目录
│   │       ├── fig_1_page2.png
│   │       ├── fig_2_page2.png
│   │       └── ...
│   └── reports/                        # 调研报告
│       └── {query}_{timestamp}/
│           ├── survey_report.md
│           └── materials/
│
└── logs/                               # 日志目录（自动生成）
    ├── {arxiv_id}_material.json        # 论文材料缓存
    └── search_{query}.json             # 搜索结果缓存
```

## 核心文件说明

### 主程序

- **`batch_read_deepxiv_with_pdf.py`**
  - 主程序，批量处理论文
  - 功能：搜索、下载、提取图片、生成笔记
  - 支持完全并行处理

### 工具脚本

- **`regenerate_card_with_figures.py`**
  - 重新生成单个论文的 card 和 deep note
  - 用于修复或更新已处理的论文

- **`batch_regenerate_cards.py`**
  - 批量重新生成所有已处理的论文
  - 用于批量更新

- **`fix_figure_links.py`**
  - 使用 vision API 分析图片并修复链接
  - 备用方案，目前有一些问题

### 配置文件

- **`.env.example`**
  - 环境变量模板
  - 包含所有配置项的说明

- **`requirements.txt`**
  - Python 依赖列表
  - 使用 `pip install -r requirements.txt` 安装

### 文档

- **`docs/SUMMARY.md`**
  - 完整的功能总结和优化说明

- **`docs/PARALLEL_OPTIMIZATION.md`**
  - 并行处理优化的详细说明
  - 性能对比和配置建议

- **`docs/FIGURE_LINKS_FIX.md`**
  - 图片链接修复的详细说明
  - 问题分析和解决方案

- **`docs/QUICK_START.md`**
  - 快速开始指南
  - 常用命令和示例

## 输出文件说明

### Cards (10min Paper Card)

快速阅读笔记，包含：
- 论文核心内容总结
- 关键图表分析（带图片链接）
- 适合 10 分钟快速了解论文

### Deep Notes (30min Deep Note)

深度阅读笔记，包含：
- 详细的方法分析
- 实验可信度评估
- 可复现性判断
- 适合 30 分钟深入理解论文

### Figures

从 PDF 提取的图片：
- 自动识别图片区域
- 包含 caption
- 按论文 ID 分目录存储

### Reports

综合调研报告：
- 多篇论文的横向对比
- 技术趋势分析
- 研究空白识别

## 缓存机制

### Material Cache (`logs/{arxiv_id}_material.json`)

缓存论文材料，避免重复请求：
- 论文元数据
- 各个章节内容
- 加速重新生成过程

### Search Cache (`logs/search_{query}.json`)

缓存搜索结果：
- 搜索返回的论文列表
- 用于调试和分析
