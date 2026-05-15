# -*- coding: utf-8 -*-
"""
限流器模块

创建全局限流器实例，避免循环导入
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

# 创建限流器 (单用户场景使用内存存储)
limiter = Limiter(key_func=get_remote_address)
