# -*- coding: utf-8 -*-
"""
操作日志服务

提供统一的日志写入和查询接口
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Any

from sqlalchemy import select, func, and_, or_, desc

from app.database import db
from app.models import OperationLog, LogType, LogLevel

logger = logging.getLogger(__name__)


class OperationLogger:
    """操作日志记录器"""

    def __init__(self):
        self._db = None
        # 确保日志目录存在
        os.makedirs("logs", exist_ok=True)

    @property
    def database(self):
        if self._db is None:
            return db
        return self._db

    async def log(
        self,
        log_type: str,
        action: str,
        operator: str = "system",
        log_level: str = LogLevel.INFO.value,
        task_name: Optional[str] = None,
        detail: Optional[dict] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[int]:
        """
        写入操作日志

        Args:
            log_type: 日志类型 (LogType)
            action: 操作类型 (LogAction)
            operator: 操作人
            log_level: 日志级别
            task_name: 关联任务名称
            detail: 详细信息 (dict)
            ip_address: IP 地址

        Returns:
            日志 ID，失败返回 None
        """
        try:
            # 序列化 detail 为 JSON 字符串
            detail_str = json.dumps(detail, ensure_ascii=False) if detail else None

            # 构建日志对象
            log_entry = OperationLog(
                log_type=log_type,
                log_level=log_level,
                task_name=task_name,
                operator=operator,
                action=action,
                detail=detail_str,
                ip_address=ip_address,
            )

            # 写入数据库
            async with self.database.get_session() as session:
                session.add(log_entry)
                await session.commit()
                await session.refresh(log_entry)
                log_id = log_entry.id

            logger.debug(f"操作日志写入成功: id={log_id}, type={log_type}, action={action}")
            return log_id

        except Exception as e:
            logger.error(f"操作日志写入失败: {e}")
            # Fallback: 写入文件
            self._fallback_log(log_type, action, operator, log_level, task_name, detail, ip_address)
            return None

    def _fallback_log(
        self,
        log_type: str,
        action: str,
        operator: str,
        log_level: str,
        task_name: Optional[str],
        detail: Optional[dict],
        ip_address: Optional[str],
    ) -> None:
        """Fallback: 写入文件日志"""
        try:
            fallback_file = "logs/operation_fallback.log"

            entry = {
                "timestamp": datetime.now().isoformat(),
                "log_type": log_type,
                "action": action,
                "operator": operator,
                "log_level": log_level,
                "task_name": task_name,
                "detail": detail,
                "ip_address": ip_address,
            }

            with open(fallback_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        except Exception as fallback_e:
            logger.error(f"Fallback 日志写入也失败: {fallback_e}")

    async def query_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        log_type: Optional[str] = None,
        task_name: Optional[str] = None,
        level: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> dict:
        """
        查询操作日志

        Args:
            page: 页码
            page_size: 每页条数
            log_type: 日志类型筛选
            task_name: 任务名称筛选
            level: 日志级别筛选
            action: 操作类型筛选
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

        if log_type:
            conditions.append(OperationLog.log_type == log_type)

        if task_name:
            conditions.append(OperationLog.task_name == task_name)

        if level:
            conditions.append(OperationLog.log_level == level)

        if action:
            conditions.append(OperationLog.action == action)

        if start_date:
            try:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                conditions.append(OperationLog.created_at >= start_dt)
            except ValueError:
                logger.warning(f"无效的 start_date 格式: {start_date}")

        if end_date:
            try:
                # 结束日期需要加一天（包含当天）
                end_dt = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
                conditions.append(OperationLog.created_at < end_dt)
            except ValueError:
                logger.warning(f"无效的 end_date 格式: {end_date}")

        # 构建查询
        query = select(OperationLog)
        count_query = select(func.count(OperationLog.id))

        if conditions:
            query = query.where(and_(*conditions))
            count_query = count_query.where(and_(*conditions))

        # 排序：最新在前
        query = query.order_by(desc(OperationLog.created_at))

        # 分页
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # 执行查询
        async with self.database.get_session() as session:
            result = await session.execute(query)
            logs = result.scalars().all()

            total_result = await session.execute(count_query)
            total = total_result.scalar() or 0

        # 转换 detail JSON 字符串为对象
        items = []
        for log in logs:
            item = {
                "id": log.id,
                "log_type": log.log_type,
                "log_level": log.log_level,
                "task_name": log.task_name,
                "operator": log.operator,
                "action": log.action,
                "detail": json.loads(log.detail) if log.detail else None,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            items.append(item)

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        }

    async def get_log_by_id(self, log_id: int) -> Optional[dict]:
        """
        根据 ID 获取单条日志

        Args:
            log_id: 日志 ID

        Returns:
            日志详情 dict 或 None
        """
        async with self.database.get_session() as session:
            result = await session.execute(
                select(OperationLog).where(OperationLog.id == log_id)
            )
            log = result.scalar_one_or_none()

        if not log:
            return None

        return {
            "id": log.id,
            "log_type": log.log_type,
            "log_level": log.log_level,
            "task_name": log.task_name,
            "operator": log.operator,
            "action": log.action,
            "detail": json.loads(log.detail) if log.detail else None,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }


# 全局单例
operation_logger = OperationLogger()