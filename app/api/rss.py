# -*- coding: utf-8 -*-
"""
RSS源API
提供RSS源的增删改查接口
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, validator
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.middleware import get_current_user
from app.database import get_db
from app.models import RSSSource, User

router = APIRouter()

# fetch_interval 常量
FETCH_INTERVAL_MIN = 5   # 最小采集间隔（分钟）
FETCH_INTERVAL_MAX = 1440 # 最大采集间隔（分钟），即24小时
FETCH_INTERVAL_DEFAULT = 60  # 默认采集间隔（分钟）


# ==================== 请求/响应模型 ====================


class RSSSourceResponse(BaseModel):
    """RSS源响应"""
    id: int
    name: str
    url: str
    category: Optional[str] = None
    source_type: str = "standard"  # standard/rsshub
    is_active: bool = True
    rsshub_unavailable: bool = False  # RSSHub 不可用时标记
    fetch_error_count: int = 0
    fetch_interval: int
    last_fetched_at: Optional[str] = None
    article_count: int
    last_modified: Optional[str] = None  # 增量检测：Last-Modified
    etag: Optional[str] = None          # 增量检测：ETag
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True


class RSSSourceListResponse(BaseModel):
    """RSS源列表响应"""
    items: List[RSSSourceResponse]
    total: int


class RSSSourceCreateRequest(BaseModel):
    """RSS源创建请求"""
    name: str
    url: str
    category: Optional[str] = None
    source_type: str = Field(
        default="standard",
        description="RSS源类型: standard(标准)/rsshub(RSSHub生成)/builtin(内置)"
    )
    is_active: bool = True
    fetch_interval: int = Field(
        default=FETCH_INTERVAL_DEFAULT,
        ge=FETCH_INTERVAL_MIN,
        le=FETCH_INTERVAL_MAX,
        description=f"采集间隔（分钟），范围 {FETCH_INTERVAL_MIN}-{FETCH_INTERVAL_MAX}"
    )

    @validator('fetch_interval')
    def validate_fetch_interval(cls, v):
        if v < FETCH_INTERVAL_MIN:
            raise ValueError(f"采集间隔不能小于 {FETCH_INTERVAL_MIN} 分钟")
        if v > FETCH_INTERVAL_MAX:
            raise ValueError(f"采集间隔不能大于 {FETCH_INTERVAL_MAX} 分钟")
        return v

    @validator('source_type')
    def validate_source_type(cls, v):
        valid_types = ["standard", "rsshub", "auto"]
        if v not in valid_types:
            raise ValueError(f"source_type 必须是 {valid_types} 之一")
        return v


class RSSSourceUpdateRequest(BaseModel):
    """RSS源更新请求"""
    name: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    source_type: Optional[str] = None
    is_active: Optional[bool] = None
    fetch_interval: Optional[int] = Field(
        default=None,
        ge=FETCH_INTERVAL_MIN,
        le=FETCH_INTERVAL_MAX,
        description=f"采集间隔（分钟），范围 {FETCH_INTERVAL_MIN}-{FETCH_INTERVAL_MAX}"
    )

    @validator('fetch_interval')
    def validate_fetch_interval(cls, v):
        if v is not None:
            if v < FETCH_INTERVAL_MIN:
                raise ValueError(f"采集间隔不能小于 {FETCH_INTERVAL_MIN} 分钟")
            if v > FETCH_INTERVAL_MAX:
                raise ValueError(f"采集间隔不能大于 {FETCH_INTERVAL_MAX} 分钟")
        return v

    @validator('source_type')
    def validate_source_type(cls, v):
        if v is not None:
            valid_types = ["standard", "rsshub", "auto"]
            if v not in valid_types:
                raise ValueError(f"source_type 必须是 {valid_types} 之一")
        return v


class RSSSourceValidateRequest(BaseModel):
    """RSS源校验请求"""
    url: str
    source_type: str = "standard"  # 用于判断是否使用自动发现


class RSSSourceDiscoverRequest(BaseModel):
    """RSS源自动发现请求"""
    url: str  # 网站首页 URL


class RSSSourceDiscoverResponse(BaseModel):
    """RSS源自动发现响应"""
    direct_rss: List[dict] = []  # 直接发现的 RSS URL
    rsshub_routes: List[str] = []  # RSSHub 发现的路由
    source_type: Optional[str] = None  # 推荐的 source_type
    message: str  # 提示信息
    rsshub_hint: Optional[str] = None  # RSSHub 数据库匹配提示（如 RSSHub 未运行时）


class RSSSourceValidateResponse(BaseModel):
    """RSS源校验响应"""
    valid: bool
    message: str
    feed_title: Optional[str] = None
    entry_count: int = 0


class RSSSourceStatusResponse(BaseModel):
    """RSS源状态响应"""
    has_sources: bool = Field(description="是否有RSS源（任意状态）")
    has_active_sources: bool = Field(description="是否有活跃RSS源")
    total_count: int = Field(description="总源数量")
    active_count: int = Field(description="活跃源数量")


# ==================== 辅助函数 ====================


def _to_iso(value) -> Optional[str]:
    """将 datetime 转换为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _build_rss_response(source: RSSSource) -> dict:
    """构建 RSS 源响应字典"""
    return {
        "id": source.id,
        "name": source.name,
        "url": source.url,
        "category": source.category,
        "source_type": source.source_type,
        "is_active": source.is_active,
        "rsshub_unavailable": source.rsshub_unavailable,
        "fetch_error_count": source.fetch_error_count,
        "fetch_interval": source.fetch_interval,
        "last_fetched_at": _to_iso(source.last_fetched_at),
        "article_count": source.article_count,
        "last_modified": source.last_modified,  # 增量检测
        "etag": source.etag,                      # 增量检测
        "created_at": _to_iso(source.created_at),
        "updated_at": _to_iso(source.updated_at),
    }


# ==================== RSS源端点 ====================


@router.get("/status", response_model=RSSSourceStatusResponse)
async def get_rss_status(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取RSS源状态

    返回：
    - has_sources: 是否有RSS源（任意状态）
    - has_active_sources: 是否有活跃RSS源
    - total_count: 总源数量
    - active_count: 活跃源数量

    用于前端判断是否显示"无活跃源"警告
    """
    # 查询总数
    total_result = await db.execute(select(func.count(RSSSource.id)))
    total_count = total_result.scalar() or 0

    # 查询活跃数
    active_result = await db.execute(
        select(func.count(RSSSource.id)).where(RSSSource.is_active == True)
    )
    active_count = active_result.scalar() or 0

    return RSSSourceStatusResponse(
        has_sources=total_count > 0,
        has_active_sources=active_count > 0,
        total_count=total_count,
        active_count=active_count
    )


@router.get("/", response_model=RSSSourceListResponse)
async def get_rss_sources(
    category: Optional[str] = Query(None, description="分类筛选"),
    is_active: Optional[bool] = Query(None, description="激活状态筛选"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取RSS源列表
    """
    # 构建查询条件
    conditions = []

    if category:
        conditions.append(RSSSource.category == category)

    if is_active is not None:
        conditions.append(RSSSource.is_active == is_active)

    # 构建查询
    query = select(RSSSource)
    if conditions:
        query = query.where(*conditions)

    query = query.order_by(RSSSource.created_at.desc())

    # 执行查询
    result = await db.execute(query)
    sources = result.scalars().all()

    return RSSSourceListResponse(
        items=[RSSSourceResponse(**_build_rss_response(source)) for source in sources],
        total=len(sources),
    )


@router.get("/{source_id}", response_model=RSSSourceResponse)
async def get_rss_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    获取RSS源详情
    """
    result = await db.execute(
        select(RSSSource).where(RSSSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RSS源不存在"
        )

    return RSSSourceResponse(**_build_rss_response(source))


@router.post("/validate", response_model=RSSSourceValidateResponse)
async def validate_rss_source(
    request: RSSSourceValidateRequest,
):
    """
    预校验RSS源URL是否可解析

    根据 source_type 决定校验逻辑:
    - standard/rsshub: 直接解析
    - auto: 不支持校验，需要先发现
    """
    # 如果是 auto 类型，不支持校验
    # 用户应该先调用 /discover 接口
    if request.source_type == "auto":
        return RSSSourceValidateResponse(
            valid=False,
            message="自动发现类型不支持直接校验，请先调用 /discover 接口发现 RSS",
        )

    import feedparser

    try:
        feed = feedparser.parse(request.url)

        if feed.bozo and not feed.entries:
            return RSSSourceValidateResponse(
                valid=False,
                message=f"RSS源格式错误: {feed.bozo_exception}",
            )

        return RSSSourceValidateResponse(
            valid=True,
            message="RSS源有效",
            feed_title=feed.feed.get("title"),
            entry_count=len(feed.entries),
        )

    except Exception as e:
        return RSSSourceValidateResponse(
            valid=False,
            message=f"校验失败: {str(e)}",
        )


@router.post("/discover", response_model=RSSSourceDiscoverResponse)
async def discover_rss_source(
    request: RSSSourceDiscoverRequest,
):
    """
    自动发现 RSS 源

    两阶段检测：
    1. 直接检测网站是否提供 RSS
    2. 如果未发现，检测 RSSHub 是否支持该网站
    """
    try:
        from app.services.fetcher.rss_discover import rss_discoverer

        result = await rss_discoverer.discover(request.url)

        # 格式化 direct_rss 为字典列表
        direct_rss_list = []
        for url in result.direct_rss:
            direct_rss_list.append({"url": url})

        return RSSSourceDiscoverResponse(
            direct_rss=direct_rss_list,
            rsshub_routes=result.rsshub_routes,
            source_type=result.source_type,
            message=result.message,
            rsshub_hint=result.rsshub_hint,
        )

    except Exception as e:
        return RSSSourceDiscoverResponse(
            direct_rss=[],
            rsshub_routes=[],
            source_type=None,
            message=f"发现失败: {str(e)}",
        )


@router.post("/", response_model=RSSSourceResponse)
async def create_rss_source(
    request: RSSSourceCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    创建RSS源
    """
    # 检查URL是否已存在
    result = await db.execute(
        select(RSSSource).where(RSSSource.url == request.url)
    )
    existing = result.scalar_one_or_none()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="该RSS源URL已存在"
        )

    # RSSHub 类型校验：必须确保 RSSHub 服务运行中
    if request.source_type == "rsshub":
        from app.services.rsshub.manager import get_rsshub_manager
        if not get_rsshub_manager().is_running():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="RSSHub 服务未运行。请先在「RSSHub 帮助」页面中部署并启动服务后再添加 RSSHub 类型源。"
            )

    # 校验RSS源是否可用
    import feedparser

    try:
        feed = feedparser.parse(request.url)

        if feed.bozo and not feed.entries:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"RSS源不可用: {feed.bozo_exception}"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"RSS源校验失败: {str(e)}"
        )

    # 创建新RSS源
    source = RSSSource(
        name=request.name,
        url=request.url,
        category=request.category,
        source_type=request.source_type,
        is_active=request.is_active,
        fetch_interval=request.fetch_interval,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(source)
    await db.commit()
    await db.refresh(source)

    return RSSSourceResponse(**_build_rss_response(source))


@router.put("/{source_id}", response_model=RSSSourceResponse)
async def update_rss_source(
    source_id: int,
    request: RSSSourceUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    更新RSS源
    """
    result = await db.execute(
        select(RSSSource).where(RSSSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RSS源不存在"
        )

    # 更新字段
    if request.name is not None:
        source.name = request.name

    if request.url is not None:
        # 检查URL是否已存在
        existing_result = await db.execute(
            select(RSSSource).where(RSSSource.url == request.url, RSSSource.id != source_id)
        )
        existing = existing_result.scalar_one_or_none()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该RSS源URL已存在"
            )

        source.url = request.url

    if request.category is not None:
        source.category = request.category

    if request.source_type is not None:
        # RSSHub 类型校验：必须确保 RSSHub 服务运行中
        if request.source_type == "rsshub":
            from app.services.rsshub.manager import get_rsshub_manager
            if not get_rsshub_manager().is_running():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="RSSHub 服务未运行。请先在「RSSHub 帮助」页面中部署并启动服务后再添加 RSSHub 类型源。"
                )
        source.source_type = request.source_type

    if request.is_active is not None:
        if request.is_active and source.rsshub_unavailable:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="该 RSS 源因 RSSHub 服务未运行而不可启用。请先启动 RSSHub 服务。"
            )
        source.is_active = request.is_active

    if request.fetch_interval is not None:
        source.fetch_interval = request.fetch_interval

    source.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(source)

    return RSSSourceResponse(**_build_rss_response(source))


@router.delete("/{source_id}")
async def delete_rss_source(
    source_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    删除RSS源
    """
    result = await db.execute(
        select(RSSSource).where(RSSSource.id == source_id)
    )
    source = result.scalar_one_or_none()

    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="RSS源不存在"
        )

    await db.delete(source)
    await db.commit()

    return {"message": "RSS源已删除"}