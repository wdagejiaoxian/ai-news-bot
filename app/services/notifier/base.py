# -*- coding: utf-8 -*-
"""
消息推送模块

负责将内容推送到各个渠道:
- 企业微信 (Webhook) -> 移至 wecom/
- Telegram
- Discord (Webhook)
- Obsidian (Git) -> 移至 obsidian/

支持:
- 即时推送
- 日报推送
- 周报推送

架构变更 (2024-04):
- 新增动态 Webhook 支持：从数据库读取配置，不再依赖 .env
- 新增推送失败处理：失败次数计数，达到阈值自动停用 webhook

架构变更 (2026-04):
- Phase 2 优化：引入 BaseDynamicNotifier 基类和注册模式
- 引入 ReportContentGenerator 统一报告内容生成
- 企业微信相关代码移至 wecom/ 目录
"""

import asyncio
import re
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import httpx

from app.config import get_settings
from app.services.processor.llm_service import llm_service
from app.models import Article, WebhookConfig
from app.services.notifier.content_converter import content_converter, MAX_CONTENT_LENGTH
from app.services.notifier.dynamic_base import (
    BaseDynamicNotifier,
    register_notifier,
    create_notifier,
)
from app.services.push_log_service import push_log_service

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



class NotificationManager:
    """
    重构后的通知管理器

    不再依赖 .env 配置，每次推送从数据库查询 WebhookConfig
    支持动态创建多个 Notifier 实例，按平台 + webhook_id 管理

    新增功能：
    - 推送失败处理：失败次数计数，达到阈值自动停用 webhook
    - 推送类型独立配置：高分推送/日报推送/周报推送各有权开关和阈值
    """

    def __init__(self):
        self._notifiers: Dict[Tuple[str, int], Any] = {}  # {(platform, webhook_id): notifier}
        self._cache_time: Optional[datetime] = None
        self._cache_duration: timedelta = timedelta(minutes=5)
        self._webhook_cache: List[WebhookConfig] = []
        self._db = None

    def _get_db(self):
        """获取数据库实例"""
        if self._db is None:
            from app.database import db
            self._db = db
        return self._db

    def _is_cache_expired(self) -> bool:
        """检查缓存是否过期"""
        if self._cache_time is None:
            return True
        return datetime.now() - self._cache_time > self._cache_duration

    def _refresh_webhook_cache(self):
        """刷新 webhook 缓存"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            # 如果在异步上下文中，使用 ensure_future 不等待
            asyncio.ensure_future(self._async_refresh_webhook_cache())
        else:
            # 同步方式刷新（仅在没有事件循环时调用）
            asyncio.run(self._async_refresh_webhook_cache())

    async def _refresh_webhook_cache_safe(self):
        """安全的缓存刷新（可在任何上下文中调用）

        解决原方法在已有事件循环中调用 asyncio.run() 的问题
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 如果已经在运行，创建一个任务但不等待
                asyncio.create_task(self._async_refresh_webhook_cache())
            else:
                await self._async_refresh_webhook_cache()
        except RuntimeError:
            # 没有事件循环，创建新的
            asyncio.run(self._async_refresh_webhook_cache())

    async def _async_refresh_webhook_cache(self):
        """异步刷新 webhook 缓存

        迁移后：webhook_configs 表只保留核心字段
        - push_immediate_enabled, push_daily_enabled, push_weekly_enabled -> PushSettings
        - is_disabled -> FailureConfig
        """
        from sqlalchemy import select
        from sqlalchemy.orm import selectinload
        from app.models import PushSettings, FailureConfig

        try:
            async with self._get_db().get_session() as session:
                # 迁移后：LEFT JOIN PushSettings 和 FailureConfig
                # 没有对应记录的 webhook 使用默认值
                result = await session.execute(
                    select(WebhookConfig)
                    .options(selectinload(WebhookConfig.push_settings))
                    .options(selectinload(WebhookConfig.failure_config))
                    .options(selectinload(WebhookConfig.git_repo_config))
                    .options(selectinload(WebhookConfig.obsidian_config))
                    .outerjoin(PushSettings, WebhookConfig.id == PushSettings.webhook_config_id)
                    .outerjoin(FailureConfig, WebhookConfig.id == FailureConfig.webhook_config_id)
                    .where(
                        WebhookConfig.is_active == True,
                        # 过滤未禁用的：FailureConfig 不存在算启用，或 is_disabled=False
                        (FailureConfig.is_disabled == False) | (FailureConfig.id == None)
                    )
                )
                self._webhook_cache = list(result.scalars().all())
                self._cache_time = datetime.now()
                logger.info(f"刷新 webhook 缓存: {len(self._webhook_cache)} 个启用中的 webhook")
        except Exception as e:
            logger.error(f"刷新 webhook 缓存失败: {e}")

    def get_active_webhooks(self, push_type: str = None) -> List[WebhookConfig]:
        """
        获取启用的 webhook 配置（同步版本，使用缓存）

        Args:
            push_type: 推送类型 (immediate/daily/weekly)，不传则返回所有启用

        Returns:
            List[WebhookConfig]: 启用的 webhook 列表
        """
        # 检查缓存是否过期
        if self._is_cache_expired():
            # 同步版本：直接查询数据库
            from sqlalchemy import select

            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # 如果在异步上下文中，使用ensure_future
                asyncio.ensure_future(self._async_refresh_webhook_cache())
            else:
                # 同步方式直接查询
                asyncio.run(self._async_refresh_webhook_cache())

        webhooks = self._webhook_cache

        # 按推送类型过滤：迁移后从 PushSettings 获取
        if push_type == "immediate":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_immediate_enabled) or (w.push_settings is None)]
        elif push_type == "daily":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_daily_enabled) or (w.push_settings is None)]
        elif push_type == "weekly":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_weekly_enabled) or (w.push_settings is None)]

        return webhooks

    async def _get_active_webhooks_async(self, push_type: str = None) -> List[WebhookConfig]:
        """
        获取启用的 webhook 配置（异步版本）

        Args:
            push_type: 推送类型 (immediate/daily/weekly)，不传则返回所有启用

        Returns:
            List[WebhookConfig]: 启用的 webhook 列表
        """
        from sqlalchemy import select

        # 检查缓存是否过期
        if self._is_cache_expired():
            await self._async_refresh_webhook_cache()

        webhooks = self._webhook_cache

        # 按推送类型过滤：迁移后从 PushSettings 获取
        if push_type == "immediate":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_immediate_enabled) or (w.push_settings is None)]
        elif push_type == "daily":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_daily_enabled) or (w.push_settings is None)]
        elif push_type == "weekly":
            webhooks = [w for w in webhooks if (w.push_settings and w.push_settings.push_weekly_enabled) or (w.push_settings is None)]

        return webhooks

    def _get_notifier(self, webhook: WebhookConfig):
        """获取或创建指定 webhook 的 notifier 实例（使用注册模式）"""
        key = (webhook.platform, webhook.id)
        if key not in self._notifiers:
            # 使用注册模式创建 notifier
            notifier = create_notifier(webhook)
            if notifier is None:
                raise ValueError(f"Unknown platform: {webhook.platform}")
            self._notifiers[key] = notifier
            logger.info(f"创建新的 notifier 实例: {webhook.platform} - {webhook.name}")
        return self._notifiers[key]

    def _check_threshold(self, score: float, webhook: WebhookConfig, push_type: str) -> bool:
        """
        检查评分是否达到阈值

        迁移后：从 PushSettings 获取阈值

        Args:
            score: 文章评分
            webhook: webhook 配置
            push_type: 推送类型

        Returns:
            bool: 是否达到阈值
        """
        # 迁移后从 PushSettings 获取阈值
        ps = webhook.push_settings
        if ps:
            if push_type == "immediate":
                threshold = ps.push_immediate_threshold
            elif push_type == "daily":
                threshold = ps.push_daily_threshold
            elif push_type == "weekly":
                threshold = ps.push_weekly_threshold
            else:
                threshold = ps.push_immediate_threshold
        else:
            # 没有 PushSettings 时使用默认值（兼容）
            if push_type == "immediate":
                threshold = 85.0
            elif push_type == "daily":
                threshold = 75.0
            elif push_type == "weekly":
                threshold = 80.0
            else:
                threshold = 85.0

        return score >= threshold

    async def _increment_fail_count(self, webhook: WebhookConfig):
        """递增失败次数，超阈值时停用 webhook

        迁移后：更新 FailureConfig 表的 push_fail_count 和 is_disabled
        """
        from sqlalchemy import select
        from app.models import FailureConfig

        try:
            async with self._get_db().get_session() as session:
                # 查询或创建 FailureConfig
                result = await session.execute(
                    select(FailureConfig).where(FailureConfig.webhook_config_id == webhook.id)
                )
                fc = result.scalar_one_or_none()

                if fc:
                    fc.push_fail_count += 1
                    if fc.push_fail_count >= fc.push_fail_threshold:
                        fc.is_disabled = True
                        logger.warning(
                            f"Webhook {webhook.id} ({webhook.name}) "
                            f"因推送失败次数过多({fc.push_fail_count})已被停用"
                        )
                    await session.commit()

                    # 更新缓存中的对象
                    if webhook.failure_config:
                        webhook.failure_config.push_fail_count = fc.push_fail_count
                        webhook.failure_config.is_disabled = fc.is_disabled

                    # 清除 notifier 缓存，强制重新创建
                    key = (webhook.platform, webhook.id)
                    if key in self._notifiers:
                        del self._notifiers[key]
        except Exception as e:
            logger.error(f"更新 webhook 失败次数失败: {e}")

    async def _reset_fail_count(self, webhook: WebhookConfig):
        """重置失败次数 - 迁移后操作 FailureConfig 表"""
        from sqlalchemy import select
        from app.models import FailureConfig

        if not webhook.failure_config or webhook.failure_config.push_fail_count > 0:
            try:
                async with self._get_db().get_session() as session:
                    result = await session.execute(
                        select(FailureConfig).where(FailureConfig.webhook_config_id == webhook.id)
                    )
                    fc = result.scalar_one_or_none()
                    if fc and fc.push_fail_count > 0:
                        fc.push_fail_count = 0
                        await session.commit()

                        # 更新缓存中的对象
                        if webhook.failure_config:
                            webhook.failure_config.push_fail_count = 0
            except Exception as e:
                logger.error(f"重置 webhook 失败次数失败: {e}")

    async def _batch_reset_fail_count(self, webhooks: List[WebhookConfig]):
        """批量重置失败次数（优化版：减少数据库commit次数）

        迁移后：操作 FailureConfig 表
        """
        from sqlalchemy import select, update
        from app.models import FailureConfig

        if not webhooks:
            return

        # 只处理有失败记录的（通过 failure_config 判断）
        webhooks_to_reset = [w for w in webhooks if w.failure_config and w.failure_config.push_fail_count > 0]
        if not webhooks_to_reset:
            return

        try:
            async with self._get_db().get_session() as session:
                webhook_ids = [w.id for w in webhooks_to_reset]

                # 批量更新 FailureConfig
                await session.execute(
                    update(FailureConfig)
                    .where(FailureConfig.webhook_config_id.in_(webhook_ids))
                    .values(push_fail_count=0)
                )
                await session.commit()

                # 更新缓存
                for webhook in webhooks_to_reset:
                    if webhook.failure_config:
                        webhook.failure_config.push_fail_count = 0

            logger.debug(f"批量重置 {len(webhooks_to_reset)} 个 webhook 的失败计数")
        except Exception as e:
            logger.error(f"批量重置失败计数失败: {e}")

    async def _batch_increment_fail_count(self, webhooks: List[WebhookConfig]):
        """批量递增失败次数，超阈值时停用 webhook（优化版：减少数据库commit次数）

        迁移后：操作 FailureConfig 表
        """
        from sqlalchemy import select, update
        from app.models import FailureConfig

        if not webhooks:
            return

        try:
            async with self._get_db().get_session() as session:
                webhook_ids = [w.id for w in webhooks]

                # 批量查询 FailureConfig
                result = await session.execute(
                    select(FailureConfig).where(FailureConfig.webhook_config_id.in_(webhook_ids))
                )
                fc_map = {fc.webhook_config_id: fc for fc in result.scalars().all()}

                # 批量更新
                disabled_webhooks = []
                for webhook in webhooks:
                    fc = fc_map.get(webhook.id)
                    if fc:
                        fc.push_fail_count += 1
                        if fc.push_fail_count >= fc.push_fail_threshold:
                            fc.is_disabled = True
                            disabled_webhooks.append((webhook, fc.push_fail_count))

                await session.commit()

                # 更新缓存并清除停用 webhook 的 notifier
                for webhook in webhooks:
                    fc = fc_map.get(webhook.id)
                    if fc:
                        if webhook.failure_config:
                            webhook.failure_config.push_fail_count = fc.push_fail_count
                            webhook.failure_config.is_disabled = fc.is_disabled
                        # 清除 notifier 缓存
                        key = (webhook.platform, webhook.id)
                        if key in self._notifiers:
                            del self._notifiers[key]

                # 记录停用的 webhook
                for webhook, fail_count in disabled_webhooks:
                    logger.warning(
                        f"Webhook {webhook.id} ({webhook.name}) "
                        f"因推送失败次数过多({fail_count})已被停用"
                    )

                if disabled_webhooks:
                    logger.info(f"本次批量更新中 {len(disabled_webhooks)} 个 webhook 因失败过多被停用")

        except Exception as e:
            logger.error(f"批量更新失败计数失败: {e}")

    def _record_push_log(
        self,
        webhook: WebhookConfig,
        push_type: str,
        is_success: bool,
        error_message: Optional[str] = None,
        article_id: Optional[int] = None,
        github_repo_id: Optional[int] = None,
        content: str = "",
    ) -> None:
        """
        异步记录推送日志（不阻塞主流程）

        使用 asyncio.ensure_future 确保 PushLog 写入不阻塞推送流程。
        写入失败时会自动降级到文件日志（由 PushLogService 内部处理）。
        """
        asyncio.ensure_future(
            push_log_service.log_push(
                webhook_config_id=webhook.id,
                webhook_config_name=webhook.name,
                platform=webhook.platform,
                push_type=push_type,
                content=content,
                is_success=is_success,
                article_id=article_id,
                github_repo_id=github_repo_id,
                error_message=error_message,
            )
        )

    def invalidate_cache(self):
        """使缓存失效，强制刷新"""
        self._cache_time = None
        self._webhook_cache = []
        self._notifiers = {}
        logger.info("NotificationManager 缓存已清除")

    # ==================== 推送方法 ====================

    async def send_article(
            self,
            article: Article,
            push_type: str = "immediate"
    ) -> Dict[str, bool]:
        """
        推送文章到所有启用的 webhook

        Args:
            article: 文章对象
            push_type: 推送类型 (immediate/daily/weekly)

        Returns:
            Dict[str, bool]: 各 webhook 发送结果 {webhook_name: success}
        """
        results = {}
        webhooks = await self._get_active_webhooks_async(push_type)

        for webhook in webhooks:
            # 检查阈值
            if article.score and not self._check_threshold(article.score, webhook, push_type):
                continue

            try:
                notifier = self._get_notifier(webhook)
                success = await notifier.send_article(
                    title=article.title,
                    summary=article.summary or "",
                    url=article.url,
                    source=article.source_name or "unknown",
                    tags=article.tags,
                    score=article.score,
                )

                if success:
                    await self._reset_fail_count(webhook)
                else:
                    await self._increment_fail_count(webhook)

                # 异步记录推送日志
                self._record_push_log(
                    webhook=webhook,
                    push_type=push_type,
                    is_success=success,
                    article_id=article.id,
                    content=article.title,
                )

                results[webhook.name] = success
            except Exception as e:
                logger.error(f"推送文章到 webhook {webhook.name} 失败: {e}")
                await self._increment_fail_count(webhook)
                # 异步记录推送失败日志
                self._record_push_log(
                    webhook=webhook,
                    push_type=push_type,
                    is_success=False,
                    article_id=article.id,
                    content=article.title,
                    error_message=str(e),
                )
                results[webhook.name] = False

        return results

    async def send_articles_batch(
            self,
            articles: List[Article],
            push_type: str = "immediate"
    ) -> Dict[str, bool]:
        """
        批量推送文章到所有启用的 webhook（并发优化版）

        使用 asyncio.gather 实现真正的并发推送，大幅提升多 webhook 时的性能

        Args:
            articles: 文章列表
            push_type: 推送类型 (immediate/daily/weekly)

        Returns:
            Dict[str, bool]: 各 webhook 发送结果
        """
        results = {}
        webhooks = await self._get_active_webhooks_async(push_type)

        if not webhooks:
            logger.info(f"[{push_type}] 没有启用的 webhook")
            return {}

        # 按 webhook 分组需要推送的文章
        articles_by_webhook = {}
        webhook_by_id = {}

        for webhook in webhooks:
            webhook_by_id[webhook.id] = webhook
            target_articles = [
                a for a in articles
                if a.score and self._check_threshold(a.score, webhook, push_type)
            ]
            if target_articles:
                articles_by_webhook[webhook.id] = (webhook, target_articles)
            else:
                threshold = self._get_threshold(webhook, push_type)
                logger.info(
                    f"[{push_type}] Webhook {webhook.name} "
                    f"无达标文章（阈值={threshold}），跳过"
                )

        if not articles_by_webhook:
            logger.info(f"[{push_type}] 所有 webhook 都没有达标文章")
            return {}

        # 构建并发推送任务
        async def push_single_webhook(webhook_id: int):
            """单个 webhook 的推送任务"""
            webhook, target_articles = articles_by_webhook[webhook_id]
            try:
                notifier = self._get_notifier(webhook)

                if hasattr(notifier, 'batch_send_article'):
                    success = await notifier.batch_send_article(target_articles)
                else:
                    # 其他平台不支持 batch_send_article，逐个发送
                    success = True
                    for article in target_articles:
                        s = await notifier.send_article(
                            title=article.title,
                            summary=article.summary or "",
                            url=article.url,
                            source=article.source_name or "unknown",
                            tags=article.tags,
                            score=article.score,
                        )
                        success = success and s

                return webhook_id, success, None
            except Exception as e:
                logger.error(f"批量推送失败 webhook={webhook.name}: {e}")
                return webhook_id, False, str(e)

        # 并发执行所有推送任务
        logger.info(f"[{push_type}] 开始并发推送到 {len(articles_by_webhook)} 个 webhook...")
        tasks = [push_single_webhook(wid) for wid in articles_by_webhook.keys()]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 收集结果并分组
        success_webhooks = []
        failed_webhooks = []

        for result in task_results:
            # asyncio.gather with return_exceptions=True returns exceptions as-is
            # BaseException catches all exceptions including SystemExit, KeyboardInterrupt
            if isinstance(result, BaseException):
                logger.error(f"推送任务异常: {result}")
                continue

            webhook_id, success, error = result
            webhook = webhook_by_id[webhook_id]
            results[webhook.name] = success

            # 异步记录推送日志
            self._record_push_log(
                webhook=webhook,
                push_type=push_type,
                is_success=success,
                error_message=error,
                content=f"批量推送 {len(articles_by_webhook[webhook_id][1])} 篇",
            )

            if success:
                success_webhooks.append(webhook)
                logger.info(
                    f"[{push_type}] 批量推送 {len(articles_by_webhook[webhook_id][1])} "
                    f"篇文章到 {webhook.name} 成功"
                )
            else:
                failed_webhooks.append(webhook)
                logger.warning(
                    f"[{push_type}] 批量推送到 {webhook.name} 失败: {error or '未知错误'}"
                )

        # 批量更新失败/成功计数（优化：减少数据库commit）
        if failed_webhooks:
            await self._batch_increment_fail_count(failed_webhooks)
        if success_webhooks:
            await self._batch_reset_fail_count(success_webhooks)

        success_count = len(success_webhooks)
        fail_count = len(failed_webhooks)
        logger.info(
            f"[{push_type}] 推送完成: 成功 {success_count}/{len(webhooks)}, "
            f"失败 {fail_count}/{len(webhooks)}"
        )

        return results

    def _get_threshold(self, webhook: WebhookConfig, push_type: str) -> float:
        """获取指定推送类型的阈值

        迁移后：从 PushSettings 获取阈值
        """
        ps = webhook.push_settings
        if ps:
            if push_type == "immediate":
                return ps.push_immediate_threshold
            elif push_type == "daily":
                return ps.push_daily_threshold
            elif push_type == "weekly":
                return ps.push_weekly_threshold
        # 默认值（兼容）
        if push_type == "immediate":
            return 85.0
        elif push_type == "daily":
            return 75.0
        elif push_type == "weekly":
            return 80.0
        return 85.0

    async def send_daily_report(
            self,
            articles: List[Dict],
            github_repos: List[Dict],
            date: str = None,
            webhook: WebhookConfig = None,
    ) -> bool:
        """
        发送日报（支持并发优化）

        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            date: 日期
            webhook: 指定 webhook，不传则发送到所有启用的日报 webhook

        Returns:
            bool: 是否成功
        """
        if webhook:
            # 发送到指定 webhook
            try:
                notifier = self._get_notifier(webhook)
                success = await notifier.send_daily_report(articles, github_repos, date)
                if success:
                    await self._reset_fail_count(webhook)
                else:
                    await self._increment_fail_count(webhook)
                # 异步记录推送日志
                self._record_push_log(
                    webhook=webhook,
                    push_type="daily",
                    is_success=success,
                    content=f"日报 {date or ''}",
                )
                return success
            except Exception as e:
                logger.error(f"发送日报到 webhook {webhook.name} 失败: {e}")
                await self._increment_fail_count(webhook)
                # 异步记录推送失败日志
                self._record_push_log(
                    webhook=webhook,
                    push_type="daily",
                    is_success=False,
                    error_message=str(e),
                    content=f"日报 {date or ''}",
                )
                return False
        else:
            # 发送到所有启用的日报 webhook（并发优化）
            return await self._send_report_to_webhooks(
                webhooks=await self._get_active_webhooks_async("daily"),
                push_func=lambda wh: self._get_notifier(wh).send_daily_report(articles, github_repos, date),
                push_type="daily"
            )

    async def send_weekly_report(
            self,
            articles: List[Dict],
            github_repos: List[Dict],
            week_start: str,
            week_end: str,
            webhook: WebhookConfig = None,
    ) -> bool:
        """
        发送周报（支持并发优化）

        Args:
            articles: 文章列表
            github_repos: GitHub项目列表
            week_start: 周开始日期
            week_end: 周结束日期
            webhook: 指定 webhook，不传则发送到所有启用的周报 webhook

        Returns:
            bool: 是否成功
        """
        if webhook:
            # 发送到指定 webhook
            try:
                notifier = self._get_notifier(webhook)
                success = await notifier.send_weekly_report(
                    articles, github_repos, week_start, week_end
                )
                if success:
                    await self._reset_fail_count(webhook)
                else:
                    await self._increment_fail_count(webhook)
                # 异步记录推送日志
                self._record_push_log(
                    webhook=webhook,
                    push_type="weekly",
                    is_success=success,
                    content=f"周报 {week_start}~{week_end}",
                )
                return success
            except Exception as e:
                logger.error(f"发送周报到 webhook {webhook.name} 失败: {e}")
                await self._increment_fail_count(webhook)
                # 异步记录推送日志
                self._record_push_log(
                    webhook=webhook,
                    push_type="weekly",
                    is_success=False,
                    error_message=str(e),
                    content=f"周报 {week_start}~{week_end}",
                )
                return False
        else:
            # 发送到所有启用的周报 webhook（并发优化）
            return await self._send_report_to_webhooks(
                webhooks=await self._get_active_webhooks_async("weekly"),
                push_func=lambda wh: self._get_notifier(wh).send_weekly_report(
                    articles, github_repos, week_start, week_end
                ),
                push_type="weekly"
            )

    async def _send_report_to_webhooks(
        self,
        webhooks: List[WebhookConfig],
        push_func: callable,
        push_type: str
    ) -> bool:
        """
        通用日报/周报推送方法（消除重复代码，并发优化）

        Args:
            webhooks: webhook 列表
            push_func: 推送函数，接受 webhook 参数返回 bool
            push_type: 推送类型日志标签

        Returns:
            bool: 是否至少有一个成功
        """
        if not webhooks:
            logger.info(f"[{push_type}] 没有启用的 webhook")
            return False

        # 并发执行所有推送任务
        async def push_single(wh: WebhookConfig):
            try:
                success = await push_func(wh)
                return wh, success, None
            except Exception as e:
                logger.error(f"[{push_type}] 推送到 {wh.name} 失败: {e}")
                return wh, False, str(e)

        logger.info(f"[{push_type}] 开始并发推送到 {len(webhooks)} 个 webhook...")
        tasks = [push_single(wh) for wh in webhooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 分组成功/失败的 webhook
        success_webhooks = []
        failed_webhooks = []

        for result in results:
            # BaseException catches all exceptions including SystemExit, KeyboardInterrupt
            if isinstance(result, BaseException):
                logger.error(f"推送任务异常: {result}")
                continue
            wh, success, error = result

            # 异步记录推送日志
            self._record_push_log(
                webhook=wh,
                push_type=push_type,
                is_success=success,
                error_message=error,
            )

            if success:
                success_webhooks.append(wh)
            else:
                failed_webhooks.append(wh)

        # 批量更新失败计数
        if failed_webhooks:
            await self._batch_increment_fail_count(failed_webhooks)
        if success_webhooks:
            await self._batch_reset_fail_count(success_webhooks)

        success_count = len(success_webhooks)
        fail_count = len(failed_webhooks)
        logger.info(
            f"[{push_type}] 推送完成: 成功 {success_count}/{len(webhooks)}, "
            f"失败 {fail_count}/{len(webhooks)}"
        )

        return success_count > 0


# 创建全局通知管理器
notification_manager = NotificationManager()
