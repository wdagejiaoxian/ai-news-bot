# -*- coding: utf-8 -*-
"""
Scheduler API 模块

拆分自 app/api/scheduler.py:
- jobs.py: 运行时任务管理
- configs.py: 任务配置 CRUD
- schemas.py: 共享 Pydantic 模型
"""

from app.api.scheduler.jobs import router as jobs_router
from app.api.scheduler.configs import router as configs_router

__all__ = [
    "jobs_router",
    "configs_router",
]