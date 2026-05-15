# -*- coding: utf-8 -*-
"""
Git 和 Obsidian 连接测试工具函数

抽离连接测试逻辑，避免重复代码，并在保存配置时进行验证
"""

import re
from typing import Tuple, Optional

import httpx

from app.config import get_settings


async def test_git_connection(
    repo_url: str,
    access_token: str,
    branch: str = "main",
    credential_type: str = "deploy_token"
) -> Tuple[bool, str, dict]:
    """
    测试 Git 仓库连接

    Args:
        repo_url: Git 仓库地址
        access_token: 访问令牌
        branch: 分支名
        credential_type: 凭证类型

    Returns:
        Tuple[bool, str, dict]: (是否成功, 消息, 详细信息)
    """
    # 解析仓库信息
    git_host = None
    owner = None
    repo = None

    # 处理 SSH 格式
    if repo_url.startswith("git@"):
        match = re.match(r'git@([^:]+):(.+?)(?:\.git)?$', repo_url)
        if match:
            git_host = match.group(1)
            path = match.group(2)
            parts = path.split('/')
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].replace('.git', '')
    else:
        # 处理 HTTPS 格式
        match = re.match(r'https?://([^/]+)/(.+?)(?:\.git)?$', repo_url)
        if match:
            git_host = match.group(1)
            path = match.group(2)
            parts = path.split('/')
            if len(parts) >= 2:
                owner = parts[0]
                repo = parts[1].replace('.git', '')

    if not all([git_host, owner, repo]):
        return False, f"无法解析 Git 仓库地址: {repo_url}", {}

    # 构建 API 请求
    git_host_str = str(git_host) if git_host else ""
    settings = get_settings()
    if "gitee.com" in git_host_str:
        base_url = f"https://gitee.com/api/v5/repos/{owner}/{repo}"
    else:
        base_url = f"{settings.github_api_base_url}/repos/{owner}/{repo}"

    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(base_url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                return True, f"连接成功: {data.get('full_name', repo)}", {
                    "repo": data.get('full_name'),
                    "branch": branch,
                    "default_branch": data.get('default_branch'),
                    "private": data.get('private'),
                }
            elif resp.status_code == 401:
                return False, "认证失败：访问令牌无效或已过期", {}
            elif resp.status_code == 404:
                return False, "仓库不存在或无权访问", {}
            else:
                return False, f"连接失败: HTTP {resp.status_code}", {"error": resp.text[:500]}
    except httpx.TimeoutException:
        return False, "请求超时，请检查网络连接", {}
    except Exception as e:
        return False, f"连接异常: {str(e)}", {}


async def test_obsidian_local_connection(
    api_url: str,
    api_key: str,
    vault_path: str,
    verify_ssl: bool = True
) -> Tuple[bool, str, dict]:
    """
    测试 Obsidian Local REST API 连接

    Args:
        api_url: Obsidian API 地址
        api_key: API 密钥
        vault_path: Vault 路径
        verify_ssl: 是否验证 SSL

    Returns:
        Tuple[bool, str, dict]: (是否成功, 消息, 详细信息)
    """
    api_url = api_url.rstrip('/')
    url = f"{api_url}/vault/"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                headers=headers,
                verify=verify_ssl
            )
            if resp.status_code == 200:
                data = resp.json()
                return True, f"连接成功: Vault={data.get('vault', vault_path)}", {
                    "vault": data.get('vault', vault_path),
                    "root": data.get('root', ''),
                }
            elif resp.status_code == 401:
                return False, "认证失败：API Key 无效或已过期", {}
            elif resp.status_code == 404:
                return False, "Obsidian Local REST API 插件未启用或 API 地址错误", {}
            else:
                return False, f"连接失败: HTTP {resp.status_code}", {"error": resp.text[:500]}
    except httpx.ConnectError:
        return False, "无法连接到 Obsidian API，请检查 API 地址是否正确", {}
    except httpx.TimeoutException:
        return False, "请求超时，请检查 Obsidian 是否正在运行", {}
    except Exception as e:
        return False, f"连接异常: {str(e)}", {}