# -*- coding: utf-8 -*-
"""
RSSHub API

提供 RSSHub 路由查询、状态查询、启停控制接口
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.config import get_settings
from app.database import db
from app.models import RSSHubRoute, User
from app.services.rsshub import get_route_sync, get_rsshub_manager

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 请求/响应模型 ====================


class RouteItem(BaseModel):
    """路由项"""
    route_path: str
    route_name: Optional[str]
    namespace_id: Optional[str]
    domain: str
    example_path: Optional[str]
    category: Optional[str]
    categories: str  # JSON string
    lang: str
    has_params: bool
    description: Optional[str]
    maintainers: str  # JSON string
    features: str    # JSON string
    source_file: str


class FiltersMeta(BaseModel):
    """可用过滤选项"""
    languages: list[str]
    categories: list[str]


class RSSHubRoutesResponse(BaseModel):
    """路由列表响应"""
    routes: list[RouteItem]
    total: int
    page: int
    page_size: int
    source: str  # "live" / "bundled"
    updated_at: str
    available_filters: FiltersMeta


class RSSHubStatusResponse(BaseModel):
    """RSSHub 状态响应"""
    status: str
    docker_available: bool
    rsshub_url: str
    version: Optional[str]
    routes_count: Optional[int]
    routes_source: Optional[str]  # "live" / "bundled"
    checked_at: Optional[str]
    auto_start_enabled: bool
    message: Optional[str]
    last_error: Optional[str] = None  # Docker 检测详细错误原因


class OperationResponse(BaseModel):
    """操作响应"""
    success: bool
    message: str


class RouteSyncResponse(BaseModel):
    """路由同步响应"""
    success: bool
    message: str
    inserted: int = 0
    updated: int = 0
    deleted: int = 0


# ==================== 辅助函数 ====================


def _to_iso(value) -> Optional[str]:
    """将 datetime 转换为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


async def _build_filters() -> FiltersMeta:
    """从数据库 DISTINCT 聚合可用的 lang 和 category"""
    async with db.get_session() as session:
        # 语言
        result = await session.execute(
            select(RSSHubRoute.lang)
            .where(RSSHubRoute.is_active == True)
            .distinct()
        )
        languages = sorted([r[0] for r in result.all() if r[0]])

        # 分类
        result = await session.execute(
            select(RSSHubRoute.category)
            .where(RSSHubRoute.is_active == True)
            .distinct()
        )
        categories = sorted([r[0] for r in result.all() if r[0]])

    return FiltersMeta(languages=languages, categories=categories)


# ==================== 路由端点 ====================


@router.get("/routes", response_model=RSSHubRoutesResponse)
async def get_routes(
    lang: Optional[str] = Query(None, description="语言过滤：zh-CN / en"),
    category: Optional[str] = Query(None, description="主分类过滤"),
    keyword: Optional[str] = Query(None, description="搜索 route_name + route_path + description"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(50, ge=10, le=200, description="每页条数"),
    current_user: User = Depends(get_current_user),
):
    """
    获取 RSSHub 路由列表

    支持多维过滤和分页
    """
    try:
        # 1. 触发增量同步检查（mtime 检测）
        sync = get_route_sync()
        await sync.sync_if_needed()

        # 2. 构建查询条件
        conditions = [RSSHubRoute.is_active == True]

        if lang:
            conditions.append(RSSHubRoute.lang == lang)

        if category:
            # JSON LIKE 匹配
            conditions.append(RSSHubRoute.categories.contains(f'"{category}"'))

        if keyword:
            from sqlalchemy import or_
            conditions.append(or_(
                RSSHubRoute.route_name.contains(keyword),
                RSSHubRoute.route_path.contains(keyword),
                RSSHubRoute.namespace_id.contains(keyword),
                RSSHubRoute.description.contains(keyword),
            ))

        # 3. 异步查询总数和分页数据
        async with db.get_session() as session:
            # 统计总数
            count_stmt = select(func.count(RSSHubRoute.id)).where(*conditions)
            total_result = await session.execute(count_stmt)
            total = total_result.scalar() or 0

            # 分页查询
            offset = (page - 1) * page_size
            select_stmt = (
                select(RSSHubRoute)
                .where(*conditions)
                .offset(offset)
                .limit(page_size)
            )
            result = await session.execute(select_stmt)
            routes = result.scalars().all()

        # 4. 构建 available_filters
        filters = await _build_filters()

        # 5. 获取数据来源
        try:
            source_path = sync._resolve_source_path()
            source = "bundled" if "static" in source_path else "live"
        except Exception:
            source = "unknown"

        # 6. 获取最后更新时间
        updated_at = _to_iso(datetime.now(timezone.utc))

        return RSSHubRoutesResponse(
            routes=[RouteItem(
                route_path=r.route_path,
                route_name=r.route_name,
                namespace_id=r.namespace_id,
                domain=r.domain,
                example_path=r.example_path,
                category=r.category,
                categories=r.categories or "[]",
                lang=r.lang,
                has_params=r.has_params,
                description=r.description,
                maintainers=r.maintainers or "[]",
                features=r.features or "{}",
                source_file=r.source_file,
            ) for r in routes],
            total=total,
            page=page,
            page_size=page_size,
            source=source,
            updated_at=updated_at or "",
            available_filters=filters,
        )

    except Exception as e:
        logger.error(f"获取路由列表失败: {e}")
        # 返回空列表，不阻塞前端
        return RSSHubRoutesResponse(
            routes=[],
            total=0,
            page=page,
            page_size=page_size,
            source="error",
            updated_at=_to_iso(datetime.now(timezone.utc)) or "",
            available_filters=FiltersMeta(languages=[], categories=[]),
        )


# ==================== 状态端点 ====================


@router.get("/status", response_model=RSSHubStatusResponse)
async def get_status(
    current_user: User = Depends(get_current_user),
):
    """
    获取 RSSHub 运行状态

    立即触发一次健康检查，返回 Manager 的当前状态快照
    """
    manager = get_rsshub_manager()
    settings = get_settings()
    state = manager.state

    # 触发一次健康检查
    if state.status not in [
        "docker_unavailable",
        "disabled",
        "unknown",
    ]:
        await manager.check_health()

    # 构建 message（基于 last_error 精确匹配，而非硬编码）
    message = None
    if state.status == "docker_unavailable":
        if state.last_error == "Docker CLI 未安装":
            message = "Docker CLI 未安装，请先安装 Docker Desktop"
        elif state.last_error == "Docker daemon 未运行":
            message = "Docker 已安装但未启动，请打开 Docker Desktop"
        elif state.last_error == "Docker Compose 不可用":
            message = "Docker Compose 不可用，请安装 Docker Desktop 并确认已启用 Compose 插件"
        elif state.last_error == "Docker 环境检测超时":
            message = "Docker 环境检测超时，请确认 Docker Desktop 正在启动中"
        else:
            message = "Docker 环境不可用，请检查 Docker Desktop"
    elif state.status == "disabled":
        message = "RSSHub 功能已禁用，请在设置中启用"
    elif state.status == "stopped" or state.status == "error":
        message = "请启动 RSSHub 服务"

    return RSSHubStatusResponse(
        status=state.status.value if hasattr(state.status, 'value') else state.status,
        docker_available=state.docker_available,
        rsshub_url=settings.rsshub_url,
        version=state.version,
        routes_count=state.routes_count,
        routes_source=state.routes_source,
        checked_at=_to_iso(state.checked_at),
        auto_start_enabled=settings.rsshub_auto_start,
        message=message,
        last_error=state.last_error,
    )


@router.post("/start", response_model=OperationResponse)
async def start_rsshub(
    current_user: User = Depends(get_current_user),
):
    """
    手动启动 RSSHub 服务
    """
    try:
        manager = get_rsshub_manager()
        success = await manager.start_rsshub()

        if success:
            return OperationResponse(
                success=True,
                message="RSSHub 启动成功"
            )
        else:
            return OperationResponse(
                success=False,
                message=manager.state.last_error if manager.state.last_error else "启动失败"
            )

    except Exception as e:
        logger.error(f"启动 RSSHub 失败: {e}")
        return OperationResponse(
            success=False,
            message=f"启动失败: {str(e)}"
        )


@router.post("/stop", response_model=OperationResponse)
async def stop_rsshub(
    current_user: User = Depends(get_current_user),
):
    """
    手动停止 RSSHub 服务
    """
    try:
        manager = get_rsshub_manager()
        success = await manager.stop_rsshub()

        if success:
            return OperationResponse(
                success=True,
                message="RSSHub 停止成功"
            )
        else:
            return OperationResponse(
                success=False,
                message="停止失败"
            )

    except Exception as e:
        logger.error(f"停止 RSSHub 失败: {e}")
        return OperationResponse(
            success=False,
            message=f"停止失败: {str(e)}"
        )


@router.post("/update", response_model=OperationResponse)
async def update_rsshub(
    current_user: User = Depends(get_current_user),
):
    """
    更新 RSSHub 镜像并重启服务

    流程：docker compose pull → docker compose up -d → 等待健康检查
    """
    try:
        manager = get_rsshub_manager()
        success, message = await manager.update_and_restart()
        return OperationResponse(success=success, message=message)
    except Exception as e:
        logger.error(f"更新 RSSHub 失败: {e}")
        return OperationResponse(success=False, message=f"更新失败: {str(e)}")


@router.post("/sync-routes", response_model=RouteSyncResponse)
async def sync_routes(
    current_user: User = Depends(get_current_user),
):
    """
    手动同步路由：从容器提取 routes.json 并增量同步到数据库
    """
    try:
        manager = get_rsshub_manager()
        if not manager.is_running():
            return RouteSyncResponse(
                success=False,
                message="RSSHub 服务未运行，无法同步路由"
            )

        sync = get_route_sync()
        counts, message = await sync.force_extract_and_sync()
        if not counts:
            return RouteSyncResponse(success=False, message=message)

        return RouteSyncResponse(
            success=True,
            message=message,
            inserted=counts.get("inserted", 0),
            updated=counts.get("updated", 0),
            deleted=counts.get("deleted", 0),
        )
    except Exception as e:
        logger.error(f"同步路由失败: {e}")
        return RouteSyncResponse(success=False, message=f"同步失败: {str(e)}")
