# -*- coding: utf-8 -*-
"""
任务执行历史服务

提供统一的定时任务执行历史查询和统计接口。
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List

from sqlalchemy import case, select, func, and_, desc

from app.database import db
from app.models import TaskExecutionHistory

logger = logging.getLogger(__name__)


class TaskExecutionHistoryService:
    """任务执行历史查询服务"""

    def __init__(self):
        self._db = None
        os.makedirs("logs", exist_ok=True)

    @property
    def database(self):
        if self._db is None:
            return db
        return self._db

    async def save_execution(
        self,
        task_name: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        duration_ms: Optional[int] = None,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> Optional[int]:
        """
        保存任务执行记录

        统一的任务执行历史写入入口，与 OperationLogger.log() 和 PushLogService.log_push() 接口风格一致。
        写入失败时降级到文件日志，不影响主流程。

        Args:
            task_name: 任务名称（如 fetch_ai_news）
            status: 执行状态（start/success/fail/timeout）
            start_time: 开始时间
            end_time: 结束时间
            duration_ms: 执行时长（毫秒）
            result: 执行结果摘要（最长 500 字符）
            error_message: 错误信息（最长 1000 字符）

        Returns:
            记录 ID，写入失败返回 None
        """
        try:
            # 长度截断（与模型字段长度一致）
            result_truncated = result[:500] if result else None
            error_truncated = error_message[:1000] if error_message else None

            record = TaskExecutionHistory(
                task_name=task_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                result=result_truncated,
                error_message=error_truncated,
            )

            async with self.database.get_session() as session:
                session.add(record)
                await session.commit()
                await session.refresh(record)
                log_id = record.id

            logger.debug(
                f"任务执行历史写入成功: id={log_id}, task={task_name}, status={status}"
            )
            return log_id

        except Exception as e:
            logger.error(f"任务执行历史写入失败: task={task_name}, status={status}, error={e}")
            # 降级：写入文件日志
            self._fallback_record(
                task_name=task_name,
                status=status,
                start_time=start_time,
                end_time=end_time,
                duration_ms=duration_ms,
                result=result,
                error_message=error_message,
            )
            return None

    def _fallback_record(
        self,
        task_name: str,
        status: str,
        start_time: datetime,
        end_time: Optional[datetime] = None,
        duration_ms: Optional[int] = None,
        result: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        """
        数据库写入失败时，降级到文件日志

        文件路径: logs/task_execution_fallback.log
        格式: JSON Lines（每行一条 JSON 记录）
        """
        try:
            entry = {
                "timestamp": datetime.now().isoformat(),
                "task_name": task_name,
                "status": status,
                "start_time": start_time.isoformat() if start_time else None,
                "end_time": end_time.isoformat() if end_time else None,
                "duration_ms": duration_ms,
                "result": result[:500] if result else None,
                "error_message": error_message[:1000] if error_message else None,
            }

            with open(
                "logs/task_execution_fallback.log", "a", encoding="utf-8"
            ) as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

            logger.info(
                f"任务执行历史已降级到文件: task={task_name}, status={status}"
            )

        except Exception as fallback_e:
            logger.error(f"任务执行历史 Fallback 写入也失败: {fallback_e}")

    async def query_history(
        self,
        page: int = 1,
        page_size: int = 20,
        task_name: Optional[str] = None,
        status: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        查询任务执行历史（分页）

        Args:
            page: 页码
            page_size: 每页条数
            task_name: 任务名称筛选
            status: 执行状态筛选（start/success/fail/timeout）
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            {
                "items": [{id, task_name, status, start_time, end_time,
                           duration_ms, result, error_message, created_at}, ...],
                "total": 100,
                "page": 1,
                "page_size": 20
            }
        """
        conditions = []

        if task_name:
            conditions.append(TaskExecutionHistory.task_name == task_name)

        if status:
            conditions.append(TaskExecutionHistory.status == status)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                conditions.append(TaskExecutionHistory.start_time >= start_dt)
            except ValueError:
                logger.warning(f"无效的 start_date 格式: {start_date}")

        if end_date:
            try:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                conditions.append(TaskExecutionHistory.start_time < end_dt)
            except ValueError:
                logger.warning(f"无效的 end_date 格式: {end_date}")

        query = select(TaskExecutionHistory)
        count_query = select(func.count(TaskExecutionHistory.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 最新在前
        query = query.order_by(desc(TaskExecutionHistory.start_time))

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        try:
            async with self.database.get_session() as session:
                result = await session.execute(query)
                records = result.scalars().all()

                total_result = await session.execute(count_query)
                total = total_result.scalar() or 0

            items = []
            for r in records:
                item = {
                    "id": r.id,
                    "task_name": r.task_name,
                    "status": r.status,
                    "start_time": r.start_time.isoformat() if r.start_time else None,
                    "end_time": r.end_time.isoformat() if r.end_time else None,
                    "duration_ms": r.duration_ms,
                    "result": r.result,
                    "error_message": r.error_message,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                items.append(item)

            return {
                "items": items,
                "total": total,
                "page": page,
                "page_size": page_size,
            }

        except Exception as e:
            logger.error(f"查询任务执行历史失败: {e}")
            return {"items": [], "total": 0, "page": page, "page_size": page_size}

    async def get_stats_by_task(
        self,
        task_name: Optional[str] = None,
        days: int = 30,
    ) -> dict:
        """
        按任务聚合统计

        Args:
            task_name: 任务名称（可选，不传则统计所有任务）
            days: 统计天数

        Returns:
            {
                "total_executions": 120,
                "success_count": 115,
                "fail_count": 5,
                "timeout_count": 0,
                "success_rate": 95.8,
                "avg_duration_ms": 23456,
                "max_duration_ms": 123456,
                "min_duration_ms": 1234,
                "by_task": [
                    {"task_name": "fetch_ai_news", "total": 30, "success": 29,
                     "success_rate": 96.7, "avg_duration_ms": 12000},
                    ...
                ]
            }
        """
        try:
            start_dt = datetime.utcnow() - timedelta(days=days)

            base_conditions = [TaskExecutionHistory.start_time >= start_dt]
            if task_name:
                base_conditions.append(TaskExecutionHistory.task_name == task_name)

            async with self.database.get_session() as session:
                # 1. 整体统计
                overall_result = await session.execute(
                    select(
                        func.count(TaskExecutionHistory.id).label("total"),
                        func.count(
                            case(
                                (TaskExecutionHistory.status == "success", 1)
                            )
                        ).label("success_count"),
                        func.count(
                            case((TaskExecutionHistory.status == "fail", 1))
                        ).label("fail_count"),
                        func.count(
                            case(
                                (TaskExecutionHistory.status == "timeout", 1)
                            )
                        ).label("timeout_count"),
                        func.avg(TaskExecutionHistory.duration_ms).label(
                            "avg_duration_ms"
                        ),
                        func.max(TaskExecutionHistory.duration_ms).label(
                            "max_duration_ms"
                        ),
                        func.min(TaskExecutionHistory.duration_ms).label(
                            "min_duration_ms"
                        ),
                    ).where(and_(*base_conditions))
                )
                overall = overall_result.one()
                total = overall.total or 0
                success_count = overall.success_count or 0
                fail_count = overall.fail_count or 0
                timeout_count = overall.timeout_count or 0
                avg_duration_ms = (
                    round(float(overall.avg_duration_ms), 1)
                    if overall.avg_duration_ms
                    else 0
                )
                max_duration_ms = overall.max_duration_ms or 0
                min_duration_ms = overall.min_duration_ms or 0
                success_rate = (
                    round(success_count / total * 100, 1) if total > 0 else 0.0
                )

                # 2. 按任务分组统计
                #    仅在未指定 task_name 时做分组统计
                by_task = []
                if not task_name:
                    by_task_result = await session.execute(
                        select(
                            TaskExecutionHistory.task_name,
                            func.count(TaskExecutionHistory.id).label("total"),
                            func.count(
                                case(
                                    (TaskExecutionHistory.status == "success", 1)
                                )
                            ).label("success"),
                            func.avg(TaskExecutionHistory.duration_ms).label(
                                "avg_duration_ms"
                            ),
                        )
                        .where(and_(*base_conditions))
                        .group_by(TaskExecutionHistory.task_name)
                    )
                    for row in by_task_result.all():
                        t_total = row.total or 0
                        t_success = row.success or 0
                        t_success_rate = (
                            round(t_success / t_total * 100, 1)
                            if t_total > 0
                            else 0.0
                        )
                        t_avg_duration = (
                            round(float(row.avg_duration_ms), 1)
                            if row.avg_duration_ms
                            else 0
                        )
                        by_task.append(
                            {
                                "task_name": row.task_name,
                                "total": t_total,
                                "success": t_success,
                                "success_rate": t_success_rate,
                                "avg_duration_ms": t_avg_duration,
                            }
                        )

            return {
                "total_executions": total,
                "success_count": success_count,
                "fail_count": fail_count,
                "timeout_count": timeout_count,
                "success_rate": success_rate,
                "avg_duration_ms": avg_duration_ms,
                "max_duration_ms": max_duration_ms,
                "min_duration_ms": min_duration_ms,
                "by_task": by_task,
            }

        except Exception as e:
            logger.error(f"获取任务执行统计失败: {e}")
            return {
                "total_executions": 0,
                "success_count": 0,
                "fail_count": 0,
                "timeout_count": 0,
                "success_rate": 0.0,
                "avg_duration_ms": 0,
                "max_duration_ms": 0,
                "min_duration_ms": 0,
                "by_task": [],
            }

    async def get_duration_trend(
        self,
        task_name: str,
        days: int = 30,
    ) -> dict:
        """
        获取指定任务的执行时长趋势（按天聚合）

        Args:
            task_name: 任务名称（必填）
            days: 统计天数

        Returns:
            {
                "task_name": "fetch_ai_news",
                "trend": [
                    {"date": "2026-05-07", "avg_duration_ms": 12000, "count": 1},
                    {"date": "2026-05-08", "avg_duration_ms": 15000, "count": 2},
                    ...
                ]
            }
        """
        try:
            start_dt = datetime.utcnow() - timedelta(days=days)

            conditions = [
                TaskExecutionHistory.task_name == task_name,
                TaskExecutionHistory.start_time >= start_dt,
                TaskExecutionHistory.status.in_(["success", "fail"]),
                TaskExecutionHistory.duration_ms.isnot(None),
            ]

            async with self.database.get_session() as session:
                result = await session.execute(
                    select(
                        func.date(TaskExecutionHistory.start_time).label("date"),
                        func.avg(TaskExecutionHistory.duration_ms).label(
                            "avg_duration_ms"
                        ),
                        func.count(TaskExecutionHistory.id).label("count"),
                    )
                    .where(and_(*conditions))
                    .group_by(func.date(TaskExecutionHistory.start_time))
                    .order_by(func.date(TaskExecutionHistory.start_time))
                )

                trend = []
                for row in result.all():
                    trend.append(
                        {
                            "date": row.date,
                            "avg_duration_ms": (
                                round(float(row.avg_duration_ms), 1)
                                if row.avg_duration_ms
                                else 0
                            ),
                            "count": row.count,
                        }
                    )

            return {"task_name": task_name, "trend": trend}

        except Exception as e:
            logger.error(f"获取任务执行时长趋势失败: {e}")
            return {"task_name": task_name, "trend": []}


# 全局任务执行历史服务
task_execution_history_service = TaskExecutionHistoryService()
