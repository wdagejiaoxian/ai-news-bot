# -*- coding: utf-8 -*-
"""
Webhook 测试逻辑
拆分自 app/api/webhook.py
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User, WebhookConfig, WebhookPlatform
from app.api.webhook.schemas import ApiResponse

router = APIRouter()
logger = logging.getLogger(__name__)


async def _test_wecom_webhook(webhook_key: str) -> dict:
    """测试企业微信 Webhook 是否可用"""
    import httpx

    test_message = {
        "msgtype": "text",
        "text": {"content": "🔔 测试消息：Webhook 配置测试成功！"}
    }

    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.webhook_api_timeout) as client:
            response = await client.post(
                f"{settings.wecom_api_base_url}/cgi-bin/webhook/send?key={webhook_key}",
                json=test_message
            )

            if response.status_code == 200:
                result = response.json()
                if result.get("errcode") == 0:
                    return {"success": True, "message": "测试消息发送成功"}
                else:
                    return {"success": False, "message": f"企业微信返回错误: {result.get('errmsg', '未知错误')}"}
            else:
                return {"success": False, "message": f"请求失败: HTTP {response.status_code}"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)}"}


@router.post("/{webhook_id}/test")
async def test_webhook(
    webhook_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    测试 Webhook 配置是否可用
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

    # 使用模型的 decrypted_key 获取解密后的密钥
    webhook_key = webhook.decrypted_key

    # 调用企业微信 API 测试
    if webhook.platform == WebhookPlatform.WECOM.value:
        test_result = await _test_wecom_webhook(webhook_key)
        return ApiResponse(
            code=200 if test_result["success"] else 400,
            data=test_result,
            message=test_result["message"]
        )

    return ApiResponse(
        code=400,
        data={"success": False, "message": f"不支持的平台类型: {webhook.platform}"},
        message="不支持的平台类型"
    )