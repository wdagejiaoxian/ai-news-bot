# -*- coding: utf-8 -*-
"""
Obsidian API
提供 Obsidian 配置的测试连接等功能

注意：连接测试逻辑已抽离到 connection_tester.py，
此处仅保留 API 端点实现
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.middleware import get_current_user
from app.models import User
from app.services.notifier.obsidian.connection_tester import (
    test_git_connection,
    test_obsidian_local_connection,
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================


class ObsidianGitTestRequest(BaseModel):
    """测试 Git 模式连接请求"""
    repo_url: str = Field(..., description="Git 仓库地址")
    branch: str = Field(default="main", description="分支")
    access_token: str = Field(..., description="访问令牌")
    credential_type: str = Field(default="deploy_token", description="凭证类型: deploy_token/pat")


class ObsidianLocalTestRequest(BaseModel):
    """测试本地 API 模式连接请求"""
    api_url: str = Field(..., description="Obsidian API 地址（obsidian_local）")
    api_key: str = Field(..., description="API 密钥")
    vault_path: str = Field(..., description="Vault 路径")
    verify_ssl: bool = Field(default=True, description="是否验证 SSL")


class TestConnectionResponse(BaseModel):
    """测试连接响应"""
    success: bool
    message: str
    details: Optional[dict] = None


# ==================== API 端点 ====================


@router.post("/test-connection/git", response_model=TestConnectionResponse)
async def test_obsidian_git_connection(
    request: ObsidianGitTestRequest,
    current_user: User = Depends(get_current_user)
) -> TestConnectionResponse:
    """
    测试 Git 仓库连接

    支持 GitHub、Gitee 等平台
    """
    success, message, details = await test_git_connection(
        repo_url=request.repo_url,
        access_token=request.access_token,
        branch=request.branch,
        credential_type=request.credential_type,
    )
    return TestConnectionResponse(success=success, message=message, details=details)


@router.post("/test-connection/local", response_model=TestConnectionResponse)
async def test_obsidian_local_connection(
    request: ObsidianLocalTestRequest,
    current_user: User = Depends(get_current_user)
) -> TestConnectionResponse:
    """
    测试 Obsidian Local REST API 连接

    前置条件：
    - Obsidian Local REST API 插件已安装并启用
    - 插件设置中已生成 API Key
    """
    success, message, details = await test_obsidian_local_connection(
        api_url=request.api_url,
        api_key=request.api_key,
        vault_path=request.vault_path,
        verify_ssl=request.verify_ssl,
    )
    return TestConnectionResponse(success=success, message=message, details=details)