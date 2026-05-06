# 快速迁移指南

## 从旧版本迁移到新版本

### 1. 安装新依赖

```bash
pip install -r requirements.txt
```

新增依赖：
- `tqdm` - 进度条显示

### 2. 使用方式对比

#### 旧版本
```bash
python batch_read_deepxiv_with_pdf.py
```

#### 新版本
```bash
python main.py
```

### 3. 配置文件

配置文件 `.env` **完全兼容**，无需修改。

### 4. 输出文件

输出目录结构**完全相同**：
```
outputs/
├── cards/              # 10min Paper Cards
├── deep_notes/         # 30min Deep Notes
├── pdfs/              # PDF 文件
├── figures/           # 提取的图片
├── latex_sources/     # LaTeX 源码
└── reports/           # 调研报告
```

### 5. 新增功能

#### 日志文件
新版本会在 `logs/paper_agent.log` 生成详细日志：
```
2026-05-06 19:30:15 - paper_agent - INFO - Paper Agent Started
2026-05-06 19:30:15 - paper_agent - INFO - Search query: multimodal LVLM MLLM
2026-05-06 19:30:16 - paper_agent - INFO - Found 5 papers
2026-05-06 19:30:16 - paper_agent - INFO - Processing papers in parallel...
```

#### 进度条
新版本会显示实时进度：
```
Processing papers: 100%|████████████████| 5/5 [04:23<00:00, 52.7s/it]
```

#### 更好的错误处理
API 调用失败会自动重试（最多 3 次），并记录详细日志。

### 6. 兼容性保证

- ✅ 旧版本 `batch_read_deepxiv_with_pdf.py` 仍然保留
- ✅ 可以同时使用新旧版本
- ✅ 共享相同的缓存和输出目录
- ✅ 不会相互干扰

### 7. 推荐迁移步骤

1. **备份当前数据**（可选）
   ```bash
   cp -r outputs outputs_backup
   cp -r logs logs_backup
   ```

2. **安装新依赖**
   ```bash
   pip install -r requirements.txt
   ```

3. **测试新版本**
   ```bash
   # 先用小数量测试
   export LIMIT=2
   python main.py
   ```

4. **验证输出**
   - 检查 `outputs/cards/` 是否生成了新的 card
   - 检查 `logs/paper_agent.log` 是否有日志
   - 确认进度条是否正常显示

5. **正式使用**
   ```bash
   # 恢复正常配置
   export LIMIT=5
   python main.py
   ```

### 8. 回退方案

如果遇到问题，可以随时回退到旧版本：
```bash
python batch_read_deepxiv_with_pdf.py
```

旧版本功能完全不受影响。

### 9. 常见问题

#### Q: 新版本会覆盖旧版本的输出吗？
A: 不会。新旧版本使用相同的输出目录，但文件名基于 arxiv_id，不会冲突。

#### Q: 缓存是否兼容？
A: 完全兼容。新旧版本共享 `logs/` 目录下的缓存文件。

#### Q: 性能有变化吗？
A: 性能相同。新版本保持了原有的并行处理能力。

#### Q: 需要修改 .env 文件吗？
A: 不需要。配置文件完全兼容。

#### Q: 如何查看详细日志？
A: 查看 `logs/paper_agent.log` 文件，或在运行时观察控制台输出。

### 10. 获取帮助

如有问题：
1. 查看 `docs/IMPROVEMENTS.md` 了解详细改进
2. 查看 `logs/paper_agent.log` 了解错误详情
3. 运行测试：`pytest tests/ -v`
4. 提交 Issue 到项目仓库
