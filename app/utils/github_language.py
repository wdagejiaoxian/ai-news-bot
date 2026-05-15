# -*- coding: utf-8 -*-
"""
GitHub 语言名称标准化工具
"""


def normalize_language_name(language_name: str) -> str:
    """
    将语言名称标准化为首字母大写形式

    Args:
        language_name: 语言名称

    Returns:
        str: 首字母大写形式的语言名称
    """
    return language_name.capitalize()