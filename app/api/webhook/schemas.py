# -*- coding: utf-8 -*-
"""
Webhook 请求/响应模型
拆分自 app/api/webhook.py
"""

from typing import Optional

from pydantic import BaseModel, Field


# ==================== 统一响应 ====================


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 请求模型 ====================


class WebhookCreate(BaseModel):
    """创建 Webhook 请求"""
    name: str = Field(..., min_length=1, max_length=100, description="配置名称")
    platform: str = Field(..., description="平台类型: wecom/obsidian_git/obsidian_local")
    webhook_key: Optional[str] = Field(None, description="Webhook 密钥（wecom 必填，Obsidian 可不填）")
    # === Obsidian Git 配置 ===
    git_repo_url: Optional[str] = Field(None, description="Git 仓库地址（obsidian_git）")
    git_branch: Optional[str] = Field(default="main", description="Git 分支（obsidian_git）")
    git_access_token: Optional[str] = Field(None, description="Git 访问令牌（obsidian_git）")
    git_credential_type: Optional[str] = Field(default="deploy_token", description="凭证类型（obsidian_git）")
    git_author_name: Optional[str] = Field(default="AI News Bot", description="提交者名称（obsidian_git）")
    git_author_email: Optional[str] = Field(None, description="提交者邮箱（obsidian_git）")
    git_daily_folder: Optional[str] = Field(default="AI-News/Daily", description="日报文件夹（obsidian_git）")
    git_weekly_folder: Optional[str] = Field(default="AI-News/Weekly", description="周报文件夹（obsidian_git）")
    git_immediate_folder: Optional[str] = Field(default="AI-News/Immediate", description="即时推送文件夹（obsidian_git）")
    # === Obsidian Local 配置 ===
    obsidian_api_url: Optional[str] = Field(None, description="Obsidian API 地址（obsidian_local）")
    obsidian_api_key: Optional[str] = Field(None, description="Obsidian API 密钥（obsidian_local）")
    obsidian_vault_path: Optional[str] = Field(None, description="Vault 路径（obsidian_local）")
    obsidian_daily_folder: Optional[str] = Field(default="AI-News/Daily", description="日报文件夹（obsidian_local）")
    obsidian_weekly_folder: Optional[str] = Field(default="AI-News/Weekly", description="周报文件夹（obsidian_local）")
    obsidian_immediate_folder: Optional[str] = Field(default="AI-News/Immediate", description="即时推送文件夹（obsidian_local）")
    obsidian_verify_ssl: Optional[bool] = Field(default=True, description="是否验证 SSL（obsidian_local）")
    # === 推送类型开关 ===
    push_immediate_enabled: bool = Field(default=True, description="是否启用高分推送")
    push_daily_enabled: bool = Field(default=True, description="是否启用日报推送")
    push_weekly_enabled: bool = Field(default=True, description="是否启用周报推送")
    # === 推送类型独立阈值 ===
    push_immediate_threshold: float = Field(default=85.0, ge=0, le=100, description="高分推送阈值")
    push_daily_threshold: float = Field(default=75.0, ge=0, le=100, description="日报推送阈值")
    push_weekly_threshold: float = Field(default=80.0, ge=0, le=100, description="周报推送阈值")
    # === 推送数量限制 ===
    push_daily_limit: int = Field(default=500, ge=1, le=2000, description="日报推送数量限制")
    push_weekly_limit: int = Field(default=300, ge=1, le=2000, description="周报推送数量限制")


class WebhookUpdate(BaseModel):
    """更新 Webhook 请求"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    webhook_key: Optional[str] = Field(None, min_length=1, description="Webhook 密钥，留空则不修改")
    # === 新增字段：推送类型开关 ===
    push_immediate_enabled: Optional[bool] = Field(None, description="是否启用高分推送")
    push_daily_enabled: Optional[bool] = Field(None, description="是否启用日报推送")
    push_weekly_enabled: Optional[bool] = Field(None, description="是否启用周报推送")
    # === 新增字段：推送类型独立阈值 ===
    push_immediate_threshold: Optional[float] = Field(None, ge=0, le=100, description="高分推送阈值")
    push_daily_threshold: Optional[float] = Field(None, ge=0, le=100, description="日报推送阈值")
    push_weekly_threshold: Optional[float] = Field(None, ge=0, le=100, description="周报推送阈值")
    # === 新增字段：推送数量限制 ===
    push_daily_limit: Optional[int] = Field(None, ge=1, le=2000, description="日报推送数量限制")
    push_weekly_limit: Optional[int] = Field(None, ge=1, le=2000, description="周报推送数量限制")
    is_active: Optional[bool] = None
    # === Obsidian Git 配置 ===
    git_repo_url: Optional[str] = Field(None, description="Git 仓库地址（obsidian_git）")
    git_branch: Optional[str] = Field(None, description="Git 分支（obsidian_git）")
    git_access_token: Optional[str] = Field(None, description="Git 访问令牌（obsidian_git）")
    git_credential_type: Optional[str] = Field(None, description="凭证类型（obsidian_git）")
    git_author_name: Optional[str] = Field(None, description="提交者名称（obsidian_git）")
    git_author_email: Optional[str] = Field(None, description="提交者邮箱（obsidian_git）")
    git_daily_folder: Optional[str] = Field(None, description="日报文件夹（obsidian_git）")
    git_weekly_folder: Optional[str] = Field(None, description="周报文件夹（obsidian_git）")
    git_immediate_folder: Optional[str] = Field(None, description="即时推送文件夹（obsidian_git）")
    # === Obsidian Local 配置 ===
    obsidian_api_url: Optional[str] = Field(None, description="Obsidian API 地址（obsidian_local）")
    obsidian_api_key: Optional[str] = Field(None, description="Obsidian API 密钥（obsidian_local）")
    obsidian_vault_path: Optional[str] = Field(None, description="Vault 路径（obsidian_local）")
    obsidian_daily_folder: Optional[str] = Field(None, description="日报文件夹（obsidian_local）")
    obsidian_weekly_folder: Optional[str] = Field(None, description="周报文件夹（obsidian_local）")
    obsidian_immediate_folder: Optional[str] = Field(None, description="即时推送文件夹（obsidian_local）")
    obsidian_verify_ssl: Optional[bool] = Field(None, description="是否验证 SSL（obsidian_local）")


class WebhookTestRequest(BaseModel):
    """测试 Webhook 请求"""
    platform: str = Field(..., description="平台类型: wecom/telegram/discord")
    webhook_key: str = Field(..., min_length=1, description="Webhook 密钥")


# ==================== 响应模型 ====================


class WebhookResponse(BaseModel):
    """Webhook 响应"""
    id: int
    name: str
    platform: str
    # === 新增字段：推送类型开关 ===
    push_immediate_enabled: bool
    push_daily_enabled: bool
    push_weekly_enabled: bool
    # === 新增字段：推送类型独立阈值 ===
    push_immediate_threshold: float
    push_daily_threshold: float
    push_weekly_threshold: float
    # === 新增字段：推送数量限制 ===
    push_daily_limit: int
    push_weekly_limit: int
    # === 新增字段：失败处理 ===
    push_fail_count: int
    push_fail_threshold: int
    is_disabled: bool
    # === 原有兼容字段 ===
    push_threshold: float  # 已废弃，但保留兼容
    push_enabled: bool  # 已废弃，但保留兼容
    is_active: bool
    created_at: str
    # === Obsidian Git 配置 ===
    git_repo_url: Optional[str] = None
    git_branch: Optional[str] = None
    git_daily_folder: Optional[str] = None
    git_weekly_folder: Optional[str] = None
    git_immediate_folder: Optional[str] = None
    # === Obsidian Local 配置 ===
    obsidian_api_url: Optional[str] = None
    obsidian_vault_path: Optional[str] = None
    obsidian_daily_folder: Optional[str] = None
    obsidian_weekly_folder: Optional[str] = None
    obsidian_immediate_folder: Optional[str] = None

    class Config:
        from_attributes = True


class WebhookListResponse(BaseModel):
    """Webhook 列表响应"""
    items: list[WebhookResponse]
    total: int
    page: int
    page_size: int


class WebhookTestResponse(BaseModel):
    """测试 Webhook 响应"""
    success: bool
    message: str