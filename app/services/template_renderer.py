# -*- coding: utf-8 -*-
"""
模板渲染引擎

支持：
- 变量插值：{{variable}}
- 循环块：{{#github_loop}} ... {{/github_loop}}, {{#article_loop}} ... {{/article_loop}}
- 默认模板回退

设计规则：
- 模板中只能有一种循环块（不支持嵌套）
- 循环块内使用单字段变量：{{github.xxx}}, {{article.xxx}}
- 循环块内的 {{xxx.index}} 自动从 1 开始计数
"""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any

from app.config import get_settings

logger = logging.getLogger(__name__)


class TemplateRenderer:
    """
    模板渲染器

    将模板字符串与上下文数据结合，生成最终文本
    """

    # 预定义变量（无上下文依赖）
    PREDEFINED_VARIABLES = {
        'date': lambda ctx: ctx.get('date', datetime.now().strftime('%Y-%m-%d')),
        'week_start': lambda ctx: ctx.get('week_start', ''),
        'week_end': lambda ctx: ctx.get('week_end', ''),
        'generated_at': lambda ctx: ctx.get('generated_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S')),
        'week_number': lambda ctx: ctx.get('week_number', ''),
        'github_count': lambda ctx: len(ctx.get('github_repos', [])),
        'article_count': lambda ctx: len(ctx.get('articles', [])),
        'app_name': lambda ctx: get_settings().app_name,
    }

    def __init__(self):
        """初始化渲染器"""
        self._logger = logger

    def render(self, template: str, context: Dict[str, Any]) -> str:
        """
        渲染模板

        Args:
            template: 模板字符串
            context: 渲染上下文，包含 articles, github_repos 等数据

        Returns:
            str: 渲染后的字符串
        """
        if not template:
            return ""

        result = template

        # 1. 处理循环块（必须在变量替换之前）
        result = self._render_github_loop(result, context.get('github_repos', []))
        result = self._render_article_loop(result, context.get('articles', []))

        # 2. 处理单字段变量
        result = self._render_variables(result, context)

        return result

    def _render_github_loop(self, template: str, github_repos: List[Dict]) -> str:
        """
        处理 GitHub 循环块

        语法：{{#github_loop}}...{{/github_loop}}

        Args:
            template: 模板字符串
            github_repos: GitHub 项目列表

        Returns:
            str: 渲染后的字符串
        """
        pattern = r'\{\{#github_loop\}\}(.*?)\{\{/github_loop\}\}'
        match = re.search(pattern, template, re.DOTALL)

        if not match:
            return template

        loop_body = match.group(1)
        rendered_items = []

        for i, repo in enumerate(github_repos):
            item_rendered = loop_body

            # 替换 GitHub 相关变量
            item_rendered = item_rendered.replace('{{github.index}}', str(i + 1))
            item_rendered = item_rendered.replace('{{github.full_name}}', self._safe_get(repo, 'full_name'))
            item_rendered = item_rendered.replace('{{github.url}}', self._safe_get(repo, 'url'))
            item_rendered = item_rendered.replace('{{github.stars}}', str(self._safe_get(repo, 'stars', 0)))
            item_rendered = item_rendered.replace('{{github.stars_today}}', str(self._safe_get(repo, 'stars_today', 0)))
            item_rendered = item_rendered.replace('{{github.language}}', self._safe_get(repo, 'language', 'Unknown'))
            item_rendered = item_rendered.replace('{{github.description}}', self._safe_get(repo, 'description', '暂无描述'))

            rendered_items.append(item_rendered)

        # 用渲染后的内容替换循环块
        rendered_loop = '\n'.join(rendered_items) if rendered_items else ''
        return re.sub(pattern, rendered_loop, template, flags=re.DOTALL)

    def _render_article_loop(self, template: str, articles: List[Dict]) -> str:
        """
        处理文章循环块

        语法：{{#article_loop}}...{{/article_loop}}

        Args:
            template: 模板字符串
            articles: 文章列表

        Returns:
            str: 渲染后的字符串
        """
        pattern = r'\{\{#article_loop\}\}(.*?)\{\{/article_loop\}\}'
        match = re.search(pattern, template, re.DOTALL)

        if not match:
            return template

        loop_body = match.group(1)
        rendered_items = []

        for i, article in enumerate(articles):
            item_rendered = loop_body

            # 替换文章相关变量
            item_rendered = item_rendered.replace('{{article.index}}', str(i + 1))
            item_rendered = item_rendered.replace('{{article.title}}', self._safe_get(article, 'title'))
            item_rendered = item_rendered.replace('{{article.url}}', self._safe_get(article, 'url'))
            item_rendered = item_rendered.replace('{{article.score}}', str(self._safe_get(article, 'score', 0)))
            item_rendered = item_rendered.replace('{{article.summary}}', self._safe_get(article, 'summary'))
            item_rendered = item_rendered.replace('{{article.tags}}', self._safe_get(article, 'tags'))
            item_rendered = item_rendered.replace('{{article.source_name}}', self._safe_get(article, 'source_name'))

            rendered_items.append(item_rendered)

        # 用渲染后的内容替换循环块
        rendered_loop = '\n'.join(rendered_items) if rendered_items else ''
        return re.sub(pattern, rendered_loop, template, flags=re.DOTALL)

    def _render_variables(self, template: str, context: Dict[str, Any]) -> str:
        """
        处理单字段变量

        替换 {{variable}} 为实际值

        Args:
            template: 模板字符串
            context: 渲染上下文

        Returns:
            str: 渲染后的字符串
        """
        result = template

        # 处理预定义变量
        for var_name, var_func in self.PREDEFINED_VARIABLES.items():
            placeholder = f'{{{{{var_name}}}}}'
            if placeholder in result:
                try:
                    value = var_func(context)
                    result = result.replace(placeholder, str(value) if value is not None else '')
                except Exception as e:
                    self._logger.warning(f"变量渲染失败 {var_name}: {e}")
                    result = result.replace(placeholder, '')

        # 处理上下文中的动态变量（如 {{custom.key}}）
        # 注意：这里只处理已知的变量模式，避免替换不存在的变量
        result = self._render_context_variables(result, context)

        return result

    def _render_context_variables(self, template: str, context: Dict[str, Any]) -> str:
        """
        处理上下文中的变量

        处理 article.xxx 和 github.xxx 形式的变量（在循环外使用）

        Args:
            template: 模板字符串
            context: 渲染上下文

        Returns:
            str: 渲染后的字符串
        """
        # 处理 article.xxx（在上下文中只有一个 article 对象时）
        if 'article' in context and isinstance(context['article'], dict):
            article = context['article']
            for key, value in article.items():
                placeholder = f'{{{{article.{key}}}}}'
                if placeholder in template:
                    template = template.replace(placeholder, str(value) if value is not None else '')

        # 处理 github.xxx（同上）
        if 'github' in context and isinstance(context['github'], dict):
            github = context['github']
            for key, value in github.items():
                placeholder = f'{{{{github.{key}}}}}'
                if placeholder in template:
                    template = template.replace(placeholder, str(value) if value is not None else '')

        return template

    def _safe_get(self, data: Dict, key: str, default: Any = '') -> Any:
        """
        安全获取字典值

        Args:
            data: 字典数据
            key: 键名
            default: 默认值

        Returns:
            Any: 字典中的值或默认值
        """
        if isinstance(data, dict):
            value = data.get(key, default)
            # 确保 None 值返回空字符串，避免 replace() 接收到 None
            return value if value is not None else ''
        return default

    def validate_template(self, template: str) -> Dict[str, Any]:
        """
        验证模板语法

        Args:
            template: 模板字符串

        Returns:
            Dict: 验证结果 {"valid": bool, "errors": list, "warnings": list}
        """
        errors = []
        warnings = []

        if not template:
            return {"valid": True, "errors": [], "warnings": []}

        # 检查未闭合的循环块
        github_loop_open = len(re.findall(r'\{\{#github_loop\}\}', template))
        github_loop_close = len(re.findall(r'\{\{/github_loop\}\}', template))
        if github_loop_open != github_loop_close:
            errors.append(f"GitHub 循环块未正确闭合：发现 {github_loop_open} 个开始标记，{github_loop_close} 个结束标记")

        article_loop_open = len(re.findall(r'\{\{#article_loop\}\}', template))
        article_loop_close = len(re.findall(r'\{\{/article_loop\}\}', template))
        if article_loop_open != article_loop_close:
            errors.append(f"文章循环块未正确闭合：发现 {article_loop_open} 个开始标记，{article_loop_close} 个结束标记")

        # 检查是否同时存在两种循环块
        if github_loop_open > 0 and article_loop_open > 0:
            warnings.append("模板中同时包含 GitHub 和文章循环块，但只能使用一种循环块")

        # 检查循环块嵌套（不支持）
        # 简单检查：如果循环块内还有循环块开始标记，则为嵌套
        github_body_match = re.search(r'\{\{#github_loop\}\}(.*?)\{\{/github_loop\}\}', template, re.DOTALL)
        if github_body_match:
            body = github_body_match.group(1)
            if '{{#article_loop}}' in body or '{{#github_loop}}' in body:
                errors.append("不支持循环块嵌套")

        article_body_match = re.search(r'\{\{#article_loop\}\}(.*?)\{\{/article_loop\}\}', template, re.DOTALL)
        if article_body_match:
            body = article_body_match.group(1)
            if '{{#article_loop}}' in body or '{{#github_loop}}' in body:
                errors.append("不支持循环块嵌套")

        # 检查模板长度
        if len(template) > 50 * 1024:  # 50KB
            warnings.append("模板长度超过 50KB，可能影响渲染性能")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings
        }


# ==================== 默认模板 ====================


DEFAULT_DAILY_TEMPLATE = """# 📊 AI资讯日报 - {{date}}

## 🔥 GitHub热门
{{#github_loop}}

{{github.index}}. [{{github.full_name}}]({{github.url}}) | ⭐ {{github.stars}}

- 📦 {{github.description}}
- 🤖 语言: {{github.language}}

{{/github_loop}}

## 📰 AI资讯
{{#article_loop}}

{{article.index}}. [{{article.title}}]({{article.url}})

- ⭐ 评分: {{article.score}}/100 | 🏷️ {{article.tags}}
- 📝 {{article.summary}}
- 📌 来源: {{article.source_name}}

{{/article_loop}}

---
*由 AI News Bot 自动生成于 {{generated_at}}*
"""

DEFAULT_WEEKLY_TEMPLATE = """# 📈 AI资讯周报

**{{week_start}} ~ {{week_end}}**

## 🔥 GitHub周热门（共 {{github_count}} 个）

{{#github_loop}}
{{github.index}}. **[{{github.full_name}}]({{github.url}})** | ⭐{{github.stars}} | {{github.language}}

- {{github.description}}

{{/github_loop}}

## 📰 本周精选资讯

{{#article_loop}}
{{article.index}}. [{{article.title}}]({{article.url}})
- {{article.summary}}
{{/article_loop}}

---
*由 AI News Bot 自动生成*
"""

DEFAULT_IMMEDIATE_TEMPLATE = """{{#article_loop}}
## 📰 {{article.title}}

- ⭐ 评分: {{article.score}}/100 | 🏷️ {{article.tags}}
- 📝 {{article.summary}}
- 📌 来源: {{article.source_name}}
- 🔗 [阅读原文]({{article.url}})

{{/article_loop}}
"""


# ==================== 预设模板 ====================


PRESET_TEMPLATES = {
    "standard_daily": {
        "name": "标准日报",
        "type": "daily",
        "content": DEFAULT_DAILY_TEMPLATE,
        "description": "包含 GitHub 热门和文章，标准格式"
    },
    "standard_weekly": {
        "name": "标准周报",
        "type": "weekly",
        "content": DEFAULT_WEEKLY_TEMPLATE,
        "description": "包含 GitHub 周热门和精选资讯"
    },
    "standard_immediate": {
        "name": "标准高分资讯批量推送",
        "type": "immediate",
        "content": DEFAULT_IMMEDIATE_TEMPLATE,
        "description": "包含高分精选资讯"
    },
    "obsidian_friendly": {
        "name": "Obsidian 友好",
        "type": "daily",
        "content": """---
created: {{generated_at}}
date: {{date}}
tags:
  - AI-News
  - Daily
type: daily-report
source: AI News Bot
---

# 📊 AI资讯日报 - {{date}}

{{#github_loop}}
## 🔥 GitHub热门

{{github.index}}. [{{github.full_name}}]({{github.url}})

- ⭐ {{github.stars}} | 🤖 {{github.language}}
- 📦 {{github.description}}

{{/github_loop}}

{{#article_loop}}
## 📰 AI资讯

{{article.index}}. [{{article.title}}]({{article.url}})

- ⭐ 评分: {{article.score}}/100
- 🏷️ {{article.tags}}
- 📝 {{article.summary}}
- 📌 来源: {{article.source_name}}

{{/article_loop}}

---
*由 AI News Bot 自动生成*""",
        "description": "优化的 frontmatter，适合 Dataview 查询"
    }
}


def get_default_template(template_type: str) -> str:
    """
    获取默认模板

    Args:
        template_type: 模板类型 (daily/weekly/immediate)

    Returns:
        str: 默认模板内容
    """
    defaults = {
        "daily": DEFAULT_DAILY_TEMPLATE,
        "weekly": DEFAULT_WEEKLY_TEMPLATE,
        "immediate": DEFAULT_IMMEDIATE_TEMPLATE
    }
    return defaults.get(template_type, DEFAULT_DAILY_TEMPLATE)


# 全局实例
template_renderer = TemplateRenderer()