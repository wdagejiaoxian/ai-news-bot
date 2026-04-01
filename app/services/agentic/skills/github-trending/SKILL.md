---
name: github-trending-expert
description: 当用户询问GitHub热门项目、开源趋势、编程语言流行度、技术栈推荐时使用此技能。此技能提供获取和分析GitHub热门项目的专业知识和工作流程。
version: 1.0.0
author: AI News Bot
---

# GitHub 热门项目专家技能

## 概述
此技能为 AI News Bot 提供 GitHub 热门项目相关的专业知识和最佳实践。

## 可用工具

### get_github_trending
获取 GitHub 热门项目列表。

**参数**：
- `language`: 编程语言筛选（如 "Python"、"JavaScript"、"Go"），默认为：None
- `time_range`: 时间范围，可选 "daily"（今日）、"weekly"（本周）、"monthly"（本月），默认为："daily"

**使用场景**：
- 用户询问"GitHub上有什么热门项目"，则此时不需要传入参数
- 用户想了解"Python领域的热门项目"，此时需要传入language参数为python
- 用户询问"本周GitHub趋势"，此时需要传入time_range参数为weekly

**返回格式**：

🔥 获取到 N 个 GitHub 热门项目：
1. owner/repo-name

   ⭐ 12345 星 | 💻 Python

   📝 项目描述...

### analyze_github_trend
分析 GitHub 热门项目的技术趋势。

**参数**：
- `repos`: GitHub项目列表

**使用场景**：
- 用户想了解技术趋势
- 用户询问"现在流行什么技术栈"

**返回格式**：

📊 GitHub 热门项目趋势分析（基于 N 个项目）：

🔤 编程语言分布：
   - Python: 8 个项目 (40%)
   - JavaScript: 5 个项目 (25%)

🌟 热门项目推荐（按星标数）：
1. owner/repo ⭐ 12345
2. ...

📈 总体趋势：
   - 平均星标数: 5000
   - 最热门语言: Python

## 工作流程

### 简单查询流程
1. 调用 `get_github_trending` 获取项目列表，不需要传入参数
2. 整理为结构化列表返回

### 趋势分析流程
1. 调用 `get_github_trending` 获取项目列表
2. 调用 `analyze_github_trend` 获取趋势分析
3. 结合用户偏好（从 /memories/ 读取）进行个性化推荐
4. 生成趋势报告

### 语言筛选流程
1. 识别用户指定的编程语言
2. 调用 `get_github_trending(language="xxx")` 获取筛选结果
3. 返回该语言的热门项目

### 日期筛选流程
1. 识别用户指定的日期范围
2. 调用 `get_github_trending(time_range="xxx")` 获取筛选结果
3. 返回该时间范围的热门项目

## 输出格式

### 项目列表格式

🔥 获取到 N 个 GitHub 热门项目：
1. owner/repo-name

   ⭐ 12345 星 | 💻 Python

   📝 项目描述...
2. ...

### 趋势分析格式

📊 GitHub 热门项目趋势分析

🔤 编程语言分布：
   - Python: 8 个项目 (40%)
   - JavaScript: 5 个项目 (25%)
   - ...

🌟 热门项目推荐：
1. owner/repo ⭐ 12345
2. ...

📈 总体趋势：
   - 平均星标数: 5000
   - 最热门语言: Python

## 最佳实践

1. **按需筛选**：用户指定语言时使用 `language` 参数，指定时间范围时使用`time_range`参数
2. **提供趋势洞察**：当需要进行趋势分析时，不仅要列出项目，还要分析趋势
3. **个性化推荐**：结合用户历史偏好（从 /memories/ 读取）
4. **标注关键信息**：星标数、语言、描述缺一不可
5. **关注新兴项目**：除了高星项目，也要关注快速成长的新项目