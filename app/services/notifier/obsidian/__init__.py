# -*- coding: utf-8 -*-
"""
Obsidian 通知器模块

提供两种推送模式：
- obsidian_git: Git 远程模式（通过 GitHub/Gitee API 推送）
- obsidian_api: Local REST API 本地模式（直接写入本地 Vault）

导入此模块会自动注册通知器到全局注册表
"""

# 导入子模块以触发 @register_notifier 装饰器
from app.services.notifier.obsidian import obsidian_git  # noqa: F401
from app.services.notifier.obsidian import obsidian_api  # noqa: F401

__all__ = [
    "obsidian_git",
    "obsidian_api",
]