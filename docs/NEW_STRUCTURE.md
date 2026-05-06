# 新项目结构说明

## 目录结构

```
paper_agent/
├── core/                           # 核心功能模块
│   ├── __init__.py
│   ├── api_client.py              # API 客户端封装（OpenAI + DeepXiv）
│   ├── config.py                  # 配置管理和验证
│   ├── file_utils.py              # 文件工具函数
│   ├── latex_processor.py         # LaTeX 源码处理
│   ├── logger.py                  # 日志系统
│   ├── paper_processor.py         # 论文处理主流程
│   ├── pdf_processor.py           # PDF 处理和图片提取
│   └── retry.py                   # 重试机制
│
├── generators/                     # 内容生成器模块
│   ├── __init__.py
│   ├── card_generator.py          # 10min Card 生成器
│   ├── note_generator.py          # 30min Deep Note 生成器
│   └── report_generator.py        # 调研报告生成器
│
├── tests/                          # 单元测试
│   ├── __init__.py
│   ├── test_config.py             # 配置测试
│   ├── test_file_utils.py         # 文件工具测试
│   └── test_retry.py              # 重试机制测试
│
├── docs/                           # 文档目录
│   ├── IMPROVEMENTS.md            # 代码改进说明（新）
│   ├── MIGRATION.md               # 迁移指南（新）
│   ├── EXAMPLE_OUTPUT.md          # 示例输出
│   ├── SUMMARY.md                 # 功能总结
│   ├── PARALLEL_OPTIMIZATION.md   # 并行优化
│   ├── FIGURE_LINKS_FIX.md       # 图片链接修复
│   ├── QUICK_START.md            # 快速开始
│   └── PROJECT_CHECKLIST.md      # 项目检查清单
│
├── outputs/                        # 输出目录（自动生成）
│   ├── cards/                     # 10min Paper Cards
│   ├── deep_notes/                # 30min Deep Notes
│   ├── pdfs/                      # PDF 文件
│   ├── figures/                   # 提取的图片
│   ├── latex_sources/             # LaTeX 源码
│   └── reports/                   # 调研报告
│
├── logs/                           # 日志目录（自动生成）
│   ├── paper_agent.log            # 主日志文件（新）
│   ├── {arxiv_id}_material.json   # 论文材料缓存
│   └── search_{query}.json        # 搜索结果缓存
│
├── main.py                         # 新的主程序入口（推荐）
├── batch_read_deepxiv_with_pdf.py # 旧版本主程序（保留）
├── regenerate_card_with_figures.py # 重新生成工具
├── batch_regenerate_cards.py      # 批量重新生成工具
├── fix_figure_links.py            # 图片链接修复工具
│
├── requirements.txt                # 生产依赖
├── requirements-dev.txt            # 开发依赖（新）
├── .env.example                    # 环境变量示例
├── .env                            # 环境变量配置
├── .gitignore                      # Git 忽略文件
│
├── README.md                       # 项目说明（中文）
├── README_EN.md                    # 项目说明（英文）
├── PROJECT_STRUCTURE.md            # 项目结构说明
├── CONTRIBUTING.md                 # 贡献指南
├── CHANGELOG.md                    # 更新日志
└── LICENSE                         # MIT 许可证
```

## 模块说明

### core/ - 核心功能模块

#### api_client.py
封装 API 调用，提供统一接口：
- `OpenAIClient` - OpenAI API 客户端，内置重试逻辑
- `DeepXivClient` - DeepXiv API 客户端，内置重试逻辑

**特性：**
- 自动重试失败的请求
- 统一的错误处理
- 详细的日志记录

#### config.py
配置管理和验证：
- `OpenAIConfig` - OpenAI API 配置
- `DeepXivConfig` - DeepXiv API 配置
- `SearchConfig` - 搜索参数配置
- `ProcessingConfig` - 处理参数配置
- `Config` - 主配置容器

**特性：**
- 类型安全的配置
- 自动验证参数
- 清晰的错误提示

#### logger.py
日志系统：
- `setup_logger()` - 初始化日志系统
- `get_logger()` - 获取日志实例

**特性：**
- 控制台和文件双输出
- 统一的日志格式
- 可配置的日志级别

#### retry.py
重试机制：
- `retry_on_exception()` - 重试装饰器

**特性：**
- 指数退避策略
- 可配置重试次数
- 支持特定异常过滤
- 支持重试回调

#### pdf_processor.py
PDF 处理：
- `PDFProcessor.download_pdf()` - 下载 PDF
- `PDFProcessor.extract_figures_from_pdf()` - 提取图片
- `PDFProcessor.detect_column_layout()` - 检测页面布局
- `PDFProcessor.find_figure_regions()` - 查找图片区域

**特性：**
- 智能识别图片区域
- 包含 caption 提取
- 支持单双栏布局

#### latex_processor.py
LaTeX 处理：
- `LaTeXProcessor.download_latex_source()` - 下载 LaTeX 源码
- `LaTeXProcessor.extract_figures_from_latex()` - 从 LaTeX 提取图片

**特性：**
- 解析 LaTeX 图片引用
- 提取 caption 和 label
- 自动转换格式

#### paper_processor.py
论文处理主流程：
- `PaperProcessor.get_paper_material()` - 获取论文材料
- `PaperProcessor.process()` - 处理单篇论文

**特性：**
- 统一的处理流程
- 缓存机制
- 错误恢复

#### file_utils.py
文件工具：
- `safe_filename()` - 生成安全的文件名

### generators/ - 内容生成器模块

#### card_generator.py
10min Card 生成器：
- `CardGenerator.generate()` - 生成 Card 内容
- `CardGenerator.save()` - 保存 Card 文件

#### note_generator.py
30min Deep Note 生成器：
- `NoteGenerator.generate()` - 生成 Note 内容
- `NoteGenerator.save()` - 保存 Note 文件

#### report_generator.py
调研报告生成器：
- `ReportGenerator.generate()` - 生成报告内容
- `ReportGenerator.save()` - 保存报告文件

### tests/ - 单元测试

- `test_config.py` - 配置管理测试（14 个测试）
- `test_retry.py` - 重试机制测试（6 个测试）
- `test_file_utils.py` - 文件工具测试（8 个测试）

**运行测试：**
```bash
pytest tests/ -v
```

## 设计原则

### 1. 单一职责原则
每个模块只负责一个功能领域：
- `api_client.py` 只负责 API 调用
- `pdf_processor.py` 只负责 PDF 处理
- `card_generator.py` 只负责 Card 生成

### 2. 依赖注入
通过构造函数注入依赖，便于测试：
```python
processor = PaperProcessor(
    deepxiv_client=deepxiv_client,
    card_generator=card_gen,
    note_generator=note_gen,
    ...
)
```

### 3. 错误处理
- 使用装饰器实现重试逻辑
- 详细的日志记录
- 不因单个失败而中断整体流程

### 4. 配置管理
- 使用 dataclass 进行类型安全的配置
- 自动验证配置参数
- 清晰的错误提示

### 5. 可测试性
- 模块化设计便于单元测试
- 依赖注入便于 mock
- 28 个单元测试覆盖核心功能

## 与旧版本的对比

### 旧版本（batch_read_deepxiv_with_pdf.py）
- 单文件 892 行
- 所有功能混在一起
- 使用 print() 输出
- 缺少错误处理
- 难以测试

### 新版本（main.py + core/ + generators/）
- 模块化设计，职责清晰
- 标准日志系统
- 完善的错误处理和重试
- 28 个单元测试
- 易于维护和扩展

## 兼容性

新旧版本**完全兼容**：
- ✅ 共享相同的 .env 配置
- ✅ 共享相同的输出目录
- ✅ 共享相同的缓存机制
- ✅ 可以同时使用

## 迁移建议

1. **先测试新版本**
   ```bash
   export LIMIT=2
   python main.py
   ```

2. **验证输出**
   - 检查 `outputs/` 目录
   - 查看 `logs/paper_agent.log`

3. **正式使用**
   ```bash
   python main.py
   ```

4. **如有问题，随时回退**
   ```bash
   python batch_read_deepxiv_with_pdf.py
   ```

详见 [docs/MIGRATION.md](./MIGRATION.md)
