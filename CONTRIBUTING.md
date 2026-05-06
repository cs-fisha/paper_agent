# 贡献指南 / Contributing Guide

[English](#english) | [简体中文](#简体中文)

---

## 简体中文

感谢你考虑为 Paper Agent 做出贡献！

### 如何贡献

#### 报告 Bug

如果你发现了 bug，请：

1. 检查 [Issues](https://github.com/yourusername/paper_agent/issues) 确认问题是否已被报告
2. 如果没有，创建一个新的 Issue，包含：
   - 清晰的标题和描述
   - 复现步骤
   - 预期行为和实际行为
   - 环境信息（Python 版本、操作系统等）
   - 相关的日志或截图

#### 提出新功能

如果你有新功能的想法：

1. 先创建一个 Issue 讨论这个功能
2. 说明为什么需要这个功能
3. 描述你期望的行为
4. 如果可能，提供实现思路

#### 提交代码

1. Fork 这个仓库
2. 创建你的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交你的改动 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建一个 Pull Request

### 代码规范

- 使用 Python 3.8+ 语法
- 遵循 PEP 8 代码风格
- 添加必要的注释和文档字符串
- 确保代码通过现有测试
- 如果添加新功能，请添加相应的测试

### 提交信息规范

使用清晰的提交信息：

- `feat: 添加新功能`
- `fix: 修复 bug`
- `docs: 更新文档`
- `style: 代码格式调整`
- `refactor: 代码重构`
- `test: 添加测试`
- `chore: 构建或辅助工具的变动`

### 开发环境设置

```bash
# 克隆你的 fork
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入你的配置

# 运行测试
python batch_read_deepxiv_with_pdf.py
```

### 问题和讨论

如果你有任何问题或想法，欢迎：

- 创建 Issue
- 参与现有的讨论
- 联系维护者

---

## English

Thank you for considering contributing to Paper Agent!

### How to Contribute

#### Reporting Bugs

If you find a bug:

1. Check [Issues](https://github.com/yourusername/paper_agent/issues) to see if it's already reported
2. If not, create a new Issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment info (Python version, OS, etc.)
   - Relevant logs or screenshots

#### Suggesting Features

If you have an idea for a new feature:

1. Create an Issue to discuss the feature first
2. Explain why this feature is needed
3. Describe the expected behavior
4. If possible, provide implementation ideas

#### Submitting Code

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Create a Pull Request

### Code Standards

- Use Python 3.8+ syntax
- Follow PEP 8 style guide
- Add necessary comments and docstrings
- Ensure code passes existing tests
- Add tests for new features

### Commit Message Convention

Use clear commit messages:

- `feat: add new feature`
- `fix: fix bug`
- `docs: update documentation`
- `style: code formatting`
- `refactor: code refactoring`
- `test: add tests`
- `chore: build or auxiliary tool changes`

### Development Setup

```bash
# Clone your fork
git clone https://github.com/yourusername/paper_agent.git
cd paper_agent

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your configuration

# Run tests
python batch_read_deepxiv_with_pdf.py
```

### Questions and Discussions

If you have questions or ideas:

- Create an Issue
- Join existing discussions
- Contact maintainers

---

Thank you for your contribution! 🎉
