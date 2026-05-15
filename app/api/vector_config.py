# -*- coding: utf-8 -*-
"""
向量服务配置 API

提供 Embedding 模型和向量数据库的 CRUD 管理接口：
- Embedding 模型：注册、查询、更新、删除、连通性测试
- 向量数据库：配置读取/更新、健康检查、集合统计
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.exc import IntegrityError

from app.auth.middleware import get_current_user
from sqlalchemy import select

from app.database import db
from app.models import EmbeddingModel as EmbeddingModelDB
from app.models import VectorDBConfig as VectorDBConfigDB
from app.models import EmbeddingProvider
from app.services.vector import embedding_manager
from app.utils.crypto import decrypt_api_key, encrypt_api_key

logger = logging.getLogger(__name__)

router = APIRouter(tags=["向量服务"])


# ===== 请求/响应模型 =====

class EmbeddingModelCreate(BaseModel):
    provider: str = Field(..., description="ollama / openai / siliconflow / openrouter")
    model_name: str = Field(..., description="模型名称，如 nomic-embed-text")
    display_name: Optional[str] = Field(None, description="展示名称")
    api_key: SecretStr = Field(default="", description="API 密钥（Ollama 可填空字符串）")
    api_base: Optional[str] = Field(None, description="API 地址")
    dimension: int = Field(default=768, description="向量维度")
    max_batch_size: int = Field(default=20, ge=1, le=100, description="最大批量大小")
    max_concurrency: int = Field(default=3, ge=1, le=20, description="最大并发数")
    priority: int = Field(default=10, ge=1, le=100, description="调度优先级")
    is_enabled: bool = Field(default=True, description="是否启用")


class EmbeddingModelUpdate(BaseModel):
    display_name: Optional[str] = None
    api_key: Optional[SecretStr] = None
    api_base: Optional[str] = None
    max_batch_size: Optional[int] = Field(None, ge=1, le=100)
    max_concurrency: Optional[int] = Field(None, ge=1, le=20)
    priority: Optional[int] = Field(None, ge=1, le=100)
    is_enabled: Optional[bool] = None


class VectorDBConfigUpdate(BaseModel):
    db_type: Optional[str] = Field(None, description="chromadb / milvus / qdrant")
    connection_string: Optional[str] = Field(None, description="连接字符串")
    is_active: Optional[bool] = None


class ApiResponse(BaseModel):
    code: int = 200
    data: Optional[dict] = None
    message: str = "success"


# ===== Embedding 模型 CRUD =====

@router.get("/embedding-models")
async def list_embedding_models(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取所有 Embedding 模型配置"""
    async with db.get_session() as session:
        result = await session.execute(
            select(EmbeddingModelDB).order_by(EmbeddingModelDB.priority.desc())
        )
        models = result.scalars().all()

    return ApiResponse(
        data={
            "models": [
                {
                    "id": m.id,
                    "provider": m.provider,
                    "model_name": m.model_name,
                    "display_name": m.display_name or m.model_name,
                    "api_base": m.api_base,
                    "dimension": m.dimension,
                    "max_batch_size": m.max_batch_size,
                    "max_concurrency": m.max_concurrency,
                    "priority": m.priority,
                    "is_enabled": m.is_enabled,
                    "consecutive_failures": m.consecutive_failures,
                    "created_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in models
            ]
        }
    )


@router.post("/embedding-models")
async def create_embedding_model(
    data: EmbeddingModelCreate,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """创建新的 Embedding 模型配置"""
    # Task 2: provider 白名单校验
    valid_providers = [p.value for p in EmbeddingProvider]
    if data.provider not in valid_providers:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的平台类型，仅支持: {', '.join(valid_providers)}",
        )

    # Task 4: 可用性测试（在数据库操作之前）
    try:
        api_key_decrypted = decrypt_api_key(data.api_key.get_secret_value())
    except Exception:
        api_key_decrypted = data.api_key.get_secret_value()

    from app.services.vector.embedding_providers import create_embedding_provider

    provider = create_embedding_provider(
        provider=data.provider,
        model_name=data.model_name,
        api_key=api_key_decrypted,
        api_base=data.api_base or "",
        dimension=data.dimension,
    )

    # Task 4: 可用性测试（维度验证）- validate_with_embed 返回实际维度
    success, message, actual_dimension = await provider.validate_with_embed(data.dimension)

    if not success:
        logger.warning("Embedding 模型验证失败: %s/%s - %s", data.provider, data.model_name, message)
        raise HTTPException(
            status_code=400,
            detail=f"模型验证失败: {message}",
        )

    # Task 5: 处理维度不匹配 - 使用实际维度保存
    final_dimension = data.dimension
    dimension_warning = None
    if actual_dimension != data.dimension:
        logger.info(
            "Embedding 模型维度调整: %s/%s - 用户配置 %d, 实际 %d, 使用实际维度",
            data.provider, data.model_name, data.dimension, actual_dimension
        )
        final_dimension = actual_dimension
        dimension_warning = f"已自动调整维度: {data.dimension} → {actual_dimension}"

    encrypted_key = encrypt_api_key(data.api_key.get_secret_value())

    try:
        async with db.get_session() as session:
            model = EmbeddingModelDB(
                provider=data.provider,
                model_name=data.model_name,
                display_name=data.display_name or data.model_name,
                api_key=encrypted_key,
                api_base=data.api_base,
                dimension=final_dimension,
                max_batch_size=data.max_batch_size,
                max_concurrency=data.max_concurrency,
                priority=data.priority,
                is_enabled=data.is_enabled,
            )
            session.add(model)
            try:
                await session.commit()
            except IntegrityError:
                raise HTTPException(status_code=400, detail="该模型已配置，请勿重复添加")
            await session.refresh(model)

        logger.info("Embedding 模型已创建: %s/%s (id=%d)", data.provider, data.model_name, model.id)

        # Task 6: 同步 embedding_manager
        if model.is_enabled:
            try:
                await embedding_manager.reload_model(model.id, action="add")
            except Exception as e:
                logger.warning("EmbeddingManager 同步失败: id=%d, error=%s", model.id, e)

        # Task 5: 返回维度调整提示
        response_data = {
            "id": model.id,
            "provider": model.provider,
            "model_name": model.model_name,
            "dimension": model.dimension,
        }
        if dimension_warning:
            response_data["dimension_warning"] = dimension_warning

        response_message = f"Embedding 模型 {model.provider}/{model.model_name} 创建成功 (id={model.id})"
        if dimension_warning:
            response_message += f"，{dimension_warning}"

        return ApiResponse(
            data=response_data,
            message=response_message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("创建 Embedding 模型异常: %s", e)
        raise HTTPException(status_code=500, detail="创建模型失败")


@router.put("/embedding-models/{model_id}")
async def update_embedding_model(
    model_id: int,
    data: EmbeddingModelUpdate,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """更新 Embedding 模型配置"""
    async with db.get_session() as session:
        result = await session.execute(
            select(EmbeddingModelDB).where(EmbeddingModelDB.id == model_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # Task 5: 变更检测 - 判断 api_key 或 api_base 是否变更（需要重新验证）
        need_retest = False
        if data.api_key is not None:
            need_retest = True
        if data.api_base is not None and data.api_base != model.api_base:
            need_retest = True

        # 初始化 dimension_warning（用于后续返回）
        dimension_warning = None

        # Task 5: 如果关键字段变更，需要重新验证可用性
        if need_retest:
            try:
                api_key_decrypted = decrypt_api_key(model.api_key)
            except Exception:
                api_key_decrypted = model.api_key

            # 如果请求中提供了新的 api_key，使用新的
            if data.api_key is not None:
                api_key_decrypted = data.api_key.get_secret_value()

            new_api_base = data.api_base if data.api_base is not None else model.api_base

            from app.services.vector.embedding_providers import create_embedding_provider

            provider = create_embedding_provider(
                provider=model.provider,
                model_name=model.model_name,
                api_key=api_key_decrypted,
                api_base=new_api_base or "",
                dimension=model.dimension,
            )

            # Task 4: validate_with_embed 返回三个值
            success, message, actual_dimension = await provider.validate_with_embed(model.dimension)
            if not success:
                logger.warning("Embedding 模型验证失败: id=%d - %s", model_id, message)
                raise HTTPException(
                    status_code=400,
                    detail=f"模型验证失败: {message}",
                )

            # Task 6: 处理维度不匹配 - 如果维度变更，更新 dimension 字段
            dimension_warning = None
            if actual_dimension != model.dimension:
                logger.info(
                    "Embedding 模型维度调整: id=%d - 原维度 %d, 实际 %d, 使用实际维度",
                    model_id, model.dimension, actual_dimension
                )
                model.dimension = actual_dimension
                dimension_warning = f"已自动调整维度: {model.dimension - (actual_dimension - model.dimension)} → {actual_dimension}"

        # 更新字段
        if data.api_key is not None:
            model.api_key = encrypt_api_key(data.api_key.get_secret_value())
        if data.display_name is not None:
            model.display_name = data.display_name
        if data.api_base is not None:
            model.api_base = data.api_base
        if data.max_batch_size is not None:
            model.max_batch_size = data.max_batch_size
        if data.max_concurrency is not None:
            model.max_concurrency = data.max_concurrency
        if data.priority is not None:
            model.priority = data.priority
        if data.is_enabled is not None:
            model.is_enabled = data.is_enabled

        try:
            await session.commit()
        except IntegrityError:
            raise HTTPException(status_code=400, detail="该模型已配置，请勿重复添加")

    logger.info("Embedding 模型已更新: id=%d", model_id)

    # Task 6: 同步 embedding_manager
    try:
        await embedding_manager.reload_model(model_id, action="update")
    except Exception as e:
        logger.warning("EmbeddingManager 同步失败: id=%d, error=%s", model_id, e)

    # Task 6: 返回维度调整提示
    response_data = {
        "id": model_id,
        "provider": model.provider,
        "model_name": model.model_name,
        "dimension": model.dimension,
    }
    if dimension_warning:
        response_data["dimension_warning"] = dimension_warning

    response_message = f"Embedding 模型 {model.provider}/{model.model_name} 更新成功 (id={model_id})"
    if dimension_warning:
        response_message += f"，{dimension_warning}"

    return ApiResponse(
        data=response_data,
        message=response_message,
    )


@router.delete("/embedding-models/{model_id}")
async def delete_embedding_model(
    model_id: int,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """删除 Embedding 模型配置"""
    async with db.get_session() as session:
        result = await session.execute(
            select(EmbeddingModelDB).where(EmbeddingModelDB.id == model_id)
        )
        model = result.scalar_one_or_none()

        if not model:
            raise HTTPException(status_code=404, detail="模型不存在")

        # 保存删除前的信息用于响应
        deleted_provider = model.provider
        deleted_model_name = model.model_name

        await session.delete(model)
        await session.commit()

    logger.info("Embedding 模型已删除: id=%d", model_id)

    # Task 6: 同步 embedding_manager
    try:
        await embedding_manager.reload_model(model_id, action="delete")
    except Exception as e:
        logger.warning("EmbeddingManager 同步失败: id=%d, error=%s", model_id, e)

    return ApiResponse(
        data={"id": model_id},
        message=f"Embedding 模型 {deleted_provider}/{deleted_model_name} 已删除 (id={model_id})",
    )


@router.post("/embedding-models/{model_id}/test")
async def test_embedding_model(
    model_id: int,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """测试 Embedding 模型连通性"""
    async with db.get_session() as session:
        result = await session.execute(
            select(EmbeddingModelDB).where(EmbeddingModelDB.id == model_id)
        )
        model = result.scalar_one_or_none()

    if not model:
        raise HTTPException(status_code=404, detail="模型不存在")

    try:
        api_key = decrypt_api_key(model.api_key)
    except Exception:
        api_key = model.api_key

    from app.services.vector.embedding_providers import create_embedding_provider

    try:
        provider = create_embedding_provider(
            provider=model.provider,
            model_name=model.model_name,
            api_key=api_key,
            api_base=model.api_base or "",
        )
        healthy = await provider.health_check()
        if healthy:
            return ApiResponse(
                data={"healthy": True},
                message="连通性正常",
            )
        else:
            return ApiResponse(
                data={"healthy": False},
                message="连通性异常",
            )
    except Exception as e:
        logger.warning("Embedding 模型 %d 测试失败: %s", model_id, e)
        return ApiResponse(
            data={"healthy": False},
            message=f"测试失败: {e}",
        )


@router.get("/embedding-models/health")
async def embedding_models_health(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取 Embedding 管理器健康状态（含维度兼容性）"""
    from app.services.vector import embedding_manager
    from app.services.vector.vector_db_manager import vector_db_manager

    active_dim = vector_db_manager.active_dimension
    all_models = [
        {
            "id": m.model_id,
            "name": m.model_name,
            "dimension": m.dimension,
            "available": m.is_available,
        }
        for m in embedding_manager._models_list
    ]

    compatible = [m for m in all_models if active_dim and m["dimension"] == active_dim]
    incompatible = [m for m in all_models if active_dim and m["dimension"] != active_dim]

    return ApiResponse(
        data={
            "available": embedding_manager.is_available(),
            "active_models": embedding_manager.get_active_model_count(),
            "dimension": embedding_manager.get_dimension(),
            "active_dimension": active_dim,
            "models_compatibility": {
                "compatible_count": len(compatible),
                "incompatible_count": len(incompatible),
                "details": [
                    {
                        "id": m["id"],
                        "name": m["name"],
                        "dimension": m["dimension"],
                        "compatible": m["dimension"] == active_dim if active_dim else True,
                    }
                    for m in all_models
                ],
            },
        }
    )


# ===== 向量数据库配置 =====

# 新增：GET /db/configs（多配置列表）
@router.get("/db/configs")
async def list_vector_db_configs(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取所有向量数据库配置"""
    from app.services.vector.config_service import config_service

    configs = await config_service.get_all_configs()
    return ApiResponse(data={"configs": configs})


@router.get("/db/config")
async def get_vector_db_config(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取当前激活的向量数据库配置（兼容旧接口）"""
    from app.services.vector.config_service import config_service

    config = await config_service.get_active_config()
    if not config:
        return ApiResponse(data=None, message="未配置向量数据库")

    return ApiResponse(
        data={
            "id": config.id,
            "db_type": config.db_type,
            "connection_string": config.connection_string,
            "collection_prefix": config.collection_prefix,
            "dimension": config.dimension,
            "is_active": config.is_active,
            "is_default": config.is_default,
        }
    )


# 新增：POST /db/configs
class AddVectorDBConfigRequest(BaseModel):
    db_type: str = Field(default="chromadb", description="向量数据库类型")
    connection_string: str = Field(default="storage/chromadb", description="连接字符串")
    dimension: int = Field(..., gt=0, description="向量维度，必须 > 0")


@router.post("/db/configs")
async def add_vector_db_config(
    data: AddVectorDBConfigRequest,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """创建新的向量数据库配置"""
    from app.services.vector.config_service import config_service

    try:
        config = await config_service.add_config(
            db_type=data.db_type,
            connection_string=data.connection_string,
            dimension=data.dimension,
        )
        return ApiResponse(
            data={
                "id": config.id,
                "db_type": config.db_type,
                "connection_string": config.connection_string,
                "dimension": config.dimension,
                "is_active": config.is_active,
                "is_default": config.is_default,
            },
            message=f"配置已创建 (id={config.id})",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 新增：PUT /db/configs/{config_id}/activate
@router.put("/db/configs/{config_id}/activate")
async def activate_vector_db_config(
    config_id: int,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """激活指定配置"""
    from app.services.vector.config_service import config_service

    try:
        config = await config_service.activate_config(config_id)
        return ApiResponse(
            data={
                "id": config.id,
                "db_type": config.db_type,
                "connection_string": config.connection_string,
                "dimension": config.dimension,
                "is_active": config.is_active,
                "is_default": config.is_default,
            },
            message=f"已切换到配置 id={config_id}，维度 {config.dimension}。维度不匹配的 Embedding 模型已自动禁用。",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# 新增：DELETE /db/configs/{config_id}
@router.delete("/db/configs/{config_id}")
async def delete_vector_db_config(
    config_id: int,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """删除向量数据库配置"""
    from app.services.vector.config_service import config_service

    try:
        result = await config_service.delete_config(config_id)
        return ApiResponse(data=result, message=f"配置 id={config_id} 已删除")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/db/config")
async def update_vector_db_config(
    data: VectorDBConfigUpdate,
    current_user=Depends(get_current_user),
) -> ApiResponse:
    """更新向量数据库配置"""
    async with db.get_session() as session:
        result = await session.execute(
            select(VectorDBConfigDB).where(VectorDBConfigDB.is_active == True)
        )
        config = result.scalar_one_or_none()

        if config:
            if data.db_type is not None:
                config.db_type = data.db_type
            if data.connection_string is not None:
                config.connection_string = data.connection_string
            if data.is_active is not None:
                config.is_active = data.is_active
            message = "向量数据库配置已更新"
        else:
            if data.db_type is None:
                data.db_type = "chromadb"
            if data.connection_string is None:
                data.connection_string = "storage/chromadb"

            config = VectorDBConfigDB(
                db_type=data.db_type,
                connection_string=data.connection_string,
                collection_prefix="ai_news_bot",
                is_active=True,
            )
            session.add(config)
            message = "向量数据库配置已创建"

        await session.commit()

    logger.info("向量数据库配置已更新: %s", data.db_type)

    return ApiResponse(message=message)


@router.get("/db/health")
async def vector_db_health(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取向量数据库健康状态"""
    from app.services.vector import vector_db_manager

    return ApiResponse(
        data={
            "available": vector_db_manager.is_available(),
        }
    )


@router.get("/db/stats")
async def vector_db_stats(current_user=Depends(get_current_user)) -> ApiResponse:
    """获取向量数据库统计信息"""
    from app.services.vector import vector_db_manager

    if not vector_db_manager.is_available():
        return ApiResponse(data={"available": False})

    try:
        adapter = await vector_db_manager.get_adapter()
        articles_name = vector_db_manager.get_collection_name("articles")
        github_name = vector_db_manager.get_collection_name("github_repos")
        articles_count = await adapter.count(articles_name)
        github_count = await adapter.count(github_name)

        return ApiResponse(
            data={
                "available": True,
                "articles_count": articles_count,
                "github_count": github_count,
                "total": articles_count + github_count,
            }
        )
    except Exception as e:
        logger.warning("向量库统计查询失败: %s", e)
        return ApiResponse(
            data={"available": False},
            message=f"统计失败: {e}",
        )