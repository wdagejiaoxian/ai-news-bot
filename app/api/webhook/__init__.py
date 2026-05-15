# -*- coding: utf-8 -*-
"""
Webhook API 模块

拆分自 app/api/webhook.py:
- schemas.py: 请求/响应模型
- crud.py: 基础 CRUD 操作
- create.py: 创建逻辑
- update.py: 更新逻辑
- delete.py: 删除逻辑
- test.py: 测试逻辑
- platforms/: 平台特定实现
"""

from app.api.webhook.crud import router as webhook_crud_router
from app.api.webhook.create import router as webhook_create_router
from app.api.webhook.update import router as webhook_update_router
from app.api.webhook.delete import router as webhook_delete_router
from app.api.webhook.test import router as webhook_test_router

__all__ = [
    "webhook_crud_router",
    "webhook_create_router",
    "webhook_update_router",
    "webhook_delete_router",
    "webhook_test_router",
]