# -*- coding: utf-8 -*-
"""
推送日志 API

提供推送日志的查询接口
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.auth.middleware import get_current_user
from app.models import User
from app.services.push_log_service import push_log_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/push-logs")
async def list_push_logs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页条数"),
    webhook_config_id: Optional[int] = Query(None, description="Webhook配置ID"),
    platform: Optional[str] = Query(None, description="推送平台"),
    push_type: Optional[str] = Query(None, description="推送类型"),
    is_success: Optional[bool] = Query(None, description="是否成功"),
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取推送日志列表

    支持分页和多维度筛选
    """
    try:
        result = await push_log_service.query_push_logs(
            page=page,
            page_size=page_size,
            webhook_config_id=webhook_config_id,
            platform=platform,
            push_type=push_type,
            is_success=is_success,
            start_date=start_date,
            end_date=end_date,
        )

        return {
            "code": 200,
            "data": result,
            "message": "success"
        }

    except Exception as e:
        logger.error(f"查询推送日志失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/push-logs/stats")
async def get_push_logs_stats(
    days: int = Query(7, ge=1, le=365, description="统计天数"),
    platform: Optional[str] = Query(None, description="按平台筛选"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    获取推送日志统计

    返回总量、成功率、今日推送数、各平台分布
    """
    try:
        stats = await push_log_service.get_stats(
            days=days,
            platform=platform,
        )

        return {
            "code": 200,
            "data": stats,
            "message": "success"
        }

    except Exception as e:
        logger.error(f"获取推送统计失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
