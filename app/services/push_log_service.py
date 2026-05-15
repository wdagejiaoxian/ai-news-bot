# -*- coding: utf-8 -*-
"""
推送日志服务

提供统一的推送日志写入和查询接口。
写入操作异步执行（asyncio.ensure_future），不阻塞推送主流程。
写入失败时降级到文件日志，不影响主业务流程。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import case, select, func, and_, desc, delete

from app.database import db
from app.models import PushLog

logger = logging.getLogger(__name__)


class PushLogService:
    """推送日志记录器"""

    def __init__(self):
        self._db = None
        # 确保日志目录存在
        os.makedirs("logs", exist_ok=True)

    @property
    def database(self):
        if self._db is None:
            return db
        return self._db

    async def log_push(
        self,
        webhook_config_id: int,
        webhook_config_name: Optional[str],
        platform: str,
        push_type: str,
        content: str,
        is_success: bool,
        article_id: Optional[int] = None,
        github_repo_id: Optional[int] = None,
        error_message: Optional[str] = None,
        obsidian_file_path: Optional[str] = None,
        git_commit_sha: Optional[str] = None,
        http_status_code: Optional[int] = None,
    ) -> Optional[int]:
        """
        写入推送日志

        Args:
            webhook_config_id: Webhook配置ID（主关联）
            webhook_config_name: Webhook配置名称（冗余字段，防 webhook 删除后丢失上下文）
            platform: 推送平台，如 wecom/git/obsidian_local
            push_type: 推送类型，如 immediate/daily/weekly
            content: 推送内容（截断到 500 字符）
            is_success: 是否成功
            article_id: 关联文章ID（可选）
            github_repo_id: 关联GitHub项目ID（可选）
            error_message: 错误信息（可选）
            obsidian_file_path: Obsidian文件路径（可选）
            git_commit_sha: Git提交SHA（可选）
            http_status_code: HTTP响应码（可选）

        Returns:
            日志 ID，失败返回 None
        """
        try:
            # content 截断，避免字段过大
            content_truncated = content[:500] if content else ""

            # 构建日志对象
            log_entry = PushLog(
                webhook_config_id=webhook_config_id,
                webhook_config_name=webhook_config_name,
                platform=platform,
                push_type=push_type,
                content=content_truncated,
                is_success=is_success,
                article_id=article_id,
                github_repo_id=github_repo_id,
                error_message=error_message,
                obsidian_file_path=obsidian_file_path,
                git_commit_sha=git_commit_sha,
                http_status_code=http_status_code,
            )

            # 写入数据库
            async with self.database.get_session() as session:
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                log_id = log_entry.id

            logger.debug(
                f"推送日志写入成功: id={log_id}, webhook={webhook_config_name}, "
                f"type={push_type}, success={is_success}"
            )
            return log_id

        except Exception as e:
            logger.error(f"推送日志写入失败: {e}")
            # Fallback: 写入文件
            self._fallback_log(
                webhook_config_id=webhook_config_id,
                webhook_config_name=webhook_config_name,
                platform=platform,
                push_type=push_type,
                content=content,
                is_success=is_success,
                error_message=error_message,
            )
            return None

    def _fallback_log(
        self,
        webhook_config_id: int,
        webhook_config_name: Optional[str],
        platform: str,
        push_type: str,
        content: str,
        is_success: bool,
        error_message: Optional[str] = None,
    ) -> None:
        """写入推送日志失败时的降级方案：写入文件"""
        try:
            fallback_file = "logs/push_fallback.log"

            entry = {
                "timestamp": datetime.now().isoformat(),
                "webhook_config_id": webhook_config_id,
                "webhook_config_name": webhook_config_name,
                "platform": platform,
                "push_type": push_type,
                "content": content[:500] if content else "",
                "is_success": is_success,
                "error_message": error_message,
            }

            with open(fallback_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        except Exception as fallback_e:
            logger.error(f"推送日志 Fallback 写入也失败: {fallback_e}")

    async def query_push_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        webhook_config_id: Optional[int] = None,
        platform: Optional[str] = None,
        push_type: Optional[str] = None,
        is_success: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        查询推送日志

        Args:
            page: 页码
            page_size: 每页条数
            webhook_config_id: Webhook配置ID筛选
            platform: 推送平台筛选
            push_type: 推送类型筛选
            is_success: 成功/失败筛选
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            {
                "items": [...],
                "total": 100,
                "page": 1,
                "page_size": 20
            }
        """
        # 构建查询条件
        conditions = []

        if webhook_config_id is not None:
            conditions.append(PushLog.webhook_config_id == webhook_config_id)

        if platform:
            conditions.append(PushLog.platform == platform)

        if push_type:
            conditions.append(PushLog.push_type == push_type)

        if is_success is not None:
            conditions.append(PushLog.is_success == is_success)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                conditions.append(PushLog.pushed_at >= start_dt)
            except ValueError:
                logger.warning(f"无效的 start_date 格式: {start_date}")

        if end_date:
            try:
                # 结束日期加一天（包含当天）
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                conditions.append(PushLog.pushed_at < end_dt)
            except ValueError:
                logger.warning(f"无效的 end_date 格式: {end_date}")

        query = select(PushLog)
        count_query = select(func.count(PushLog.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 最新在前
        query = query.order_by(desc(PushLog.pushed_at))

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        try:
            async with self.database.get_session() as session:
                result = await session.execute(query)
                logs = result.scalars().all()

                total_result = await session.execute(count_query)
                total = total_result.scalar() or 0

            items = []
            for log in logs:
                item = {
                    "id": log.id,
                    "webhook_config_id": log.webhook_config_id,
                    "webhook_config_name": log.webhook_config_name,
                    "platform": log.platform,
                    "push_type": log.push_type,
                    "content": log.content,
                    "is_success": log.is_success,
                    "error_message": log.error_message,
                    "article_id": log.article_id,
                    "github_repo_id": log.github_repo_id,
                    "obsidian_file_path": log.obsidian_file_path,
                    "git_commit_sha": log.git_commit_sha,
                    "http_status_code": log.http_status_code,
                    "pushed_at": log.pushed_at.isoformat() if log.pushed_at else None,
                }
                items.append(item)

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        except Exception as e:
            logger.error(f"查询推送日志失败: {e}")
            return {
                "items": [],
                "total": 0,
                "page": page,
                "page_size": page_size,
            }

    async def get_stats(
        self,
        days: int = 7,
        platform: Optional[str] = None,
    ) -> dict:
        """
        获取推送统计

        Args:
            days: 统计天数
            platform: 平台筛选（可选）

        Returns:
            {
                "total": 120,
                "success_count": 115,
                "fail_count": 5,
                "success_rate": 95.8,
                "today": 3,
                "by_platform": {"wecom": 80, "obsidian_local": 40},
                "daily_trend": [
                    {"date": "2026-05-07", "total": 15, "success": 14},
                    ...
                ]
            }
        """
        try:
            now = datetime.utcnow()
            start_dt = now - timedelta(days=days)
            today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

            async with self.database.get_session() as session:
                # 基础统计条件
                base_conditions = [PushLog.pushed_at >= start_dt]
                if platform:
                    base_conditions.append(PushLog.platform == platform)

                # 1. 总量统计
                stats_result = await session.execute(
                    select(
                        func.count(PushLog.id).label("total"),
                        func.count(
                            case((PushLog.is_success == True, 1))
                        ).label("success_count"),
                    ).where(and_(*base_conditions))
                )
                stats_row = stats_result.one()
                total = stats_row.total or 0
                success_count = stats_row.success_count or 0
                fail_count = total - success_count
                success_rate = round(success_count / total * 100, 1) if total > 0 else 0.0

                # 2. 今日统计
                today_conditions = [PushLog.pushed_at >= today_start]
                if platform:
                    today_conditions.append(PushLog.platform == platform)

                today_result = await session.execute(
                    select(func.count(PushLog.id)).where(and_(*today_conditions))
                )
                today_count = today_result.scalar() or 0

                # 3. 按平台统计
                by_platform_conditions = [PushLog.pushed_at >= start_dt]
                if platform:
                    by_platform_conditions.append(PushLog.platform == platform)

                platform_result = await session.execute(
                    select(PushLog.platform, func.count(PushLog.id))
                    .where(and_(*by_platform_conditions))
                    .group_by(PushLog.platform)
                )
                by_platform = {row[0]: row[1] for row in platform_result.all()}

            return {
                "total": total,
                "success_count": success_count,
                "fail_count": fail_count,
                "success_rate": success_rate,
                "today": today_count,
                "by_platform": by_platform,
            }

        except Exception as e:
            logger.error(f"获取推送统计失败: {e}")
            return {
                "total": 0,
                "success_count": 0,
                "fail_count": 0,
                "success_rate": 0.0,
                "today": 0,
                "by_platform": {},
            }


# 全局推送日志记录器
push_log_service = PushLogService()
