# -*- coding: utf-8 -*-
"""
指令处理器模块

处理用户发送的各种指令:
- /ai_news [数量] [时间范围]
- /github [语言] [时间]
- /today
- /search <关键词>
- /sub <topic>
- /settings
- /help
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple

from app.database import db
from app.models import Article, GitHubRepo, User
from app.services.fetcher.github_trending import github_fetcher
from app.services.fetcher.rss_parser import rss_fetcher
from app.services.notifier.base import notification_manager
from app.services.processor.deduplicator import deduplicator

logger = logging.getLogger(__name__)


class CommandType(str, Enum):
    """指令类型枚举"""
    AI_NEWS = "ai_news"
    GITHUB = "github"
    TODAY = "today"
    SEARCH = "search"
    SUBSCRIBE = "sub"
    UNSUBSCRIBE = "unsub"
    SETTINGS = "settings"
    HELP = "help"
    UNKNOWN = "unknown"


@dataclass
class Command:
    """指令数据结构"""
    type: CommandType
    args: List[str]
    raw_text: str


class CommandParser:
    """
    指令解析器
    
    将用户输入解析为结构化指令
    """
    
    # 指令匹配模式
    PATTERNS = {
        CommandType.AI_NEWS: [r"^/ai_news\s*(.*)$", r"^/news\s*(.*)$"],
        CommandType.GITHUB: [r"^/github\s*(.*)$", r"^/gh\s*(.*)$"],
        CommandType.TODAY: [r"^/today(?:\s+(.*))?$", r"^/今日(?:\s+(.*))?$"],
        CommandType.SEARCH: [r"^/search\s+(.+)$", r"^/搜索\s+(.+)$"],
        CommandType.SUBSCRIBE: [r"^/sub\s+(.+)$", r"^/订阅\s+(.+)$"],
        CommandType.UNSUBSCRIBE: [r"^/unsub\s+(.+)$", r"^/取消订阅\s+(.+)$"],
        CommandType.SETTINGS: [r"^/settings(?:\s+(.*))?$", r"^/设置(?:\s+(.*))?$"],
        CommandType.HELP: [r"^/help(?:\s+(.*))?$", r"^/帮助(?:\s+(.*))?$", r"^/start(?:\s+(.*))?$"],
    }
    
    def parse(self, text: str) -> Command:
        """
        解析指令
        
        Args:
            text: 用户输入文本
        
        Returns:
            Command: 解析后的指令
        """
        text = text.strip()
        
        # 遍历所有模式
        for cmd_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                match = re.match(pattern, text, re.IGNORECASE)
                if match:
                    args = match.group(1).strip() if match.group(1) else ""
                    # 将参数分割为列表
                    arg_list = self._parse_args(args)
                    
                    return Command(
                        type=cmd_type,
                        args=arg_list,
                        raw_text=text
                    )
        
        # 无法识别
        return Command(
            type=CommandType.UNKNOWN,
            args=[],
            raw_text=text
        )
    
    def _parse_args(self, args_str: str) -> List[str]:
        """
        解析参数
        
        支持:
        - 空格分隔: "5 daily"
        - 逗号分隔: "5,daily"
        
        Args:
            args_str: 参数字符串
        
        Returns:
            List[str]: 参数列表
        """
        if not args_str:
            return []
        
        # 尝试按空格和逗号分割
        args = re.split(r"[,\s]+", args_str.strip())
        return [a for a in args if a]


class CommandHandler:
    """
    指令处理器
    
    执行各种指令并返回结果
    """
    
    def __init__(self):
        self.parser = CommandParser()
    
    async def handle(self, text: str, user_id: str = None) -> str:
        """
        处理用户指令
        
        Args:
            text: 用户输入
            user_id: 用户ID (可选)
        
        Returns:
            str: 回复文本
        """
        # 解析指令
        command = self.parser.parse(text)
        
        # 路由处理
        handlers = {
            CommandType.AI_NEWS: self._handle_ai_news,
            CommandType.GITHUB: self._handle_github,
            CommandType.TODAY: self._handle_today,
            CommandType.SEARCH: self._handle_search,
            CommandType.SUBSCRIBE: self._handle_subscribe,
            CommandType.UNSUBSCRIBE: self._handle_unsubscribe,
            CommandType.SETTINGS: self._handle_settings,
            CommandType.HELP: self._handle_help,
        }
        
        handler = handlers.get(command.type)
        if handler:
            return await handler(command.args, user_id)
        else:
            return await self._fallback_to_llm(text, user_id)

    async def _fallback_to_llm(self, text: str, user_id: str = None) -> str:
        """
        当命令无法识别时，调用LLM生成回答

        Args:
            text: 用户原始输入
            user_id: 用户ID

        Returns:
            str: LLM生成的回答
        """
        # TODO: 实现LLM调用逻辑
        # 可以使用现有的llm_manager或llm_service
        # 例如：
        # from app.services.processor.llm_manager import llm_manager, LLMThinkMode
        # from app.services.processor.llm_service import LLMService
        #
        # llm_service = LLMService()
        # prompt = f"用户问：{text}\n请作为AI助手回答这个问题。"
        # result = await llm_service.enhance_report_content(prompt)  # 或其他适当方法
        # return result or "抱歉，我暂时无法理解您的问题。"

        # 暂时返回提示信息
        return f"您问了：「{text}」\n这是一个新功能，我正在学习中！请尝试使用 /help 查看可用命令。"
    
    async def _handle_ai_news(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /ai_news 指令
        
        用法: /ai_news [数量] [时间范围]
        示例: /ai_news 5 daily
        """
        # 解析参数
        limit = 10
        time_range = "daily"
        
        if len(args) >= 1:
            try:
                limit = int(args[0])
            except ValueError:
                pass
        
        if len(args) >= 2:
            time_range = args[1]
        
        # 获取资讯
        articles = await deduplicator.get_recent_articles(limit=limit)
        
        if not articles:
            return "暂无最新AI资讯"
        
        # 格式化输出
        lines = ["📰 **AI资讯**\n"]
        
        for i, article in enumerate(articles, 1):
            lines.append(f"{i}. **{article.title}**")
            if article.summary:
                lines.append(f"   {article.summary[:100]}...")
            if article.score:
                lines.append(f"   ⭐ 评分: {article.score}/10")
            lines.append(f"   📌 来源: {article.source_name}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def _handle_github(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /github 指令
        
        用法: /github [语言] [时间]
        示例: /github python weekly
        """
        # 解析参数
        language = None
        time_range = "daily"
        
        if len(args) >= 1:
            lang = args[0].capitalize()
            # 简单检查是否是语言
            if lang in ["Python", "JavaScript", "TypeScript", "Go", "Rust", "Java"]:
                language = lang
            else:
                time_range = args[0]
        
        if len(args) >= 2:
            time_range = args[1]
        
        # 获取GitHub热门
        repos = await deduplicator.get_recent_github_repos(
            limit=10,
            language=language,
            time_range=time_range,
        )
        
        if not repos:
            # 如果数据库没有，尝试实时获取
            repos_data = await github_fetcher.fetch_trending(
                language=language,
                time_range=time_range,
                limit=10
            )
            
            if not repos_data:
                return "暂无GitHub热门项目"
            
            # 格式化
            lines = ["🔥 **GitHub热门**\n"]
            for i, repo in enumerate(repos_data, 1):
                lines.append(f"{i}. **{repo['full_name']}** ⭐{repo['stars']}")
                if repo.get("description"):
                    lines.append(f"   {repo['description'][:80]}")
                if repo.get("language"):
                    lines.append(f"   🔱 {repo['language']}")
                lines.append("")
            
            return "\n".join(lines)
        
        # 格式化输出
        lines = ["🔥 **GitHub热门**\n"]
        
        for i, repo in enumerate(repos, 1):
            lines.append(f"{i}. **{repo.full_name}** ⭐{repo.stars}")
            if repo.description:
                lines.append(f"   {repo.description[:80]}")
            if repo.language:
                lines.append(f"   🔱 {repo.language}")
            lines.append("")
        
        return "\n".join(lines)
    
    async def _handle_today(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /today 指令 - 今日简报
        """
        # 获取今日内容
        today = datetime.now().strftime("%Y-%m-%d")
        
        articles = await deduplicator.get_recent_articles(limit=5)
        repos = await deduplicator.get_recent_github_repos(limit=5)
        
        lines = [f"📊 **今日简报** - {today}\n"]
        
        # GitHub热门
        if repos:
            lines.append("## 🔥 GitHub热门")
            for repo in repos:
                lines.append(f"- **{repo.full_name}** ⭐{repo.stars}")
            lines.append("")
        
        # AI资讯
        if articles:
            lines.append("## 📰 AI资讯")
            for article in articles:
                lines.append(f"- [{article.title}]({article.url})")
            lines.append("")
        
        if not repos and not articles:
            return "暂无今日数据，请先运行采集任务"
        
        return "\n".join(lines)
    
    async def _handle_search(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /search 指令
        
        用法: /search <关键词>
        """
        if not args:
            return "请提供搜索关键词，例如: /search LLM"
        
        keyword = " ".join(args)
        
        # 搜索
        articles = await deduplicator.search_articles(keyword, limit=10)
        
        if not articles:
            return f"未找到包含「{keyword}」的资讯"
        
        lines = [f"🔍 搜索结果: 「{keyword}」\n"]
        
        for i, article in enumerate(articles, 1):
            lines.append(f"{i}. **{article.title}**")
            lines.append(f"   📌 来源: {article.source_name} | ")
            lines.append(f"   🔗 [查看]({article.url})")
            lines.append("")
        
        return "\n".join(lines)
    
    async def _handle_subscribe(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /sub 指令 - 订阅主题
        """
        if not args:
            return "请指定要订阅的主题，例如: /sub LLM"
        
        topic = " ".join(args)
        
        # TODO: 实现订阅逻辑
        return f"已订阅主题: {topic}，将推送相关资讯"
    
    async def _handle_unsubscribe(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /unsub 指令 - 取消订阅
        """
        if not args:
            return "请指定要取消订阅的主题"
        
        topic = " ".join(args)
        
        # TODO: 实现取消订阅逻辑
        return f"已取消订阅主题: {topic}"
    
    async def _handle_settings(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /settings 指令 - 设置
        """
        # TODO: 返回用户设置
        settings_text = """⚙️ **当前设置**

- 即时推送阈值: ⭐ 8分
- 日报推送时间: 08:00
- 周报推送时间: 09:00 (周一)
- 通知渠道: 企业微信

回复对应数字修改设置:
1. 修改推送阈值
2. 修改日报时间
3. 修改周报时间
4. 切换通知渠道
"""
        return settings_text
    
    async def _handle_help(
        self,
        args: List[str],
        user_id: str = None
    ) -> str:
        """
        处理 /help 指令
        """
        return self._help_text()
    
    def _help_text(self) -> str:
        """
        帮助文本
        """
        help_text = """🤖 **AI News Bot 命令帮助**

**获取资讯:**
- `/ai_news [数量] [时间]` - 获取AI资讯
  示例: `/ai_news 5 daily`
- `/github [语言] [时间]` - 获取GitHub热门
  示例: `/github python weekly`
- `/today` - 今日简报
- `/search <关键词>` - 搜索历史资讯
  示例: `/search GPT`

**订阅管理:**
- `/sub <主题>` - 订阅主题
- `/unsub <主题>` - 取消订阅

**其他:**
- `/settings` - 个人设置
- `/help` - 查看帮助

---
由 AI News Bot 提供
"""
        return help_text


# 创建全局指令处理器
command_handler = CommandHandler()
