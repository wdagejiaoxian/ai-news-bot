# -*- coding: utf-8 -*-
"""
动态通知器基类

提供统一的密钥解密、配置检查等公共逻辑
使用注册模式实现插件式扩展
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional, Type

from app.models import WebhookConfig
from app.services.notifier.report_generator import report_content_generator
from app.services.template_renderer import template_renderer, get_default_template

logger = logging.getLogger(__name__)


class BaseDynamicNotifier(ABC):
    """
    动态通知器基类

    提供公共的：
    - 凭证解密逻辑
    - 配置检查逻辑
    - 注册模式支持

    使用方式：
    1. 定义子类并继承 BaseDynamicNotifier
    2. 使用 @register_notifier 装饰器注册
    3. 实现 platform_name 和抽象方法

    示例：
        @register_notifier("wecom")
        class DynamicWeComNotifier(BaseDynamicNotifier):
            platform_name = "wecom"

            def _decrypt_credentials_impl(self, encrypted_key: str) -> Dict[str, Any]:
                return {"webhook_key": encrypted_key}

            async def _send_impl(self, content: str, msg_type: str) -> bool:
                ...
    """

    # 注册表：platform -> notifier_class
    _registry: Dict[str, Type['BaseDynamicNotifier']] = {}

    def __init__(self, webhook_config: WebhookConfig):
        """
        初始化动态通知器

        Args:
            webhook_config: WebhookConfig 数据库模型实例
        """
        self.webhook_config = webhook_config
        self._raw_key: str = ""
        self._is_configured: bool = False

        # 解密凭证
        self._decrypt_credentials()

        # 检查配置是否完整
        self._is_configured = self._check_configured()

        # 子类特定初始化
        self._init_notifier()

    def _decrypt_credentials(self) -> None:
        """
        解密凭证 - 公共逻辑

        使用模型的 decrypted_key 属性统一处理解密
        """
        self._raw_key = self.webhook_config.decrypted_key

    def _check_configured(self) -> bool:
        """
        检查配置是否完整

        Returns:
            bool: 配置是否完整
        """
        return bool(self._raw_key)

    def _init_notifier(self) -> None:
        """
        子类特定初始化

        可在子类中覆盖以实现特定的初始化逻辑
        """
        pass

    @property
    def platform_name(self) -> str:
        """平台名称 - 子类必须覆盖"""
        raise NotImplementedError("子类必须设置 platform_name")

    @property
    def is_available(self) -> bool:
        """检查通知器是否可用"""
        return self._is_configured

    @abstractmethod
    async def send(self, content: str, msg_type: str = "text", **kwargs) -> bool:
        """
        发送消息 - 子类必须实现

        Args:
            content: 消息内容
            msg_type: 消息类型 (text/markdown/image)
            **kwargs: 额外参数

        Returns:
            bool: 是否发送成功
        """
        pass

    # ==================== 内容推送方法 ====================

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
        发送单篇文章

        默认实现会构建 Markdown 格式内容后发送
        子类可覆盖以实现自定义格式
        """
        content = f"## 📰 {title}\n\n"
        if tags:
            content += f"**标签**：{tags}\n\n"
        if score is not None:
            content += f"**评分**: ⭐ {score}/10\n\n"
        content += f"{summary}\n\n"
        content += f"**来源**: {source}\n\n"
        content += f"🔗 [阅读原文]({url})"

        return await self.send(content, "markdown", push_type="immediate")

    async def batch_send_article(self, article_list: List) -> bool:
        """
        批量发送文章

        直接构建一个包含所有文章的Markdown内容进行发送，避免多次调用API

        2026-04: 优先使用用户自定义模板，fallback 到默认格式
        """
        # 获取自定义模板（immediate 类型）
        template = await self._get_template_for_push_type("immediate")

        if template:
            # 使用自定义模板渲染
            context = {
                "articles": article_list,  # article_list 是 Article 对象列表
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            content = template_renderer.render(template, context)
            # # LLM 增强
            # from app.services.processor.llm_service import llm_service
            # content = await llm_service.enhance_article_content(content)
            return await self.send(content, "markdown", file_name='高分资讯', push_type="immediate")

        # Fallback 到默认格式
        content = report_content_generator.generate_article_batch_content(
            [{'title': a.title, 'tags': a.tags, 'score': a.score, 'summary': a.summary,
              'source_name': a.source_name, 'url': a.url} for a in article_list],
            enhance=False
        )

        return await self.send(content, "markdown", file_name='高分资讯', push_type="immediate")
    
    async def send_daily_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        date: Optional[str] = None,
    ) -> bool:
        """
        发送日报

        默认实现使用 ReportContentGenerator 生成内容
        子类可覆盖以实现自定义格式

        2026-04: 优先使用用户自定义模板，fallback 到默认模板
        """

        # 获取自定义模板
        template = await self._get_template_for_push_type("daily")
        if template:
            context = {
                "date": date or datetime.now().strftime("%Y-%m-%d"),
                "articles": articles,
                "github_repos": github_repos,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            content = template_renderer.render(template, context)
            # LLM 增强（可选）
            # from app.services.processor.llm_service import llm_service
            # content = await llm_service.enhance_report_content(content)
            return await self.send(content, "markdown", file_name='日报', push_type="daily")

# Fallback 到默认实现
        content = await report_content_generator.generate_daily_report_content(
            articles, github_repos, enhance=False
        )
        return await self.send(content, "markdown", file_name='日报', push_type="daily")

    async def send_weekly_report(
        self,
        articles: List[Dict],
        github_repos: List[Dict],
        week_start: str,
        week_end: str,
    ) -> bool:
        """
        发送周报

        默认实现使用 ReportContentGenerator 生成内容
        子类可覆盖以实现自定义格式

        2026-04: 优先使用用户自定义模板，fallback 到默认模板
        """

        # 获取自定义模板
        template = await self._get_template_for_push_type("weekly")
        if template:
            context = {
                "week_start": week_start,
                "week_end": week_end,
                "articles": articles,
                "github_repos": github_repos,
                "github_count": len(github_repos),
                "article_count": len(articles),
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
            content = template_renderer.render(template, context)
            # LLM 增强（可选）
            # from app.services.processor.llm_service import llm_service
            # content = await llm_service.enhance_report_content(content, report_type='weekly')
            return await self.send(content, "markdown", file_name='周报', push_type="weekly")

        # Fallback 到默认实现
        content = await report_content_generator.generate_weekly_report_content(
            articles, github_repos, week_start, week_end, enhance=False
        )
        return await self.send(content, "markdown", file_name='周报', push_type="weekly")

    async def _get_template_for_push_type(self, push_type: str) -> Optional[str]:
        """
        获取指定推送类型的自定义模板（异步查询）

        从数据库直接查询模板，避免懒加载 Session 问题

        Args:
            push_type: 推送类型 (daily/weekly/immediate)

        Returns:
            Optional[str]: 模板内容，如果未找到则返回 None
        """
        from sqlalchemy import select
        from app.models import WebhookTemplate

        try:
            from app.database import db
            async with db.get_session() as session:
                result = await session.execute(
                    select(WebhookTemplate).where(
                        WebhookTemplate.webhook_config_id == self.webhook_config.id,
                        WebhookTemplate.template_type == push_type,
                        WebhookTemplate.is_active == True,
                        WebhookTemplate.template_content != ''
                    )
                )
                template = result.scalar_one_or_none()
                if template:
                    return template.template_content
                return None
        except Exception as e:
            logger.warning(f"获取模板失败，使用默认模板: {e}")
            return None


def register_notifier(platform: str):
    """
    通知器注册装饰器

    用于将通知器类注册到全局注册表

    Args:
        platform: 平台名称 (wecom/obsidian)

    用法：
        @register_notifier("wecom")
        class DynamicWeComNotifier(BaseDynamicNotifier):
            platform_name = "wecom"
            ...
    """
    def decorator(notifier_class: Type[BaseDynamicNotifier]) -> Type[BaseDynamicNotifier]:
        # 存储到注册表，platform_name 属性在实例上通过 platform 属性获取
        BaseDynamicNotifier._registry[platform] = notifier_class
        logger.debug(f"注册通知器: {platform} -> {notifier_class.__name__}")
        return notifier_class
    return decorator


def get_notifier_class(platform: str) -> Optional[Type[BaseDynamicNotifier]]:
    """
    获取指定平台的 notifier 类

    Args:
        platform: 平台名称

    Returns:
        Type[BaseDynamicNotifier]: notifier 类，如果不存在返回 None
    """
    return BaseDynamicNotifier._registry.get(platform)


def create_notifier(webhook_config: WebhookConfig) -> Optional[BaseDynamicNotifier]:
    """
    根据 WebhookConfig 创建对应的 notifier 实例

    Args:
        webhook_config: WebhookConfig 实例

    Returns:
        BaseDynamicNotifier: notifier 实例，如果平台未注册返回 None
    """
    notifier_class = get_notifier_class(webhook_config.platform)
    if notifier_class is None:
        logger.warning(f"未知的平台类型: {webhook_config.platform}")
        return None
    return notifier_class(webhook_config)