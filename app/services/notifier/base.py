# -*- coding: utf-8 -*-
"""
消息推送模块

负责将内容推送到各个渠道:
- 企业微信 (Webhook)
- Telegram
- Discord (Webhook)

支持:
- 即时推送
- 日报推送
- 周报推送
"""
import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional

import httpx

from app.config import get_settings
from app.services.processor.llm_service import llm_service
from app.models import Article
from app.services.notifier.content_converter import content_converter, MAX_CONTENT_LENGTH

logger = logging.getLogger(__name__)


class BaseNotifier(ABC):
    """
    消息通知基类
    
    定义通知器的通用接口
    """
    
    @abstractmethod
    async def send(self, content: str, msg_type: str = "text") -> bool:
        """
        发送消息
        
        Args:
            content: 消息内容
            msg_type: 消息类型 (text/markdown/image)
        
        Returns:
            bool: 是否发送成功
        """
        pass
    
    @abstractmethod
    async def send_article(
        self,
        title: str,
        summary: str,
        url: str,
        source: str,
        tags: Optional[str] = None,
        score: Optional[float] = None,
    ) -> bool:
        """
        发送文章
        
        Args:
            title: 标题
            summary: 摘要
            url: 链接
            source: 来源
            tags: 标签
            score: 评分
        
        Returns:
            bool: 是否发送成功
        """
        pass
    
    @abstractmethod
    async def send_github_repo(
        self,
        full_name: str,
        description: str,
        url: str,
        language: str,
        stars: int,
        stars_today: int,
    ) -> bool:
        """
        发送GitHub项目
        
        Args:
            full_name: 仓库名
            description: 描述
            url: 链接
            language: 语言
            stars: 星标数
            stars_today: 今日新增
        
        Returns:
            bool: 是否发送成功
        """
        pass


class WeComNotifier(BaseNotifier):
    """
    企业微信机器人通知器
    
    使用 Webhook 方式发送消息
    支持:
    - 文本消息
    - Markdown消息
    - 图片消息
    - 图文消息
    
    配置:
    - 在企业微信群中添加机器人
    - 获取 Webhook Key
    - 配置到 .env 文件
    """
    
    def __init__(self, webhook_key: Optional[str] = None):
        self.settings = get_settings()
        self.webhook_key = webhook_key or self.settings.wecom_webhook_key
        self.api_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={self.webhook_key}"
        self.api_key = self.settings.openai_api_key
        self.api_base = self.settings.openai_api_base
        self.model = self.settings.openai_summary_model
        self._is_configured = bool(self.webhook_key)
    
    @property
    def is_available(self) -> bool:
        """检查是否配置"""
        return self._is_configured
    
    async def send(
            self,
            content: str,
            msg_type: str = "text",
            file_name: Optional[str] = None
    ) -> bool:
        """
        发送消息
        
        Args:
            content: 消息内容
            msg_type: 消息类型
            file_name: 文件名
        
        Returns:
            bool: 是否成功
        """
        if not self.is_available:
            logger.warning("企业微信 Webhook 未配置")
            return False
        
        try:
            # 检测是否需要特殊处理
            if content_converter.check_length(content):
                logger.info("内容超过长度限制，尝试转为文件发送")
                return await self._send_as_file(content, file_name = file_name)

            # 若长度未超过限制，则正常发送
            payload = self._build_payload(msg_type, content)
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.api_url, json=payload)
                result = response.json()
                
                if result.get("errcode") == 0:
                    logger.info(f"企业微信消息发送成功")
                    return True
                else:
                    logger.error(f"企业微信发送失败: {result}")
                    return False
                    
        except Exception as e:
            logger.error(f"企业微信发送异常: {e}")
            return False

    async def _send_as_file(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """
        将内容作为文件发送（PDF优先，Markdown备选）

        发送优先级：
        1. PDF文件（使用WeasyPrint + mistune生成）
        2. Markdown文件（降级方案）
        3. 卡片摘要（最后降级方案）
        """
        # ===== 方案1: 尝试发送PDF文件 =====
        pdf_result = await self._send_as_pdf(content, file_name = file_name)
        if pdf_result:
            logger.info("PDF文件发送成功")
            return True

        # # ===== 方案2: 降级为Markdown文件 =====
        logger.info("PDF生成/发送失败，尝试Markdown文件...")
        md_result = await self._send_as_markdown(content, file_name = file_name)
        if md_result:
            logger.info("Markdown文件发送成功")
            return True
        #
        # # ===== 方案3: 最后降级为卡片摘要 =====
        # logger.info("文件发送失败，尝试降级为卡片摘要...")
        # return await self._send_card_summary(content)

        return False

    async def _send_as_pdf(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """
        将Markdown内容转换为PDF并发送

        Returns:
            bool: 是否发送成功
        """
        try:
            # 1. 生成PDF文件（使用WeasyPrint + mistune）
            logger.info("开始生成PDF文件...")
            pdf_bytes = await content_converter.markdown_to_pdf(content)


            if not pdf_bytes:
                logger.warning("PDF生成失败，返回空字节")
                return False

            # 2. 生成文件名
            filename = content_converter.generate_pdf_filename(file_name)


            # 3. 调用企业微信上传临时文件接口
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {
                    "file": (filename, pdf_bytes, "application/pdf")
                }
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"PDF文件上传失败: {result}")
                    return False

                # 4. 发送文件消息
                media_id = result.get("media_id")
                logger.info(f"PDF文件上传成功，media_id: {media_id}")
                return await self._send_file_message(media_id, filename)

        except ImportError as e:
            logger.warning(f"PDF依赖未安装，跳过PDF方案: {e}")
            return False
        except Exception as e:
            logger.error(f"PDF生成或发送失败: {e}")
            return False

    async def _send_as_markdown(
            self,
            content: str,
            file_name: Optional[str] = None,
    ) -> bool:
        """
        将Markdown内容保存为文件并发送

        Returns:
            bool: 是否发送成功
        """
        try:
            # # 1. 保存为Markdown文件
            # filepath, filename = content_converter.save_to_markdown(content, filename = file_name)
            #
            # # 2. 读取文件内容
            # with open(filepath, 'rb') as f:
            #     file_data = f.read()

            # 1. 将字符串编码为 bytes（直接在内存中处理）
            file_data = content.encode('utf-8')

            # 2. 生成文件名
            filename =content_converter.generate_filename(file_name)

            # 3. 调用企业微信上传临时文件接口
            upload_url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={self.webhook_key}&type=file"

            async with httpx.AsyncClient(timeout=60.0) as client:
                files = {"file": (filename, file_data, "text/markdown")}
                response = await client.post(upload_url, files=files)
                result = response.json()

                if result.get("errcode") != 0:
                    logger.error(f"Markdown文件上传失败: {result}")
                    return False

                # 4. 发送文件消息
                media_id = result.get("media_id")
                return await self._send_file_message(media_id, filename)

        except Exception as e:
            logger.error(f"Markdown文件发送失败: {e}")
            return False

    async def _send_file_message(self, media_id: str, filename: str) -> bool:
        """发送文件消息（通用）"""
        try:
            payload = {
                "msgtype": "file",
                "file": {"media_id": media_id}
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.api_url, json=payload)
                result = response.json()

                if result.get("errcode") == 0:
                    logger.info(f"文件消息发送成功: {filename}")
                    return True
                else:
                    logger.error(f"文件消息发送失败: {result}")
                    return False
        except Exception as e:
            logger.error(f"发送文件消息异常: {e}")
            return False

    def _build_payload(self, msg_type: str, content: str) -> dict:
        """
        构建消息载荷
        
        Args:
            msg_type: 消息类型
            content: 内容
        
        Returns:
            dict: 消息载荷
        """
        if msg_type == "markdown":
            return {
                "msgtype": "markdown",
                "markdown": {
                    "content": content
                }
            }
        elif msg_type == "image":
            return {
                "msgtype": "image",
                "image": {
                    "base64": content  # 需要Base64编码
                }
            }
        else:
            # 默认文本
            return {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
    
    async def send_article(
        self,
        title: str,
        summary: str,
        url: str,
        source: str,
        tags: Optional[str] = None,
        score: Optional[float] = None,
    ) -> bool:
        """
        发送文章
        
        Args:
            title: 标题
            summary: 摘要
            url: 链接
            source: 来源
            tags: 标签
            score: 评分
        
        Returns:
            bool: 是否成功
        """
        # 构建Markdown格式
        content = f"## 📰 {title}\n\n"
        
        if tags:
            content += f"**标签**：{tags}\n\n"
        
        if score is not None:
            content += f"**评分**: ⭐ {score}/10\n\n"
        
        content += f"{summary}\n\n"
        content += f"**来源**: {source}\n\n"
        content += f"🔗 [阅读原文]({url})"
        
        return await self.send(content, "markdown")

    async def batch_send_article(
            self,
            article_list: List[Article],
    ) -> bool:
        """
        发送文章

        Args:
            article_list: List[Article]
        Returns:
            bool: 是否成功
        """
        # 构建Markdown格式
        content = ''
        for i,article in enumerate(article_list):
            content += f"## 📰 {i+1}. {article.title}\n\n"

            if article.tags:
                content += f"**标签**：{article.tags}\n\n"

            if article.score is not None:
                content += f"**评分**: ⭐ {article.score}/100\n\n"

            content += f"**摘要**: {article.summary}\n\n"
            content += f"**来源**: {article.source_name}\n\n"
            content += f"🔗 [阅读原文]({article.url})\n\n"
        enhance_content = await llm_service.enhance_article_content(content)

        return await self.send(enhance_content, "markdown", file_name='高分资讯')
    
    async def send_github_repo(
        self,
        full_name: str,
        description: str,
        url: str,
        language: str,
        stars: int,
        stars_today: int,
    ) -> bool:
        """
        发送GitHub项目
        
        Args:
            full_name: 仓库名
            description: 描述
            url: 链接
            language: 语言
            stars: 星标数
            stars_today: 今日新增
        
        Returns:
            bool: 是否成功
        """
        # Emoji映射
        lang_emoji = {
            "Python": "🐍",
            "JavaScript": "📜",
            "TypeScript": "💎",
            "Go": "🔵",
            "Rust": "🦀",
            "Java": "☕",
            "C++": "⚡",
            "C#": "🎯",
        }
        emoji = lang_emoji.get(language, "📦")
        
        # 构建Markdown格式
        content = f"## {emoji} {full_name}\n\n"
        content += f"{description or '暂无描述'}\n\n"
        content += f"⭐ **{stars}** (+{stars_today} today) | "
        content += f"🔱 **{language or 'Unknown'}**\n\n"
        content += f"🔗 [查看项目]({url})"
        
        return await self.send(content, "markdown")
    
    async def send_daily_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        date: str = None,
    ) -> bool:
        """
        发送日报
        
        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            date: 日期
            
        Returns:
            bool: 是否成功
        """
        if not date:
            date = datetime.now().strftime("%Y-%m-%d")
        
        content = f"# 📊 AI资讯日报 - {date}\n\n"
        
        # GitHub热门
        if github_repos:
            content += "## 🔥 GitHub热门\n\n"
            for i,repo in enumerate(github_repos):
                # content += f"- **{repo['full_name']}** "
                # content += f"⭐{repo['stars']} ({repo.get('language', 'N/A')})\n"
                content += f"""
                    ### {i+1}. [{repo['full_name']}]({repo['url']}) | ⭐ {repo['stars']}\n
- 📦 {repo.get('description', '暂无描述')[:100].strip()}\n
- 🤖 语言: {repo.get('language', 'Unknown')}\n
"""
            content += "---\n"
        
        # AI资讯
        if articles:
            content += "## 📰 AI资讯\n\n"
            for i,article in enumerate(articles):
                # content += f"- [{article['title']}]({article['url']})\n"
                # if article.get('score'):
                #     content += f"  - ⭐ 评分: {article['score']}\n"
                # content += "\n"
                content += f"""
                    ### {i+1}. [{article['title']}]({article['url']})\n
- ⭐ 评分: {article['score']}/100 | 🏷️ {article.get('tags', '')}\n
- 📝 {article.get('summary', '')[:200]}\n
- 📌 来源: {article.get('source_name', 'unknown')}\n
"""
        
        content += "---\n"
        content += "*由 AI News Bot 自动生成*"
        res_content = await llm_service.enhance_report_content(content)
        
        return await self.send(res_content, "markdown", file_name='日报')
    
    async def send_weekly_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        week_start: str,
        week_end: str,
    ) -> bool:
        """
        发送周报
        
        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            week_start: 周开始日期
            week_end: 周结束日期
            
        Returns:
            bool: 是否成功
        """
        content = f"# 📈 AI资讯周报\n"
        content += f"**{week_start} ~ {week_end}**\n\n"
        
        # GitHub周热门
        if github_repos:
            content += "## 🔥 GitHub周热门TOP10\n\n"
            for i, repo in enumerate(github_repos[:10]):
                content += f"{i+1}. **[{repo['full_name']}]({repo['url']})** | ⭐{repo['stars']} | {repo.get('language', 'Unknown')}\n"
                if repo.get('description'):
                    content += f"   - {repo.get('description', '暂无描述')[:100].strip()}\n"
            content += "\n"
        
        # 精选资讯
        if articles:
            content += "## 📰 本周精选资讯\n\n"
            for i, article in enumerate(articles[:10]):
                content += f"{i+1}. [{article['title']}]({article['url']})\n- {article.get('summary', '')[:200]}\n"
            content += "\n"
        
        content += "---\n"
        content += "*由 AI News Bot 自动生成*"
        res_content = await llm_service.enhance_report_content(content, report_type='weekly')
        
        return await self.send(res_content, "markdown", file_name= '周报')




class TelegramNotifier(BaseNotifier):
    """
    Telegram 机器人通知器
    
    使用 Telegram Bot API 发送消息
    """
    
    def __init__(self, bot_token: str = None, chat_id: str = None):
        self.settings = get_settings()
        self.bot_token = bot_token or self.settings.telegram_bot_token
        self.chat_id = chat_id or self.settings.telegram_chat_id
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        self._is_configured = bool(self.bot_token and self.chat_id)
    
    @property
    def is_available(self) -> bool:
        return self._is_configured
    
    async def send(self, content: str, msg_type: str = "text") -> bool:
        """发送消息"""
        if not self.is_available:
            return False
        
        try:
            payload = {
                "chat_id": self.chat_id,
                "text": content,
                "parse_mode": "Markdown",
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{self.api_url}/sendMessage",
                    json=payload
                )
                return response.status_code == 200
                
        except Exception as e:
            logger.error(f"Telegram发送异常: {e}")
            return False
    
    async def send_article(self, title, summary, url, source, tags=None, score=None):
        """发送文章"""
        content = f"*{title}*\n\n"
        if tags:
            content += f"{tags}\n\n"
        if score:
            content += f"⭐ 评分: {score}/10\n\n"
        content += f"{summary}\n\n"
        content += f"📌 来源: {source}\n"
        content += f"[阅读原文]({url})"
        
        return await self.send(content)
    
    async def send_github_repo(
        self,
        full_name: str,
        description: str,
        url: str,
        language: str,
        stars: int,
        stars_today: int,
    ) -> bool:
        """发送GitHub项目"""
        content = f"*{full_name}*\n"
        content += f"⭐ {stars} (+{stars_today})\n"
        content += f"🔱 {language}\n\n"
        content += f"{description}\n\n"
        content += f"[查看项目]({url})"
        
        return await self.send(content)


class DiscordNotifier(BaseNotifier):
    """
    Discord Webhook 通知器
    """
    
    def __init__(self, webhook_url: str = None):
        self.webhook_url = webhook_url
        self._is_configured = bool(webhook_url)
    
    @property
    def is_available(self) -> bool:
        return self._is_configured
    
    async def send(self, content: str, msg_type: str = "text") -> bool:
        """发送消息"""
        if not self.is_available:
            return False
        
        try:
            payload = {"content": content}
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.webhook_url, json=payload)
                return response.status_code in [200, 204]
                
        except Exception as e:
            logger.error(f"Discord发送异常: {e}")
            return False
    
    async def send_article(self, title, summary, url, source, tags=None, score=None):
        """发送文章"""
        content = f"**{title}**\n\n"
        if tags:
            content += f"{tags}\n"
        if score:
            content += f"⭐ 评分: {score}/10\n"
        content += f"{summary}\n\n"
        content += f"📌 来源: {source} | [阅读原文]({url})"
        
        return await self.send(content)
    
    async def send_github_repo(
        self,
        full_name: str,
        description: str,
        url: str,
        language: str,
        stars: int,
        stars_today: int,
    ) -> bool:
        """发送GitHub项目"""
        content = f"**{full_name}**\n"
        content += f"⭐ {stars} (+{stars_today}) | 🔱 {language}\n"
        content += f"{description}\n\n"
        content += f"[查看项目]({url})"
        
        return await self.send(content)


# 创建全局通知器实例
wecom_notifier = WeComNotifier()
telegram_notifier = TelegramNotifier()
discord_notifier = DiscordNotifier()


class NotificationManager:
    """
    通知管理器
    
    统一管理多个通知渠道
    支持按配置启用/禁用
    """
    
    def __init__(self):
        self.notifiers = []
        
        # 添加已配置的通知器
        if wecom_notifier.is_available:
            self.notifiers.append(("wecom", wecom_notifier))
        if telegram_notifier.is_available:
            self.notifiers.append(("telegram", telegram_notifier))
        if discord_notifier.is_available:
            self.notifiers.append(("discord", discord_notifier))
    
    async def broadcast(self, content: str, msg_type: str = "text") -> Dict[str, bool]:
        """
        广播消息到所有渠道
        
        Args:
            content: 消息内容
            msg_type: 消息类型
        
        Returns:
            dict: 各渠道发送结果
        """
        results = {}
        
        for name, notifier in self.notifiers:
            try:
                success = await notifier.send(content, msg_type)
                results[name] = success
            except Exception as e:
                logger.error(f"广播到 {name} 失败: {e}")
                results[name] = False
        
        return results
    
    async def send_article(
            self,
            article_dict: Dict[str, str] = None,
            article_list: List[Article] = None,
            many = False
    ) -> Dict[str, bool]:
        """发送文章到所有渠道"""
        results = {}
        
        for name, notifier in self.notifiers:
            try:
                if many:
                    success = await notifier.batch_send_article(
                        article_list
                    )
                else:
                    success = await notifier.send_article(
                        title = article_dict.get("title"),
                        summary = article_dict.get("summary"),
                        url = article_dict.get("url"),
                        source = article_dict.get("source_name"),
                        tags = article_dict.get("tags"),
                        score = article_dict.get("score"),
                    )
                results[name] = success
            except Exception as e:
                logger.error(f"发送文章到 {name} 失败: {e}")
                results[name] = False
        
        return results

    async def send_daily_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        date: str = None,
    ) -> bool:
        """
        发送日报到所有渠道
        
        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            date: 日期
        
        Returns:
            bool: 是否成功
        """
        # 调用 WeComNotifier 的方法（因为只有它实现了这个方法）
        if wecom_notifier.is_available:
            return await wecom_notifier.send_daily_report(
                articles, github_repos, date
            )
        return False

    async def send_weekly_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        week_start: str,
        week_end: str,
    ) -> bool:
        """
        发送周报到所有渠道
        
        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            week_start: 周开始日期
            week_end: 周结束日期
        
        Returns:
            bool: 是否成功
        """
        # 调用 WeComNotifier 的方法
        if wecom_notifier.is_available:
            return await wecom_notifier.send_weekly_report(
                articles, github_repos, week_start, week_end
            )
        return False


# 创建全局通知管理器
notification_manager = NotificationManager()
