# -*- coding: utf-8 -*-
"""
企业微信通知模块

提供企业微信 Webhook 机器人的通知功能
"""

from app.services.notifier.wecom.wecom_dynamic import DynamicWeComNotifier

__all__ = ["DynamicWeComNotifier"]