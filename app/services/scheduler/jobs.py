# -*- coding: utf-8 -*-
"""
定时任务调度模块

使用 APScheduler 实现定时任务:
- 定时采集AI资讯
- 定时采集GitHub热门
- 每日精选推送
- 周报汇总推送
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select, and_, or_, delete, func

from app.config import get_settings
from app.database import db
from app.models import Article, ArticleStatus, GitHubRepo
from app.services.fetcher.github_trending import github_fetcher
from app.services.fetcher.rss_parser import rss_fetcher
from app.services.notifier.base import notification_manager
from app.services.processor.deduplicator import deduplicator
from app.services.processor.scorer import scorer
from app.services.processor.summarizer import summarizer

logger = logging.getLogger(__name__)


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
        self._init_scheduler()
    
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
                "misfire_grace_time": 3600,  # 允许1小时内延迟
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
        """注册所有定时任务"""
        
        # 1. 每日资讯采集
        self.scheduler.add_job(
            self.fetch_ai_news,
            # CronTrigger(hour=22, minute=41),
            IntervalTrigger(hours=1, minutes=30),
            id="fetch_ai_news",
            name="采集AI资讯",
            replace_existing=True,
        )
        
        # 2. 每日GitHub热门采集 (晚上10点)
        self.scheduler.add_job(
            self.fetch_github_trending,
            # CronTrigger(hour=self.settings.fetch_github_hour, minute=0),
            CronTrigger(hour=16, minute=0),
            id="fetch_github_trending",
            name="采集GitHub的daily热门",
            replace_existing=True,
        )

        # 3. 每周GitHub热门采集 (周一早上7点)
        self.scheduler.add_job(
            self.fetch_weekly_github_trending,
            CronTrigger(day_of_week=self.settings.weekly_report_day,
                hour=7,
                minute=0),
            # CronTrigger(day_of_week=4,
            #             hour=21,
            #             minute=8),
            id="fetch_weekly_github_trending",
            name="采集GitHub的weekly热门",
            replace_existing=True,
        )
        
        # 4. 每日精选推送 (晚上11点40分)
        self.scheduler.add_job(
            self.send_daily_report,
            # CronTrigger(hour=self.settings.daily_report_hour, minute=40),
            CronTrigger(hour=17,minute=0),
            id="send_daily_report",
            name="发送日报",
            replace_existing=True,
        )
        
        # 5. 周报推送 (每周一早上8点)
        self.scheduler.add_job(
            self.send_weekly_report,
            CronTrigger(
                day_of_week=self.settings.weekly_report_day,
                hour=self.settings.weekly_report_hour,
                minute=0
            ),
            # CronTrigger(day_of_week=4,
            #             hour=23,
            #             minute=8),
            id="send_weekly_report",
            name="发送周报",
            replace_existing=True,
        )
        
        # 6. 定时处理待处理内容 (每半小时)
        self.scheduler.add_job(
            self.process_pending_content,
            IntervalTrigger(minutes=30),
            # CronTrigger(hour=22,
            #             minute=42),
            id="process_pending_content",
            name="处理待处理内容",
            replace_existing=True,
        )

        # 7. 每天凌晨3点清理低分文章
        self.scheduler.add_job(
            self.cleanup_low_score_articles,
            CronTrigger(hour=self.settings.cleanup_hour, minute=0),
            # CronTrigger(hour=3, minute=51),
            id="cleanup_low_score_articles",
            name="清理低分文章",
            replace_existing=True,
        )

        # 8. 每天凌晨4点清理过期Agent
        self.scheduler.add_job(
            self.to_cleanup_expired_agents,
            CronTrigger(hour=4, minute=0),
            id="cleanup_expired_agents",
            name="清理过期Agent",
            replace_existing=True,
        )

        logger.info(f"已注册 {len(self.scheduler.get_jobs())} 个定时任务")
    
    # ==================== 任务实现 ====================
    
    async def fetch_ai_news(self):
        """
        采集AI资讯任务
        
        从RSS源获取最新资讯
        """
        logger.info("开始采集AI资讯...")
        
        try:
            # 获取RSS源
            # rss_sources = self.settings.get_rss_sources()
            rss_sources = [s.strip() for s in self.settings.default_rss_sources.split("|") if s.strip()]
            logger.info(f"使用RSS源采集资讯: {rss_sources}")
            # 如果没有配置，使用默认源  "https://openai.com/blog/rss.xml",
            if not rss_sources:
                rss_sources = [
                    "https://news.ycombinator.com/rss",
                ]
            
            # 采集
            articles_data = await rss_fetcher.fetch_multiple_feeds(rss_sources)
            
            # 保存到数据库 (去重)
            saved_count = 0
            for article_data in articles_data:
                article = await deduplicator.save_article(
                    title=article_data["title"],
                    url=article_data["url"],
                    source=article_data["source"],
                    source_name=article_data["source_name"],
                    summary=article_data["summary"],
                    content=article_data.get("content"),
                    author=article_data.get("author"),
                    published_at=article_data.get("published_at"),
                )
                if article:
                    saved_count += 1
            
            logger.info(f"AI资讯采集完成，新增 {saved_count} 篇")
            return saved_count
            
        except Exception as e:
            logger.error(f"采集AI资讯失败: {e}")
            return 0

    async def _fetch_github_trending(self, time_range):
        languages = self.settings.get_github_languages()

        # 采集多个语言
        repos_data = await github_fetcher.fetch_multiple_languages(
            languages=languages,
            time_range=time_range,
            limit_per_lang=20,
        )

        # 保存到数据库
        saved_count = 0
        for repo_data in repos_data:
            # logger.info(f'采集到的git项目：{repo_data}')
            repo = await deduplicator.save_github_repo(
                full_name=repo_data["full_name"],
                url=repo_data["url"],
                language=repo_data.get("language"),
                description=repo_data.get("description"),
                stars=repo_data.get("stars", 0),
                forks=repo_data.get("forks", 0),
                stars_today=repo_data.get("stars_today", 0),
                trending_date=repo_data.get("trending_date"),
                trending_range=repo_data.get("trending_range", time_range),
            )
            if repo:
                saved_count += 1
        return saved_count

    async def fetch_github_trending(self):
        """
        采集GitHub热门项目
        """
        logger.info("开始采集GitHub热门...")
        
        try:
            saved_count = await self._fetch_github_trending('daily')
            
            logger.info(f"GitHub热门采集完成，新增或修改 {saved_count} 个项目")
            return saved_count
            
        except Exception as e:
            logger.error(f"采集GitHub热门失败: {e}")
            return 0

    async def fetch_weekly_github_trending(self):
        """
        采集GitHub的周热门项目
        """
        logger.info("开始采集GitHub每周热门...")

        try:
            saved_count = await self._fetch_github_trending('weekly')

            logger.info(f"GitHub周热门项目采集完成，新增或修改 {saved_count} 个项目")
            return saved_count

        except Exception as e:
            logger.error(f"采集GitHub热门失败: {e}")
            return 0

    async def process_pending_content(self):
        """
        处理待处理内容

        对新采集的内容进行:
        - LLM摘要生成
        - 价值评分
        - 打标
        """
        logger.info("开始处理待处理内容...")

        try:
            processed_count = 0
            # 获取待处理的文章
            async with db.get_session() as session:

                # 获取未处理的文章
                stmt = select(Article).where(
                    and_(
                        Article.status == ArticleStatus.PENDING.value,
                        Article.content.isnot(None),
                        Article.content != '',
                    )
                ).limit(45)

                result = await session.execute(stmt)
                articles = list(result.scalars().all())


                # 收集需要评分的数据到一个列表
                to_score_list = []

                # 收集已经获取了摘要但是没有获取到关键词、标签的数据，包括content长度太小直接将content作为摘要的数据
                to_keywords_tags_list = []

                # logger.info(f'收集了{len(articles)}篇文章')
                for article in articles:
                    try:
                        # 生成摘要、关键词和标签
                        if article.content and len(article.content) < 200 and not article.summary:
                            article.summary = article.content
                        if article.summary and (not article.keywords or not article.tags):
                            to_keywords_tags_list.append(
                                {
                                    "article": article,  # 用于添加对应的分数
                                    "title": article.title,
                                    "content": article.content,
                                }
                            )
                        # logger.info(f'{summarizer.is_available}，{len(article.content)}，{article.summary}')
                        if summarizer.is_available and article.content and not article.summary:
                            llm_result = await summarizer.process_article(
                                title=article.title,
                                content=article.content,
                            )
                            # logger.info(f'摘要结果：{llm_result}')
                            if llm_result.get("summary"):
                                article.summary = llm_result["summary"]
                            if llm_result.get("keywords"):
                                article.keywords = llm_result["keywords"]
                            if llm_result.get("tags"):
                                article.tags = llm_result["tags"]

                        # 收集待评分列表
                        if scorer.is_available and article.summary and article.keywords and article.tags:
                            to_score_list.append(
                                {
                                    "article": article,  # 用于添加对应的分数
                                    "title": article.title,
                                    "summary": article.summary,
                                    "source": article.source_name or 'unknown',
                                }
                            )
                    except Exception as e:
                        logger.error(f"处理文章失败: {article.id}, {e}")
                        continue
                # logger.info(f'关键词列表有{len(to_keywords_tags_list)}')
                # logger.info(f'1.待评分列表有{len(to_score_list)}')
                for k in range(0, len(to_keywords_tags_list), 5):
                    k_t_batch = to_keywords_tags_list[k:k + 5]
                    k_t_batch_result = await summarizer.batch_extract_tags_keywords(k_t_batch)
                    if k_t_batch_result and len(k_t_batch_result) == len(k_t_batch):
                        for kt,k_t_result in enumerate(k_t_batch_result):
                            article = k_t_result.get('article')
                            if article.keywords and article.tags:
                                to_score_list.append(
                                    {
                                        "article": article,  # 用于添加对应的分数
                                        "title": article.title,
                                        "summary": article.summary,
                                        "source": article.source or 'unknown',
                                    }
                                )

                processed_articles = []     # 保存评分成功的数据

                threshold = self.settings.push_score_threshold  # 阈值配置

                # logger.info(f'2.待评分列表有{len(to_score_list)}')
                for i in range(0, len(to_score_list), 5):
                    batch = to_score_list[i : i + 5]
                    batch_result = await scorer.batch_score(batch)

                    if batch_result:
                        for j,score_result in enumerate(batch_result):
                            # article = batch[j]["article"]  # 直接取对应的article对象
                            article = score_result["article"]
                            score = score_result.get('score_data', {}).get('score')

                            if score:
                                article.score = score
                                article.status = ArticleStatus.PROCESSED.value
                                if article.score and article.score >= threshold and not article.is_pushed and not article.pushed_at:
                                    processed_articles.append(article)
                                processed_count += 1
                            else:
                                logger.warning(f'文章{article.id}评分缺失')
                if processed_count > 0 and len(processed_articles) > 0:
                    await self.push_high_score_articles(processed_articles)
                # 保存修改到数据库
                await session.commit()
                        #     score_result = await scorer.score_article(
                    #         title=article.title,
                    #         summary=article.summary,
                    #         source=article.source_name or "",
                    #     )
                    #     logger.info(f'评分结果：{score_result}')
                    #     if score_result:
                    #         article.score = score_result.get("score")
                    #     await asyncio.sleep(1)

                        # # 更新状态
                        # article.status = ArticleStatus.PROCESSED.value
                        # processed_count += 1


                    # try:
                    #     await session.commit()
                    # except Exception as commit_e:
                    #     await session.rollback()
                    #     logger.error(f"提交失败: {article.id}, {commit_e}")
                    #     # 重置session状态，继续处理下一篇
                    #     await session.begin()
            logger.info(f"内容处理完成，处理了 {processed_count} 篇")


            return processed_count

        except Exception as e:
            logger.error(f"处理待处理内容失败: {e}")
            return 0
    
    async def send_daily_report(self):
        """
        发送每日精选
        
        推送今日高价值内容
        """
        logger.info("开始发送日报...")
        
        try:
            # 获取今日高评分内容
            threshold = self.settings.push_score_threshold-10
            
            async with db.get_session() as session:
                
                # 获取今日已处理的高评分文章
                today = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                
                stmt = select(Article).where(
                    and_(
                        Article.status == ArticleStatus.PROCESSED.value,
                        Article.published_at >= today,
                        Article.score >= threshold,
                        Article.is_pushed == False,
                    )
                ).order_by(Article.score.desc()).limit(20)
                
                result = await session.execute(stmt)
                articles = list(result.scalars().all())
                
                # 获取GitHub热门
                stmt2 = select(GitHubRepo).where(
                    and_(
                        GitHubRepo.trending_date >= today,
                        GitHubRepo.trending_range == "daily",
                    )
                ).order_by(GitHubRepo.stars.desc()).limit(20)
                
                result2 = await session.execute(stmt2)
                repos = list(result2.scalars().all())
            
            if not articles and not repos:
                logger.info("今日无新内容，跳过推送")
                return 0
            
            # 格式化
            articles_data = [
                {
                    "title": a.title,
                    "url": a.url,
                    "score": a.score,
                    "tags": a.tags,
                    "summary": a.summary,
                    "source_name":a.source_name,
                }
                for a in articles
            ]
            
            repos_data = [
                {
                    "full_name": r.full_name,
                    "description": r.description,
                    "url": r.url,
                    "language": r.language,
                    "stars": r.stars,
                    "stars_today": r.stars_today,
                }
                for r in repos
            ]
            
            # 发送
            success = await notification_manager.send_daily_report(
                articles=articles_data,
                github_repos=repos_data,
            )
            
            if success:
                # 标记已推送
                for article in articles:
                    await deduplicator.mark_article_pushed(article.id)
            
            logger.info(f"日报发送完成")
            return 1
            
        except Exception as e:
            logger.error(f"发送日报失败: {e}")
            return 0
    
    async def send_weekly_report(self):
        """
        发送周报
        
        汇总本周热门内容
        """
        logger.info("开始发送周报...")
        
        try:
            # 计算本周日期
            now = datetime.now()
            week_start = now - timedelta(days=now.weekday())
            week_start = week_start.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            week_end = week_start + timedelta(days=6)
            
            week_start_str = week_start.strftime("%Y-%m-%d")
            week_end_str = week_end.strftime("%Y-%m-%d")

            threshold = self.settings.push_score_threshold - 5
            async with db.get_session() as session:
                
                # 获取本周高评分文章
                stmt = select(Article).where(
                    and_(
                        Article.status == ArticleStatus.PROCESSED.value,
                        Article.published_at >= week_start,
                        Article.score >= threshold,  # 周报降低阈值
                    )
                ).order_by(Article.score.desc()).limit(50)
                
                result = await session.execute(stmt)
                articles = list(result.scalars().all())
                
                # 获取本周GitHub热门
                stmt2 = select(GitHubRepo).where(
                    and_(
                        GitHubRepo.trending_date >= week_start,
                        GitHubRepo.trending_range == "weekly",
                    )
                ).order_by(GitHubRepo.stars.desc()).limit(20)
                
                result2 = await session.execute(stmt2)
                repos = list(result2.scalars().all())
            
            # 格式化
            articles_data = [
                {"title": a.title, "url": a.url, "summary": a.summary}
                for a in articles
            ]
            
            repos_data = [
                {
                    "full_name": r.full_name,
                    "description": r.description,
                    "url": r.url,
                    "stars": r.stars,
                    "language": r.language,
                }
                for r in repos
            ]
            
            # 发送
            success = await notification_manager.send_weekly_report(
                articles=articles_data,
                github_repos=repos_data,
                week_start=week_start_str,
                week_end=week_end_str,
            )
            
            logger.info(f"周报发送完成")
            return 1
            
        except Exception as e:
            logger.error(f"发送周报失败: {e}")
            return 0

    async def cleanup_low_score_articles(self):
        """
        清理低分和无效内容文章

        删除条件：
        - published_at < 一周前（7天前）
        - AND (score < 75 OR content为空)

        执行频率：每天凌晨3点
        """
        logger.info("开始清理低分文章...")

        try:
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


        except Exception as e:
            logger.error(f"清理低分文章失败: {e}")
            return 0

    async def to_cleanup_expired_agents(self):
        """定时清理过期的Agent实例"""

        try:
            # 导入清理函数
            from app.services.notifier.wecom_callback import cleanup_expired_agents

            count = cleanup_expired_agents()

            if count > 0:
                logger.info(f"定时清理完成，已清理 {count} 个过期Agent")
                return count
            else:
                logger.info("没有需要清理的过期Agent")
                return 0

        except Exception as e:
            logger.error(f"清理过期Agent失败: {e}")
            return 0


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

    async def push_high_score_articles(self, processed_articles: List[Article]):
        """
        推送处理完成的高分文章（即时推送）
        """
        logger.info("开始即时推送高分文章...")

        # threshold = self.settings.push_score_threshold  # 阈值配置
        pushed_count = 0

        # for article in processed_articles:
        #     # 筛选条件：评分 >= 阈值 且 未推送
        #     # if article.score and article.score >= threshold and not article.is_pushed and not article.pushed_at:
        #         try:
        #             # 发送到所有渠道
        #
        #             await notification_manager.send_article(
        #                 title=article.title,
        #                 summary=article.summary or "",
        #                 url=article.url,
        #                 source=article.source_name or "unknown",
        #                 tags=article.tags,
        #                 score=article.score,
        #             )
        #             article.pushed_at = datetime.now(timezone.utc)
        #             # await deduplicator.mark_article_pushed(article.id)
        #             pushed_count += 1
        #
        #         except Exception as e:
        #             logger.error(f"即时推送失败: {article.id}, {e}")
        #
        # logger.info(f"即时推送完成，推送了 {pushed_count} 篇文章")
        # return pushed_count

            # 筛选条件：评分 >= 阈值 且 未推送
            # if article.score and article.score >= threshold and not article.is_pushed and not article.pushed_at:
        try:
            # 发送到所有渠道
            # article_dict = {
            #     "title" = article.title,
            #     "summary" = article.summary or "",
            #     "url" = article.url,
            #     "source" = article.source_name or "unknown",
            #     "tags" = article.tags,
            #     "score" = article.score,
            # }
            senf_res = await notification_manager.send_article(
                article_list=processed_articles,
                many = True
            )
            if senf_res:
                for article in processed_articles:
                    article.pushed_at = datetime.now(timezone.utc)
                    # await deduplicator.mark_article_pushed(article.id)
                    pushed_count += 1
                logger.info(f"即时推送完成，推送了 {pushed_count} 篇文章")
                return pushed_count

        except Exception as e:
            logger.error(f"即时推送失败: {e}")



# 创建全局调度器
scheduler = TaskScheduler()
