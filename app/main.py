# -*- coding: utf-8 -*-
"""
AI News Bot 主应用

FastAPI 应用入口
提供 REST API 和 Webhook 接口
"""

import asyncio
import logging.config
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.database import close_database, init_database, db
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.exception_handler import register_exception_handlers
from app.services.commands import command_handler
from app.services.scheduler.jobs import scheduler
from app.services.notifier.wecom_callback import router as wecom_router
from app.services.processor.llm_manager import llm_manager, LLMProvider, LLMMode

# 从限流器模块导入
from app.api.rate_limit import limiter

# 导入API路由
from app.api import (
    auth_router,
    articles_router,
    github_router,
    github_languages_router,
    rss_router,
    stats_router,
    jobs_router,
    configs_router,
    webhook_crud_router,
    webhook_create_router,
    webhook_update_router,
    webhook_delete_router,
    webhook_test_router,
    template_router,
    model_router,
    llm_config_router,
    logs_router,
    push_logs_router,
    task_execution_history_router,
    obsidian_router,
    rsshub_status_router,
    vector_config_router,
    system_config_router,
)

# 配置日志 - 输出到文件
import os
os.makedirs('logs', exist_ok=True)

logging.config.fileConfig('app/logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)



# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时: 初始化数据库、启动定时任务
    关闭时: 关闭数据库连接、停止定时任务
    """
    # 启动时
    logger.info("应用启动中...")

    # 验证配置安全性（S2/S3修复：检查JWT密钥和Web面板密码）
    from app.config import validate_settings
    try:
        validate_settings()
        logger.info("配置安全检查通过")
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        raise  # 启动失败

    # 初始化数据库
    await init_database()
    logger.info("数据库初始化完成")

    # ★ 从数据库恢复用户配置覆盖值（数据库初始化后、其他服务初始化前执行）
    try:
        from app.services.config_sync import config_sync_service
        restored_count = await config_sync_service.load_from_db()
        if restored_count > 0:
            logger.info("已从数据库恢复 %d 项用户配置", restored_count)
        else:
            logger.info("数据库无用户配置覆盖，使用 config.py 默认值")
    except Exception as e:
        logger.warning("加载用户配置覆盖失败，使用 config.py 默认值: %s", e)

    # 初始化内置RSS源（降级源）
    # 当 rss_sources 表为空时，自动写入预设的降级源
    try:
        from app.database import init_builtin_rss_sources
        await init_builtin_rss_sources()
        logger.info("内置RSS源初始化完成")
    except Exception as e:
        logger.warning(f"内置RSS源初始化失败（不影响启动）: {e}")

    # 向量数据库配置表迁移（已废弃，模型已包含最新字段）
    # from app.database_migrations_vector import migrate_vector_db_config

    # # 执行数据库迁移
    # from app.database_migrations import run_migrations
    # async with db.get_session() as session:
    #     await run_migrations(session)
    # logger.info("数据库迁移完成")

    # 初始化 Web Panel 用户
    await init_web_panel_user()
    logger.info("Web Panel 用户初始化完成")

    # 初始化 LLM 模型
    await init_llm_models()
    logger.info("LLM模型初始化完成")


    # 初始化 Agent 数据库
    from app.services.agentic.agent_database import init_agent_database
    init_agent_database()
    logger.info("Agent 数据库初始化完成")

    # 初始化定时任务配置（数据库优先，config.py 兜底）
    from app.services.scheduler.config_loader import config_loader
    await config_loader.initialize_db_configs()
    logger.info("定时任务配置初始化完成")

    # Phase 2 统一方案：初始化动态域名跳过服务
    # 从静态配置增量导入域名到动态跳过表
    from app.services.processor.domain_skip import domain_skip_service
    try:
        await domain_skip_service.initialize_from_config()
    except Exception as e:
        logger.warning(f"动态域名跳过初始化失败（不影响启动）: {e}")

    # Phase 1：初始化 RSSHub 管理器（后台执行，不阻塞启动）
    # 注意：路由同步在 Manager 内部延迟执行
    from app.services.rsshub.manager import get_rsshub_manager
    try:
        asyncio.create_task(get_rsshub_manager().initialize())
        logger.info("RSSHub 初始化任务已提交（后台执行）")
    except Exception as e:
        logger.warning(f"RSSHub 初始化失败（不影响启动）: {e}")

    # 在启动定时任务前，同步任务状态
    # 检查 LLM 和 Webhook 配置，确保在配置不完整时禁用所有定时任务
    from app.services.scheduler.task_state_manager import TaskStateManager
    await TaskStateManager.check_and_update_task_state()
    logger.info("定时任务状态同步完成")

    # 启动定时任务
    scheduler.start()
    logger.info("定时任务已启动")

    # Phase Vector: 初始化向量服务（严格顺序）
    try:
        # 1. 初始化 VectorDBManager（连接 ChromaDB + 健康检查）
        #    注意：此步在 config 之前，因为它不依赖 config 存在
        from app.services.vector.vector_db_manager import vector_db_manager
        await vector_db_manager.initialize()
        logger.info("VectorDBManager 初始化完成")

        # 2. 初始化默认配置（含 collection 创建）
        #    移到 embedding_manager 之前：config 创建后才能过滤模型
        from app.services.vector.config_service import config_service
        await config_service.initialize_default()
        logger.info("VectorDBConfig 初始化完成")

        # 3. 初始化 Embedding 模型管理器
        #    此时 config 已存在，加载后可直接按 dimension 过滤
        #    注意：_load_models_from_db() 内部已完成维度过滤（标记不匹配模型为不可用），
        #    因此无需再调用 config_service.sync_model_availability()（该方法用于运行时配置切换）
        from app.services.vector.embedding_manager import embedding_manager
        await embedding_manager.initialize()
        logger.info("EmbeddingManager 初始化完成")

        # 4. 启动文章索引器
        from app.services.vector.article_indexer import article_indexer
        settings = get_settings()
        await article_indexer.start(concurrency=settings.indexer_concurrency)
        logger.info("ArticleIndexer 启动完成")
    except Exception as e:
        logger.warning(f"向量服务初始化失败（不影响核心功能）: {e}")

    yield

    # 关闭时
    logger.info("应用关闭中...")

    # Phase Vector: 清理向量服务
    try:
        from app.services.vector.article_indexer import article_indexer
        await article_indexer.shutdown(timeout=10.0)
        logger.info("ArticleIndexer 关闭完成")
    except Exception as e:
        logger.warning(f"ArticleIndexer 关闭异常: {e}")

    try:
        from app.services.vector.vector_db_manager import vector_db_manager
        await vector_db_manager.shutdown()
        logger.info("VectorDBManager 关闭完成")
    except Exception as e:
        logger.warning(f"VectorDBManager 关闭异常: {e}")

    # Phase P0-A 优化: 优雅关闭后台补全任务
    try:
        await scheduler._cancel_pending_enrich(timeout=10.0)
    except Exception as e:
        logger.warning(f"后台补全任务清理失败: {e}")

    # 停止定时任务（异步方式，避免阻塞）
    try:
        loop = asyncio.get_running_loop()
        # 在后台线程中执行 shutdown，不阻塞关闭流程
        await asyncio.to_thread(scheduler.scheduler.shutdown)
    except Exception as e:
        logger.error(f"停止调度器失败: {e}")
        # 降级处理：直接调用
        try:
            scheduler.shutdown(wait=False)
        except Exception as shutdown_e:
            logger.error(f"强制关闭调度器失败: {shutdown_e}")


    # ✅ 关闭 Agent 数据库
    from app.services.agentic.agent_database import close_agent_database
    close_agent_database()
    logger.info("Agent 数据库已关闭")
    
    # 关闭数据库
    await close_database()
    logger.info("应用已关闭")


async def init_web_panel_user():
    """
    初始化 Web Panel 用户
    
    检查是否存在 Web Panel 用户，如果不存在则从配置创建
    """
    from app.database import db
    from app.models import User
    from app.auth.jwt import get_password_hash
    from sqlalchemy import select
    
    settings = get_settings()
    
    # 如果未配置用户名密码，则跳过
    if not settings.web_panel_username or not settings.web_panel_password:
        logger.warning("未配置 Web Panel 用户名/密码，跳过创建")
        return
    
    async with db.get_session() as session:
        # 检查是否已存在 Web Panel 用户
        result = await session.execute(
            select(User).where(User.is_web_panel_user == True)
        )
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            logger.info(f"Web Panel 用户已存在: {existing_user.platform_id}")
            return
        
        # 创建新用户
        password_hash = get_password_hash(settings.web_panel_password)
        web_panel_user = User(
            platform="web_panel",
            platform_id=settings.web_panel_username,
            is_web_panel_user=True,
            password_hash=password_hash,
            name=settings.web_panel_username,
            is_active=True,
        )
        session.add(web_panel_user)
        await session.commit()
        logger.info(f"Web Panel 用户创建成功: {settings.web_panel_username}")


async def init_llm_models():
    """
    初始化LLM模型注册

    从数据库加载 is_active=True 的模型
    """
    from app.database import db
    from app.models import LLMModel
    from sqlalchemy import select

    # 设置数据库会话工厂到 llm_manager
    llm_manager.set_db_session_factory(db.get_session)

    # 从数据库加载 is_active=True 的模型
    try:
        async with db.get_session() as session:
            result = await session.execute(
                select(LLMModel).where(LLMModel.is_active == True)
            )
            db_models = list(result.scalars().all())

            if not db_models:
                logger.info("数据库中没有启用的LLM模型配置")
                return

            # 加载模型
            llm_manager.load_models_from_db(db_models)
            logger.info(f"从数据库加载了 {len(db_models)} 个LLM模型")
    except Exception as e:
        logger.error(f"加载LLM模型失败: {e}")
        # 失败时跳过，不阻塞应用启动



# ==================== FastAPI 应用 ====================

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    description="AI资讯与GitHub热门项目自动收录工具",
    version=settings.app_version,
    lifespan=lifespan,
    # Swagger UI 仅在调试模式开启
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    openapi_url="/openapi.json" if settings.debug else None,
)

# CORS 中间件 - 从环境变量读取允许的来源
_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["*"],
)

# 限流中间件 - 单用户场景使用内存存储
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 请求 ID 追踪中间件
app.add_middleware(RequestIDMiddleware)

# 注册统一异常处理器
register_exception_handlers(app)


# ==================== 数据模型 ====================

class CommandRequest(BaseModel):
    """指令请求"""
    text: str
    user_id: Optional[str] = None


class CommandResponse(BaseModel):
    """指令响应"""
    success: bool
    message: str


class WebhookRequest(BaseModel):
    """Webhook请求"""
    msgtype: str
    content: Optional[str] = None


class FetchRequest(BaseModel):
    """采集请求"""
    source: str  # "news" / "github" / "all"
    language: Optional[str] = None
    time_range: Optional[str] = "daily"

#PP|

# 注册企业微信回调路由
app.include_router(wecom_router, tags=["企业微信"])

# 注册Web面板API路由
app.include_router(auth_router, prefix="/api/auth", tags=["认证"])
app.include_router(articles_router, prefix="/api/articles", tags=["文章"])
app.include_router(github_router, prefix="/api/github-repos", tags=["GitHub"])
app.include_router(github_languages_router, prefix="/api/github-languages", tags=["GitHub语言"])
app.include_router(rss_router, prefix="/api/rss-sources", tags=["RSS"])
app.include_router(stats_router, prefix="/api/stats", tags=["统计"])
app.include_router(jobs_router, prefix="/api/scheduler", tags=["调度-任务"])
app.include_router(configs_router, prefix="/api/scheduler", tags=["调度-配置"])
app.include_router(webhook_crud_router, prefix="/api/webhooks", tags=["Webhook"])
app.include_router(webhook_create_router, prefix="/api/webhooks", tags=["Webhook"])
app.include_router(webhook_update_router, prefix="/api/webhooks", tags=["Webhook"])
app.include_router(webhook_delete_router, prefix="/api/webhooks", tags=["Webhook"])
app.include_router(webhook_test_router, prefix="/api/webhooks", tags=["Webhook"])
app.include_router(template_router, prefix="/api", tags=["模板"])
app.include_router(model_router, prefix="/api/models", tags=["模型"])
app.include_router(llm_config_router, prefix="/api/llm", tags=["LLM配置"])
app.include_router(logs_router, prefix="/api/admin/logs", tags=["管理"])
app.include_router(push_logs_router, prefix="/api/admin", tags=["推送日志"])
app.include_router(task_execution_history_router, prefix="/api/admin", tags=["任务执行历史"])
app.include_router(obsidian_router, prefix="/api/obsidian", tags=["Obsidian"])
app.include_router(rsshub_status_router, prefix="/api/rsshub", tags=["RSSHub"])
app.include_router(vector_config_router, prefix="/api/vector", tags=["向量服务"])
app.include_router(system_config_router, prefix="/api/system-configs", tags=["系统配置"])

# ==================== 路由 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "name": "AI News Bot",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "healthy"}


# ==================== 指令处理 ====================

@app.post("/command", response_model=CommandResponse)
async def handle_command(request: CommandRequest):
    """
    处理用户指令
    
    用于接收用户通过API发送的指令
    """
    try:
        result = await command_handler.handle(request.text, request.user_id)
        return CommandResponse(success=True, message=result)
    except Exception as e:
        logger.error(f"处理指令失败: {e}")
        return CommandResponse(
            success=False,
            message=f"处理失败: {str(e)}"
        )


# ==================== Webhook 回调 ====================

# @app.post("/webhook/wecom")
# async def wecom_webhook(request: Request, background_tasks: BackgroundTasks):
#     """
#     企业微信Webhook回调
#
#     接收企业微信发送的消息
#     """
#     try:
#         # 解析请求体
#         body = await request.json()
#
#         # 提取消息内容
#         msg_type = body.get("msgtype", "text")
#
#         if msg_type == "text":
#             content = body.get("text", {}).get("content", "").strip()
#
#             # 处理指令
#             result = await command_handler.handle(content)
#
#             # TODO: 回复消息
#             # 需要根据实际企业微信API实现
#
#             return {"errcode": 0, "errmsg": "ok"}
#
#         return {"errcode": 0, "errmsg": "unsupported msgtype"}
#
#     except Exception as e:
#         logger.error(f"Webhook处理失败: {e}")
#         return {"errcode": 1, "errmsg": str(e)}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """
    Telegram Webhook回调
    """
    try:
        body = await request.json()
        
        # 提取消息
        message = body.get("message", {})
        text = message.get("text", "").strip()
        chat_id = message.get("chat", {}).get("id")
        
        if text and text.startswith("/"):
            # 处理指令
            result = await command_handler.handle(text, str(chat_id))
            
            # TODO: 发送回复
            # 需要使用 Telegram Bot API
            
            return {"ok": True}
        
        return {"ok": True}
        
    except Exception as e:
        logger.error(f"Telegram Webhook处理失败: {e}")
        return {"ok": False, "error": str(e)}


# ==================== 手动触发 ====================

@app.post("/fetch")
async def trigger_fetch(request: FetchRequest, background_tasks: BackgroundTasks):
    """
    手动触发数据采集
    
    用于测试或立即刷新数据
    """
    try:
        if request.source == "news" or request.source == "all":
            # 采集新闻
            background_tasks.add_task(scheduler.fetch_ai_news)
        
        if request.source == "github" or request.source == "all":
            # 采集GitHub
            background_tasks.add_task(scheduler.fetch_github_trending)
        
        return {
            "success": True,
            "message": f"已触发 {request.source} 采集任务"
        }
        
    except Exception as e:
        logger.error(f"触发采集失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 管理接口 ====================

@app.get("/stats")
async def get_stats():
    """
    获取统计信息
    
    返回当前数据库中的内容数量
    """
    from app.database import db
    from app.models import Article, GitHubRepo, User
    from sqlalchemy import select, func
    
    async with db.get_session() as session:
        # 统计文章
        news_count = await session.scalar(
            select(func.count(Article.id))
        )
        
        # 统计GitHub
        github_count = await session.scalar(
            select(func.count(GitHubRepo.id))
        )
        
        # 统计用户
        user_count = await session.scalar(
            select(func.count(User.id))
        )
        
        return {
            "articles": news_count or 0,
            "github_repos": github_count or 0,
            "users": user_count or 0,
        }


# ==================== 运行入口 ====================

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level="info",
    )
