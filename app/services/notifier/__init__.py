# -*- coding: utf-8 -*-
"""
消息通知服务

支持平台：
- 企业微信 (wecom)
- Obsidian (obsidian) - Git 远程模式 + API 本地模式
"""

# 导入企业微信通知器以触发注册
from app.services.notifier.wecom import wecom_bot  # noqa: F401
from app.services.notifier.wecom import wecom_dynamic  # noqa: F401

# 导入 Obsidian 通知器以触发注册
from app.services.notifier.obsidian import obsidian_git  # noqa: F401
from app.services.notifier.obsidian import obsidian_api  # noqa: F401

from app.services.notifier.base import (
    # 通知管理器（推荐使用）
    notification_manager,
)

from app.services.notifier.content_converter import (
    MAX_CONTENT_LENGTH,
    ContentConverter,
    content_converter
)

from app.services.notifier.report_generator import (
    ReportContentGenerator,
    report_content_generator,
)

from app.services.notifier.dynamic_base import (
    BaseDynamicNotifier,
    register_notifier,
    create_notifier,
)

__all__ = [
    # 通知管理器
    "notification_manager",
    # 内容转换器
    "MAX_CONTENT_LENGTH",
    "ContentConverter",
    "content_converter",
    # 报告生成器
    "ReportContentGenerator",
    "report_content_generator",
    # 动态通知器基类
    "BaseDynamicNotifier",
    "register_notifier",
    "create_notifier",
]