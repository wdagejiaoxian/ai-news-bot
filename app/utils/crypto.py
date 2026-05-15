# -*- coding: utf-8 -*-
"""
加密工具模块
提供可逆加密功能用于敏感数据存储
"""

import base64
import logging
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class DecryptionError(Exception):
    """解密失败异常"""
    pass


class EncryptionError(Exception):
    """加密失败异常"""
    pass


def _get_encryption_key() -> bytes:
    """
    获取加密密钥

    使用 secret_key 生成 32 字节的 AES-256 密钥
    """
    from app.config import get_settings
    settings = get_settings()
    key = settings.secret_key
    # 确保密钥长度足够，使用 SHA256 哈希
    import hashlib
    return hashlib.sha256(key.encode()).digest()


def encrypt_api_key(plain_key: str) -> str:
    """
    使用 AES-256-GCM 加密 API Key

    Args:
        plain_key: 明文 API Key

    Returns:
        Base64 编码的加密字符串 (IV + 密文 + Tag)

    Raises:
        EncryptionError: 加密失败时抛出
    """
    if not plain_key:
        return plain_key

    try:
        key = _get_encryption_key()
        iv = os.urandom(12)  # GCM 模式推荐 12 字节 IV

        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv),
            backend=default_backend()
        )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plain_key.encode('utf-8')) + encryptor.finalize()

        # 合并 IV + 密文 + authentication tag
        encrypted = iv + ciphertext + encryptor.tag

        # Base64 编码
        result = base64.b64encode(encrypted).decode('utf-8')
        logger.debug("API Key 加密成功")
        return result
    except Exception as e:
        logger.error(f"API Key 加密失败: {e}")
        raise EncryptionError(f"加密失败: {e}") from e


def decrypt_api_key(encrypted_key: str, raise_on_error: bool = False) -> str:
    """
    解密 API Key

    Args:
        encrypted_key: Base64 编码的加密字符串
        raise_on_error: 是否在解密失败时抛出异常，默认 False（返回原文以保持兼容性）

    Returns:
        明文 API Key

    Raises:
        DecryptionError: 解密失败且 raise_on_error=True 时抛出
    """
    if not encrypted_key:
        return encrypted_key

    try:
        # Base64 解码
        encrypted = base64.b64decode(encrypted_key.encode('utf-8'))

        # 分离 IV (12字节) + Tag (16字节) + 密文
        iv = encrypted[:12]
        tag = encrypted[-16:]
        ciphertext = encrypted[12:-16]

        key = _get_encryption_key()

        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(iv, tag),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        logger.debug("API Key 解密成功")
        return plaintext.decode('utf-8')

    except DecryptionError:
        # 已经是 DecryptionError，直接重新抛出
        raise
    except Exception as e:
        error_msg = f"API Key 解密失败: {e}"

        if raise_on_error:
            logger.error(error_msg)
            raise DecryptionError(error_msg) from e
        else:
            # 兼容模式：记录警告但仍返回原文
            # 注意：这可能导致安全问题，仅用于兼容旧数据
            logger.warning(
                f"{error_msg}。返回原文（可能存在安全风险），"
                f"请尽快更新密钥配置"
            )
            return encrypted_key
