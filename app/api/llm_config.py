# -*- coding: utf-8 -*-
"""
LLM配置API
提供LLM模型配置的查询和测试（全局配置模式）
"""

from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.auth.middleware import get_current_user
from app.config import get_settings
from app.models import User

router = APIRouter()


# ==================== 常量 ====================

# 支持的LLM平台及其模型（全局配置）
SUPPORTED_PLATFORMS = {
    "zhipu": {
        "name": "智谱AI",
        "models": ["glm-4.7-flash", "glm-4-flash-250414", "glm-4-plus"],
        "default_api_base": "https://open.bigmodel.cn/api/paas/v4",
    },
    "siliconflow": {
        "name": "硅基流动",
        "models": ["Qwen/Qwen3-8B", "Qwen/Qwen2.5-72B-Instruct"],
        "default_api_base": "https://api.siliconflow.cn/v1",
    },
    "openrouter": {
        "name": "OpenRouter",
        "models": ["z-ai/glm-4.5-air:free", "nvidia/nemotron-3-nano-30b-a3b:free"],
        "default_api_base": "https://openrouter.ai/api/v1",
    },
    "modelscope": {
        "name": "ModelScope",
        "models": ["MiniMax/MiniMax-M2.5", "ZhipuAI/GLM-5", "moonshotai/Kimi-K2.5", "Qwen/Qwen3.5-27B"],
        "default_api_base": "https://api-inference.modelscope.cn/v1",
    },
}


# ==================== 请求/响应模型 ====================


class LLMConfigResponse(BaseModel):
    """LLM配置响应"""
    llm_platform: Optional[str] = None
    llm_model_name: Optional[str] = None
    llm_api_base: Optional[str] = None
    has_api_key: bool = False


class LLMConfigRequest(BaseModel):
    """LLM配置请求"""
    llm_platform: str
    llm_model_name: str
    llm_api_key: str
    llm_api_base: str


class LLMTestRequest(BaseModel):
    """LLM测试请求"""
    llm_platform: str
    llm_model_name: str
    llm_api_key: str
    llm_api_base: str


class LLMTestResponse(BaseModel):
    """LLM测试响应"""
    success: bool
    message: str


class ApiResponse(BaseModel):
    """统一API响应格式"""
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ==================== 端点 ====================


@router.get("/platforms")
async def get_platforms() -> ApiResponse:
    """获取支持的LLM平台列表"""
    platforms = [
        {"key": k, "name": v["name"], "models": v["models"], "default_api_base": v["default_api_base"]}
        for k, v in SUPPORTED_PLATFORMS.items()
    ]
    return ApiResponse(
        code=200,
        data={"platforms": platforms},
        message="success"
    )


@router.get("/my-config")
async def get_my_llm_config(
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """获取当前LLM配置（全局配置模式）"""
    # 返回全局配置的占位信息
    return ApiResponse(
        code=200,
        data=LLMConfigResponse(
            llm_platform=None,
            llm_model_name=None,
            llm_api_base=None,
            has_api_key=True,  # 全局模式假设已配置
        ).model_dump(),
        message="success"
    )


@router.put("/my-config")
async def update_my_llm_config(
    request: LLMConfigRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """保存LLM配置（全局配置模式，仅验证格式）"""
    # 验证平台
    if request.llm_platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的LLM平台: {request.llm_platform}")

    # 验证模型是否属于该平台
    platform_models = SUPPORTED_PLATFORMS[request.llm_platform]["models"]
    if request.llm_model_name not in platform_models:
        raise HTTPException(
            status_code=400,
            detail=f"平台 {request.llm_platform} 不支持模型: {request.llm_model_name}"
        )

    # 全局模式：仅验证格式，不保存用户配置
    return ApiResponse(
        code=200,
        data={"message": "配置已验证（全局模式）"},
        message="配置格式验证通过"
    )


@router.post("/test")
async def test_llm_config(
    request: LLMTestRequest,
    current_user: User = Depends(get_current_user),
) -> ApiResponse:
    """测试LLM配置是否有效"""
    # 验证平台
    if request.llm_platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"不支持的平台: {request.llm_platform}")

    try:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=settings.llm_api_timeout) as client:
            response = await client.post(
                f"{request.llm_api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.llm_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": request.llm_model_name,
                    "messages": [
                        {"role": "user", "content": "Hi, reply with OK only."}
                    ],
                },
            )

        if response.status_code == 200:
            return ApiResponse(
                code=200,
                data=LLMTestResponse(success=True, message="连接测试成功").model_dump(),
                message="success"
            )
        else:
            return ApiResponse(
                code=200,
                data=LLMTestResponse(
                    success=False,
                    message=f"API返回错误 (HTTP {response.status_code}): {response.text[:200]}"
                ).model_dump(),
                message="测试失败"
            )

    except httpx.ConnectError:
        return ApiResponse(
            code=200,
            data=LLMTestResponse(success=False, message="连接失败：无法连接到API地址").model_dump(),
            message="连接失败"
        )
    except Exception as e:
        return ApiResponse(
            code=200,
            data=LLMTestResponse(success=False, message=f"连接失败: {str(e)}").model_dump(),
            message="测试失败"
        )