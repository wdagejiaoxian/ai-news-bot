# -*- coding: utf-8 -*-
"""
定时任务调度模块

使用 APScheduler 实现定时任务:
- 定时采集AI资讯
- 定时采集GitHub热门
- 每日精选推送
- 周报汇总推送
"""

import gc
import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List
from tenacity import retry, stop_after_attempt, wait_fixed

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_, or_, delete, func

from app.config import get_settings
from app.database import db
from app.models import Article, ArticleStatus, GitHubRepo, RSSSource
from app.services.fetcher.github_trending import github_fetcher
from app.services.fetcher.rss_parser import rss_fetcher, RSSFetcher
from app.services.notifier.base import notification_manager
from app.services.processor.deduplicator import deduplicator
from app.services.processor.batch_processor import batch_processor
from app.services.scheduler.config_loader import config_loader
from app.services.scheduler.config_logger import config_logger
from app.services.scheduler.task_decorator import task_wrapper
from app.utils.github_language import normalize_language_name

logger = logging.getLogger(__name__)


def get_rss_error_threshold() -> int:
    """获取RSS错误阈值"""
    from app.config import get_settings
    return get_settings().rss_error_threshold


# 任务ID到方法名的映射
TASK_METHOD_MAP = {
    "fetch_ai_news": "fetch_ai_news",
    "fetch_github_trending": "fetch_github_trending",
    "fetch_weekly_github_trending": "fetch_weekly_github_trending",
    "send_daily_report": "send_daily_report",
    "send_weekly_report": "send_weekly_report",
    "process_pending_content": "process_pending_content",
    "cleanup_low_score_articles": "cleanup_low_score_articles",
    "cleanup_expired_data": "to_cleanup_expired_data",
    "cluster_topics": "cluster_topics",
    "reindex_vectors": "reindex_vectors",
}

# 任务ID到显示名称的映射
TASK_NAME_MAP = {
    "fetch_ai_news": "采集AI资讯",
    "fetch_github_trending": "采集GitHub热门",
    "fetch_weekly_github_trending": "采集GitHub周热门",
    "send_daily_report": "发送日报",
    "send_weekly_report": "发送周报",
    "process_pending_content": "处理待处理内容",
    "cleanup_low_score_articles": "清理低分文章",
    "cleanup_expired_data": "清理过期数据",
    "cluster_topics": "主题聚类",
    "reindex_vectors": "向量对账",
}


class TaskScheduler:
    """
    定时任务调度器
    
    管理所有定时任务:
    - 数据采集
    - 内容处理
    - 消息推送
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.scheduler = None
        self.config_loader = config_loader
        self.config_logger = config_logger
        # 延迟导入 operation_logger，避免循环导入
        self._operation_logger = None
        # Phase P0-A 优化: Task 追踪
        # 存储所有 fire-and-forget 后台补全任务的引用
        self._enrich_tasks: List[asyncio.Task] = []
        self._init_scheduler()

    @property
    def operation_logger(self):
        """延迟获取 operation_logger"""
        if self._operation_logger is None:
            from app.services.operation_logger import operation_logger
            self._operation_logger = operation_logger
        return self._operation_logger
    
    def _init_scheduler(self):
        """初始化调度器"""
        # 配置执行器
        executors = {
            "default": AsyncIOExecutor(),
        }
        
        # 创建调度器
        self.scheduler = AsyncIOScheduler(
            executors=executors,
            job_defaults={
                "coalesce": True,  # 合并错过的任务
                "max_instances": 1,  # 最多同时运行1个实例
                "misfire_grace_time": 600,  # 允许10分钟内延迟，超时任务将被跳过（修复S1）
            }
        )
    
    def start(self):
        """启动调度器并注册任务"""
        if self.scheduler is None:
            self._init_scheduler()
        
        # 注册任务
        self._register_jobs()
        
        # 启动
        self.scheduler.start()
        logger.info("定时任务调度器已启动")
    
    def shutdown(self):
        """关闭调度器"""
        if self.scheduler:
            self.scheduler.shutdown()
            logger.info("定时任务调度器已关闭")
    
    def _register_jobs(self):
        """从数据库读取配置注册所有定时任务"""
        import asyncio

        # 获取事件循环
        try:
            loop = asyncio.get_event_loop()
        except Exception as e:
            logger.error(f"获取事件循环失败: {e}")
            return

        # 在运行中的循环调度异步注册任务
        if loop.is_running():
            asyncio.ensure_future(self._register_jobs_async())
        else:
            loop.run_until_complete(self._register_jobs_async())

    async def _register_jobs_async(self, skip_init=False):
        """异步注册任务（内部方法）

        Args:
            skip_init: 是否跳过初始化配置（True时用于热重载，避免重复初始化日志）
        """
        # 等待数据库配置初始化完成（热重载时跳过以避免重复日志）
        if not skip_init:
            try:
                await self.config_loader.initialize_db_configs()
            except Exception as e:
                logger.warning(f"初始化配置检查失败: {e}")

        # 获取所有任务配置
        try:
            configs = await self.config_loader.get_all_configs()
        except Exception as e:
            logger.warning(f"获取任务配置失败: {e}")
            configs = []

        # 注册每个任务
        for config in configs:
            self._register_single_job(config)

        logger.info(f"已注册 {len(self.scheduler.get_jobs())} 个定时任务")

    def _register_single_job(self, config):
        """
        注册单个定时任务

        Args:
            config: ScheduledTaskConfig 实例
        """
        task_name = config.task_name
        task_id = config.task_name

        # 检查是否激活
        if not config.is_active:
            logger.info(f"任务 {task_name} 已禁用，跳过注册")
            return

        # 获取任务方法
        method_name = TASK_METHOD_MAP.get(task_name)
        if not method_name:
            logger.warning(f"未知任务: {task_name}")
            return

        job_func = getattr(self, method_name, None)
        if not job_func:
            logger.warning(f"任务方法不存在: {method_name}")
            return

        # 构建 trigger
        try:
            if config.task_type == "interval":
                trigger = IntervalTrigger(minutes=config.interval_minutes or 30)
            else:  # fixed
                trigger = CronTrigger(
                    hour=config.hour or 0,
                    minute=config.minute or 0,
                    day_of_week=config.day_of_week,
                )
        except Exception as e:
            logger.error(f"创建触发器失败 for {task_name}: {e}")
            return

        # 注册任务
        self.scheduler.add_job(
            job_func,
            trigger,
            id=task_id,
            name=TASK_NAME_MAP.get(task_name, task_name),
            replace_existing=True,
        )
    
    # ==================== 任务实现 ====================

    @task_wrapper("fetch_ai_news")
    async def fetch_ai_news(self):
        """
        采集AI资讯任务

        从RSS源获取最新资讯
        使用 @task_wrapper 统一处理日志和异常

        功能：
        - 支持源级别独立采集间隔（fetch_interval）
        - 支持增量检测（Last-Modified/ETag）
        - 采集后更新 last_fetched_at, last_modified, etag
        """
        from app.config import get_settings
        settings = get_settings()

        # 获取当前时间（用于间隔判断）
        now = datetime.now(timezone.utc)

        # ========== 第一步：筛选需要采集的源 ==========
        try:
            async with db.get_session() as session:
                # 查询数据库中 is_active=True 的 RSS 源
                result = await session.execute(
                    select(RSSSource).where(RSSSource.is_active == True)
                )
                db_sources = result.scalars().all()

                if not db_sources:
                    logger.warning("数据库中无活跃RSS源，跳过本次采集。请在前端配置RSS源。")
                    return 0

                # 筛选需要采集的源（根据 fetch_interval）
                sources_to_fetch = []
                for source in db_sources:
                    # 检查是否到达采集时间
                    if source.last_fetched_at is None:
                        # 从未采集过，立即采集
                        sources_to_fetch.append(source)
                        logger.debug(f"源 {source.name} 从未采集，立即采集")
                    elif source.fetch_interval <= 0:
                        # 间隔为0或不合法，视为立即采集
                        sources_to_fetch.append(source)
                    else:
                        # 检查时间差
                        last_fetched = source.last_fetched_at
                        if last_fetched.tzinfo is None:
                            last_fetched = last_fetched.replace(tzinfo=timezone.utc)

                        elapsed_seconds = (now - last_fetched).total_seconds()
                        elapsed_minutes = elapsed_seconds / 60

                        if elapsed_seconds >= source.fetch_interval * 60:
                            sources_to_fetch.append(source)
                            logger.debug(
                                f"源 {source.name} 距上次采集 {elapsed_minutes:.1f} 分钟，"
                                f"已达到间隔 {source.fetch_interval} 分钟，开始采集"
                            )
                        else:
                            remaining_minutes = source.fetch_interval - elapsed_minutes
                            logger.debug(
                                f"源 {source.name} 距上次采集 {elapsed_minutes:.1f} 分钟，"
                                f"还需 {remaining_minutes:.1f} 分钟，跳过本次采集"
                            )

                if not sources_to_fetch:
                    logger.info("所有RSS源均未到达采集时间，跳过本次采集")
                    return 0

                logger.info(f"从 {len(db_sources)} 个活跃源中筛选出 {len(sources_to_fetch)} 个需要采集的源")

        except Exception as e:
            logger.error(f"查询数据库RSS源失败: {e}")
            raise  # 向上抛出异常，由 task_wrapper 处理

        # ========== 第二步：并发采集（使用增量检测）==========
        all_articles = []
        # T13 优化: fetch_results 不再保留 articles 列表，只保留元数据
        fetch_results = []  # [(source, is_success, error_msg, new_last_modified, new_etag), ...]
        semaphore = asyncio.Semaphore(settings.rss_concurrent_limit)

        async def fetch_single_source(source):
            """采集单个源（带并发限制和任务级超时）"""
            async with semaphore:
                try:
                    # Phase 2 A3 优化: 任务级超时（只对 HTTP 请求计时，不包含 semaphore 等待时间）
                    articles, is_success, error_msg, new_last_modified, new_etag = \
                        await asyncio.wait_for(
                            rss_fetcher.fetch_feed_incremental(
                                feed_url=source.url,
                                last_modified=source.last_modified,
                                etag=source.etag,
                            ),
                            timeout=settings.rss_fetch_timeout
                        )
                    return source, articles, is_success, error_msg, new_last_modified, new_etag
                except asyncio.TimeoutError:
                    logger.warning(
                        f"RSS 源采集超时（{settings.rss_fetch_timeout}秒）: {source.name} ({source.url})"
                    )
                    # 超时时返回失败元组，不影响其他源
                    return source, [], False, "采集超时", None, None

        # 并发执行所有采集任务
        tasks = [fetch_single_source(source) for source in sources_to_fetch]
        task_results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整理结果
        # T15 优化: 异常分类处理
        for result in task_results:
            if isinstance(result, Exception):
                # 分类处理异常
                if isinstance(result, asyncio.TimeoutError):
                    logger.warning(f"采集超时 (timeout)")
                elif isinstance(result, ConnectionError):
                    logger.warning(f"网络连接错误: {result}")
                elif isinstance(result, RuntimeError):
                    logger.error(f"采集运行时异常 (runtime): {result}")
                else:
                    logger.error(f"采集异常 (unknown): {type(result).__name__}: {result}")
                continue

            source, articles, is_success, error_msg, new_last_modified, new_etag = result
            all_articles.extend(articles)
            # T13: 只保留元数据，不保留 articles 列表
            fetch_results.append((source, is_success, error_msg, new_last_modified, new_etag))

        # ========== 第三步：保存文章（补全已在 _parse_entry 中完成）==========
        if all_articles:
            articles_to_enrich = []
            to_save_articles = []

            # 先进行url哈希去重
            url_hash_unique_articles = await deduplicator.batch_check_duplicate_article(all_articles)

            # 对文章根据需不需要补全进行分组
            for article in url_hash_unique_articles:
                if article.get("needs_enrichment"):
                    articles_to_enrich.append(article)
                else:
                    to_save_articles.append(article)

            saved_count, skipped_count = await deduplicator.batch_save_articles(
                to_save_articles, skip_url_dedup=True
            )
            logger.info(f"不需要补全的文章保存完成，新增 {saved_count} 篇，跳过 {skipped_count} 篇重复文章")

            # Phase 3 PH3 优化：后台异步补全（不影响采集流程）
            # 筛选需要后台补全的文章（包含 needs_enrichment 标记的文章）

            if articles_to_enrich:
                logger.info(f"触发后台补全: {len(articles_to_enrich)} 篇文章")
                self._launch_background_enrich(articles_to_enrich)
        else:
            saved_count = 0
            skipped_count = 0
            logger.info("本次采集无新文章")

        # ========== 第四步：更新源的采集状态（last_fetched_at, last_modified, etag）==========
        # Phase 5 B1 优化: tenacity 导入已移到文件顶部
        @retry(stop=stop_after_attempt(3), wait=wait_fixed(1))
        async def _commit_with_retry(session):
            """带重试的数据库提交"""
            await session.commit()

        async with db.get_session() as session:
            # T17 优化: 复用第一次查询的结果，避免重复查询
            # 直接使用 sources_to_fetch 列表，不需要重新查询

            # Phase 1 A1 优化: 双重循环 O(k²) → O(k) 索引查找
            results_by_id = {
                sr[0].id: sr
                for sr in fetch_results
            }

            for source in sources_to_fetch:
                # O(1) 查找
                sr = results_by_id.get(source.id)
                if not sr:
                    continue

                fetched_source, is_success, error_msg, new_last_modified, new_etag = sr
                if is_success:
                    # 采集成功，更新状态
                    source.last_fetched_at = datetime.now(timezone.utc)
                    source.last_modified = new_last_modified
                    source.etag = new_etag
                    # 重置错误计数
                    if source.fetch_error_count > 0:
                        logger.info(f"源 {source.name} 采集成功，重置错误计数")
                        source.fetch_error_count = 0
                else:
                    # 采集失败，增加错误计数
                    source.fetch_error_count += 1
                    logger.warning(
                        f"源 {source.url} 采集失败，"
                        f"错误次数: {source.fetch_error_count}/{get_rss_error_threshold()}"
                    )

            # T14: 使用重试机制提交
            try:
                await _commit_with_retry(session)
            except Exception as e:
                logger.error(f"数据库提交失败（已重试3次）: {e}")
                await session.rollback()

        # ========== 第五步：错误计数和自动禁用逻辑 ==========
        failed_sources = []
        for source, is_success, error_msg, _, _ in fetch_results:
            if not is_success:
                failed_sources.append(source)

        if failed_sources:
            logger.warning(f"本次采集有 {len(failed_sources)} 个RSS源失败")
            async with db.get_session() as session:
                # 批量查询失败的源
                failed_urls = [s.url for s in failed_sources]
                result = await session.execute(
                    select(RSSSource).where(RSSSource.url.in_(failed_urls))
                )
                failed_db_sources = result.scalars().all()

                disabled_sources = []
                for source in failed_db_sources:
                    error_threshold = get_rss_error_threshold()
                    if source.fetch_error_count >= error_threshold:
                        source.is_active = False
                        disabled_sources.append(source.url)
                        logger.error(f"RSS源因错误次数达到阈值已自动禁用: {source.url}")

                if disabled_sources:
                    await session.commit()

        # T16 优化: 触发 GC 回收内存
        # Phase 5 B1 优化: gc 导入已移到文件顶部
        gc.collect()
        logger.debug("GC 已触发，回收内存")

        logger.info(f"AI资讯采集完成，新增 {saved_count} 篇")
        return saved_count

    # =========================================================================
    # Phase P0-A 优化: Task 追踪 + 优雅关闭
    # =========================================================================

    def _launch_background_enrich(self, articles_to_enrich: List[dict]) -> None:
        """
        启动后台补全任务并追踪

        Phase P0-A 优化：取代直接的 asyncio.create_task
        保留 Task 引用以支持优雅关闭和状态查询
        """
        if not articles_to_enrich:
            return

        task = asyncio.create_task(
            self._background_enrich(articles_to_enrich),
            name="background_enrich"
        )
        self._enrich_tasks.append(task)
        task.add_done_callback(self._enrich_tasks.remove)
        logger.info(f"后台补全任务已启动: {len(articles_to_enrich)} 篇文章")

    async def _cancel_pending_enrich(self, timeout: float = 5.0) -> None:
        """
        优雅关闭：取消并等待所有进行中的补全任务

        Phase P0-A 优化：应用关闭时调用，避免 task 被事件循环强制销毁

        Args:
            timeout: 等待每个 task 完成的最大秒数
        """
        if not self._enrich_tasks:
            return

        pending_count = len(self._enrich_tasks)
        logger.info(f"正在取消 {pending_count} 个后台补全任务...")

        # 先尝试取消所有未完成的任务
        for task in self._enrich_tasks:
            if not task.done():
                task.cancel()

        # 等待任务响应取消（最多 timeout 秒）
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._enrich_tasks, return_exceptions=True),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            logger.warning(
                f"等待后台补全任务超时（{timeout}s），"
                f"仍有 {sum(1 for t in self._enrich_tasks if not t.done())} 个未完成"
            )

        self._enrich_tasks.clear()
        logger.info("后台补全任务清理完成")

    # =========================================================================
    # Phase 3 PH3 优化: 后台补全
    # =========================================================================

    async def _background_enrich(self, articles_to_enrich: List[dict]) -> None:
        """
        后台异步补全文章内容并保存

        Phase 3 PH3 优化：将内容补全从采集主流程解耦
        Phase 3B 优化：添加并发控制和进度日志
        Phase P0-B 优化(B1)：收集结果后批量 UPDATE，N 个事务 → 1 个事务

        流程：
        1. 逐篇调用 trafilatura 获取完整内容
        2. 补全成功 → 更新 article_info['content'] 为完整正文
        3. 补全失败/超时/域名跳过 → 保留原始 article_info（content 可能是 summary 兜底）
        4. 所有文章（含补全成功和失败）统一通过 batch_save_articles 进行语义去重 + 批量 INSERT
        5. 向量索引由 process_pending_content 定时任务统一处理，此处不做

        Args:
            articles_to_enrich: 需要补全的文章列表，每项为完整的 article dict
                                （需包含 title, url, url_hash, content, summary,
                                 source, source_name, author, published_at）
        """
        if not articles_to_enrich:
            return

        total_count = len(articles_to_enrich)
        logger.info(f"后台补全开始: {total_count} 篇文章等待补全")

        # Phase P1-A 配置化：读取配置
        settings = get_settings()

        # Phase 3B/P0-B 优化：并发控制（配置化）
        semaphore = asyncio.Semaphore(settings.enrich_concurrency)
        success_count = 0
        skip_count = 0
        fail_count = 0

        # Phase P1-B 优化：异常分类统计
        fail_by_reason: dict[str, int] = {}

        # Phase P0-B (B1): 内存收集补全结果
        # enrichment_results: List[dict] = []

        async def enrich_one(article_info: dict, index: int) -> dict:
            """单个文章的补全任务（不操作 DB）"""
            nonlocal success_count, skip_count, fail_count
            async with semaphore:
                url_hash = article_info["url_hash"]
                url = article_info["url"]

                # 提取域名用于统计
                from urllib.parse import urlparse
                domain = urlparse(url).netloc.lower()

                try:
                    # 域名跳过检查（复用 Phase 2 的逻辑）
                    if RSSFetcher._should_skip_enrichment(url):
                        logger.debug(
                            f"[{index + 1}/{total_count}] 后台补全跳过（域名）: {url}"
                        )
                        skip_count += 1
                        return article_info

                    # 尝试补全（配置化超时）
                    content_fetcher = RSSFetcher._get_content_fetcher()
                    full_content = await asyncio.wait_for(
                        content_fetcher.fetch_content(url),
                        timeout=settings.enrich_timeout,
                    )

                    # Phase P1-A 配置化：最小长度
                    if full_content and len(full_content) >= settings.enrich_min_content_length:
                        article_info['content'] = full_content
                        success_count += 1
                        logger.debug(
                            f"[{index + 1}/{total_count}] ✓ 后台补全成功: {url}"
                        )

                        # Phase P1-D 优化：记录补全成功（用于统计）
                        if settings.dynamic_skip_enabled:
                            from app.services.processor.domain_skip import domain_skip_service
                            await domain_skip_service.record_success(domain)
                    else:
                        logger.debug(
                            f"[{index + 1}/{total_count}] - 内容过短/空: {url}"
                        )
                        fail_count += 1
                    return article_info

                except asyncio.TimeoutError:
                    fail_count += 1
                    fail_by_reason["timeout"] = fail_by_reason.get("timeout", 0) + 1
                    logger.debug(
                        f"[{index + 1}/{total_count}] ⏱ 超时: {url}"
                    )

                    # Phase P1-D 优化：记录补全失败（用于统计）
                    if settings.dynamic_skip_enabled:
                        from app.services.processor.domain_skip import domain_skip_service
                        await domain_skip_service.record_failure(domain, "timeout")
                    return article_info

                except Exception as e:
                    fail_count += 1
                    error_type = type(e).__name__
                    fail_by_reason[error_type] = fail_by_reason.get(error_type, 0) + 1
                    logger.warning(
                        f"[{index + 1}/{total_count}] ✗ 异常 ({error_type}): {url}, 错误: {e}"
                    )

                    # Phase P1-D 优化：记录补全失败（用于统计）
                    if settings.dynamic_skip_enabled:
                        from app.services.processor.domain_skip import domain_skip_service
                        await domain_skip_service.record_failure(domain, error_type)
                    return article_info

        # Phase 3B: 并发执行所有补全任务
        tasks = [
            enrich_one(info, i)
            for i, info in enumerate(articles_to_enrich)
        ]
        result_articles = await asyncio.gather(*tasks, return_exceptions=True)

        import json

        # Phase P0-B (B1): 所有补全完成后，一次性批量写入 DB
        if result_articles:
            logger.info(f"补全收集完成: {success_count} 篇，跳过{skip_count}篇，失败{fail_count}篇，开始批量写入 DB")
            saved_count, skipped_count = await deduplicator.batch_save_articles(
                result_articles, skip_url_dedup=True
            )
            logger.info(
                f"批量写入完成: {saved_count}/{len(result_articles)} 篇，因为语义重复跳过{skipped_count}篇"
            )
            # 内存释放
            result_articles.clear()
        else:
            logger.info("无补全结果需要写入 DB")

        # Phase P1-B 优化：结构化总结日志
        event_log = {
            "event": "background_enrich_complete",
            "total": total_count,
            "success": success_count,
            "skip": skip_count,
            "fail": fail_count,
            "success_rate": f"{success_count / max(total_count, 1) * 100:.1f}%",
        }
        if fail_by_reason:
            event_log["fail_reasons"] = fail_by_reason
        logger.info(json.dumps(event_log))

        # Phase P1-B 优化：写入 OperationLog（通过 operation_logger 服务）
        try:
            from app.services.operation_logger import operation_logger

            detail_dict = {
                "total": total_count,
                "success": success_count,
                "skip": skip_count,
                "fail": fail_count,
                "success_rate": event_log["success_rate"],
            }
            if fail_by_reason:
                detail_dict["fail_reasons"] = fail_by_reason

            await operation_logger.log(
                log_type="task_exec",
                action="background_enrich",
                operator="scheduler",
                log_level="INFO",
                detail=detail_dict,
            )
        except Exception as e:
            logger.warning(f"写入操作日志失败: {e}")

    async def _fetch_github_trending(self, time_range):
        # 获取GitHub语言列表 - 优先从数据库，fallback 到配置文件
        languages = []

        try:
            # 尝试从数据库获取激活的语言
            from app.api.github_languages import get_active_languages
            db_languages = await get_active_languages()

            if db_languages:
                languages = db_languages
                logger.info(f"从数据库加载 {len(languages)} 个活跃GitHub语言")
            else:
                # Fallback: 使用配置文件中的默认语言
                languages = self.settings.get_github_languages()
                if not languages:
                    languages = ["Python", "JavaScript"]
                logger.info(f"数据库无活跃语言，使用配置文件中的 {len(languages)} 个语言")

        except Exception as e:
            logger.error(f"查询数据库GitHub语言失败: {e}，使用配置文件")
            languages = self.settings.get_github_languages()
            if not languages:
                languages = ["Python", "JavaScript"]

        logger.info(f"使用GitHub语言采集: {languages}")

        # 采集多个语言
        repos_data = await github_fetcher.fetch_multiple_languages(
            languages=languages,
            time_range=time_range,
            limit_per_lang=20,
        )

        # 保存到数据库
        saved_count = 0
        # 预处理：标准化语言名称
        processed_repos = []
        for repo_data in repos_data:
            # logger.info(f'采集到的git项目：{repo_data}')
            # 标准化语言名称为首字母大写
            language = repo_data.get("language")
            if language:
                language = normalize_language_name(language)

            processed_repos.append({
                "full_name": repo_data["full_name"],
                "url": repo_data["url"],
                "language": language,
                "description": repo_data.get("description"),
                "stars": repo_data.get("stars", 0),
                "forks": repo_data.get("forks", 0),
                "stars_today": repo_data.get("stars_today", 0),
                "trending_date": repo_data.get("trending_date"),
                "trending_range": repo_data.get("trending_range", time_range),
            })

        # 批量保存到数据库
        if processed_repos:
            new_count, updated_count = await deduplicator.batch_save_github_repos(
                processed_repos,
                default_trending_range=time_range,
            )
            saved_count = new_count + updated_count

        return saved_count

    @task_wrapper("fetch_github_trending")
    async def fetch_github_trending(self):
        """
        采集GitHub热门项目

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始采集GitHub热门...")

        saved_count = await self._fetch_github_trending('daily')

        logger.info(f"GitHub热门采集完成，新增或修改 {saved_count} 个项目")
        return saved_count

    @task_wrapper("fetch_weekly_github_trending")
    async def fetch_weekly_github_trending(self):
        """
        采集GitHub的周热门项目

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始采集GitHub每周热门...")

        saved_count = await self._fetch_github_trending('weekly')

        logger.info(f"GitHub周热门项目采集完成，新增或修改 {saved_count} 个项目")
        return saved_count

    @task_wrapper("process_pending_content")
    async def process_pending_content(self):
        """
        处理待处理内容（新流程 - 阶段一/二优化 + M7内存优化）

        对新采集的内容进行:
        - 按摘要有无分类
        - 列表A(有摘要): 批量提取关键词+标签+评分
        - 列表B(无摘要): 批量生成摘要+关键词+标签+评分
        - 并行执行两个列表的处理

        内存优化（M7）：
        - 分批处理，每批数量可配置（默认45篇）
        - 每批次处理完显式 GC
        - 批次间延迟可配置（默认2秒）
        - 每次任务最多处理数量可配置（默认200篇）

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始处理待处理内容(优化流程)...")

        # ========== M7 内存优化：分批处理 + GC ==========
        # 从配置读取批次参数
        batch_size = self.settings.process_batch_size
        max_total = self.settings.process_max_total
        batch_delay = self.settings.process_batch_delay

        processed_total = 0

        while processed_total < max_total:
            # 获取一小批待处理的文章
            async with db.get_session() as session:
                stmt = select(Article).where(
                    and_(
                        Article.status == ArticleStatus.PENDING.value,
                        Article.content.isnot(None),
                        Article.content != '',
                    )
                ).order_by(Article.published_at.desc()).limit(batch_size)

                result = await session.execute(stmt)
                articles = list(result.scalars().all())

                if not articles:
                    break

                logger.info(f"批次查询到 {len(articles)} 篇待处理文章")

                # ========== 步骤1: S2 缓存检查 + 构建统一处理列表 ==========
                articles_to_process = []
                cache_hits_count = 0
                batch_articles_to_push = []
                batch_processed_count = 0

                for article in articles:
                    try:
                        from app.services.vector import vector_service
                        cache_result = await vector_service.check_llm_cache(
                            title=article.title or "",
                            content=article.content or "",
                            summary=article.summary or "",
                            ttl_days=1,
                        )

                        if cache_result.is_hit and cache_result.cached_data:
                            cached_data = cache_result.cached_data
                            article.summary = cached_data.get("summary", "")
                            article.keywords = cached_data.get("keywords", "")
                            article.tags = cached_data.get("tags", "")
                            article.score = cached_data.get("score", 0)
                            article.status = ArticleStatus.PROCESSED.value
                            article.cache_hit = True
                            article.cache_source_id = cache_result.cached_article_id
                            await vector_service.record_cache_hit(
                                source_article_id=cache_result.cached_article_id,
                                cached_article_id=article.id,
                                similarity_score=cache_result.similarity_score,
                            )
                            # Step 5: 向量索引（fire-and-forget）
                            await self._submit_article_to_vector_index(article)
                            batch_articles_to_push.append(article)
                            batch_processed_count += 1
                            cache_hits_count += 1
                            continue

                        articles_to_process.append({
                            "article": article,
                            "title": article.title,
                            "content": article.content,
                            "source": article.source_name or 'unknown',
                        })
                    except Exception as e:
                        logger.debug(f"LLM 缓存检查异常（降级走 LLM）: {e}")
                        articles_to_process.append({
                            "article": article,
                            "title": article.title,
                            "content": article.content,
                            "source": article.source_name or 'unknown',
                        })

                if cache_hits_count > 0:
                    logger.info(f"S2 缓存命中: {cache_hits_count} 篇")

                logger.info(f"开始处理 {len(articles_to_process)} 篇文章（{len(articles_to_process)} 篇需 LLM 调用）")

                # ========== 步骤2: 统一调用LLM处理 ==========
                try:
                    results = await batch_processor.process_list_b(articles_to_process)
                except Exception as e:
                    logger.error(f"批量处理异常: {e}")
                    results = []

                # ========== 步骤3: 收集处理完成的文章 ==========
                for item in results:
                    article = item.get("article")
                    if article and article.score:
                        article.status = ArticleStatus.PROCESSED.value
                        # Step 5: 向量索引（fire-and-forget）
                        await self._submit_article_to_vector_index(article)
                        batch_articles_to_push.append(article)
                        batch_processed_count += 1

                # 保存本批次修改到数据库
                await session.commit()

                # 异步推送本批次高分文章
                if batch_articles_to_push:
                    asyncio.create_task(
                        self._safe_push_high_score_articles(batch_articles_to_push)
                    )
                    logger.info(f"已触发异步推送: {len(batch_articles_to_push)} 篇")

                processed_total += batch_processed_count
                logger.info(f"批次处理完成: {batch_processed_count}篇，累计{processed_total}篇")

                # M7 内存优化：显式 GC + 批次间延迟
                gc.collect()
                await asyncio.sleep(batch_delay)

        logger.info(f"内容处理完成，共处理 {processed_total} 篇")
        return processed_total

    async def _submit_article_to_vector_index(self, article) -> None:
        """
        将文章投递到向量索引队列（fire-and-forget）

        Args:
            article: Article 模型实例
        """
        try:
            from app.services.vector import article_indexer
            await article_indexer.index_article(
                article_id=article.id,
                article_data={
                    "title": article.title or "",
                    "content": article.content or "",
                    "summary": article.summary or "",
                    "source_type": f"rss_{article.source_name}" if article.source_name else "rss",
                    "processed_at": article.updated_at or article.created_at,
                    "score": article.score,
                }
            )
        except Exception as e:
            logger.debug(f"向量索引投递失败（降级忽略）: {e}")

    @task_wrapper("send_daily_report")
    async def send_daily_report(self):
        """
        发送每日精选（优化版：一次性查询 + 内存分组 + 并发推送）

        优化点：
        1. 一次性查询所有文章（使用最低阈值）
        2. 在内存中按各 webhook 阈值分组
        3. 复用 NotificationManager 的并发推送

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始发送日报...")

        # 计算时间范围
        time_range_start = datetime.now() - timedelta(hours=24)

        # 获取所有启用了日报推送的 webhook
        webhooks = await notification_manager._get_active_webhooks_async("daily")

        if not webhooks:
            logger.info("没有启用日报推送的 webhook")
            return 0

        # 一次性查询所有文章（使用最低阈值避免漏选）
        # 迁移后从 PushSettings 获取阈值
        min_threshold = min(
            w.push_settings.push_daily_threshold if w.push_settings else 75.0
            for w in webhooks
        )

        async with db.get_session() as session:
            # 查询所有达标的文章
            stmt = select(Article).where(
                and_(
                    Article.status == ArticleStatus.PROCESSED.value,
                    Article.published_at >= time_range_start,
                    Article.score >= min_threshold,
                    Article.is_pushed == False,
                )
            ).order_by(Article.score.desc())
            result = await session.execute(stmt)
            all_articles = list(result.scalars().all())

            # 一次性查询 GitHub repos（所有 webhook 相同，无阈值筛选）
            stmt2 = select(GitHubRepo).where(
                and_(
                    GitHubRepo.trending_date >= time_range_start,
                    GitHubRepo.trending_range == "daily",
                )
            ).order_by(GitHubRepo.stars.desc()).limit(20)
            result2 = await session.execute(stmt2)
            all_repos = list(result2.scalars().all())

        logger.info(f"日报查询完成: {len(all_articles)} 篇文章, {len(all_repos)} 个 GitHub 项目")

        # 按 webhook 阈值过滤 + 数量限制分组
        # 1. 先按分数降序排序所有文章（一次排序）
        # 2. 对每个 webhook：筛选 score >= threshold 的文章，取前 push_daily_limit 条
        all_articles_sorted = sorted(all_articles, key=lambda a: a.score or 0.0, reverse=True)

        articles_by_webhook = {w.id: [] for w in webhooks}
        for webhook in webhooks:
            # 迁移后从 PushSettings 获取阈值和限制
            ps = webhook.push_settings
            daily_threshold = ps.push_daily_threshold if ps else 75.0
            daily_limit = ps.push_daily_limit if ps else 30
            # 筛选阈值以上文章并取前 limit 条
            eligible_articles = [
                a for a in all_articles_sorted
                if (a.score or 0.0) >= daily_threshold
            ][:daily_limit]
            articles_by_webhook[webhook.id] = eligible_articles

        # 格式化 GitHub repos
        repos_data = [
            {
                "full_name": r.full_name,
                "description": r.description,
                "url": r.url,
                "language": r.language,
                "stars": r.stars,
                "stars_today": r.stars_today,
            }
            for r in all_repos
        ]

        # 统计和标记
        total_articles = 0
        success_count = 0
        pushed_articles = []  # 记录成功推送的文章用于后续标记

        # 并发推送到所有 webhook
        async def push_to_webhook(webhook):
            """并发推送辅助函数"""
            articles = articles_by_webhook[webhook.id]

            if not articles and not repos_data:
                logger.debug(f"Webhook {webhook.name} 无新内容，跳过")
                return None

            # 格式化文章
            articles_data = [
                {
                    "title": a.title,
                    "url": a.url,
                    "score": a.score,
                    "tags": a.tags,
                    "summary": a.summary,
                    "source_name": a.source_name,
                }
                for a in articles
            ]

            try:
                # 发送到该 webhook
                success = await notification_manager.send_daily_report(
                    articles=articles_data,
                    github_repos=repos_data,
                    webhook=webhook,
                )

                if success:
                    logger.info(f"日报推送到 {webhook.name} 成功 ({len(articles)} 篇文章)")
                    return (webhook.name, True, articles)
                else:
                    logger.warning(f"日报推送到 {webhook.name} 失败")
                    return (webhook.name, False, None)

            except Exception as e:
                logger.error(f"日报推送到 {webhook.name} 失败: {e}")
                return (webhook.name, False, None)

        # 并发执行所有推送
        tasks = [push_to_webhook(w) for w in webhooks]
        results = await asyncio.gather(*tasks)

        # 收集结果
        for result in results:
            if result is None:
                continue
            name, success, articles = result
            if success:
                success_count += 1
                if articles:
                    total_articles += len(articles)
                    pushed_articles.extend(articles)

        # 批量标记已推送的文章（一次性数据库连接）
        if pushed_articles:
            article_ids = [article.id for article in pushed_articles]
            marked_count = await deduplicator.mark_articles_pushed(article_ids)
            logger.info(f"已标记 {marked_count} 篇文章为已推送")

        logger.info(f"日报发送完成，成功推送到 {success_count}/{len(webhooks)} 个 webhook")
        return 1 if success_count > 0 else 0

    @task_wrapper("send_weekly_report")
    async def send_weekly_report(self):
        """
        发送周报（优化版：一次性查询 + 内存分组 + 并发推送）

        优化点：
        1. 一次性查询所有文章（使用最低阈值）
        2. 在内存中按各 webhook 阈值分组
        3. 复用 NotificationManager 的并发推送

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始发送周报...")

        # 计算本周日期范围
        now = datetime.now()
        week_start = now - timedelta(days=now.weekday())
        week_start = week_start.replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        week_end = week_start + timedelta(days=6)

        week_start_str = week_start.strftime("%Y-%m-%d")
        week_end_str = week_end.strftime("%Y-%m-%d")

        # 获取所有启用了周报推送的 webhook
        webhooks = await notification_manager._get_active_webhooks_async("weekly")

        if not webhooks:
            logger.info("没有启用周报推送的 webhook")
            return 0

        # 一次性查询所有文章（使用最低阈值避免漏选）
        # 迁移后从 PushSettings 获取阈值
        min_threshold = min(
            w.push_settings.push_weekly_threshold if w.push_settings else 80.0
            for w in webhooks
        )

        async with db.get_session() as session:
            # 查询所有达标的文章
            stmt = select(Article).where(
                and_(
                    Article.status == ArticleStatus.PROCESSED.value,
                    Article.published_at >= week_start,
                    Article.score >= min_threshold,
                )
            ).order_by(Article.score.desc())
            result = await session.execute(stmt)
            all_articles = list(result.scalars().all())

            # 一次性查询 GitHub repos（所有 webhook 相同，无阈值筛选）
            stmt2 = select(GitHubRepo).where(
                and_(
                    GitHubRepo.trending_date >= week_start,
                    GitHubRepo.trending_range == "weekly",
                )
            ).order_by(GitHubRepo.stars.desc()).limit(40)
            result2 = await session.execute(stmt2)
            all_repos = list(result2.scalars().all())

        logger.info(f"周报查询完成: {len(all_articles)} 篇文章, {len(all_repos)} 个 GitHub 项目")

        # 按 webhook 阈值过滤 + 数量限制分组
        # 1. 先按分数降序排序所有文章（一次排序）
        # 2. 对每个 webhook：筛选 score >= threshold 的文章，取前 push_weekly_limit 条
        all_articles_sorted = sorted(all_articles, key=lambda a: a.score or 0.0, reverse=True)

        articles_by_webhook = {w.id: [] for w in webhooks}
        for webhook in webhooks:
            # 迁移后从 PushSettings 获取阈值和限制
            ps = webhook.push_settings
            weekly_threshold = ps.push_weekly_threshold if ps else 80.0
            weekly_limit = ps.push_weekly_limit if ps else 60
            # 筛选阈值以上文章并取前 limit 条
            eligible_articles = [
                a for a in all_articles_sorted
                if (a.score or 0.0) >= weekly_threshold
            ][:weekly_limit]
            articles_by_webhook[webhook.id] = eligible_articles

        # 格式化 GitHub repos
        repos_data = [
            {
                "full_name": r.full_name,
                "description": r.description,
                "url": r.url,
                "language": r.language,
                "stars": r.stars,
                "stars_today": r.stars_today,
            }
            for r in all_repos
        ]

        # 统计
        total_articles = 0
        success_count = 0

        # 并发推送到所有 webhook
        async def push_to_webhook(webhook):
            """并发推送辅助函数"""
            articles = articles_by_webhook[webhook.id]

            if not articles and not repos_data:
                logger.debug(f"Webhook {webhook.name} 无本周内容，跳过")
                return None

            # 格式化文章
            articles_data = [
                {
                    "title": a.title,
                    "url": a.url,
                    "score": a.score,
                    "tags": a.tags,
                    "summary": a.summary,
                    "source_name": a.source_name,
                }
                for a in articles
            ]

            try:
                # 发送到该 webhook
                success = await notification_manager.send_weekly_report(
                    articles=articles_data,
                    github_repos=repos_data,
                    week_start=week_start_str,
                    week_end=week_end_str,
                    webhook=webhook,
                )

                if success:
                    logger.info(f"周报推送到 {webhook.name} 成功 ({len(articles)} 篇文章)")
                    return (webhook.name, True, articles)
                else:
                    logger.warning(f"周报推送到 {webhook.name} 失败")
                    return (webhook.name, False, None)

            except Exception as e:
                logger.error(f"周报推送到 {webhook.name} 失败: {e}")
                return (webhook.name, False, None)

        # 并发执行所有推送
        tasks = [push_to_webhook(w) for w in webhooks]
        results = await asyncio.gather(*tasks)

        # 收集结果
        for result in results:
            if result is None:
                continue
            name, success, articles = result
            if success:
                success_count += 1
                if articles:
                    total_articles += len(articles)

        logger.info(f"周报发送完成，成功推送到 {success_count}/{len(webhooks)} 个 webhook")
        return 1 if success_count > 0 else 0

    @task_wrapper("cleanup_low_score_articles")
    async def cleanup_low_score_articles(self):
        """
        清理低分和无效内容文章

        删除条件：
        - published_at < 一周前（7天前）
        - AND (score < 75 OR content为空)

        执行频率：每天凌晨3点

        使用 @task_wrapper 统一处理日志和异常
        """
        logger.info("开始清理低分文章...")

        threshold1 = self.settings.push_score_threshold - 10
        threshold2 = self.settings.push_score_threshold - 20

        # 计算一周前的时间
        timedelta1 = datetime.now(timezone.utc) - timedelta(days=self.settings.cleanup_days_threshold_min)
        timedelta2 = datetime.now(timezone.utc) - timedelta(days=self.settings.cleanup_days_threshold_max)

        async with db.get_session() as session:

            # 条件1: 默认情况下7天前发布的，评分<65 或 content为空
            condition1 = and_(
                Article.published_at < timedelta1,
                or_(
                    Article.score < threshold2,
                    Article.content == None,
                    Article.content == '',
                )
            )

            # 条件2: 默认情况下为30天前发布的，评分<75
            condition2 = and_(
                Article.published_at < timedelta2,
                Article.score < threshold1
            )

            # 最终条件 = 条件1 OR 条件2
            final_condition = or_(condition1, condition2)

            count_stmt = select(func.count(Article.id)).where(final_condition)

            result = await session.execute(count_stmt)
            total_count = result.scalar() or 0

            if total_count == 0:
                logger.info("没有需要清理的低分文章")
                return 0

            # -------- 分别统计两个条件的删除数量 --------
            # 条件1统计
            count_cond1 = select(func.count(Article.id)).where(condition1)
            result1 = await session.execute(count_cond1)
            cond1_count = result1.scalar() or 0

            # 条件2统计
            count_cond2 = select(func.count(Article.id)).where(condition2)
            result2 = await session.execute(count_cond2)
            cond2_count = result2.scalar() or 0

            logger.info(f"准备删除 {total_count} 篇文章 "
                        f"(7天前低分/无内容: {cond1_count}, 30天前低分: {cond2_count})")

            # 执行删除
            delete_stmt = delete(Article).where(final_condition)

            await session.execute(delete_stmt)
            await session.commit()

            logger.info(f"清理完成，已删除 {total_count} 篇低分/无效文章 "
f"(条件1: {cond1_count}, 条件2: {cond2_count})")

            return total_count

    @task_wrapper("cleanup_expired_data")
    async def to_cleanup_expired_data(self):
        """
        定时清理过期数据（Agent实例 + 语义搜索缓存 + 聚类数据）

        使用 @task_wrapper 统一处理日志和异常
        """
        results = {}

        # 1. 清理过期 Agent
        from app.services.notifier.wecom_callback import cleanup_expired_agents
        agent_count = cleanup_expired_agents()
        results["expired_agents"] = agent_count

        # 2. 清理过期语义搜索缓存
        from app.services.vector.semantic_search_cache import semantic_search_cache
        cache_count = semantic_search_cache.cleanup_expired()
        results["expired_cache_entries"] = cache_count

        # 3. 清理过期聚类数据（保留90天）
        from app.models import ClusterTopic, ClusterArticle

        cutoff_date = datetime.now(timezone.utc) - timedelta(days=90)

        async with db.get_session() as session:
            # 先查询过期聚类ID
            cluster_ids_result = await session.execute(
                select(ClusterTopic.id)
                .where(ClusterTopic.cluster_date < cutoff_date)
            )
            cluster_ids = [row[0] for row in cluster_ids_result.fetchall()]

            if cluster_ids:
                # 删除关联文章
                await session.execute(
                    delete(ClusterArticle)
                    .where(ClusterArticle.cluster_id.in_(cluster_ids))
                )
                # 删除聚类主题
                await session.execute(
                    delete(ClusterTopic)
                    .where(ClusterTopic.id.in_(cluster_ids))
                )
                await session.commit()
                results["expired_clusters"] = len(cluster_ids)
            else:
                results["expired_clusters"] = 0

        # 4. 清理过期推送日志
        from app.models import PushLog
        push_cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.push_log_retention_days)
        async with db.get_session() as session:
            push_result = await session.execute(
                delete(PushLog).where(PushLog.pushed_at < push_cutoff)
            )
            if push_result.rowcount > 0:
                results["expired_push_logs"] = push_result.rowcount

        # 5. 清理过期的任务执行历史
        from app.models import TaskExecutionHistory
        task_cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.task_history_retention_days)
        async with db.get_session() as session:
            task_result = await session.execute(
                delete(TaskExecutionHistory).where(TaskExecutionHistory.start_time < task_cutoff)
            )
            if task_result.rowcount > 0:
                results["expired_task_history"] = task_result.rowcount

        # 6. 清理过期的操作日志
        from app.models import OperationLog
        op_cutoff = datetime.now(timezone.utc) - timedelta(days=self.settings.operation_log_retention_days)
        async with db.get_session() as session:
            op_result = await session.execute(
                delete(OperationLog).where(OperationLog.created_at < op_cutoff)
            )
            if op_result.rowcount > 0:
                results["expired_operation_logs"] = op_result.rowcount

        # 日志
        if agent_count > 0:
            logger.info(f"清理过期Agent: {agent_count} 个")
        if cache_count > 0:
            logger.info(f"清理过期缓存: {cache_count} 条")
        if results.get("expired_clusters", 0) > 0:
            logger.info(f"清理过期聚类: {results['expired_clusters']} 条")
        if results.get("expired_push_logs", 0) > 0:
            logger.info(f"清理过期推送日志: {results['expired_push_logs']} 条")
        if results.get("expired_task_history", 0) > 0:
            logger.info(f"清理过期任务执行历史: {results['expired_task_history']} 条")
        if results.get("expired_operation_logs", 0) > 0:
            logger.info(f"清理过期操作日志: {results['expired_operation_logs']} 条")

        if (
            agent_count == 0
            and cache_count == 0
            and results.get("expired_clusters", 0) == 0
            and results.get("expired_push_logs", 0) == 0
            and results.get("expired_task_history", 0) == 0
            and results.get("expired_operation_logs", 0) == 0
        ):
            logger.info("没有需要清理的过期数据")

        return results

    @task_wrapper("cluster_topics")
    async def cluster_topics(self):
        """主题聚类定时任务（每日凌晨执行）"""
        from app.services.vector import vector_service

        logger.info("开始主题聚类...")

        try:
            clusters = await vector_service.cluster(days=7, min_cluster_size=3)
            logger.info(f"主题聚类完成: 发现 {len(clusters)} 个聚类")

            emerging = [c for c in clusters if getattr(c, "is_emerging", False)]
            if emerging:
                logger.info(f"新兴话题: {len(emerging)} 个")
                for c in emerging[:3]:
                    keywords = getattr(c, "keywords", [])
                    article_count = getattr(c, "article_count", 0)
                    hotness = getattr(c, "hotness", 0.0)
                    logger.info(f"  - {', '.join(keywords)} ({article_count}篇, 热度{hotness:.1f})")

            return {"cluster_count": len(clusters), "emerging_count": len(emerging)}

        except Exception as e:
            logger.error(f"主题聚类失败: {e}", exc_info=True)
            raise

    @task_wrapper("reindex_vectors")
    async def reindex_vectors(self):
        """向量对账任务（每日凌晨执行，在聚类之后）"""
        from app.services.vector import article_indexer

        logger.info("开始向量对账...")

        try:
            count = await article_indexer.reindex_stale(max_age_hours=24)
            logger.info(f"向量对账完成: 补索引 {count} 篇")
            return {"reindexed": count}

        except Exception as e:
            logger.error(f"向量对账失败: {e}", exc_info=True)
            raise

    async def run_immediate_fetch(self):
        """
        手动触发立即采集
        
        用于测试或立即刷新
        """
        news_count = await self.fetch_ai_news()
        github_count = await self.fetch_github_trending()
        
        return {
            "news": news_count,
            "github": github_count,
        }

    async def _safe_push_high_score_articles(self, processed_articles: List[Article]):
        """
        安全的异步推送方法

        捕获所有异常，避免影响主流程。
        由 asyncio.create_task() 异步调用，不阻塞主流程。
        """
        start_time = datetime.now()
        try:
            logger.info(f"开始异步高分推送...")

            results = await notification_manager.send_articles_batch(
                articles=processed_articles,
                push_type="immediate"
            )

            success_count = sum(1 for success in results.values() if success)
            duration = (datetime.now() - start_time).total_seconds()
            logger.info(f"异步推送完成: {success_count}/{len(results)} 个webhook成功, 耗时: {duration:.2f}s")

            # 标记推送时间
            for article in processed_articles:
                article.pushed_at = datetime.now(timezone.utc)
                article.is_pushed_immediate = True

        except Exception as e:
            duration = (datetime.now() - start_time).total_seconds()
            logger.error(f"异步推送异常: {e}, 耗时: {duration:.2f}s")
            # 推送失败不影响主流程

    def get_jobs(self):
        """获取所有调度任务"""
        if self.scheduler:
            return self.scheduler.get_jobs()
        return []

    def get_job(self, job_id):
        """获取单个调度任务"""
        if self.scheduler:
            return self.scheduler.get_job(job_id)
        return None

    async def reload_job_async(self, job_id: str, config=None) -> dict:
        """
        异步重载单个任务（推荐方式）

        从数据库读取最新配置，重新注册指定任务。

        Args:
            job_id: 任务ID
            config: 可选，直接传入配置对象避免异步查询

        Returns:
            dict: {"job_id": str, "reloaded": bool, "message": str}
        """
        if not self.scheduler:
            return {"job_id": job_id, "reloaded": False, "message": "调度器未初始化"}

        # 如果没有传入配置，才需要从数据库获取
        if config is None:
            try:
                config = await self.config_loader.get_task_config(job_id)
            except Exception as e:
                logger.error(f"获取任务配置失败: {type(e).__name__}: {e}")
                return {"job_id": job_id, "reloaded": False, "message": str(e)}

        if not config:
            return {"job_id": job_id, "reloaded": False, "message": "任务配置不存在"}

        # 移除旧任务
        try:
            existing_job = self.scheduler.get_job(job_id)
            if existing_job:
                self.scheduler.remove_job(job_id)
                logger.info(f"热重载：已移除任务 {job_id}")
        except Exception as e:
            logger.warning(f"热重载：移除任务 {job_id} 失败 - {e}")

        # 重新注册任务
        try:
            if config.is_active:
                self._register_single_job(config)
                self.config_logger.record_reload(job_id, True)
                logger.info(f"热重载：已重新注册任务 {job_id}")
                return {"job_id": job_id, "reloaded": True, "message": "success"}
            else:
                self.config_logger.record_reload(job_id, True, "任务已禁用")
                logger.info(f"热重载：任务 {job_id} 已禁用，跳过注册")
                return {"job_id": job_id, "reloaded": True, "message": "任务已禁用"}
        except Exception as e:
            self.config_logger.record_reload(job_id, False, str(e))
            logger.error(f"热重载：重新注册任务 {job_id} 失败 - {e}")
            return {"job_id": job_id, "reloaded": False, "message": str(e)}

    def reload_job(self, job_id: str, config=None) -> dict:
        """
        同步重载单个任务（兼容旧代码）

        内部使用线程池执行异步方法，避免在已运行的事件循环中调用 run_until_complete。

        Args:
            job_id: 任务ID
            config: 可选，直接传入配置对象避免异步查询

        Returns:
            dict: {"job_id": str, "reloaded": bool, "message": str}
        """
        if not self.scheduler:
            return {"job_id": job_id, "reloaded": False, "message": "调度器未初始化"}

        import asyncio
        try:
            loop = asyncio.get_running_loop()
            # 如果事件循环正在运行，使用线程池执行避免阻塞
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(
                    asyncio.run,
                    self.reload_job_async(job_id, config)
                )
                return future.result(timeout=30)
        except RuntimeError:
            # 没有正在运行的事件循环，可以使用 run
            return asyncio.run(self.reload_job_async(job_id, config))
        except Exception as e:
            logger.error(f"热重载失败: {e}")
            return {"job_id": job_id, "reloaded": False, "message": str(e)}

    def reload_jobs(self) -> dict:
        """
        热重载所有定时任务

        移除现有任务后重新注册，使配置变更生效。
        用于 Web 面板修改定时任务配置后无需重启服务。

        Returns:
            dict: {
                "reloaded": True,
                "jobs_count": N,
                "jobs": [{"id": job_id, "next_run": "..."}]
            }
        """
        if not self.scheduler:
            self._init_scheduler()
            self.scheduler.start()

        # 所有任务 ID 列表
        job_ids = list(TASK_METHOD_MAP.keys())

        # 移除现有任务
        removed_count = 0
        for jid in job_ids:
            try:
                existing_job = self.scheduler.get_job(jid)
                if existing_job:
                    self.scheduler.remove_job(jid)
                    removed_count += 1
                    logger.info(f"热重载：已移除任务 {jid}")
            except Exception as e:
                logger.warning(f"热重载：移除任务 {jid} 失败 - {e}")

        # 重新注册所有任务
        import asyncio
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 事件循环已在运行，使用 ensure_future 在后台执行
                asyncio.ensure_future(self._register_jobs_async(skip_init=True))
            else:
                loop.run_until_complete(self._register_jobs_async(skip_init=True))
        except Exception as e:
            logger.error(f"热重载：重新注册任务失败 - {e}")

        # 获取新注册的任务信息
        new_jobs = self.scheduler.get_jobs()
        jobs_info = [
            {"id": j.id, "next_run": str(j.next_run_time) if j.next_run_time else None}
            for j in new_jobs
        ]

        logger.info(f"热重载完成，移除了 {removed_count} 个任务，重新注册了 {len(new_jobs)} 个任务")

        return {
            "reloaded": True,
            "jobs_count": len(new_jobs),
            "jobs": jobs_info
        }

    async def run_job(self, job_id):
        """
        手动触发执行指定任务

        原理: 通过 job_id 获取 Job 对象，取出其绑定的 func/args/kwargs 直接调用
        """
        if not self.scheduler:
            raise RuntimeError("调度器未初始化")

        job = self.scheduler.get_job(job_id)
        if not job:
            raise ValueError(f"任务不存在: {job_id}")

        # 取出绑定的函数和参数
        func = job.func
        args = job.args
        kwargs = job.kwargs

        # 判断是否是协程函数，决定调用方式
        import asyncio
        import inspect

        if inspect.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            # 同步函数，在线程池中执行避免阻塞事件循环
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, lambda: func(*args, **kwargs))

# 创建全局调度器
scheduler = TaskScheduler()
