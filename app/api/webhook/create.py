# -*- coding: utf-8 -*-
"""
Webhook 创建逻辑
拆分自 app/api/webhook.py
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User, WebhookConfig, WebhookPlatform, PushSettings, FailureConfig, ObsidianConfig, GitRepoConfig
from app.utils.crypto import encrypt_api_key
from app.services.notifier.obsidian.connection_tester import test_obsidian_local_connection
from app.api.webhook.schemas import (
    ApiResponse,
    WebhookCreate,
)

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
    except httpx.TimeoutException:
        return {"success": False, "message": "请求超时"}
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)}"}


@router.post("", include_in_schema=False)
@router.post("/")
async def create_webhook(
    request: WebhookCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    创建 Webhook 配置

    - 校验密钥格式
    - 实际调用企业微信 API 测试
    - 测试通过后 AES 加密存储密钥
    """
    # 验证平台类型
    valid_platforms = [p.value for p in WebhookPlatform]
    if request.platform not in valid_platforms:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台类型，仅支持: {', '.join(valid_platforms)}"
        )

    # 验证密钥格式（Obsidian 平台不需要）
    if request.platform == WebhookPlatform.WECOM.value:
        webhook_key = request.webhook_key
        if not webhook_key or len(webhook_key) < 32:
            raise HTTPException(
                status_code=400,
                detail="Webhook 密钥格式无效，企业微信 Webhook Key 至少需要 32 字符"
            )
        # 实际调用企业微信 API 测试
        test_result = await _test_wecom_webhook(webhook_key)
        if not test_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"Webhook 测试失败: {test_result['message']}"
            )
    elif request.platform in (WebhookPlatform.GIT.value, WebhookPlatform.OBSIDIAN_LOCAL.value):
        # Obsidian 平台：验证 Git 或 Local API 配置是否提供，并测试连接
        if request.platform == WebhookPlatform.GIT.value:
            if not request.git_repo_url:
                raise HTTPException(
                    status_code=400,
                    detail="Git 模式需要提供仓库地址"
                )
            if not request.git_access_token:
                raise HTTPException(
                    status_code=400,
                    detail="Git 模式需要提供访问令牌"
                )
            # 测试 Git 连接
            from app.services.notifier.obsidian.connection_tester import test_git_connection
            success, message, _ = await test_git_connection(
                repo_url=request.git_repo_url,
                access_token=request.git_access_token,
                branch=request.git_branch or "main",
            )
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Git 连接测试失败: {message}"
                )
        elif request.platform == WebhookPlatform.OBSIDIAN_LOCAL.value:
            if not request.obsidian_api_url:
                raise HTTPException(
                    status_code=400,
                    detail="Obsidian Local API 模式需要提供 API 地址"
                )
            if not request.obsidian_api_key:
                raise HTTPException(
                    status_code=400,
                    detail="Obsidian Local API 模式需要提供 API Key"
                )
            # 测试 Obsidian Local API 连接
            success, message, _ = await test_obsidian_local_connection(
                api_url=request.obsidian_api_url,
                api_key=request.obsidian_api_key,
                vault_path=request.obsidian_vault_path or "",
                verify_ssl=request.obsidian_verify_ssl if request.obsidian_verify_ssl is not None else True,
            )
            if not success:
                raise HTTPException(
                    status_code=400,
                    detail=f"Obsidian Local API 连接测试失败: {message}"
                )

    # 创建 Webhook 配置（使用 AES 加密）
    webhook = WebhookConfig(
        name=request.name,
        platform=request.platform,
        webhook_key=encrypt_api_key(request.webhook_key) if request.webhook_key else "",
        push_threshold=request.push_immediate_threshold,
        push_enabled=True,
        is_active=True,
    )

    db.add(webhook)
    await db.flush()

    # 创建 PushSettings（推送类型开关、阈值、数量限制）
    push_settings = PushSettings(
        webhook_config_id=webhook.id,
        push_immediate_enabled=request.push_immediate_enabled,
        push_daily_enabled=request.push_daily_enabled,
        push_weekly_enabled=request.push_weekly_enabled,
        push_immediate_threshold=request.push_immediate_threshold,
        push_daily_threshold=request.push_daily_threshold,
        push_weekly_threshold=request.push_weekly_threshold,
        push_daily_limit=request.push_daily_limit,
        push_weekly_limit=request.push_weekly_limit,
    )
    db.add(push_settings)

    # 创建 FailureConfig（失败处理配置）
    failure_config = FailureConfig(
        webhook_config_id=webhook.id,
        push_fail_count=0,
        push_fail_threshold=10,
        is_disabled=False,
    )
    db.add(failure_config)

    # 创建 Obsidian 配置（如果平台是 obsidian_git 或 obsidian_local）
    obsidian_config = None
    if request.platform in (WebhookPlatform.GIT.value, WebhookPlatform.OBSIDIAN_LOCAL.value):
        if request.platform == WebhookPlatform.GIT.value:
            obsidian_config = GitRepoConfig(
                webhook_config_id=webhook.id,
                repo_url=request.git_repo_url or "",
                branch=request.git_branch or "main",
                access_token=encrypt_api_key(request.git_access_token) if request.git_access_token else "",
                credential_type=request.git_credential_type or "deploy_token",
                author_name=request.git_author_name or "AI News Bot",
                author_email=request.git_author_email or "",
                daily_folder=request.git_daily_folder or "AI-News/Daily",
                weekly_folder=request.git_weekly_folder or "AI-News/Weekly",
                immediate_folder=request.git_immediate_folder or "AI-News/Immediate",
            )
        else:
            obsidian_config = ObsidianConfig(
                webhook_config_id=webhook.id,
                api_url=request.obsidian_api_url or "",
                api_key=encrypt_api_key(request.obsidian_api_key) if request.obsidian_api_key else "",
                vault_path=request.obsidian_vault_path or "",
                daily_folder=request.obsidian_daily_folder or "AI-News/Daily",
                weekly_folder=request.obsidian_weekly_folder or "AI-News/Weekly",
                immediate_folder=request.obsidian_immediate_folder or "AI-News/Immediate",
                verify_ssl=request.obsidian_verify_ssl if request.obsidian_verify_ssl is not None else True,
            )
        db.add(obsidian_config)

    await db.commit()
    await db.refresh(webhook)
    await db.refresh(push_settings)
    await db.refresh(failure_config)
    if request.platform in (WebhookPlatform.GIT.value, WebhookPlatform.OBSIDIAN_LOCAL.value):
        await db.refresh(obsidian_config)

    logger.info(f"创建 Webhook 配置成功: {webhook.name} (ID: {webhook.id})")

    # 同步定时任务状态
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data={
            "id": webhook.id,
            "name": webhook.name,
            "platform": webhook.platform,
            "push_immediate_enabled": push_settings.push_immediate_enabled,
            "push_daily_enabled": push_settings.push_daily_enabled,
            "push_weekly_enabled": push_settings.push_weekly_enabled,
            "push_immediate_threshold": push_settings.push_immediate_threshold,
            "push_daily_threshold": push_settings.push_daily_threshold,
            "push_weekly_threshold": push_settings.push_weekly_threshold,
            "push_daily_limit": push_settings.push_daily_limit,
            "push_weekly_limit": push_settings.push_weekly_limit,
            "push_fail_count": failure_config.push_fail_count,
            "push_fail_threshold": failure_config.push_fail_threshold,
            "is_disabled": failure_config.is_disabled,
            "push_threshold": webhook.push_threshold,
            "push_enabled": webhook.push_enabled,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else "",
        },
        message="Webhook 配置成功"
    )