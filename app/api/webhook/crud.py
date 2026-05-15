# -*- coding: utf-8 -*-
"""
Webhook 基础 CRUD 操作
拆分自 app/api/webhook.py
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import User, WebhookConfig
from app.api.webhook.schemas import (
    ApiResponse,
    WebhookResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


def _build_webhook_response(w: WebhookConfig) -> dict:
    """构建 Webhook 响应字典"""
    ps = w.push_settings
    fc = w.failure_config
    return {
        "id": w.id,
        "name": w.name,
        "platform": w.platform,
        # === PushSettings 字段 ===
        "push_immediate_enabled": ps.push_immediate_enabled if ps else True,
        "push_daily_enabled": ps.push_daily_enabled if ps else True,
        "push_weekly_enabled": ps.push_weekly_enabled if ps else True,
        "push_immediate_threshold": ps.push_immediate_threshold if ps else 85.0,
        "push_daily_threshold": ps.push_daily_threshold if ps else 75.0,
        "push_weekly_threshold": ps.push_weekly_threshold if ps else 80.0,
        "push_daily_limit": ps.push_daily_limit if ps else 500,
        "push_weekly_limit": ps.push_weekly_limit if ps else 300,
        # === FailureConfig 字段 ===
        "push_fail_count": fc.push_fail_count if fc else 0,
        "push_fail_threshold": fc.push_fail_threshold if fc else 10,
        "is_disabled": fc.is_disabled if fc else False,
        # === 兼容字段 ===
        "push_threshold": w.push_threshold,
        "push_enabled": w.push_enabled,
        "is_active": w.is_active,
        "created_at": w.created_at.isoformat() if w.created_at else "",
        # === Git 配置 ===
        "git_repo_url": w.git_repo_config.repo_url if w.git_repo_config else None,
        "git_branch": w.git_repo_config.branch if w.git_repo_config else None,
        "git_daily_folder": w.git_repo_config.daily_folder if w.git_repo_config else None,
        "git_weekly_folder": w.git_repo_config.weekly_folder if w.git_repo_config else None,
        "git_immediate_folder": w.git_repo_config.immediate_folder if w.git_repo_config else None,
        # === Obsidian Local 配置 ===
        "obsidian_api_url": w.obsidian_config.api_url if w.obsidian_config else None,
        "obsidian_vault_path": w.obsidian_config.vault_path if w.obsidian_config else None,
        "obsidian_daily_folder": w.obsidian_config.daily_folder if w.obsidian_config else None,
        "obsidian_weekly_folder": w.obsidian_config.weekly_folder if w.obsidian_config else None,
        "obsidian_immediate_folder": w.obsidian_config.immediate_folder if w.obsidian_config else None,
    }


@router.get("", include_in_schema=False)
@router.get("/")
async def list_webhooks(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    platform: Optional[str] = Query(None, description="按平台筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取 Webhook 配置列表
    """
    # 构建查询（使用 selectinload 预加载关联表）
    query = (
        select(WebhookConfig)
        .options(selectinload(WebhookConfig.push_settings))
        .options(selectinload(WebhookConfig.failure_config))
        .options(selectinload(WebhookConfig.git_repo_config))
        .options(selectinload(WebhookConfig.obsidian_config))
    )
    count_query = select(func.count(WebhookConfig.id))

    if platform:
        query = query.where(WebhookConfig.platform == platform)
        count_query = count_query.where(WebhookConfig.platform == platform)

    # 统计总数
    total = await db.scalar(count_query) or 0

    # 分页查询
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(WebhookConfig.created_at.desc())

    result = await db.execute(query)
    webhooks = result.scalars().all()

    items = [_build_webhook_response(w) for w in webhooks]

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


@router.get("/{webhook_id}")
async def get_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取单个 Webhook 配置
    """
    result = await db.execute(
        select(WebhookConfig)
        .options(selectinload(WebhookConfig.push_settings))
        .options(selectinload(WebhookConfig.failure_config))
        .options(selectinload(WebhookConfig.git_repo_config))
        .options(selectinload(WebhookConfig.obsidian_config))
        .where(WebhookConfig.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook 配置不存在")

    return ApiResponse(
        code=200,
        data=_build_webhook_response(webhook),
        message="success"
    )