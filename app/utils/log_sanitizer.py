# -*- coding: utf-8 -*-
"""
日志脱敏工具模块

提供日志输出时的敏感信息脱敏功能，防止密钥、Token 等敏感信息泄露
"""

import logging
import re
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)

# 敏感字段名称模式（不区分大小写）
SENSITIVE_FIELD_PATTERNS = [
    r'.*key$',           # key, api_key, webhook_key, secret_key
    r'.*token$',         # token, access_token, refresh_token
    r'.*secret$',        # secret, client_secret
    r'.*password$',      # password, passwd
    r'.*credential$',    # credential
    r'.*auth$',          # auth, authorization
    r'.*aes_key$',       # aes_key, encoding_aes_key
    r'.*corp_secret$',   # corp_secret
    r'.*app_secret$',    # app_secret
]

# 编译后的正则表达式
SENSITIVE_FIELD_REGEX = re.compile(
    '|'.join(SENSITIVE_FIELD_PATTERNS),
    re.IGNORECASE
)

# 脱敏后的占位符
SANITIZED_PLACEHOLDER = "***REDACTED***"


def is_sensitive_field(field_name: str) -> bool:
    """
    判断字段名是否为敏感字段

    Args:
        field_name: 字段名

    Returns:
        True 表示敏感字段
    """
    return bool(SENSITIVE_FIELD_REGEX.match(field_name))


def sanitize_value(value: Any, field_name: str = "") -> Any:
    """
    对值进行脱敏处理

    Args:
        value: 待脱敏的值
        field_name: 字段名（用于判断是否需要脱敏）

    Returns:
        脱敏后的值
    """
    if not is_sensitive_field(field_name):
        return value

    # 如果是字符串，进行脱敏
    if isinstance(value, str):
        return SANITIZED_PLACEHOLDER

    # 如果是字典，递归脱敏
    if isinstance(value, dict):
        return sanitize_dict(value)

    # 如果是列表，递归脱敏
    if isinstance(value, list):
        return [sanitize_value(item, field_name) for item in value]

    # 其他类型（int, float, bool）直接返回
    return value


def sanitize_dict(data: Dict[str, Any], extra_sensitive_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    对字典进行脱敏处理

    Args:
        data: 待脱敏的字典
        extra_sensitive_keys: 额外的敏感字段名列表

    Returns:
        脱敏后的字典
    """
    if not data:
        return data

    result = {}
    # 敏感字段集合：字符串模式 或 已编译的正则
    all_sensitive: List[Union[str, re.Pattern]] = list(SENSITIVE_FIELD_PATTERNS)

    # 添加额外的敏感字段（编译为正则）
    if extra_sensitive_keys:
        for key in extra_sensitive_keys:
            all_sensitive.append(re.compile(re.escape(key), re.IGNORECASE))

    for key, value in data.items():
        # 检查是否需要脱敏
        should_sanitize = any(
            pattern.match(key) if isinstance(pattern, re.Pattern) else bool(re.match(pattern, key, re.IGNORECASE))
            for pattern in all_sensitive
        )

        if should_sanitize:
            result[key] = SANITIZED_PLACEHOLDER
        elif isinstance(value, dict):
            result[key] = sanitize_dict(value, extra_sensitive_keys)
        elif isinstance(value, list):
            result[key] = [
                sanitize_dict(item, extra_sensitive_keys) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value

    return result


def sanitize_for_log(
    data: Any,
    field_name: str = "",
    extra_sensitive_keys: Optional[List[str]] = None
) -> str:
    """
    将数据转换为日志安全字符串

    Args:
        data: 待脱敏的数据（dict, str, 或其他）
        field_name: 字段名
        extra_sensitive_keys: 额外的敏感字段名

    Returns:
        日志安全的字符串表示
    """
    try:
        # 先脱敏
        if isinstance(data, dict):
            sanitized = sanitize_dict(data, extra_sensitive_keys)
        else:
            sanitized = sanitize_value(data, field_name)

        # 转换为字符串
        if isinstance(sanitized, str):
            return sanitized

        import json
        return json.dumps(sanitized, ensure_ascii=False, default=str)

    except Exception as e:
        # 转换失败时返回脱敏占位符
        logger.warning(f"日志转换失败: {e}")
        return SANITIZED_PLACEHOLDER


def safe_log(level: int, msg: str, *args, **kwargs):
    """
    安全日志记录（自动脱敏）

    用法:
        safe_log(logging.INFO, "发送失败: %s", result, extra_sensitive=['custom_field'])
        safe_log(logging.ERROR, "错误: %s", error_data)

    Args:
        level: 日志级别 (logging.INFO, logging.ERROR 等)
        msg: 日志消息模板
        *args: 位置参数
        **kwargs: 关键字参数，extra_sensitive_keys 用于额外敏感字段
    """
    extra_keys = kwargs.pop('extra_sensitive_keys', None)

    # 对 args 进行脱敏（只处理复杂对象）
    sanitized_args = tuple(
        sanitize_for_log(arg, extra_sensitive_keys=extra_keys)
        if not isinstance(arg, (str, int, float, bool, type(None)))
        else arg
        for arg in args
    )

    # 记录日志 - 只传递消息和位置参数，避免 kwargs 类型问题
    logger.log(level, msg, *sanitized_args)


# 便捷函数
def log_info(msg: str, *args, **kwargs):
    """安全记录 INFO 日志"""
    safe_log(logging.INFO, msg, *args, **kwargs)


def log_warning(msg: str, *args, **kwargs):
    """安全记录 WARNING 日志"""
    safe_log(logging.WARNING, msg, *args, **kwargs)


def log_error(msg: str, *args, **kwargs):
    """安全记录 ERROR 日志"""
    safe_log(logging.ERROR, msg, *args, **kwargs)


def log_debug(msg: str, *args, **kwargs):
    """安全记录 DEBUG 日志"""
    safe_log(logging.DEBUG, msg, *args, **kwargs)
