# Markdown Viewer 使用指南

## 📚 功能介绍

Paper Agent Markdown Viewer 是一个专为查看论文笔记设计的 Web 界面，支持：

- ✅ **Markdown 渲染** - 完整的 Markdown 语法支持
- ✅ **LaTeX 公式** - 使用 KaTeX 渲染数学公式
- ✅ **代码高亮** - 使用 Highlight.js 高亮代码块
- ✅ **图片预览** - 自动加载论文图片
- ✅ **暗色主题** - GitHub 风格的暗色界面
- ✅ **文件浏览** - 按类型分组浏览所有笔记

## 🚀 快速开始

### 1. 启动服务器

```bash
cd paper_agent
python viewer/server.py
```

你会看到：
```
============================================================
📚 Paper Agent Markdown Viewer
============================================================
Server running at: http://localhost:8000
Open in browser:   http://localhost:8000/index.html
============================================================
Press Ctrl+C to stop the server
```

### 2. 打开浏览器

访问 http://localhost:8000/index.html

### 3. 浏览笔记

- 左侧边栏显示所有笔记文件，按类型分组：
  - 📝 **Cards** - 10分钟快速卡片
  - 📖 **Notes** - 30分钟深度笔记
  - 📊 **Reports** - 综合调研报告

- 点击文件名即可查看内容
- 支持 LaTeX 公式渲染
- 支持代码语法高亮
- 自动加载图片

## 📖 LaTeX 公式支持

Viewer 支持以下 LaTeX 公式格式：

### 行内公式
```markdown
这是一个行内公式 $E = mc^2$ 在文本中。
```

### 独立公式
```markdown
这是一个独立公式：

$$
\int_{-\infty}^{\infty} e^{-x^2} dx = \sqrt{\pi}
$$
```

### 自动转换

Markdown Beautifier 会自动将以下格式转换为标准格式：

- `\[ ... \]` → `$$...$$` (独立公式)
- `\( ... \)` → `$...$` (行内公式)

## 🎨 界面功能

### 工具栏

- **🔄 Refresh** - 刷新文件列表
- **文件路径** - 显示当前查看的文件路径

### 侧边栏

- 按类型分组显示文件
- 显示每个类型的文件数量
- 点击文件名切换查看

### 内容区域

- 最大宽度 900px，居中显示
- GitHub 风格的 Markdown 渲染
- 自动渲染 LaTeX 公式
- 代码块语法高亮
- 图片自动加载

## 🔧 高级配置

### 修改端口

编辑 `viewer/server.py`：

```python
port = 8000  # 改为你想要的端口
```

### 自定义样式

编辑 `viewer/index.html` 中的 CSS 变量：

```css
:root {
    --bg-primary: #0d1117;      /* 主背景色 */
    --bg-secondary: #161b22;    /* 次背景色 */
    --text-primary: #c9d1d9;    /* 主文字色 */
    --accent-color: #58a6ff;    /* 强调色 */
}
```

## 📝 Markdown 美化工具

Paper Agent 内置了 Markdown 美化工具，会自动：

1. **转换 LaTeX 格式**
   - `\[ ... \]` → `$$...$$`
   - `\( ... \)` → `$...$`

2. **清理公式空格**
   - 移除多余空格
   - 保持公式可读性

3. **修复格式问题**
   - 标题后添加空格
   - 列表项后添加空格
   - 代码块格式化

4. **验证公式**
   - 检查未匹配的 `$` 符号
   - 检查过长的公式
   - 提供警告信息

### 使用美化工具

美化工具已集成到所有生成器中，自动应用于：
- 10分钟 Card
- 30分钟 Deep Note
- 调研报告

你也可以单独使用：

```python
from core.markdown_beautifier import MarkdownBeautifier

# 美化 Markdown 内容
content = "Your markdown with \\[ formulas \\]"
beautified = MarkdownBeautifier.beautify(content)

# 提取公式
formulas = MarkdownBeautifier.extract_formulas(content)

# 验证公式
warnings = MarkdownBeautifier.validate_formulas(content)
```

## 🐛 故障排除

### 服务器无法启动

**问题：** `Address already in use`

**解决：**
```bash
# 查找占用端口的进程
lsof -i :8000

# 杀死进程
kill -9 <PID>

# 或者使用其他端口
python viewer/server.py  # 修改代码中的端口号
```

### 文件列表为空

**问题：** 侧边栏显示 "Failed to load files"

**解决：**
1. 确保 `outputs/` 目录存在
2. 确保至少有一个 `.md` 文件
3. 检查文件权限

### LaTeX 公式不显示

**问题：** 公式显示为纯文本

**解决：**
1. 检查网络连接（需要加载 KaTeX CDN）
2. 检查公式格式是否正确
3. 查看浏览器控制台错误信息

### 图片无法加载

**问题：** 图片显示为损坏图标

**解决：**
1. 检查图片路径是否正确
2. 确保图片文件存在于 `outputs/figures/` 目录
3. 检查相对路径是否正确

## 💡 使用技巧

### 1. 快速切换文件

使用键盘上下键快速浏览文件列表（未来功能）

### 2. 搜索功能

按 `Ctrl+F` 在当前文档中搜索

### 3. 复制公式

右键点击公式可以复制 LaTeX 代码（KaTeX 功能）

### 4. 导出 PDF

点击工具栏的 "📄 Export PDF" 按钮（未来功能）

## 🔒 安全说明

- Viewer 只在本地运行（localhost）
- 不会上传任何数据到外部服务器
- 只读取 `outputs/` 目录下的文件
- 使用 Marked.js 的安全模式解析 Markdown

## 📚 相关文档

- [Marked.js 文档](https://marked.js.org/)
- [KaTeX 文档](https://katex.org/)
- [Highlight.js 文档](https://highlightjs.org/)

## 🎯 未来功能

- [ ] 主题切换（亮色/暗色）
- [ ] 导出 PDF
- [ ] 全文搜索
- [ ] 键盘快捷键
- [ ] 文件对比
- [ ] 笔记编辑
- [ ] 标签系统
- [ ] 收藏功能
