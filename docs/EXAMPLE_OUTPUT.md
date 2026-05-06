# 示例输出 / Example Output

本文档展示 Paper Agent 生成的各类输出示例。

## 10min Paper Card 示例

### Section 7: 最值得看的图/表/实验

这是 Card 中最重要的部分，包含图片链接和详细分析：

```markdown
## 7. 最值得看的图/表/实验 ⭐

### Figure 1: Overview of reliable and responsible foundation models

![Figure 1](figures/2602.08145/fig_1_page2.png)

**图片说明了什么**：
这是全文的核心框架图，展示了九大维度（偏见与公平、对齐、安全、隐私、
幻觉、不确定性、分布偏移、可解释性、AIGC检测）如何与四类基础模型
（LLM、MLLM、图像生成、视频生成）交互。图中用不同颜色和连接线表示
各维度之间的相互影响关系。

**如何体现论文创新**：
这张图直观地展示了本文的核心贡献——**首次提供跨模态、跨维度的统一
分析框架**。与已有综述不同，本文不仅列举问题，还通过可视化揭示了
维度间的协同效应（如安全与隐私的耦合、幻觉与不确定性的关联）。这种
系统性视角是现有文献所缺乏的。

**逻辑严密性**：
图的设计合理，清晰地传达了复杂的多维关系。但连接线的具体含义（是
因果关系还是相关性？）未在图中明确标注，需结合正文理解。此外，四类
模型的排列顺序（LLM→MLLM→图像→视频）暗示了技术演进路径，但这一
逻辑未在图例中显式说明。

**只看图能理解多少**：约60%
- 可以理解：九大维度的分类、四类模型的覆盖范围、维度间存在交叉影响
- 无法理解：具体的交叉影响机制（如为何对抗训练会影响公平性）、每个
  维度在不同模型中的具体表现差异

---

### Figure 2: Foundation models pipeline and reliability issues

![Figure 2](figures/2602.08145/fig_2_page2.png)

**图片说明了什么**：
这张图展示了基础模型的完整生命周期：从多模态数据训练（文本、图像、
视频、音频）→预训练→下游应用适配（如对话、图像生成、视频生成）。
图中标注了在不同阶段可能出现的可靠性与责任性问题（如训练阶段的偏见、
部署阶段的幻觉等）。

**如何体现论文创新**：
这张图将可靠性问题**嵌入到模型开发的全流程**中，而非孤立讨论技术
细节。这种"全生命周期"视角对实际部署至关重要——它提醒研究者和
工程师，可靠性不是事后补救，而应贯穿设计、训练、部署的每个环节。

**逻辑严密性**：
图的流程清晰，但存在两个问题：
1. **阶段划分不够细致**：例如"下游应用"阶段未区分微调（fine-tuning）
   和推理（inference），而这两个阶段面临的挑战差异很大
2. **问题标注不完整**：图中仅标注了部分问题，但未覆盖所有九大维度在
   每个阶段的具体表现

**只看图能理解多少**：约70%
- 可以理解：基础模型的开发流程、问题出现的阶段性特征
- 无法理解：每个阶段具体的技术挑战和解决方案（需结合正文各章节）
```

## 30min Deep Note 示例

### 图表详解部分

Deep Note 末尾包含所有提取的图片：

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

### Figure 3 (Page 2)

![Figure 3](figures/2602.08145/fig_3_page2.png)

**位置**：第 2 页

---
```

## Survey Report 示例

批量处理后生成的综合调研报告：

```markdown
# 调研报告：LVLM MLLM adversarial attack

## 1. 整体概览

- 论文总数：16
- 主要研究方向分布：
  - 对抗攻击与防御（8篇）
  - 鲁棒性评估（4篇）
  - 越狱攻击（3篇）
  - 安全性综述（1篇）
- 时间跨度：2025-06 至 2026-04

## 2. 核心技术趋势

### 趋势 1：Black-box 对抗攻击

**代表论文**：
- Paper A: Query-efficient black-box attack
- Paper B: Transfer-based attack

**核心思路**：
在不访问模型参数的情况下，通过查询或迁移生成对抗样本

**优缺点**：
- 优点：实用性强，适用于闭源模型
- 缺点：查询次数多，容易被检测

### 趋势 2：Imperceptible 攻击

**代表论文**：
- Paper C: Invisible perturbations
- Paper D: Semantic-preserving attacks

**核心思路**：
生成人眼难以察觉的扰动，同时保持语义不变

**优缺点**：
- 优点：隐蔽性强
- 缺点：攻击成功率相对较低

## 3. 重点论文推荐

1. **Paper A** (优先级：⭐⭐⭐⭐⭐)
   - 理由：首次提出 query-efficient 方法，实用性强

2. **Paper B** (优先级：⭐⭐⭐⭐)
   - 理由：comprehensive benchmark，适合了解领域全貌

3. **Paper C** (优先级：⭐⭐⭐)
   - 理由：创新的 imperceptible 方法

## 4. 方法对比与差异

| 论文 | 攻击类型 | 数据集 | 成功率 | 查询次数 |
|-----|---------|--------|--------|---------|
| Paper A | Black-box | COCO | 85% | 100 |
| Paper B | White-box | ImageNet | 95% | - |
| Paper C | Transfer | Custom | 70% | 50 |

## 5. 研究空白与机会

1. **多模态联合攻击**：现有工作多关注单模态，跨模态攻击研究不足
2. **防御机制**：攻击方法多，但有效的防御手段少
3. **真实场景评估**：大多在学术数据集上测试，缺乏真实应用场景验证

## 6. 对我的科研方向的启发

- 可以探索 training-free 的防御方法
- 结合 test-time adaptation 提升鲁棒性
- 关注 black-box 场景下的高效攻击
```

## 文件结构示例

```
outputs/
├── cards/
│   ├── 2602.08145_Reliable_and_Responsible_Foundation_Models.md
│   ├── 2601.06169_Think_Bright_Diffuse_Nice.md
│   └── ...
├── deep_notes/
│   ├── 2602.08145_Reliable_and_Responsible_Foundation_Models.md
│   ├── 2601.06169_Think_Bright_Diffuse_Nice.md
│   └── ...
├── pdfs/
│   ├── 2602.08145.pdf
│   ├── 2601.06169.pdf
│   └── ...
├── figures/
│   ├── 2602.08145/
│   │   ├── fig_1_page2.png
│   │   ├── fig_2_page2.png
│   │   └── ...
│   └── 2601.06169/
│       ├── fig_1_page3.png
│       └── ...
└── reports/
    └── LVLM_MLLM_adversarial_attack_20260506_163000/
        ├── survey_report.md
        └── materials/
            ├── 2602.08145_material.json
            └── ...
```

## 使用建议

1. **快速浏览**：先看 Card 的 Section 7，通过图片快速了解论文核心
2. **深入理解**：阅读 Deep Note，结合图片理解方法细节
3. **横向对比**：查看 Survey Report，了解领域全貌
4. **原文阅读**：对于重点论文，打开 PDF 深入阅读

## 注意事项

- 图片编号可能与论文实际编号不完全对应，需要结合 caption 判断
- 图片分析基于 LLM 对论文材料的理解，建议结合原文验证
- 如果图片提取失败，可以手动从 PDF 中截图补充
