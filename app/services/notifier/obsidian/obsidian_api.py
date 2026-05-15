# -*- coding: utf-8 -*-
"""
Obsidian API 本地模式通知器

通过 Obsidian Local REST API 推送文件到本地 Vault

前置条件：
- Obsidian Local REST API 插件已安装并启用
- 插件设置中已生成 API Key

使用方式：
1. 配置 ObsidianConfig（API URL、API Key、Vault Path）
2. 使用 @register_notifier("obsidian") 注册
3. 调用 send() 方法推送内容
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

import aiohttp
from app.models import WebhookConfig
from app.services.notifier.dynamic_base import BaseDynamicNotifier, register_notifier
from app.services.notifier.obsidian.obsidian_base import (
    compute_file_hash,
    generate_daily_filename,
    generate_weekly_filename,
    generate_immediate_filename,
    get_folder_for_push_type,
    check_file_exists_in_vault,
    record_vault_file,
)

logger = logging.getLogger(__name__)

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒
RETRY_BACKOFF = 2  # 指数退避因子
MAX_DELETE_RETRY = 2  # 409冲突时最大删除重试次数


@register_notifier("obsidian_local")
class DynamicObsidianAPINotifier(BaseDynamicNotifier):
    """
    Obsidian API 本地模式通知器

    适用于 Bot 部署在本地机器，可以直接访问 Obsidian Vault 的场景
    """

    platform_name = "obsidian_local"

    def _init_notifier(self) -> None:
        """初始化 Obsidian API 配置"""
        config = self.webhook_config.obsidian_config
        if not config:
            self._is_configured = False
            logger.warning(f"Webhook {self.webhook_config.id} 缺少 Obsidian API 配置")
            return

        self.api_url = config.api_url.rstrip('/')
        # 需要解密存储的 api_key
        from app.utils.crypto import decrypt_api_key
        self.api_key = decrypt_api_key(config.api_key, raise_on_error=False)
        self.vault_path = config.vault_path
        self.daily_folder = config.daily_folder or "AI-News/Daily"
        self.weekly_folder = config.weekly_folder or "AI-News/Weekly"
        self.immediate_folder = config.immediate_folder or "AI-News/Immediate"
        self.verify_ssl = config.verify_ssl

    def _check_configured(self) -> bool:
        """检查 API 配置是否完整"""
        # 注意：这里直接访问 webhook_config.obsidian_config，因为 _init_notifier() 还没被调用
        config = self.webhook_config.obsidian_config
        if not config:
            return False
        # 检查必要字段是否存在（api_key 是否加密需要在解密后检查）
        if not config.api_url or not config.vault_path:
            return False
        # api_key 是加密存储的，需要解密后检查是否有效
        from app.utils.crypto import decrypt_api_key
        try:
            decrypted_key = decrypt_api_key(config.api_key, raise_on_error=False)
            return bool(decrypted_key)
        except Exception:
            return False

    async def send(self, content: str, msg_type: str = "text", **kwargs) -> bool:
        """
        发送内容到 Obsidian Vault

        Args:
            content: 文件内容
            msg_type: 消息类型（仅支持 markdown/text）
            **kwargs: 额外参数
                - push_type: 推送类型 (daily/weekly/immediate)
                - file_name: 自定义文件名

        Returns:
            bool: 是否发送成功
        """
        if not self._is_configured:
            logger.error(f"Obsidian API 未配置或配置不完整")
            return False

        push_type = kwargs.get("push_type", "daily")
        custom_filename = kwargs.get("file_name")

        # 生成文件名
        if custom_filename:
            filename = f"{custom_filename}-{datetime.now().strftime('%Y-%m-%d')}.md"
        elif push_type == "weekly":
            week_start = kwargs.get("week_start", datetime.now().strftime("%Y-%m-%d"))
            week_end = kwargs.get("week_end", datetime.now().strftime("%Y-%m-%d"))
            filename = generate_weekly_filename(week_start, week_end)
        elif push_type == "immediate":
            title = kwargs.get("title") or ""
            filename = generate_immediate_filename(title)
        else:
            filename = generate_daily_filename()

        # 获取文件夹路径
        folder = get_folder_for_push_type(
            push_type,
            self.daily_folder,
            self.weekly_folder,
            self.immediate_folder
        )

        # 完整文件路径
        file_path = f"{folder}/{filename}" if folder else filename

        # 计算内容哈希
        content_hash = compute_file_hash(content)

        # 检查是否已推送过（去重）
        if await check_file_exists_in_vault(self.webhook_config.id, file_path, content_hash):
            logger.info(f"文件已存在（内容相同），跳过推送: {file_path}")
            return True

        # 调用实际写入逻辑（带重试）
        return await self._do_write(file_path, content, content_hash, msg_type, push_type)

    async def _do_write(self, file_path: str, content: str, content_hash: str,
                       msg_type: str, push_type: str) -> bool:
        """
        执行实际的写入逻辑（带重试机制）

        Args:
            file_path: 文件路径（相对于 vault）
            content: 文件内容
            content_hash: 内容哈希（用于去重记录）
            msg_type: 消息类型
            push_type: 推送类型

        Returns:
            bool: 是否写入成功
        """
        # 构建完整的 API URL
        # 路径需要 URL 编码
        from urllib.parse import quote
        encoded_path = quote(file_path)
        # 注意：文件路径不能有尾随斜杠，否则 Obsidian API 会认为是目录而不是文件
        url = f"{self.api_url}/vault/{encoded_path}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "text/markdown" if msg_type == "markdown" else "text/plain",
        }

        # 重试循环
        for attempt in range(MAX_RETRIES):
            try:
                result = await self._do_push(
                    url, headers, content, file_path, content_hash, push_type
                )
                if result is True:
                    return True
                # 如果明确失败（返回 False），不重试
                if result is False:
                    return False
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    logger.warning(
                        f"Obsidian API 推送失败 (尝试 {attempt + 1}/{MAX_RETRIES}), "
                        f"{wait_time}s 后重试: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Obsidian API 推送最终失败: {e}")
            except Exception as e:
                logger.error(f"Obsidian API 推送异常: {e}")
                return False

        return False

    async def _do_push(self, url: str, headers: dict, content: str,
                      file_path: str, content_hash: str, push_type: str) -> bool:
        """
        执行单次写入操作

        Returns:
            bool: True 表示成功，False 表示明确失败
        """
        try:
            async with aiohttp.ClientSession() as session:
                async with session.put(
                    url,
                    data=content.encode('utf-8'),
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=None if self.verify_ssl else False
                ) as resp:
                    if resp.status in (200, 201, 204):
                        logger.info(f"Obsidian 文件写入成功: {file_path}")

                        # 记录推送历史（用于去重）
                        await record_vault_file(self.webhook_config.id, file_path, content_hash, push_type)

                        return True
                    elif resp.status == 409:
                        # 文件已存在，需要先删除再写入
                        for retry_count in range(MAX_DELETE_RETRY):
                            logger.info(f"文件已存在，尝试删除 (重试 {retry_count + 1}/{MAX_DELETE_RETRY}): {file_path}")
                            if await self._delete_file(file_path):
                                # 再次尝试写入
                                delete_success = await self._write_file_single(
                                    session, url, headers, content, file_path, content_hash, push_type
                                )
                                if delete_success:
                                    return True
                            else:
                                logger.warning(f"删除文件失败: {file_path}")
                                break
                        logger.error(f"文件删除后仍无法写入: {file_path}")
                        return False
                    else:
                        error_text = await resp.text()
                        logger.error(f"Obsidian API 写入失败: HTTP {resp.status} - {error_text}")
                        return False

        except asyncio.TimeoutError:
            logger.error(f"Obsidian API 请求超时: {file_path}")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Obsidian API 连接错误: {e}")
            raise

    async def _write_file_single(self, session, url: str, headers: dict,
                                  content: str, file_path: str,
                                  content_hash: str, push_type: str) -> bool:
        """
        执行单次写入操作（供重试时调用）

        Args:
            session: aiohttp ClientSession
            url: 请求 URL
            headers: 请求头
            content: 文件内容
            file_path: 文件路径
            content_hash: 内容哈希
            push_type: 推送类型

        Returns:
            bool: 是否写入成功
        """
        try:
            async with session.put(
                url,
                data=content.encode('utf-8'),
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30),
                ssl=None if self.verify_ssl else False
            ) as resp:
                if resp.status in (200, 201, 204):
                    logger.info(f"Obsidian 文件写入成功（重试后）: {file_path}")

                    # 记录推送历史（用于去重）
                    await record_vault_file(self.webhook_config.id, file_path, content_hash, push_type)

                    return True
                elif resp.status == 409:
                    logger.warning(f"重试后仍遇到 409: {file_path}")
                    return False
                else:
                    error_text = await resp.text()
                    logger.error(f"Obsidian API 写入失败: HTTP {resp.status} - {error_text}")
                    return False
        except Exception as e:
            logger.error(f"重试写入异常: {e}")
            return False

    async def _delete_file(self, file_path: str) -> bool:
        """
        通过 Obsidian Local REST API 删除文件

        API 端点：DELETE /vault/{path}

        Args:
            file_path: 文件路径（相对于 vault）

        Returns:
            bool: 是否删除成功
        """
        from urllib.parse import quote
        encoded_path = quote(file_path)
        url = f"{self.api_url}/vault/{encoded_path}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                    ssl=None if self.verify_ssl else False
                ) as resp:
                    if resp.status in (200, 204):
                        logger.info(f"Obsidian 文件删除成功: {file_path}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Obsidian API 删除失败: HTTP {resp.status} - {error_text}")
                        return False

        except Exception as e:
            logger.error(f"Obsidian API 删除异常: {e}")
            return False

    async def test_connection(self) -> dict:
        """
        测试 Obsidian API 连接

        Returns:
            dict: 测试结果 {
                "success": bool,
                "message": str,
                "details": dict
            }
        """
        if not self._is_configured:
            return {
                "success": False,
                "message": "Obsidian API 配置不完整",
                "details": {}
            }

        # 测试 API 连接 - 获取 vault 信息
        url = f"{self.api_url}/vault"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                    ssl=None if self.verify_ssl else False
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return {
                            "success": True,
                            "message": f"连接成功: Vault={data.get('vault', self.vault_path)}",
                            "details": {
                                "vault": data.get('vault', self.vault_path),
                                "root": data.get('root', ''),
                            }
                        }
                    else:
                        error_text = await resp.text()
                        return {
                            "success": False,
                            "message": f"连接失败: HTTP {resp.status}",
                            "details": {"error": error_text[:500]}
                        }
        except Exception as e:
            return {
                "success": False,
                "message": f"连接异常: {str(e)}",
                "details": {}
            }