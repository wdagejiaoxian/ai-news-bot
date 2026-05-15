# -*- coding: utf-8 -*-
"""
定时任务装饰器

提供统一的异常处理和日志记录
"""

import asyncio
import logging
from functools import wraps
from datetime import datetime
from typing import Callable, Any, Optional

from app.models import TaskExecutionStatus
from app.services.operation_logger import operation_logger

logger = logging.getLogger(__name__)


async def _save_execution_history(
    task_name: str,
    status: str,
    start_time: datetime,
    end_time: datetime,
    duration_ms: Optional[int] = None,
    result: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    保存任务执行历史到数据库（委托到 TaskExecutionHistoryService）

    Args:
        task_name: 任务名称
        status: 执行状态 (start/success/fail/timeout)
        start_time: 开始时间
        end_time: 结束时间
        duration_ms: 执行时长（毫秒）
        result: 执行结果摘要
        error_message: 错误信息
    """
    from app.services.task_execution_history_service import (
        task_execution_history_service,
    )
    await task_execution_history_service.save_execution(
        task_name=task_name,
        status=status,
        start_time=start_time,
        end_time=end_time,
        duration_ms=duration_ms,
        result=result,
        error_message=error_message,
    )


def task_wrapper(task_name: str):
    """
    统一的任务包装器，处理日志记录和异常

    使用方式：
        @task_wrapper("fetch_ai_news")
        async def fetch_ai_news(self):
            ...

    解决的问题：
    - 统一的任务开始/成功/失败日志记录
    - 减少重复的异常处理代码（23处 -> 1处）
    - 自动计算任务执行时长

    Args:
        task_name: 任务标识名称，与 TASK_METHOD_MAP 中的 key 一致
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self, *args, **kwargs) -> Any:
            start_time = datetime.now()
            task_id = task_name

            # 记录任务开始
            _log_task_event(
                logger=logger,
                action="start",
                task_name=task_id,
                message=f"任务 {task_id} 开始执行"
            )

            # 保存任务开始到执行历史（使用 ensure_future 并跟踪）
            start_task = asyncio.ensure_future(
                _save_execution_history(
                    task_name=task_id,
                    status=TaskExecutionStatus.START.value,
                    start_time=start_time,
                    end_time=start_time,
                )
            )

            try:
                result = await func(self, *args, **kwargs)

                # 记录任务成功
                end_time = datetime.now()
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                _log_task_event(
                    logger=logger,
                    action="success",
                    task_name=task_id,
                    message=f"任务 {task_id} 执行成功",
                    detail={
                        "duration_ms": duration_ms,
                        "result": str(result)[:500] if result else None,  # 限制长度避免日志过长
                    }
                )

                # 保存任务成功到执行历史
                success_task = asyncio.ensure_future(
                    _save_execution_history(
                        task_name=task_id,
                        status=TaskExecutionStatus.SUCCESS.value,
                        start_time=start_time,
                        end_time=end_time,
                        duration_ms=duration_ms,
                        result=str(result)[:500] if result else None,
                    )
                )

                return result

            except Exception as e:
                end_time = datetime.now()
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                error_msg = f"任务 {task_id} 执行失败: {str(e)}"
                error_str = str(e)[:1000]

                # 记录任务失败
                logger.error(error_msg)
                _log_task_event(
                    logger=logger,
                    action="fail",
                    task_name=task_id,
                    log_level="ERROR",
                    message=error_msg,
                    detail={
                        "duration_ms": duration_ms,
                        "error": error_str[:500],
                    }
                )

                # 保存任务失败到执行历史
                fail_task = asyncio.ensure_future(
                    _save_execution_history(
                        task_name=task_id,
                        status=TaskExecutionStatus.FAIL.value,
                        start_time=start_time,
                        end_time=end_time,
                        duration_ms=duration_ms,
                        error_message=error_str,
                    )
                )

                # 重新抛出异常，让调用者知道任务失败了
                raise

        return wrapper
    return decorator


def _log_task_event(
    logger: logging.Logger,
    action: str,
    task_name: str,
    message: str,
    log_level: str = "INFO",
    detail: Optional[dict] = None
) -> None:
    """
    内部辅助函数：记录任务事件

    Args:
        logger: 日志记录器
        action: 事件动作 (start/success/fail)
        task_name: 任务名称
        message: 日志消息
        log_level: 日志级别
        detail: 详细信息
    """
    # 写入门日志
    if action == "start":
        logger.info(message)
    elif action == "success":
        logger.info(message)
    elif action == "fail":
        if log_level == "ERROR":
            logger.error(message)
        else:
            logger.warning(message)

    # 写入数据库 operation_log（异步，不阻塞）
    try:
        asyncio.create_task(
            operation_logger.log(
                log_type="task_exec",
                action=action,
                operator="scheduler",
                task_name=task_name,
                log_level=log_level if action == "fail" else "INFO",
                detail=detail or {"message": message},
            )
        )
    except Exception as e:
        logger.warning(f"记录任务 {action} 日志失败: {e}")