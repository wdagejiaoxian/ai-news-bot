# -*- coding: utf-8 -*-
"""
报告内容生成器

将报告内容生成逻辑从 Notifier 中提取，实现 DRY 原则
"""

from datetime import datetime
from typing import Dict, List, Optional

from app.services.processor.llm_service import llm_service


class ReportContentGenerator:
    """
    报告内容生成器

    提供统一的报告内容生成逻辑，供所有 Notifier 使用
    """

    # 语言 Emoji 映射
    LANG_EMOJI = {
        "Python": "🐍",
        "JavaScript": "📜",
        "TypeScript": "💎",
        "Go": "🔵",
        "Rust": "🦀",
        "Java": "☕",
        "C++": "⚡",
        "C#": "🎯",
    }

    @classmethod
    def _get_lang_emoji(cls, language: Optional[str]) -> str:
        """获取语言的 Emoji"""
        return cls.LANG_EMOJI.get(language, "📦")

    @classmethod
    async def generate_daily_report_content(
        cls,
        articles: List[Dict],
        github_repos: List[Dict],
        date: Optional[str] = None,
        enhance: bool = False,
    ) -> str:
        """
        生成日报内容

        Args:
            articles: 文章列表
            github_repos: GitHub 项目列表
            date: 日期，默认为当天
            enhance: 是否使用 LLM 增强内容

        Returns:
            str: 日报 Markdown 内容
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")

        content = f"# 📊 AI资讯日报 - {date}\n\n"

        # GitHub 热门
        if github_repos:
            content += "## 🔥 GitHub热门\n\n"
            for i, repo in enumerate(github_repos):
                emoji = cls._get_lang_emoji(repo.get('language'))
                content += f"""
### {i + 1}. [{repo['full_name']}]({repo['url']}) | ⭐ {repo['stars']}

- 📦 {(repo.get('description') or '暂无描述').strip()}

- 🤖 语言: {repo.get('language', 'Unknown')}

"""
            content += "---\n"

        # AI 资讯
        if articles:
            content += "## 📰 AI资讯\n\n"
            for i, article in enumerate(articles):
                content += f"""
### {i + 1}. [{article['title']}]({article['url']})

- ⭐ 评分: {article['score']}/100 | 🏷️ {article.get('tags', '')}

- 📝 {article.get('summary', '')}

- 📌 来源: {article.get('source_name', 'unknown')}

"""

        content += "---\n"
        content += "*由 AI News Bot 自动生成*"

        # LLM 增强
        if enhance:
            content = await llm_service.enhance_report_content(content)

        return content

    @classmethod
    async def generate_weekly_report_content(
        cls,
        articles: List[Dict],
        github_repos: List[Dict],
        week_start: str,
        week_end: str,
        enhance: bool = False,
    ) -> str:
        """
        生成周报内容

        Args:
            articles: 文章列表
            github_repos: GitHub 项目列表
            week_start: 周开始日期
            week_end: 周结束日期
            enhance: 是否使用 LLM 增强内容

        Returns:
            str: 周报 Markdown 内容
        """
        content = f"# 📈 AI资讯周报\n"
        content += f"**{week_start} ~ {week_end}**\n\n"

        # GitHub 周热门
        if github_repos:
            content += "## 🔥 GitHub周热门TOP10\n\n"
            for i, repo in enumerate(github_repos):
                content += f"{i + 1}. **[{repo['full_name']}]({repo['url']})** | ⭐{repo['stars']} | {repo.get('language', 'Unknown')}\n"
                if repo.get('description'):
                    content += f"   - {(repo.get('description') or '暂无描述')[:100].strip()}\n"
            content += "\n"

        # 精选资讯
        if articles:
            content += "## 📰 本周精选资讯\n\n"
            for i, article in enumerate(articles):
                content += f"{i + 1}. [{article['title']}]({article['url']})\n- {article.get('summary', '')[:200]}\n"
            content += "\n"

        content += "---\n"
        content += "*由 AI News Bot 自动生成*"

        # LLM 增强
        if enhance:
            content = await llm_service.enhance_report_content(content, report_type='weekly')

        return content

    @classmethod
    def generate_article_batch_content(
        cls,
        articles: List[Dict],
        enhance: bool = True,
    ) -> str:
        """
        生成批量文章内容

        Args:
            articles: 文章列表
            enhance: 是否使用 LLM 增强内容

        Returns:
            str: 文章 Markdown 内容
        """
        content = ''
        for i, article in enumerate(articles):
            content += f"## 📰 {i + 1}. {article['title']}\n\n"

            if article.get('tags'):
                content += f"**标签**：{article['tags']}\n\n"

            if article.get('score') is not None:
                content += f"**评分**: ⭐ {article['score']}/100\n\n"

            content += f"**摘要**: {article.get('summary', '')}\n\n"
            content += f"**来源**: {article.get('source_name', 'unknown')}\n\n"
            content += f"🔗 [阅读原文]({article.get('url')})\n\n"

        return content

    @classmethod
    async def enhance_article_content(cls, content: str) -> str:
        """使用 LLM 增强文章内容"""
        return await llm_service.enhance_article_content(content)


# 全局实例
report_content_generator = ReportContentGenerator()