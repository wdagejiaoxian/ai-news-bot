# -*- coding: utf-8 -*-
"""
响应映射工具函数
用于简化 ORM 模型到 Pydantic 响应的转换
"""

from datetime import datetime
from typing import Optional, TypeVar, Type, List

from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)


def model_to_response(
    model,
    response_class: Type[T],
    datetime_fields: Optional[List[str]] = None,
    extra_fields: Optional[dict] = None,
) -> dict:
    """
    将 ORM 模型转换为响应字典

    Args:
        model: ORM 模型实例
        response_class: Pydantic 响应类
        datetime_fields: 需要格式化的 datetime 字段列表
        extra_fields: 额外添加的字段

    Returns:
        dict: 响应字典
    """
    if datetime_fields is None:
        datetime_fields = ['created_at', 'updated_at', 'published_at', 'last_fetched_at']

    result = {}
    for field_name in response_class.model_fields.keys():
        if hasattr(model, field_name):
            value = getattr(model, field_name)
            if field_name in datetime_fields and isinstance(value, datetime):
                result[field_name] = value.isoformat() if value else None
            else:
                result[field_name] = value
        elif field_name in ('created_at', 'updated_at', 'published_at', 'last_fetched_at'):
            # 处理可选的 datetime 字段
            value = getattr(model, field_name, None)
            result[field_name] = value.isoformat() if value else None

    if extra_fields:
        result.update(extra_fields)

    return result


def parse_datetime(value) -> Optional[str]:
    """解析 datetime 为 ISO 格式字符串"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def build_datetime_field(model, field_name: str) -> Optional[str]:
    """构建 datetime 字段的响应值"""
    value = getattr(model, field_name, None)
    return parse_datetime(value)