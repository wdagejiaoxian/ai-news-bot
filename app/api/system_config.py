# -*- coding: utf-8 -*-
"""
系统配置管理 API

提供用户自定义配置的查询、修改和恢复默认值接口。
基于方案四（Config Sync）设计，修改后即时生效，无需重启。

端点（挂载于 /api/system-configs 前缀下）：
- GET    /                       — 获取所有可配置项
- PUT    /{key}                  — 修改单个配置
- DELETE /{key}/customization    — 恢复为默认值
"""

import json
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import User, OperationLog
from app.services.config_sync import config_sync_service, ConfigSyncValidationError

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Pydantic 模型 ====================


class ApiResponse(BaseModel):
    """统一 API 响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


class UpdateConfigRequest(BaseModel):
    """修改配置请求体"""
    value: Any

    @field_validator("value")
    @classmethod
    def value_must_not_be_none(cls, v):
        if v is None:
            raise ValueError("配置值不能为空")
        return v


# ==================== 依赖注入 ====================


async def _require_web_panel_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """验证当前用户是否为 Web 面板管理员"""
    if not current_user.is_web_panel_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="仅 Web 面板用户可以管理系统配置",
        )
    return current_user


# ==================== 辅助函数 ====================


async def _record_operation_log(
    session: AsyncSession,
    operator: str,
    action: str,
    detail: dict,
    ip_address: Optional[str] = None,
) -> None:
    """
    记录系统配置变更到操作日志

    Args:
        session: 数据库会话
        operator: 操作者标识
        action: 操作类型（update/reset）
        detail: 操作详情（含 key、前后值等）
        ip_address: 客户端 IP

    注意：此函数不阻塞主流程，日志记录失败不影响配置修改结果。
    """
    try:
        log_entry = OperationLog(
            log_type="config_change",
            log_level="INFO",
            operator=operator,
            action=action,
            detail=json.dumps(detail, ensure_ascii=False),
            ip_address=ip_address,
        )
        session.add(log_entry)
        await session.commit()
        logger.debug("已记录系统配置操作日志: action=%s, key=%s", action, detail.get("key"))
    except Exception as e:
        logger.warning("记录操作日志失败（不影响配置）: %s", e)
        await session.rollback()


def _get_operator(current_user: User) -> str:
    """获取操作者标识"""
    if current_user.is_web_panel_user:
        return f"web_panel:{current_user.platform_id}"
    return f"user:{current_user.platform_id}"


# ==================== API 端点 ====================


@router.get("")
async def list_system_configs(
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_web_panel_user),
) -> ApiResponse:
    """
    获取全部可动态配置的系统配置项

    返回所有可配置参数的当前值、默认值、类型、分类、
    加密状态和自定义标记。敏感配置（如 github_token）
    自动脱敏返回。

    未自定义的配置项 updated_at 返回 None。
    总数始终为 41（配置项完整），customized_count 表示用户已自定义的数量。
    """
    try:
        configs = await config_sync_service.get_all(db)
        total = len(configs)
        customized_count = sum(1 for c in configs if c["is_customized"])

        return ApiResponse(
            code=200,
            data={
                "configs": configs,
                "total": total,
                "customized_count": customized_count,
            },
            message="success",
        )
    except Exception as e:
        logger.error("获取系统配置列表失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取系统配置列表失败: {e}",
        )


@router.put("/{key}")
async def update_system_config(
    request: Request,
    key: str,
    body: UpdateConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_web_panel_user),
) -> ApiResponse:
    """
    修改单个系统配置

    验证流程：
    1. 检查 key 是否在白名单中（OVERRIDABLE_KEYS）
    2. 使用 pydantic TypeAdapter 自动类型转换（如 "85" → 85）
    3. 检查 Field metadata 中的约束（Ge/Le）
    4. 敏感配置（如 github_token）自动加密存储
    5. 写入 system_configs 表 + setattr 即时生效

    Args:
        key: 配置键名（如 push_score_threshold）

    Request body:
        {"value": 90}

    Returns:
        修改后的当前值和修改前的旧值
    """
    try:
        result = await config_sync_service.save_and_apply(
            key=key, value=body.value, session=db
        )

        # 记录操作日志（异步写入，不阻塞响应）
        ip_address = request.client.host if request.client else None
        operator = _get_operator(current_user)
        await _record_operation_log(
            session=db,
            operator=operator,
            action="update",
            detail={
                "key": key,
                "previous_value": str(result["previous_value"]),
                "current_value": str(result["current_value"]),
            },
            ip_address=ip_address,
        )

        return ApiResponse(
            code=200,
            data=result,
            message="success",
        )

    except ConfigSyncValidationError as e:
        # 类型/约束验证失败
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except ValueError as e:
        # 配置项不支持的 key
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("修改配置 '%s' 失败: %s", key, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改配置失败: {e}",
        )


@router.delete("/{key}/customization")
async def reset_system_config(
    request: Request,
    key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(_require_web_panel_user),
) -> ApiResponse:
    """
    恢复单个系统配置为 config.py 默认值

    从 system_configs 表中删除该配置的自定义记录，
    并将 settings 对象中的值重置为 config.py Field 定义的默认值。
    恢复后该配置不再标记为"已自定义"。
    """
    try:
        result = await config_sync_service.reset_to_default(
            key=key, session=db
        )

        # 记录操作日志
        ip_address = request.client.host if request.client else None
        operator = _get_operator(current_user)
        await _record_operation_log(
            session=db,
            operator=operator,
            action="reset",
            detail={
                "key": key,
                "current_value": str(result["current_value"]),
            },
            ip_address=ip_address,
        )

        return ApiResponse(
            code=200,
            data=result,
            message="success",
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("恢复配置 '%s' 默认值失败: %s", key, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"恢复配置默认值失败: {e}",
        )
