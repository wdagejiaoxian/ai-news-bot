# -*- coding: utf-8 -*-
"""
系统配置加密工具模块

提供系统配置特有的加解密能力，复用 app.utils.crypto 中已有的
AES-256-GCM 加密实现，增加 ENC: 前缀标记便于判断值是否已加密。

使用方式：
    from app.utils.config_crypto import encrypt_config_value, decrypt_config_value

    # 加密
    encrypted = encrypt_config_value("ghp_xxxxx")
    # -> "ENC:base64(iv+ciphertext+tag)"

    # 解密
    plain = decrypt_config_value("ENC:base64(...)")
    # -> "ghp_xxxxx"

    # 判断是否已加密
    is_encrypted_value("ENC:base64(...)")  # -> True
    is_encrypted_value("plain_text")       # -> False
"""

import logging

from app.utils.crypto import encrypt_api_key, decrypt_api_key, EncryptionError, DecryptionError

logger = logging.getLogger(__name__)

ENC_PREFIX = "ENC:"


def encrypt_config_value(plain_value: str) -> str:
    """
    加密配置值

    使用 AES-256-GCM 加密，并在结果前添加 ENC: 前缀标记。
    空字符串直接返回（不加密）。

    Args:
        plain_value: 明文配置值

    Returns:
        加密后的字符串，格式为 "ENC:base64(iv+ciphertext+tag)"

    Raises:
        EncryptionError: 加密失败
    """
    if not plain_value:
        return plain_value

    try:
        encrypted = encrypt_api_key(plain_value)
        result = f"{ENC_PREFIX}{encrypted}"
        logger.debug("配置值加密成功")
        return result
    except EncryptionError:
        raise
    except Exception as e:
        logger.error(f"配置值加密失败: {e}")
        raise EncryptionError(f"配置加密失败: {e}") from e


def decrypt_config_value(stored_value: str) -> str:
    """
    解密配置值

    检测 ENC: 前缀，有则解密，无则返回原文（兼容未加密的旧值）。

    Args:
        stored_value: 数据库中存储的值

    Returns:
        明文字符串

    Raises:
        DecryptionError: 加密值解密失败时抛出
    """
    if not stored_value:
        return stored_value

    if not stored_value.startswith(ENC_PREFIX):
        # 无前缀标记 → 明文存储（兼容旧数据）
        return stored_value

    try:
        encrypted_part = stored_value[len(ENC_PREFIX):]
        plain = decrypt_api_key(encrypted_part, raise_on_error=True)
        logger.debug("配置值解密成功")
        return plain
    except DecryptionError:
        raise
    except Exception as e:
        logger.error(f"配置值解密失败: {e}")
        raise DecryptionError(f"配置解密失败: {e}") from e


def is_encrypted_value(stored_value: str) -> bool:
    """
    判断数据库中的配置值是否为加密格式

    通过检测 ENC: 前缀做快速判断。

    Args:
        stored_value: 数据库中存储的值

    Returns:
        True 表示已加密，False 表示明文
    """
    if not stored_value:
        return False
    return stored_value.startswith(ENC_PREFIX)


def ensure_decrypted(stored_value: str) -> str:
    """
    确保返回明文（兼容加密/明文两种状态）

    与 decrypt_config_value 的区别：解密失败时不抛异常，降级返回原文。

    Args:
        stored_value: 数据库中存储的值

    Returns:
        明文字符串（解密失败时返回原值）
    """
    try:
        return decrypt_config_value(stored_value)
    except (DecryptionError, Exception) as e:
        logger.warning(f"配置值解密降级（返回原文）: {e}")
        return stored_value
