# 图片链接修复说明

## 问题描述

之前生成的 paper card 和 deep note 存在以下问题：

1. **图片未插入到正文中**：虽然代码提取了论文中的图片，但只是简单地附加在文档末尾，没有在"最值得看的图/表/实验"这一节中插入图片链接
2. **缺少图片分析**：即使提到了 Figure 1、Figure 2 等，但没有实际的图片链接和详细分析
3. **图片编号不匹配**：提取的图片文件名（如 `fig_1_page2.png`）与论文中的实际图号可能不对应

## 解决方案

### 1. 修改了 `batch_read_deepxiv_with_pdf.py`

**修改 `make_10min_card` 函数**：
- 在 prompt 中明确要求 LLM 在 section 7 插入图片链接
- 提供图片路径列表给 LLM
- 要求 LLM 对每个图片进行详细分析，包括：
  - 图片说明了什么
  - 如何体现论文创新
  - 逻辑严密性评价
  - 只看图能理解多少（百分比）

**修改 `make_30min_note` 函数**：
- 在 deep note 末尾添加"论文关键图表详解"部分
- 包含所有提取的图片及其位置信息
- 在 section 7 中也要求详细分析图表

### 2. 创建了 `regenerate_card_with_figures.py`

这个脚本用于重新生成单个论文的 card 和 deep note：

```bash
python regenerate_card_with_figures.py <arxiv_id>
```

例如：
```bash
python regenerate_card_with_figures.py 2602.08145
```

功能：
- 读取已保存的论文材料
- 查找提取的图片
- 使用新的 prompt 重新生成 card 和 deep note
- 确保图片正确链接到文档中

### 3. 创建了 `batch_regenerate_cards.py`

这个脚本用于批量重新生成所有已有的 cards：

```bash
python batch_regenerate_cards.py
```

功能：
- 扫描 `outputs/cards/` 目录下的所有 markdown 文件
- 提取 arxiv_id
- 并行重新生成所有 cards 和 deep notes

### 4. 创建了 `fix_figure_links.py`（备用方案）

这是一个使用 vision API 的高级方案，可以：
- 自动识别图片中的 caption 和图号
- 使用 vision API 分析图片内容
- 将分析结果插入到 markdown 中

但由于 vision API 调用可能有问题，目前推荐使用方案 2 和 3。

## 新的输出格式

### Card 的 Section 7 格式

```markdown
## 7. 最值得看的图/表/实验 ⭐

### Figure 1: Overview of reliable and responsible foundation models

![Figure 1](figures/2602.08145/fig_1_page2.png)

**图片说明了什么**：
这是全文的核心框架图，展示了九大维度...

**如何体现论文创新**：
这张图直观地展示了本文的核心贡献...

**逻辑严密性**：
图的设计合理，清晰地传达了复杂的多维关系...

**只看图能理解多少**：约60%
- 可以理解：九大维度的分类、四类模型的覆盖范围...
- 无法理解：具体的交叉影响机制...

---

### Figure 2: Foundation models pipeline

![Figure 2](figures/2602.08145/fig_2_page2.png)

...
```

### Deep Note 的图表部分

在文档末尾添加：

```markdown
## 论文关键图表详解

> **提示**：以下是从论文中提取的关键图表，结合正文理解效果更佳。

### Figure 1 (Page 2)

![Figure 1](figures/2602.08145/fig_1_page2.png)

**位置**：第 2 页

---

### Figure 2 (Page 2)

![Figure 2](figures/2602.08145/fig_2_page2.png)

**位置**：第 2 页

---
```

## 使用方法

### 对于新论文

直接运行 `batch_read_deepxiv_with_pdf.py`，新生成的 cards 和 deep notes 会自动包含正确的图片链接。

### 对于已有论文

#### 单个论文：
```bash
python regenerate_card_with_figures.py 2602.08145
```

#### 批量处理所有论文：
```bash
python batch_regenerate_cards.py
```

注意：批量处理会调用 LLM API，可能需要较长时间和费用。

## 验证

重新生成后，可以用 markdown 阅读器打开 card 文件，应该能看到：

1. Section 7 中有图片链接（`![Figure X](path/to/image.png)`）
2. 每个图片都有详细的分析说明
3. Deep note 末尾有完整的图表列表
4. 图片路径是相对路径，可以正确显示

## 注意事项

1. **图片编号可能不准确**：自动提取的图片编号（fig_1, fig_2...）可能与论文中的实际编号不完全对应，因为：
   - 论文可能有多栏布局
   - 图片可能跨页
   - 某些图片可能被识别为多个独立图片

2. **需要手动验证**：建议对重要论文手动检查生成的 card，确保图片编号和分析正确

3. **LLM 分析质量**：图片分析的质量取决于 LLM 对论文材料的理解，如果材料不足（如只有 abstract），分析可能不够深入

## 未来改进方向

1. 使用 vision API 直接分析图片内容，而不是仅依赖文本材料
2. 改进图片提取算法，更准确地识别图片编号和 caption
3. 支持表格的提取和分析
4. 添加图片质量检查（如分辨率、清晰度）
