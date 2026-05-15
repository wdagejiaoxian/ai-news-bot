# -*- coding: utf-8 -*-
"""
Obsidian Git 远程模式通知器

通过 Git 仓库推送文件到 Obsidian Vault

支持的平台：
- GitHub
- Gitee
- 其他 Git 平台

使用方式：
1. 配置 GitRepoConfig（仓库URL、Branch、Access Token）
2. 使用 @register_notifier("obsidian") 注册
3. 调用 send() 方法推送内容
"""

import asyncio
import logging
import re
from asyncio import Semaphore
from datetime import datetime
from typing import Optional

import aiohttp
from app.config import get_settings
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

# 平台常量
PLATFORM_GITHUB = "github"
PLATFORM_GITEE = "gitee"
PLATFORM_OTHER = "other"

# 重试配置
MAX_RETRIES = 3
RETRY_DELAY = 1  # 秒
RETRY_BACKOFF = 2  # 指数退避因子

# 并发限流配置
MAX_CONCURRENT_PUSH = 5  # 最多5个并发推送请求


@register_notifier("git")
class DynamicObsidianGitNotifier(BaseDynamicNotifier):
    """
    Obsidian Git 远程模式通知器

    适用于 Bot 部署在云端，需要通过 Git 推送文件的场景
    """

    platform_name = "git"

    # 类级别信号量，用于限制并发推送数
    _semaphore = Semaphore(MAX_CONCURRENT_PUSH)

    @staticmethod
    def _mask_token(token: str) -> str:
        """脱敏 Token 用于日志输出"""
        if len(token) <= 8:
            return "***"
        return f"{token[:4]}...{token[-4:]}"

    def _init_notifier(self) -> None:
        """初始化 Git 配置"""
        config = self.webhook_config.git_repo_config
        if not config:
            self._is_configured = False
            logger.warning(f"Webhook {self.webhook_config.id} 缺少 Git 配置")
            return

        self.repo_url = config.repo_url
        self.branch = config.branch or "main"
        # 需要解密存储的 access_token
        from app.utils.crypto import decrypt_api_key
        self.access_token = decrypt_api_key(config.access_token, raise_on_error=False)
        self.credential_type = config.credential_type or "deploy_token"
        self.author_name = config.author_name or "AI News Bot"
        self.author_email = config.author_email or ""
        self.daily_folder = config.daily_folder or "Daily"
        self.weekly_folder = config.weekly_folder or "Weekly"
        self.immediate_folder = config.immediate_folder or "Immediate"

        # 解析仓库信息
        self._parse_repo_info()

    def _parse_repo_info(self) -> None:
        """
        解析仓库 URL 获取平台信息

        支持：
        - https://github.com/user/repo
        - https://gitee.com/user/repo
        - git@github.com:user/repo.git
        """
        url = self.repo_url

        # 处理 SSH 格式
        if url.startswith("git@"):
            match = re.match(r'git@([^:]+):(.+?)(?:\.git)?$', url)
            if match:
                host, path = match.groups()
                self.git_host = host
                self.owner, self.repo = path.split('/')
                return

        # 处理 HTTPS 格式
        match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', url)
        if match:
            self.git_host = match.group(1)
            path = match.group(2)
            parts = path.split('/')
            if len(parts) >= 2:
                self.owner = parts[0]
                self.repo = parts[1].replace('.git', '')
            else:
                self.owner = ""
                self.repo = path
        else:
            logger.error(f"无法解析 Git 仓库 URL: {url}")
            self._is_configured = False

        # 检测平台类型
        self.platform = self._detect_platform(self.git_host)
        self.is_gitee = self.platform == PLATFORM_GITEE
        self.is_github = self.platform == PLATFORM_GITHUB

    def _detect_platform(self, git_host: str) -> str:
        """
        检测 Git 平台类型

        Args:
            git_host: Git 主机地址

        Returns:
            str: 平台类型 (github/gitee/other)
        """
        git_host_lower = git_host.lower()
        if "github" in git_host_lower:
            return PLATFORM_GITHUB
        elif "gitee" in git_host_lower:
            return PLATFORM_GITEE
        else:
            return PLATFORM_OTHER

    def _check_configured(self) -> bool:
        """检查 Git 配置是否完整"""
        # 关键修复：obsidian_git 平台不使用 webhook_key，而是使用 git_repo_config 中的 access_token
        # 因此需要检查 git_repo_config 是否存在且有有效的 access_token
        config = self.webhook_config.git_repo_config
        if not config:
            return False
        # 检查必要的配置项
        return bool(config.repo_url and config.access_token)

    async def send(self, content: str, msg_type: str = "text", **kwargs) -> bool:
        """
        发送内容到 Git 仓库

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
            logger.error(f"Git 未配置或配置不完整")
            return False

        push_type = kwargs.get("push_type", "daily")
        custom_filename = kwargs.get("file_name")

        # 生成文件名
        if custom_filename:
            filename = f"{custom_filename}-{datetime.now().strftime('%Y-%m-%d')}.md"
        elif push_type == "weekly":
            # 周报需要 week_start 和 week_end
            week_start = kwargs.get("week_start", datetime.now().strftime("%Y-%m-%d"))
            week_end = kwargs.get("week_end", datetime.now().strftime("%Y-%m-%d"))
            filename = generate_weekly_filename(week_start, week_end)
        elif push_type == "immediate":
            title = kwargs.get("title")
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

        # 使用信号量限制并发推送数
        async with self._semaphore:
            # 调用实际发送逻辑（带重试）
            return await self._do_send(content, file_path, filename, push_type, content_hash)

    async def _do_send(self, content: str, file_path: str, filename: str,
                       push_type: str, content_hash: str) -> bool:
        """
        执行实际的发送逻辑（带重试机制）

        Args:
            content: 文件内容
            file_path: 完整文件路径
            filename: 文件名
            push_type: 推送类型
            content_hash: 内容哈希

        Returns:
            bool: 是否发送成功
        """
        # 构建 API 请求
        api_path = f"repos/{self.owner}/{self.repo}/contents/{file_path}"
        settings = get_settings()

        if self.is_gitee:
            base_url = f"https://gitee.com/api/v5/{api_path}"
        else:
            base_url = f"{settings.github_api_base_url}/{api_path}"

        headers = {
            "Authorization": f"token {self.access_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }

        # 重试循环
        for attempt in range(MAX_RETRIES):
            try:
                result = await self._do_push(
                    content, file_path, filename, push_type, content_hash,
                    base_url, headers
                )
                if result is True:
                    return True
                # 如果明确失败（返回 False），不重试
                if result is False:
                    return False
                # 如果返回 "retry"，继续重试
            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                if attempt < MAX_RETRIES - 1:
                    wait_time = RETRY_DELAY * (RETRY_BACKOFF ** attempt)
                    logger.warning(
                        f"Git 推送失败 (尝试 {attempt + 1}/{MAX_RETRIES}), "
                        f"{wait_time}s 后重试: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Git 推送最终失败: {e}")
            except Exception as e:
                logger.error(f"Git 推送异常: {e}")
                return False

        return False

    async def _do_push(self, content: str, file_path: str, filename: str,
                       push_type: str, content_hash: str,
                       base_url: str, headers: dict) -> bool | str:
        """
        执行单次推送操作

        Returns:
            bool | str: True 表示成功，False 表示明确失败，"retry" 表示需要重试
        """
        import base64

        try:
            async with aiohttp.ClientSession() as session:
                # 1. 先尝试获取现有文件信息（用于更新）
                get_url = f"{base_url}?ref={self.branch}"
                existing_sha = None

                async with session.get(get_url, headers=headers, timeout=10) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        # 防御性处理：检查响应类型
                        if isinstance(data, list):
                            existing_sha = data[0].get("sha") if data else None
                            logger.info(f"文件已存在（列表格式）: {file_path}, SHA: {existing_sha}")
                        else:
                            existing_sha = data.get("sha")
                            logger.info(f"文件已存在，将更新: {file_path}, SHA: {existing_sha}")
                    elif resp.status == 404:
                        logger.info(f"文件不存在，将创建新文件: {file_path}")
                    else:
                        logger.warning(f"获取文件信息失败: HTTP {resp.status}")

                # 2. 提交文件
                commit_message = f"Update {filename} - AI News Bot {datetime.now().strftime('%Y-%m-%d %H:%M')}"

                # Gitee API 要求：
                # - 创建新文件：POST，不需要 sha（或 sha=null）
                # - 更新文件：PUT，必须提供 sha
                # GitHub API：
                # - 创建新文件：PUT，不需要 sha
                # - 更新文件：PUT，必须提供 sha
                # 注意：content 必须使用 Base64 编码
                encoded_content = base64.b64encode(content.encode('utf-8')).decode('utf-8')

                payload = {
                    "message": commit_message,
                    "content": encoded_content,
                    "branch": self.branch
                }

                if self.is_gitee:
                    # Gitee: 始终需要 sha，新文件用 null
                    payload["sha"] = existing_sha or ""
                    method = "post" if not existing_sha else "put"
                    http_method = session.post if method == "post" else session.put
                    request_url = base_url
                else:
                    # GitHub: 有 sha 就传，没有就不传
                    if existing_sha:
                        payload["sha"] = existing_sha
                    http_method = session.put
                    request_url = base_url

                async with http_method(request_url, json=payload, headers=headers, timeout=10) as resp:
                    if resp.status in (200, 201):
                        data = await resp.json()
                        # 验证响应包含有效的 commit
                        commit_sha = None
                        if isinstance(data, list):
                            commit_sha = data[0].get("commit", {}).get("sha") if data else None
                        else:
                            commit_sha = data.get("commit", {}).get("sha")

                        if commit_sha:
                            logger.info(f"文件推送成功: {file_path}, Commit: {commit_sha}")
                            # 记录推送历史（用于去重）
                            await record_vault_file(self.webhook_config.id, file_path, content_hash, push_type)
                            return True
                        else:
                            logger.warning(f"推送响应缺少 commit 信息: {data}")
                            return False
                    elif resp.status == 409:
                        # 冲突，需要删除后重试
                        return "retry"
                    else:
                        error_text = await resp.text()
                        logger.error(f"文件推送失败: {resp.status} - {error_text}")
                        return False

        except asyncio.TimeoutError:
            logger.error(f"Git API 请求超时: {file_path}")
            raise
        except aiohttp.ClientError as e:
            logger.error(f"Git API 客户端错误: {e}")
            raise
        except Exception as e:
            logger.error(f"Git 推送异常: {e}")
            raise

    async def test_connection(self) -> dict:
        """
        测试 Git 连接

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
                "message": "Git 配置不完整",
                "details": {}
            }

        # 调用 connection_tester 中的统一实现，消除代码重复
        from app.services.notifier.obsidian.connection_tester import test_git_connection
        success, message, details = await test_git_connection(
            repo_url=self.repo_url,
            access_token=self.access_token,
            branch=self.branch,
            credential_type=self.credential_type,
        )
        return {
            "success": success,
            "message": message,
            "details": details
        }
