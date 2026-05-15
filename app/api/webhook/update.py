# -*- coding: utf-8 -*-
"""
Webhook 更新逻辑
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
from app.models import User, WebhookConfig, WebhookPlatform, PushSettings, FailureConfig, GitRepoConfig, ObsidianConfig
from app.utils.crypto import encrypt_api_key
from app.api.webhook.schemas import (
    ApiResponse,
    WebhookUpdate,
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
    except Exception as e:
        return {"success": False, "message": f"测试失败: {str(e)}"}


@router.put("/{webhook_id}")
async def update_webhook(
    webhook_id: int,
    request: WebhookUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    更新 Webhook 配置

    迁移后：推送配置在 PushSettings 表，失败配置在 FailureConfig 表
    条件校验：webhook_key 变更时才测试，其他字段直接保存
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

    # 判断 webhook_key 是否变更（变更时才需要测试）
    if request.webhook_key:
        old_webhook_key = webhook.decrypted_key
        if request.webhook_key != old_webhook_key:
            test_result = await _test_wecom_webhook(request.webhook_key)
            if not test_result["success"]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Webhook 测试失败: {test_result['message']}"
                )
            webhook.webhook_key = encrypt_api_key(request.webhook_key)

    # 更新 WebhookConfig 核心字段
    if request.name is not None:
        webhook.name = request.name
    if request.is_active is not None:
        webhook.is_active = request.is_active

    # 更新 PushSettings（推送类型开关、阈值、数量限制）
    ps = webhook.push_settings
    if ps is None:
        ps = PushSettings(webhook_config_id=webhook.id)
        db.add(ps)

    if request.push_immediate_enabled is not None:
        ps.push_immediate_enabled = request.push_immediate_enabled
    if request.push_daily_enabled is not None:
        ps.push_daily_enabled = request.push_daily_enabled
    if request.push_weekly_enabled is not None:
        ps.push_weekly_enabled = request.push_weekly_enabled
    if request.push_immediate_threshold is not None:
        ps.push_immediate_threshold = request.push_immediate_threshold
    if request.push_daily_threshold is not None:
        ps.push_daily_threshold = request.push_daily_threshold
    if request.push_weekly_threshold is not None:
        ps.push_weekly_threshold = request.push_weekly_threshold
    if request.push_daily_limit is not None:
        ps.push_daily_limit = request.push_daily_limit
    if request.push_weekly_limit is not None:
        ps.push_weekly_limit = request.push_weekly_limit

    await db.flush()

    # 更新 Obsidian 配置（如果平台是 obsidian_git 或 obsidian_local）
    if webhook.platform in (WebhookPlatform.GIT.value, WebhookPlatform.OBSIDIAN_LOCAL.value):
        if webhook.platform == WebhookPlatform.GIT.value:
            git_config = webhook.git_repo_config
            if git_config is None:
                git_config = GitRepoConfig(webhook_config_id=webhook.id)
                db.add(git_config)
                await db.flush()

            if request.git_repo_url is not None:
                git_config.repo_url = request.git_repo_url
            if request.git_branch is not None:
                git_config.branch = request.git_branch
            # 只有在真正提供了仓库地址或访问令牌时才测试连接
            # 使用 `and request.git_repo_url` 而非 `is not None` 来排除空字符串
            if request.git_repo_url and (request.git_repo_url or request.git_access_token):
                from app.services.notifier.obsidian.connection_tester import test_git_connection
                success, message, _ = await test_git_connection(
                    repo_url=request.git_repo_url or git_config.repo_url,
                    access_token=request.git_access_token or git_config.access_token or "",
                    branch=request.git_branch or git_config.branch or "main",
                )
                if not success:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Git 连接测试失败: {message}"
                    )
                if request.git_access_token is not None:
                    git_config.access_token = encrypt_api_key(request.git_access_token)
            if request.git_credential_type is not None:
                git_config.credential_type = request.git_credential_type
            if request.git_author_name is not None:
                git_config.author_name = request.git_author_name
            if request.git_author_email is not None:
                git_config.author_email = request.git_author_email
            if request.git_daily_folder is not None:
                git_config.daily_folder = request.git_daily_folder
            if request.git_weekly_folder is not None:
                git_config.weekly_folder = request.git_weekly_folder
            if request.git_immediate_folder is not None:
                git_config.immediate_folder = request.git_immediate_folder
        else:
            obsidian_config = webhook.obsidian_config
            if obsidian_config is None:
                obsidian_config = ObsidianConfig(webhook_config_id=webhook.id)
                db.add(obsidian_config)
                await db.flush()

            if request.obsidian_api_url is not None:
                obsidian_config.api_url = request.obsidian_api_url
            if request.obsidian_api_key is not None:
                from app.services.notifier.obsidian.connection_tester import test_obsidian_local_connection
                success, message, _ = await test_obsidian_local_connection(
                    api_url=request.obsidian_api_url or obsidian_config.api_url or "",
                    api_key=request.obsidian_api_key,
                    vault_path=request.obsidian_vault_path or obsidian_config.vault_path or "",
                    verify_ssl=request.obsidian_verify_ssl if request.obsidian_verify_ssl is not None else (obsidian_config.verify_ssl if obsidian_config.verify_ssl is not None else True),
                )
                if not success:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Obsidian Local API 连接测试失败: {message}"
                    )
                obsidian_config.api_key = encrypt_api_key(request.obsidian_api_key)
            if request.obsidian_vault_path is not None:
                obsidian_config.vault_path = request.obsidian_vault_path
            if request.obsidian_daily_folder is not None:
                obsidian_config.daily_folder = request.obsidian_daily_folder
            if request.obsidian_weekly_folder is not None:
                obsidian_config.weekly_folder = request.obsidian_weekly_folder
            if request.obsidian_immediate_folder is not None:
                obsidian_config.immediate_folder = request.obsidian_immediate_folder
            if request.obsidian_verify_ssl is not None:
                obsidian_config.verify_ssl = request.obsidian_verify_ssl

    await db.commit()
    await db.refresh(webhook)
    await db.refresh(ps)

    # 获取或创建 FailureConfig
    fc = webhook.failure_config
    if fc is None:
        fc = FailureConfig(webhook_config_id=webhook.id)
        db.add(fc)
        await db.flush()
        await db.refresh(fc)

    logger.info(f"更新 Webhook 配置成功: {webhook.name} (ID: {webhook.id})")

    # 同步定时任务状态
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data={
            "id": webhook.id,
            "name": webhook.name,
            "platform": webhook.platform,
            "push_immediate_enabled": ps.push_immediate_enabled,
            "push_daily_enabled": ps.push_daily_enabled,
            "push_weekly_enabled": ps.push_weekly_enabled,
            "push_immediate_threshold": ps.push_immediate_threshold,
            "push_daily_threshold": ps.push_daily_threshold,
            "push_weekly_threshold": ps.push_weekly_threshold,
            "push_daily_limit": ps.push_daily_limit,
            "push_weekly_limit": ps.push_weekly_limit,
            "push_fail_count": fc.push_fail_count,
            "push_fail_threshold": fc.push_fail_threshold,
            "is_disabled": fc.is_disabled,
            "push_threshold": webhook.push_threshold,
            "push_enabled": webhook.push_enabled,
            "is_active": webhook.is_active,
            "created_at": webhook.created_at.isoformat() if webhook.created_at else "",
        },
        message="Webhook 配置已更新"
    )