# -*- coding: utf-8 -*-
"""
LLM 模型管理 API
提供 LLM 模型配置的 CRUD 操作
"""

import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.config import get_settings
from app.database import get_db
from app.models import User, LLMModel, LLMProvider
from app.utils.crypto import encrypt_api_key, decrypt_api_key

router = APIRouter()
logger = logging.getLogger(__name__)


# ==================== 常量 ====================

# 支持的 LLM 平台及其模型
SUPPORTED_PLATFORMS = {
    "ZHIPU": {
        "name": "智谱AI",
        "models": ["glm-4-flash", "glm-4-plus", "glm-4.7-flash"],
        "default_api_base": "https://open.bigmodel.cn/api/paas/v4",
    },
    "SILICONFLOW": {
        "name": "硅基流动",
        "models": ["Qwen/Qwen3-8B", "Qwen/Qwen2.5-72B-Instruct", "THUDM/GLM-4-Flash"],
        "default_api_base": "https://api.siliconflow.cn/v1",
    },
    "OPENROUTER": {
        "name": "OpenRouter",
        "models": ["z-ai/glm-4.5-air:free", "nvidia/nemotron-3-nano-30b-a3b:free"],
        "default_api_base": "https://openrouter.ai/api/v1",
    },
    "MODELSCOPE": {
        "name": "ModelScope",
        "models": ["MiniMax/MiniMax-M2.5", "ZhipuAI/GLM-5", "moonshotai/Kimi-K2.5"],
        "default_api_base": "https://api-inference.modelscope.cn/v1",
    },
}


# ==================== 请求/响应模型 ====================


class ModelCreate(BaseModel):
    """创建模型请求"""
    provider: str = Field(..., description="平台: ZHIPU/SILICONFLOW/OPENROUTER/MODELSCOPE")
    model_name: str = Field(..., min_length=1, max_length=100, description="模型名称")
    api_key: str = Field(..., min_length=1, description="API 密钥")
    api_base: Optional[str] = Field(None, description="API 地址")
    can_disable_thinking: bool = Field(default=False, description="是否可关闭思考模式")
    # can_use_tool 不再由前端传递，由后端自动判断
    max_concurrent: int = Field(default=1, ge=1, le=10, description="最大并发数")


class ModelUpdate(BaseModel):
    """更新模型请求"""
    provider: Optional[str] = None
    model_name: Optional[str] = None
    api_key: Optional[str] = None
    api_base: Optional[str] = None
    can_disable_thinking: Optional[bool] = None
    # can_use_tool 由后端测试自动判断，不允许前端手动设置
    max_concurrent: Optional[int] = Field(None, ge=1, le=10)
    is_active: Optional[bool] = None


class ModelResponse(BaseModel):
    """模型响应"""
    id: int
    provider: str
    model_name: str
    api_base: Optional[str]
    can_disable_thinking: bool
    can_use_tool: bool
    max_concurrent: int
    is_active: bool
    consecutive_failures: int
    created_at: str

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 模型端点 ====================


@router.get("/platforms")
async def get_platforms() -> ApiResponse:
    """获取支持的LLM平台列表"""
    platforms = [
        {
            "platform": k,
            "name": v["name"],
            "models": v["models"],
            "api_base": v["default_api_base"]
        }
        for k, v in SUPPORTED_PLATFORMS.items()
    ]
    return ApiResponse(
        code=200,
        data={"platforms": platforms},
        message="success"
    )


@router.get("", include_in_schema=False)
@router.get("/")
async def list_models(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    provider: Optional[str] = Query(None, description="按平台筛选"),
    is_active: Optional[bool] = Query(None, description="按启用状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取模型配置列表
    """
    # 构建查询
    query = select(LLMModel)
    count_query = select(func.count(LLMModel.id))
    
    if provider:
        query = query.where(LLMModel.provider == provider)
        count_query = count_query.where(LLMModel.provider == provider)
    
    if is_active is not None:
        query = query.where(LLMModel.is_active == is_active)
        count_query = count_query.where(LLMModel.is_active == is_active)
    
    # 统计总数
    total = await db.scalar(count_query) or 0
    
    # 分页查询
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size).order_by(LLMModel.created_at.desc())
    
    result = await db.execute(query)
    models = result.scalars().all()
    
    items = [
        ModelResponse(
            id=m.id,
            provider=m.provider,
            model_name=m.model_name,
            api_base=m.api_base,
            can_disable_thinking=m.can_disable_thinking,
            can_use_tool=m.can_use_tool,
            max_concurrent=m.max_concurrent,
            is_active=m.is_active,
            consecutive_failures=m.consecutive_failures,
            created_at=m.created_at.isoformat() if m.created_at else "",
        ).model_dump()
        for m in models
    ]
    
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


@router.get("/{model_id}")
async def get_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    获取单个模型配置
    """
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    return ApiResponse(
        code=200,
        data=ModelResponse(
            id=model.id,
            provider=model.provider,
            model_name=model.model_name,
            api_base=model.api_base,
            can_disable_thinking=model.can_disable_thinking,
            can_use_tool=model.can_use_tool,
            max_concurrent=model.max_concurrent,
            is_active=model.is_active,
            consecutive_failures=model.consecutive_failures,
            created_at=model.created_at.isoformat() if model.created_at else "",
        ).model_dump(),
        message="success"
    )


@router.post("", include_in_schema=False)
@router.post("/")
async def create_model(
    request: ModelCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    创建模型配置
    
    - 校验平台类型
    - 校验模型重复性 (provider + model_name)
    - 加密存储 API 密钥
    """
    # 验证平台类型
    valid_providers = [p.value for p in LLMProvider]
    if request.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台类型，仅支持: {', '.join(valid_providers)}"
        )
    
    # 检查重复性
    result = await db.execute(
        select(LLMModel).where(
            LLMModel.provider == request.provider,
            LLMModel.model_name == request.model_name
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=400,
            detail="该模型已配置，请勿重复添加"
        )
    
    # 保存前先测试模型可用性
    test_result = await _test_model_connection(
        provider=request.provider,
        model_name=request.model_name,
        api_key=request.api_key,
        api_base=request.api_base
    )
    
    if not test_result["success"]:
        raise HTTPException(
            status_code=400,
            detail=f"模型测试失败: {test_result['message']}"
        )
    
    # 创建模型配置（使用测试结果中的 can_use_tool）
    model = LLMModel(
        provider=request.provider,
        model_name=request.model_name,
        api_key=encrypt_api_key(request.api_key),  # AES加密存储
        api_base=request.api_base,
        can_disable_thinking=request.can_disable_thinking,
        can_use_tool=test_result["can_use_tool"],  # 自动判断
        max_concurrent=request.max_concurrent,
        is_active=True,
        consecutive_failures=0,
    )
    
    db.add(model)
    await db.flush()
    await db.commit()  # 必须commit后才能被其他会话查询到
    await db.refresh(model)

    logger.info(f"创建模型配置成功: {model.provider}/{model.model_name} (ID: {model.id})")

    # 注册到 llm_manager（只有 is_active=True 时才注册）
    if model.is_active:
        from app.services.processor.llm_manager import llm_manager
        from app.utils.crypto import decrypt_api_key

        try:
            api_key = decrypt_api_key(model.api_key)
        except Exception:
            api_key = model.api_key

        llm_manager.register_model_from_db(
            provider=model.provider,
            model_name=model.model_name,
            api_key=api_key,
            api_base=model.api_base or "",
            can_disable_thinking=model.can_disable_thinking,
            can_use_tool=model.can_use_tool,
            max_concurrent=model.max_concurrent
        )

    # 同步定时任务状态（检查LLM和Webhook配置，决定是否启用任务）
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data={
            "id": model.id,
            "provider": model.provider,
            "model_name": model.model_name,
            "can_use_tool": model.can_use_tool,
            "is_active": model.is_active,
            "created_at": model.created_at.isoformat() if model.created_at else "",
            "test_result": {
                "success": test_result["success"],
                "can_use_tool": test_result["can_use_tool"],
                "message": test_result["message"]
            }
        },
        message="模型注册成功"
    )


@router.put("/{model_id}")
async def update_model(
    model_id: int,
    request: ModelUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    更新模型配置
    """
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 判断关键字段是否变更（需要重新测试）
    need_retest = False
    new_provider = model.provider
    new_model_name = model.model_name
    new_api_key = model.api_key  # 加密存储的
    new_api_base = model.api_base

    if request.provider is not None and request.provider != model.provider:
        need_retest = True
        new_provider = request.provider
    if request.model_name is not None and request.model_name != model.model_name:
        need_retest = True
        new_model_name = request.model_name
    if request.api_key is not None:
        need_retest = True
        new_api_key = encrypt_api_key(request.api_key)
    if request.api_base is not None:
        need_retest = True
        new_api_base = request.api_base

    # 如果关键字段变更，需要重新测试
    if need_retest:
        # 使用新值进行测试（new_api_key 已经是加密后的值）
        test_result = await _test_model_connection(
            provider=new_provider,
            model_name=new_model_name,
            api_key=new_api_key,
            api_base=new_api_base
        )

        if not test_result["success"]:
            raise HTTPException(
                status_code=400,
                detail=f"模型测试失败: {test_result['message']}"
            )

        # 测试通过，更新 can_use_tool
        model.can_use_tool = test_result["can_use_tool"]

    # 更新字段
    if request.api_key is not None:
        model.api_key = encrypt_api_key(request.api_key)
    if request.api_base is not None:
        model.api_base = request.api_base
    if request.can_disable_thinking is not None:
        model.can_disable_thinking = request.can_disable_thinking
    # can_use_tool 不再由前端设置，由测试自动判断
    if request.max_concurrent is not None:
        model.max_concurrent = request.max_concurrent
    if request.is_active is not None:
        model.is_active = request.is_active
        # 如果启用，重置失败计数
        if request.is_active and model.consecutive_failures > 0:
            model.consecutive_failures = 0

    await db.flush()
    await db.commit()  # 必须commit后才能被其他会话查询到
    await db.refresh(model)

    logger.info(f"更新模型配置成功: {model.provider}/{model.model_name} (ID: {model.id})")

    # 同步 llm_manager 状态
    from app.services.processor.llm_manager import llm_manager
    from app.utils.crypto import decrypt_api_key

    try:
        api_key = decrypt_api_key(model.api_key)
    except Exception:
        api_key = model.api_key

    if model.is_active:
        # 如果 is_active=True，检查是否已在管理器中，不在则添加
        model_in_manager = any(
            m.provider.value == model.provider and m.model_name == model.model_name
            for m in llm_manager.models
        )
        if not model_in_manager:
            llm_manager.register_model_from_db(
                provider=model.provider,
                model_name=model.model_name,
                api_key=api_key,
                api_base=model.api_base or "",
                can_disable_thinking=model.can_disable_thinking,
                can_use_tool=model.can_use_tool,
                max_concurrent=model.max_concurrent
            )
    else:
        # 如果 is_active=False，从管理器中移除
        llm_manager.unregister_model(model.provider, model.model_name)

    # 同步定时任务状态（检查LLM和Webhook配置，决定是否启用任务）
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data={
            "id": model.id,
            "provider": model.provider,
            "model_name": model.model_name,
            "can_use_tool": model.can_use_tool,
            "is_active": model.is_active,
            "consecutive_failures": model.consecutive_failures,
        },
        message="模型配置已更新"
    )


@router.delete("/{model_id}")
async def delete_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    删除模型配置
    """
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    # 先从 llm_manager 移除
    from app.services.processor.llm_manager import llm_manager
    llm_manager.unregister_model(model.provider, model.model_name)

    # 再删除数据库记录
    await db.delete(model)
    await db.commit()  # 必须commit后才能被其他会话查询到

    logger.info(f"删除模型配置成功: ID {model_id}")

    # 同步定时任务状态（检查LLM和Webhook配置，决定是否启用任务）
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()

    return ApiResponse(
        code=200,
        data=None,
        message="模型已删除"
    )


# ==================== 测试功能 ====================


async def _test_model_connection(
    provider: str,
    model_name: str,
    api_key: str,
    api_base: Optional[str] = None
) -> dict:
    """
    测试模型连接并判断是否支持工具调用
    
    Returns:
        {
            "success": bool,
            "can_use_tool": bool,
            "message": str,
            "model_used": str
        }
    """
    # 获取 API Base
    if not api_base:
        api_base = SUPPORTED_PLATFORMS.get(provider, {}).get("default_api_base", "")
    
    if not api_base:
        return {
            "success": False,
            "can_use_tool": False,
            "message": f"不支持的平台: {provider}",
            "model_used": model_name
        }
    
    # 解密 API Key
    try:
        api_key_decrypted = decrypt_api_key(api_key)
    except Exception:
        api_key_decrypted = api_key
    
    headers = {
        "Authorization": f"Bearer {api_key_decrypted}",
        "Content-Type": "application/json"
    }
    
    # 测试请求 - 同时判断可用性和工具调用能力
    test_payload = {
        "model": model_name,
        "messages": [
            {"role": "user", "content": "你是否有工具调用能力，请回答有或者没有，不输出其他任意内容。"}
        ]
    }
    
    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.llm_api_timeout) as client:
            response = await client.post(
                f"{api_base}/chat/completions",
                json=test_payload,
                headers=headers
            )
            
            if response.status_code != 200:
                return {
                    "success": False,
                    "can_use_tool": False,
                    "message": f"API请求失败: {response.status_code} - {response.text[:100]}",
                    "model_used": model_name
                }
            
            # 解析响应内容
            data = response.json()
            content = ""
            choices_valid = False
            try:
                choices = data.get("choices", [])
                if choices and len(choices) > 0:
                    choice = choices[0]
                    # 检查 choices 格式是否有效（message 存在，content 不为 None）
                    if choice.get("message") and choice["message"].get("content") is not None:
                        content = choice["message"]["content"].strip().lower()
                        choices_valid = True
            except Exception:
                pass
            
            # 如果 choices 为空或格式无效，视为模型不可用
            if not choices_valid:
                return {
                    "success": False,
                    "can_use_tool": False,
                    "message": f"模型不可用：API 返回空响应或响应格式异常",
                    "model_used": model_name
                }
            
            # 判断是否支持工具调用：响应中包含"有"字样即认为支持
            can_use_tool = "有" in content
            
            return {
                "success": True,
                "can_use_tool": can_use_tool,
                "message": "连接测试成功" + ("，支持工具调用" if can_use_tool else "，不支持工具调用"),
                "model_used": model_name
            }
            
    except httpx.TimeoutException:
        return {
            "success": False,
            "can_use_tool": False,
            "message": "请求超时",
            "model_used": model_name
        }
    except Exception as e:
        return {
            "success": False,
            "can_use_tool": False,
            "message": f"测试失败: {str(e)}",
            "model_used": model_name
        }


@router.post("/{model_id}/test")
async def test_model(
    model_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> ApiResponse:
    """
    测试模型配置是否有效，并判断是否支持工具调用
    """
    # 获取模型配置
    result = await db.execute(
        select(LLMModel).where(LLMModel.id == model_id)
    )
    model = result.scalar_one_or_none()
    
    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")
    
    # 测试模型
    test_result = await _test_model_connection(
        provider=model.provider,
        model_name=model.model_name,
        api_key=model.api_key,
        api_base=model.api_base
    )
    
    return ApiResponse(
        code=200 if test_result["success"] else 400,
        data=test_result,
        message=test_result["message"]
    )
