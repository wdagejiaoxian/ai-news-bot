# -*- coding: utf-8 -*-
"""
任务配置管理 API

提供数据库中的任务配置 CRUD 功能
拆分自 app/api/scheduler.py
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import User, ScheduledTaskConfig
from app.services.scheduler.jobs import scheduler
from app.services.scheduler.config_loader import config_loader, validate_task_dependency
from app.services.scheduler.config_logger import config_logger
from app.api.scheduler.schemas import (
    ApiResponse,
    TaskConfigUpdate,
    TaskConfigResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/configs")
async def list_task_configs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    task_type: Optional[str] = Query(None, description="按任务类型筛选"),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """获取定时任务配置列表"""
    query = select(ScheduledTaskConfig)
    count_query = select(func.count(ScheduledTaskConfig.id))

    if task_type:
        query = query.where(ScheduledTaskConfig.task_type == task_type)
        count_query = count_query.where(ScheduledTaskConfig.task_type == task_type)

    if is_active is not None:
        query = query.where(ScheduledTaskConfig.is_active == is_active)
        count_query = count_query.where(ScheduledTaskConfig.is_active == is_active)

    total = await db.scalar(count_query) or 0

    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(ScheduledTaskConfig.created_at.desc())

    result = await db.execute(query)
    tasks = result.scalars().all()

    items = []
    for task in tasks:
        next_run = None
        try:
            job = scheduler.get_job(task.task_name)
            if job:
                next_run = str(job.next_run_time) if job.next_run_time else None
        except Exception as e:
            logger.warning(f"获取任务 {task.task_name} 下次执行时间失败: {e}")

        items.append(TaskConfigResponse(
            id=task.id,
            task_name=task.task_name,
            task_type=task.task_type,
            hour=task.hour,
            minute=task.minute,
            day_of_week=task.day_of_week,
            interval_minutes=task.interval_minutes,
            is_active=task.is_active,
            config_version=task.config_version,
            next_run=next_run,
            created_at=task.created_at.isoformat() if task.created_at else "",
        ).model_dump())

    return ApiResponse(
        code=200,
        data={
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        message="success"
    )


@router.get("/configs/{task_id}")
async def get_task_config(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """获取单个任务配置"""
    result = await db.execute(
        select(ScheduledTaskConfig).where(ScheduledTaskConfig.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务配置不存在")

    return ApiResponse(
        code=200,
        data=TaskConfigResponse(
            id=task.id,
            task_name=task.task_name,
            task_type=task.task_type,
            hour=task.hour,
            minute=task.minute,
            day_of_week=task.day_of_week,
            interval_minutes=task.interval_minutes,
            is_active=task.is_active,
            config_version=task.config_version,
            created_at=task.created_at.isoformat() if task.created_at else "",
        ).model_dump(),
        message="success"
    )


@router.put("/configs/{task_id}")
async def update_task_config(
    task_id: int,
    request: TaskConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    更新任务配置

    更新后自动触发增量热重载
    """
    result = await db.execute(
        select(ScheduledTaskConfig).where(ScheduledTaskConfig.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务配置不存在")

    # 保存旧配置用于日志
    old_config = {
        "task_type": task.task_type,
        "hour": task.hour,
        "minute": task.minute,
        "day_of_week": task.day_of_week,
        "interval_minutes": task.interval_minutes,
        "is_active": task.is_active,
        "config_version": task.config_version,
    }

    # 计算新配置值（用于校验）
    new_task_type = request.task_type if request.task_type is not None else task.task_type
    new_interval = request.interval_minutes if request.interval_minutes is not None else task.interval_minutes

    # 校验配置
    try:
        # 获取 fetch_ai_news 的间隔用于校验
        fetch_interval = await config_loader.validate_and_get_fetch_interval(task.task_name)

        is_valid, error_msg = config_loader.validate_config(
            task_name=task.task_name,
            task_type=new_task_type,
            interval_minutes=new_interval,
            fetch_interval=fetch_interval,
        )

        if not is_valid:
            raise HTTPException(status_code=400, detail=error_msg)

        # M13: 校验任务依赖（只在 is_active 变更时校验）
        if request.is_active is not None:
            dep_valid, dep_error = await validate_task_dependency(
                task_name=task.task_name,
                is_active=request.is_active,
            )
            if not dep_valid:
                raise HTTPException(status_code=400, detail=dep_error)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"配置校验失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置校验失败: {str(e)}")

    # 更新字段
    if request.task_type is not None:
        task.task_type = request.task_type
    if request.hour is not None:
        task.hour = request.hour
    if request.minute is not None:
        task.minute = request.minute
    if request.day_of_week is not None:
        task.day_of_week = request.day_of_week
    if request.interval_minutes is not None:
        task.interval_minutes = request.interval_minutes
    if request.is_active is not None:
        task.is_active = request.is_active

    # 增加配置版本号（用于热重载检测）
    task.config_version += 1

    await db.flush()
    await db.refresh(task)

    # 新配置用于日志
    new_config = {
        "task_type": task.task_type,
        "hour": task.hour,
        "minute": task.minute,
        "day_of_week": task.day_of_week,
        "interval_minutes": task.interval_minutes,
        "is_active": task.is_active,
        "config_version": task.config_version,
    }

    # 记录配置变更日志
    try:
        config_logger.record_change(
            task_name=task.task_name,
            old_config=old_config,
            new_config=new_config,
            changed_by="web_panel",
        )
    except Exception as e:
        logger.warning(f"记录配置变更日志失败: {e}")

    # 增量热重载（只重载当前任务）
    try:
        reload_result = scheduler.reload_job(task.task_name, config=task)
        logger.info(f"任务配置更新后增量热重载: {reload_result}")
    except Exception as e:
        logger.error(f"增量热重载失败: {e}")

    logger.info(f"更新任务配置成功: {task.task_name} (ID: {task.id})")

    return ApiResponse(
        code=200,
        data={
            "id": task.id,
            "task_name": task.task_name,
            "task_type": task.task_type,
            "hour": task.hour,
            "minute": task.minute,
            "day_of_week": task.day_of_week,
            "interval_minutes": task.interval_minutes,
            "is_active": task.is_active,
            "config_version": task.config_version,
        },
        message="任务配置已更新"
    )


@router.post("/configs/{task_id}/trigger")
async def trigger_task_config(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """手动触发任务执行"""
    result = await db.execute(
        select(ScheduledTaskConfig).where(ScheduledTaskConfig.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务配置不存在")

    try:
        success = scheduler.run_job(task.task_name)

        if success:
            logger.info(f"手动触发任务成功: {task.task_name}")
            return ApiResponse(
                code=200,
                data={
                    "job_id": task.task_name,
                    "triggered_at": None,
                    "status": "triggered"
                },
                message="任务已手动触发"
            )
        else:
            return ApiResponse(
                code=400,
                data=None,
                message="任务触发失败"
            )
    except Exception as e:
        logger.error(f"手动触发任务失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/configs/reload")
async def reload_scheduler_configs(
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """热重载所有定时任务"""
    try:
        result = scheduler.reload_jobs()

        logger.info(f"热重载定时任务完成: {result}")

        return ApiResponse(
            code=200,
            data={
                "reloaded": True,
                "jobs_count": result.get("jobs_count", 0),
                "jobs": result.get("jobs", [])
            },
            message="热重载成功"
        )
    except Exception as e:
        logger.error(f"热重载失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/configs/{task_id}/history")
async def get_config_history(
    task_id: int,
    limit: int = Query(20, ge=1, le=100, description="返回条数"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """获取配置变更历史"""
    # 获取任务名称
    result = await db.execute(
        select(ScheduledTaskConfig).where(ScheduledTaskConfig.id == task_id)
    )
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(status_code=404, detail="任务配置不存在")

    # 从日志中读取
    try:
        logs = config_logger.get_logs(task_name=task.task_name, limit=limit)
        return ApiResponse(
            code=200,
            data={"items": logs},
            message="success"
        )
    except Exception as e:
        logger.error(f"获取配置历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))