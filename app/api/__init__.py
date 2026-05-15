# -*- coding: utf-8 -*-
"""
API模块
包含所有API路由
"""

from app.api.auth import router as auth_router
from app.api.articles import router as articles_router
from app.api.github import router as github_router
from app.api.github_languages import router as github_languages_router
from app.api.rss import router as rss_router
from app.api.stats import router as stats_router
from app.api.scheduler import jobs_router, configs_router
from app.api.webhook import (
    webhook_crud_router,
    webhook_create_router,
    webhook_update_router,
    webhook_delete_router,
    webhook_test_router,
)
from app.api.template import router as template_router
from app.api.model import router as model_router
from app.api.llm_config import router as llm_config_router
from app.api.logs import router as logs_router
from app.api.push_logs import router as push_logs_router
from app.api.task_execution_history import router as task_execution_history_router
from app.api.obsidian import router as obsidian_router
from app.api.rsshub_status import router as rsshub_status_router
from app.api.vector_config import router as vector_config_router
from app.api.system_config import router as system_config_router

__all__ = [
    "auth_router",
    "articles_router",
    "github_router",
    "github_languages_router",
    "rss_router",
    "stats_router",
    "jobs_router",
    "configs_router",
    "webhook_crud_router",
    "webhook_create_router",
    "webhook_update_router",
    "webhook_delete_router",
    "webhook_test_router",
    "template_router",
    "model_router",
    "llm_config_router",
    "logs_router",
    "push_logs_router",
    "task_execution_history_router",
    "obsidian_router",
    "rsshub_status_router",
    "vector_config_router",
    "system_config_router",
]
