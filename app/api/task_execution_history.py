# -*- coding: utf-8 -*-
"""
任务执行历史 API

提供定时任务执行历史的查询、统计和趋势接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.middleware import get_current_user
from app.models import User
from app.services.task_execution_history_service import (
    task_execution_history_service,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/task-execution-history/history")
async def list_task_history(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    task_name: Optional[str] = Query(None, description="任务名称筛选"),
    status: Optional[str] = Query(None, description="执行状态：start/success/fail/timeout"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取任务执行历史列表

    支持分页和多维度筛选
    """
    try:
        result = await task_execution_history_service.query_history(
            page=page,
            page_size=page_size,
            task_name=task_name,
            status=status,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "code": 200,
            "data": result,
            "message": "success",
        }

    except Exception as e:
        logger.error(f"查询任务执行历史失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task-execution-history/history/stats")
async def get_task_stats(
    task_name: Optional[str] = Query(None, description="任务名称（不传则统计所有）"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取任务执行统计

    返回执行次数、成功率、平均时长等聚合数据
    """
    try:
        stats = await task_execution_history_service.get_stats_by_task(
            task_name=task_name,
            days=days,
        )

        return {
            "code": 200,
            "data": stats,
            "message": "success",
        }

    except Exception as e:
        logger.error(f"获取任务执行统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/task-execution-history/history/trend")
async def get_duration_trend(
    task_name: str = Query(..., description="任务名称（必填）"),
    days: int = Query(30, ge=1, le=365, description="统计天数"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取指定任务的执行时长趋势（按天聚合）

    用于前端图表展示
    """
    try:
        trend = await task_execution_history_service.get_duration_trend(
            task_name=task_name,
            days=days,
        )

        return {
            "code": 200,
            "data": trend,
            "message": "success",
        }

    except Exception as e:
        logger.error(f"获取任务执行时长趋势失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
