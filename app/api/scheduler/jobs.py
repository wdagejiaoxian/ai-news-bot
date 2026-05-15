# -*- coding: utf-8 -*-
"""
运行时任务管理 API

提供 APScheduler 任务状态查询和手动触发功能
拆分自 app/api/scheduler.py
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException

from app.auth.middleware import get_current_user
from app.models import User
from app.services.scheduler.jobs import scheduler
from app.api.scheduler.schemas import (
    ApiResponse,
    JobResponse,
    JobTriggerResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/jobs")
async def get_scheduler_jobs(
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取所有定时任务状态"""
    jobs = []
    scheduler_jobs = scheduler.get_jobs()

    for job in scheduler_jobs:
        jobs.append(
            JobResponse(
                id=job.id,
                name=job.name or job.id,
                func=job.func_ref or str(job.func),
                trigger=str(job.trigger),
                next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
                last_run_time=None,
                status="active",
            )
        )

    return ApiResponse(
        code=200,
        data={
            "items": [j.model_dump() for j in jobs],
            "total": len(jobs),
        },
        message="success"
    )


@router.get("/jobs/{job_id}")
async def get_scheduler_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取定时任务详情"""
    job = scheduler.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="任务不存在"
        )

    return ApiResponse(
        code=200,
        data=JobResponse(
            id=job.id,
            name=job.name or job.id,
            func=job.func_ref or str(job.func),
            trigger=str(job.trigger),
            next_run_time=job.next_run_time.isoformat() if job.next_run_time else None,
            last_run_time=None,
            status="active",
        ).model_dump(),
        message="success"
    )


@router.post("/jobs/{job_id}/trigger")
async def trigger_scheduler_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """手动触发定时任务"""
    job = scheduler.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=404,
            detail="任务不存在"
        )

    try:
        import asyncio
        # 注意：这不会等待任务完成，任务会异步执行
        # API 会立即返回，任务在后台运行
        asyncio.create_task(scheduler.run_job(job_id))

        return ApiResponse(
            code=200,
            data=JobTriggerResponse(
                success=True,
                message=f"任务 {job_id} 已触发执行",
                job_id=job_id,
            ).model_dump(),
            message="success"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"触发任务失败: {str(e)}"
        )