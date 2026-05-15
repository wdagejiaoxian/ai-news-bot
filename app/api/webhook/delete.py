# -*- coding: utf-8 -*-
"""
Webhook 删除逻辑
拆分自 app/api/webhook.py
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import User, WebhookConfig
from app.api.webhook.schemas import ApiResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.delete("/{webhook_id}")
async def delete_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    删除 Webhook 配置
    """
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()

    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook 配置不存在")

    webhook_name = webhook.name
    await db.delete(webhook)
    await db.commit()

    logger.info(f"删除 Webhook 配置成功: {webhook_name} (ID: {webhook_id})")

    # 同步定时任务状态
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data=None,
        message="Webhook 已删除"
    )