# -*- coding: utf-8 -*-
"""
AI News Bot 主应用

FastAPI 应用入口
提供 REST API 和 Webhook 接口
"""

import logging
import logging.config
import sqlite3
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.config import get_settings
from app.database import close_database, init_database
from app.services.commands import command_handler
from app.services.scheduler.jobs import scheduler
from app.services.notifier.wecom_callback import router as wecom_router
from app.services.processor.llm_manager import llm_manager, LLMProvider, LLMMode

# 配置日志 - 输出到文件
import os
os.makedirs('logs', exist_ok=True)

logging.config.fileConfig('app/logging.conf', disable_existing_loggers=False)
logger = logging.getLogger(__name__)


# 全局 SQLite 连接（用于 Agent 持久化）
# agent_sqlite_conn: Optional[sqlite3.Connection] = None

# ==================== 应用生命周期 ====================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理
    
    启动时: 初始化数据库、启动定时任务
    关闭时: 关闭数据库连接、停止定时任务
    """
    # global agent_sqlite_conn

    # 启动时
    logger.info("应用启动中...")
    
    # 初始化数据库
    await init_database()
    logger.info("数据库初始化完成")

    init_llm_models()

    # db_path = "storage/agent_memory.db"
    # if db_path:
    #     dir_path = os.path.dirname(db_path)
    #     if dir_path and not os.path.exists(dir_path):
    #         os.makedirs(dir_path, exist_ok=True)
    # agent_sqlite_conn = sqlite3.connect(db_path, check_same_thread=False)
    # logger.info("Agent SQLite 连接已建立")

    # 初始化 Agent 数据库
    from app.services.agentic.agent_database import init_agent_database
    init_agent_database()
    logger.info("Agent 数据库初始化完成")

    # 启动定时任务
    scheduler.start()
    logger.info("定时任务已启动")
    
    yield
    
    # 关闭时
    logger.info("应用关闭中...")

    # 停止定时任务
    scheduler.shutdown()

    # # 清理所有Agent实例
    # from app.services.notifier.wecom_callback import cleanup_expired_agents, _user_data
    #
    # # 强制清理所有用户数据
    # for user_id in list(_user_data.keys()):
    #     if 'agent' in _user_data[user_id]:
    #         agent_obj = _user_data[user_id]['agent']
    #         if hasattr(agent_obj, 'close'):
    #             try:
    #                 agent_obj.close()
    #             except Exception as e:
    #                 logger.error(f"关闭Agent失败 [{user_id}]: {e}")
    #
    # _user_data.clear()
    # logger.info("所有Agent实例已清理")

    # ✅ 关闭 Agent 数据库
    from app.services.agentic.agent_database import close_agent_database
    close_agent_database()
    logger.info("Agent 数据库已关闭")
    
    # 关闭数据库
    await close_database()
    logger.info("应用已关闭")


def init_llm_models():
    """初始化LLM模型注册"""
    settings = get_settings()

    # 注册智谱平台模型
    llm_manager.register_model(
        provider=LLMProvider.ZHIPU,
        model_name="glm-4.7-flash",
        api_key=settings.openai_api_key,  # 假设智谱使用相同的API Key字段
        api_base=settings.openai_api_base,
        can_disable_thinking=True,  # glm-4.7-flash支持关闭思考模式
        can_use_tool=False,
        max_concurrent=1  # 根据文档，并发限制为1
    )

    llm_manager.register_model(
        provider=LLMProvider.ZHIPU,
        model_name="glm-4-flash-250414",
        api_key=settings.openai_api_key,
        api_base=settings.openai_api_base,
        can_disable_thinking=True,
        can_use_tool=False,
        max_concurrent=5  # 根据文档，并发限制为5
    )

    # modelscope平台模型
    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="MiniMax/MiniMax-M2.5",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=False,
        can_use_tool=True,
        max_concurrent=settings.modelscope_max_concurrent
    )

    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="ZhipuAI/GLM-5",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=False,
        can_use_tool=True,
        max_concurrent=settings.modelscope_max_concurrent
    )


    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="moonshotai/Kimi-K2.5",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=True,
        can_use_tool=True,
        max_concurrent=settings.modelscope_max_concurrent
    )

    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="Qwen/Qwen3.5-27B",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=True,
        can_use_tool=True,
        max_concurrent=settings.modelscope_max_concurrent
    )

    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="deepseek-ai/DeepSeek-V3.2",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=True,
        can_use_tool=False,
        max_concurrent=settings.modelscope_max_concurrent
    )

    llm_manager.register_model(
        provider=LLMProvider.MODELSCOPE,
        model_name="Qwen/Qwen3.5-35B-A3B",
        api_key=settings.modelscope_api_key,
        api_base=settings.modelscope_api_base,
        can_disable_thinking=True,
        can_use_tool=True,
        max_concurrent=settings.modelscope_max_concurrent
    )


    # openrouter平台的模型
    llm_manager.register_model(
        provider=LLMProvider.OPENROUTER,
        model_name="z-ai/glm-4.5-air:free",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_api_base,
        can_disable_thinking=True,
        can_use_tool=False,
        max_concurrent=settings.openrouter_max_concurrent
    )

    llm_manager.register_model(
        provider=LLMProvider.OPENROUTER,
        model_name="nvidia/nemotron-3-nano-30b-a3b:free",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_api_base,
        can_disable_thinking=False,
        can_use_tool=True,
        max_concurrent=settings.openrouter_max_concurrent  # 根据文档，并发限制为1
    )

    llm_manager.register_model(
        provider=LLMProvider.OPENROUTER,
        model_name="nvidia/nemotron-3-super-120b-a12b:free",
        api_key=settings.openrouter_api_key,
        api_base=settings.openrouter_api_base,
        can_disable_thinking=False,
        can_use_tool=True,
        max_concurrent=settings.openrouter_max_concurrent  # 根据文档，并发限制为1
    )

    # 注册硅基流动平台模型
    # 支持关闭思考模式的模型
    llm_manager.register_model(
        provider=LLMProvider.SILICONFLOW,
        model_name="Qwen/Qwen3-8B",
        api_key=settings.siliconflow_api_key,  # 需要在config.py中添加此字段
        api_base=settings.siliconflow_api_base,  # 需要在config.py中添加此字段
        can_disable_thinking=True,
        can_use_tool=True,
        max_concurrent=settings.siliconflow_max_concurrent or 1 # 可配置
    )

    # 不支持关闭思考模式的模型（但所有模型都是推理模型，可用于需要思考的任务）
    # llm_manager.register_model(
    #     provider=LLMProvider.SILICONFLOW,
    #     model_name="deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    #     api_key=settings.siliconflow_api_key,
    #     api_base=settings.siliconflow_api_base,
    #     can_disable_thinking=False,
    #     can_use_tool=False,
    #     max_concurrent=settings.siliconflow_max_concurrent or 1
    # )
    #
    # llm_manager.register_model(
    #     provider=LLMProvider.SILICONFLOW,
    #     model_name="THUDM/GLM-Z1-9B-0414",
    #     api_key=settings.siliconflow_api_key,
    #     api_base=settings.siliconflow_api_base,
    #     can_disable_thinking=False,
    #     can_use_tool=False,
    #     max_concurrent=settings.siliconflow_max_concurrent or 1
    # )

    # llm_manager.register_model(
    #     provider=LLMProvider.SILICONFLOW,
    #     model_name="THUDM/GLM-4.1V-9B-Thinking",
    #     api_key=settings.siliconflow_api_key,
    #     api_base=settings.siliconflow_api_base,
    #     can_disable_thinking=False,
    #     can_use_tool=False,
    #     max_concurrent=settings.siliconflow_max_concurrent or 1  # 思考模型可能并发较低
    # )

    logger.info("LLM模型注册完成")



# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="AI News Bot",
    description="AI资讯与GitHub热门项目自动收录工具",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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

#VV|# ==================== 路由 ====================
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
        port=8001,
        reload=settings.debug,
        log_level="info",
    )
