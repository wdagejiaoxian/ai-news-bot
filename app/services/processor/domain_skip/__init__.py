"""
域名动态跳过模块

功能：
- 记录域名补全成功/失败
- 判断是否触发跳过
"""

from .service import DomainSkipService

# 全局单例
domain_skip_service = DomainSkipService()

__all__ = ["domain_skip_service", "DomainSkipService"]
