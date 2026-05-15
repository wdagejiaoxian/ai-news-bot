# -*- coding: utf-8 -*-
"""
模板 API

提供模板配置的 CRUD 操作
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import User, WebhookConfig, WebhookTemplate, TemplateType
from app.services.template_renderer import (
    template_renderer,
    get_default_template,
    PRESET_TEMPLATES
)

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== 请求/响应模型 ====================


class TemplateCreate(BaseModel):
    """创建模板请求"""
    webhook_id: int = Field(..., description="关联的 Webhook ID")
    template_type: str = Field(..., description="模板类型: daily/weekly/immediate")
    template_name: str = Field(..., min_length=1, max_length=100, description="模板名称")
    template_content: str = Field(default="", description="模板内容（Markdown + 变量占位符）")
    is_active: bool = Field(default=True, description="是否启用")


class TemplateUpdate(BaseModel):
    """更新模板请求"""
    template_name: Optional[str] = Field(None, min_length=1, max_length=100)
    template_content: Optional[str] = Field(None, description="模板内容")
    is_active: Optional[bool] = None


class TemplateResponse(BaseModel):
    """模板响应"""
    id: int
    webhook_config_id: int
    template_type: str
    template_name: str
    template_content: str
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        from_attributes = True


class TemplateListResponse(BaseModel):
    """模板列表响应"""
    items: List[TemplateResponse]
    total: int


class TemplateCopyRequest(BaseModel):
    """复制模板请求"""
    template_id: int = Field(..., description="源模板 ID")
    target_webhook_id: int = Field(..., description="目标 Webhook ID")


class TemplateValidateRequest(BaseModel):
    """验证模板请求"""
    template_content: str = Field(..., description="模板内容")


class TemplateValidateResponse(BaseModel):
    """验证模板响应"""
    valid: bool
    errors: List[str]
    warnings: List[str]


class TemplatePreviewRequest(BaseModel):
    """预览模板请求"""
    template_content: str = Field(..., description="模板内容")
    # 预览用的模拟数据
    date: Optional[str] = Field(default="2026-04-23", description="日期")
    week_start: Optional[str] = Field(default="2026-04-20", description="周开始日期")
    week_end: Optional[str] = Field(default="2026-04-26", description="周结束日期")
    github_repos: Optional[List[dict]] = Field(default=None, description="GitHub 项目列表")
    articles: Optional[List[dict]] = Field(default=None, description="文章列表")


class PresetTemplateInfo(BaseModel):
    """预设模板信息"""
    key: str
    name: str
    type: str
    description: str
    content: str


class PresetTemplateListResponse(BaseModel):
    """预设模板列表响应"""
    items: List[PresetTemplateInfo]


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 辅助函数 ====================


def _build_template_response(template: WebhookTemplate) -> dict:
    """构建模板响应字典"""
    return {
        "id": template.id,
        "webhook_config_id": template.webhook_config_id,
        "template_type": template.template_type,
        "template_name": template.template_name,
        "template_content": template.template_content,
        "is_active": template.is_active,
        "created_at": template.created_at.isoformat() if template.created_at else "",
        "updated_at": template.updated_at.isoformat() if template.updated_at else "",
    }


# ==================== 模板端点 ====================


@router.get("/templates/presets")
async def list_preset_templates(
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取预设模板列表
    """
    items = []
    for key, preset in PRESET_TEMPLATES.items():
        items.append({
            "key": key,
            "name": preset["name"],
            "type": preset["type"],
            "description": preset["description"],
            "content": preset["content"]
        })

    return ApiResponse(
        code=200,
        data={"items": items, "total": len(items)},
        message="success"
    )


@router.get("/webhooks/{webhook_id}/templates")
async def list_webhook_templates(
    webhook_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    获取 Webhook 的所有模板
    """
    # 检查 webhook 是否存在
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == webhook_id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook 配置不存在")

    # 查询模板
    result = await db.execute(
        select(WebhookTemplate).where(WebhookTemplate.webhook_config_id == webhook_id)
    )
    templates = result.scalars().all()

    items = [_build_template_response(t) for t in templates]

    return ApiResponse(
        code=200,
        data={"items": items, "total": len(items)},
        message="success"
    )


@router.post("/templates")
async def create_template(
    request: TemplateCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    创建模板
    """
    # 检查 webhook 是否存在
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == request.webhook_id)
    )
    webhook = result.scalar_one_or_none()
    if not webhook:
        raise HTTPException(status_code=404, detail="Webhook 配置不存在")

    # 检查是否已存在同类型模板
    result = await db.execute(
        select(WebhookTemplate).where(
            and_(
                WebhookTemplate.webhook_config_id == request.webhook_id,
                WebhookTemplate.template_type == request.template_type
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"该 Webhook 已存在 {request.template_type} 类型的模板，请使用更新接口"
        )

    # 验证模板内容
    if request.template_content:
        validation = template_renderer.validate_template(request.template_content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"模板语法错误: {', '.join(validation['errors'])}"
            )

    # 创建模板
    template = WebhookTemplate(
        webhook_config_id=request.webhook_id,
        template_type=request.template_type,
        template_name=request.template_name,
        template_content=request.template_content,
        is_active=request.is_active
    )
    db.add(template)
    await db.commit()
    await db.refresh(template)

    logger.info(f"创建模板成功: {template.template_name} (ID: {template.id})")

    return ApiResponse(
        code=200,
        data=_build_template_response(template),
        message="模板创建成功"
    )


@router.put("/templates/{template_id}")
async def update_template(
    template_id: int,
    request: TemplateUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    更新模板
    """
    result = await db.execute(
        select(WebhookTemplate).where(WebhookTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 更新字段
    if request.template_name is not None:
        template.template_name = request.template_name
    if request.template_content is not None:
        # 验证模板内容
        validation = template_renderer.validate_template(request.template_content)
        if not validation["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"模板语法错误: {', '.join(validation['errors'])}"
            )
        template.template_content = request.template_content
    if request.is_active is not None:
        template.is_active = request.is_active

    await db.commit()
    await db.refresh(template)

    logger.info(f"更新模板成功: {template.template_name} (ID: {template.id})")

    return ApiResponse(
        code=200,
        data=_build_template_response(template),
        message="模板已更新"
    )


@router.delete("/templates/{template_id}")
async def delete_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    删除模板
    """
    result = await db.execute(
        select(WebhookTemplate).where(WebhookTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    template_name = template.template_name
    await db.delete(template)
    await db.commit()

    logger.info(f"删除模板成功: {template_name} (ID: {template_id})")

    return ApiResponse(
        code=200,
        data=None,
        message="模板已删除"
    )


@router.post("/templates/validate")
async def validate_template_content(
    request: TemplateValidateRequest,
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    验证模板语法
    """
    result = template_renderer.validate_template(request.template_content)

    return ApiResponse(
        code=200 if result["valid"] else 400,
        data=result,
        message="模板验证通过" if result["valid"] else "模板验证失败"
    )


@router.post("/templates/preview")
async def preview_template(
    request: TemplatePreviewRequest,
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    预览模板渲染结果
    """
    # 构建模拟上下文
    context = {
        "date": request.date or "2026-04-23",
        "week_start": request.week_start or "2026-04-20",
        "week_end": request.week_end or "2026-04-26",
        "generated_at": "2026-04-23 12:00:00",
        "github_repos": request.github_repos or [
            {
                "full_name": "openai/gpt-5",
                "url": "https://github.com/openai/gpt-5",
                "stars": 25000,
                "stars_today": 1500,
                "language": "Python",
                "description": "Next generation AI model"
            },
            {
                "full_name": "anthropic/claude-4",
                "url": "https://github.com/anthropic/claude-4",
                "stars": 18000,
                "stars_today": 900,
                "language": "Python",
                "description": "Advanced AI assistant"
            }
        ],
        "articles": request.articles or [
            {
                "title": "GPT-5 发布：通往通用人工智能的新里程碑",
                "url": "https://example.com/gpt5",
                "score": 95,
                "summary": "OpenAI 发布 GPT-5，带来多项重大突破...",
                "tags": "AI,大模型,OpenAI",
                "source_name": "AI News"
            },
            {
                "title": "Claude 4 发布：更安全、更智能",
                "url": "https://example.com/claude4",
                "score": 92,
                "summary": "Anthropic 发布 Claude 4，强调安全性和可控性...",
                "tags": "AI,大模型,安全",
                "source_name": "AI News"
            }
        ]
    }

    # 渲染模板
    try:
        rendered = template_renderer.render(request.template_content, context)
        return ApiResponse(
            code=200,
            data={"rendered": rendered},
            message="预览生成成功"
        )
    except Exception as e:
        logger.error(f"模板预览失败: {e}")
        return ApiResponse(
            code=400,
            data={"rendered": "", "error": str(e)},
            message="模板渲染失败"
        )


@router.post("/templates/copy")
async def copy_template(
    request: TemplateCopyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    复制模板到其他 Webhook
    """
    # 查找源模板
    result = await db.execute(
        select(WebhookTemplate).where(WebhookTemplate.id == request.template_id)
    )
    source_template = result.scalar_one_or_none()
    if not source_template:
        raise HTTPException(status_code=404, detail="源模板不存在")

    # 检查目标 webhook 是否存在
    result = await db.execute(
        select(WebhookConfig).where(WebhookConfig.id == request.target_webhook_id)
    )
    target_webhook = result.scalar_one_or_none()
    if not target_webhook:
        raise HTTPException(status_code=404, detail="目标 Webhook 不存在")

    # 检查目标是否已存在同类型模板
    result = await db.execute(
        select(WebhookTemplate).where(
            and_(
                WebhookTemplate.webhook_config_id == request.target_webhook_id,
                WebhookTemplate.template_type == source_template.template_type
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"目标 Webhook 已存在 {source_template.template_type} 类型的模板"
        )

    # 创建新模板
    new_template = WebhookTemplate(
        webhook_config_id=request.target_webhook_id,
        template_type=source_template.template_type,
        template_name=f"{source_template.template_name} (副本)",
        template_content=source_template.template_content,
        is_active=source_template.is_active
    )
    db.add(new_template)
    await db.commit()
    await db.refresh(new_template)

    logger.info(f"复制模板成功: {source_template.template_name} -> {new_template.template_name} (ID: {new_template.id})")

    return ApiResponse(
        code=200,
        data=_build_template_response(new_template),
        message="模板复制成功"
    )


@router.get("/templates/{template_id}")
async def get_template(
    template_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
) -> ApiResponse:
    """
    获取单个模板详情
    """
    result = await db.execute(
        select(WebhookTemplate).where(WebhookTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    return ApiResponse(
        code=200,
        data=_build_template_response(template),
        message="success"
    )