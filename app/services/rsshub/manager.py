"""
RSSHub 服务管理器

职责：
- RSSHub 服务生命周期管理（启动/停止/健康检查）
- Docker 可用性检测
- RSSHub 状态管理

单例模式：通过 get_rsshub_manager() 获取全局实例
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class RSSHubStatus(str, Enum):
    """RSSHub 状态枚举"""
    UNKNOWN = "unknown"  # 初始化前
    DOCKER_UNAVAILABLE = "docker_unavailable"  # Docker 未安装
    STARTING = "starting"  # 启动中
    RUNNING = "running"  # 正常运行
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 启动/运行错误
    DISABLED = "disabled"  # 功能已禁用


@dataclass
class RSSHubState:
    """RSSHub 运行时状态"""
    status: RSSHubStatus = RSSHubStatus.UNKNOWN
    docker_available: bool = False
    version: Optional[str] = None
    routes_count: Optional[int] = None
    routes_source: Optional[str] = None  # "live" / "bundled"
    checked_at: Optional[datetime] = None
    last_error: Optional[str] = None


class RSSHubManager:
    """
    RSSHub 服务管理器

    功能：
    - Docker 环境检测
    - RSSHub 服务启动/停止
    - 健康状态检查
    - 状态持久化管理
    """

    def __init__(self):
        self._state = RSSHubState()
        self._settings = get_settings()
        self._health_check_task: Optional[asyncio.Task] = None
        self._compose_command: list[str] = ["docker", "compose"]

    @property
    def state(self) -> RSSHubState:
        """获取当前状态"""
        return self._state

    def is_running(self) -> bool:
        """判断 RSSHub 是否正在运行"""
        return self._state.status == RSSHubStatus.RUNNING

    def is_enabled(self) -> bool:
        """判断 RSSHub 功能是否启用"""
        return self._settings.rsshub_enabled

    # ==================== Docker 可用性检测 ====================

    async def _detect_docker_available(self) -> bool:
        """
        检测 Docker 环境是否可用

        检测步骤：
        1. docker --version - Docker CLI 是否安装
        2. docker compose version - compose 插件检测
        3. docker info - daemon 是否运行

        Returns:
            bool: Docker 环境可用返回 True
        """
        try:
            # 步骤1：检查 Docker CLI
            try:
                await asyncio.create_subprocess_exec(
                    "docker", "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
            except FileNotFoundError:
                logger.warning("Docker CLI 未安装")
                self._state.last_error = "Docker CLI 未安装"
                return False

            # 步骤2：检查 docker compose 插件
            compose_cmd = await self._detect_compose_command()
            if not compose_cmd:
                logger.warning("Docker Compose 不可用")
                self._state.last_error = "Docker Compose 不可用"
                return False

            # 步骤3：检查 Docker daemon
            proc = await asyncio.create_subprocess_exec(
                "docker", "info", "--format", "{{.ServerVersion}}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode != 0:
                logger.warning(f"Docker daemon 未运行: {stderr.decode().strip()}")
                self._state.last_error = "Docker daemon 未运行"
                return False

            logger.info("Docker 环境检测通过")
            return True

        except asyncio.TimeoutError:
            logger.warning("Docker 环境检测超时（5秒）")
            self._state.last_error = "Docker 环境检测超时"
            return False
        except Exception as e:
            logger.warning(f"Docker 环境检测失败: {e}")
            self._state.last_error = str(e)
            return False

    async def _detect_compose_command(self) -> Optional[list[str]]:
        """
        检测可用的 docker compose 命令

        优先级：
        1. docker compose（新版）
        2. docker-compose（旧版）

        Returns:
            list[str] 或 None: 可用的 compose 命令
        """
        # 优先尝试 docker compose
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker", "compose", "version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                self._compose_command = ["docker", "compose"]
                logger.debug("使用 docker compose（新版）")
                return ["docker", "compose"]
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

        # 降级尝试 docker-compose
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker-compose", "--version",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=5.0)
            if proc.returncode == 0:
                self._compose_command = ["docker-compose"]
                logger.debug("使用 docker-compose（旧版）")
                return ["docker-compose"]
        except (FileNotFoundError, asyncio.TimeoutError):
            pass

        return None

    async def pull_image(self) -> tuple[bool, str]:
        """
        拉取 RSSHub 最新镜像

        执行 docker compose -f docker-compose.rsshub.yml pull

        Returns:
            tuple[bool, str]: (成功/失败, 消息)
        """
        try:
            compose_file = "docker-compose.rsshub.yml"
            cmd = self._compose_command + ["-f", compose_file, "pull"]

            logger.info(f"拉取 RSSHub 镜像: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120.0)

            if proc.returncode == 0:
                logger.info("RSSHub 镜像拉取成功")
                return True, "镜像拉取成功"
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"RSSHub 镜像拉取失败: {error_msg}")
                return False, error_msg

        except asyncio.TimeoutError:
            logger.error("RSSHub 镜像拉取超时（120秒）")
            return False, "拉取镜像超时（120秒），请检查网络连接"
        except Exception as e:
            logger.error(f"RSSHub 镜像拉取异常: {e}")
            return False, str(e)

    # ==================== 生命周期管理 ====================

    async def start_rsshub(self) -> bool:
        """
        启动 RSSHub 服务

        执行 docker compose up -d

        Returns:
            bool: 启动成功返回 True
        """
        try:
            compose_file = "docker-compose.rsshub.yml"
            # 确保 compose 命令完整
            cmd = self._compose_command + ["-f", compose_file, "up", "-d"]

            logger.info(f"启动 RSSHub: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode == 0:
                logger.info("RSSHub 启动成功")
                self._state.status = RSSHubStatus.RUNNING
                asyncio.create_task(self._re_enable_rsshub_sources())
                return True
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"RSSHub 启动失败: {error_msg}")
                self._state.last_error = error_msg
                self._state.status = RSSHubStatus.ERROR
                return False

        except asyncio.TimeoutError:
            logger.error("RSSHub 启动超时（30秒）")
            self._state.last_error = "启动超时"
            self._state.status = RSSHubStatus.ERROR
            return False
        except Exception as e:
            logger.error(f"RSSHub 启动异常: {e}")
            self._state.last_error = str(e)
            self._state.status = RSSHubStatus.ERROR
            return False

    async def stop_rsshub(self) -> bool:
        """
        停止 RSSHub 服务

        执行 docker compose down

        Returns:
            bool: 停止成功返回 True
        """
        try:
            compose_file = "docker-compose.rsshub.yml"
            cmd = self._compose_command + ["-f", compose_file, "down"]

            logger.info(f"停止 RSSHub: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode == 0:
                logger.info("RSSHub 停止成功")
                self._state.status = RSSHubStatus.STOPPED
                asyncio.create_task(self._disable_rsshub_sources())
                return True
            else:
                error_msg = stderr.decode().strip()
                logger.error(f"RSSHub 停止失败: {error_msg}")
                self._state.last_error = error_msg
                return False

        except asyncio.TimeoutError:
            logger.error("RSSHub 停止超时（30秒）")
            self._state.last_error = "停止超时"
            return False
        except Exception as e:
            logger.error(f"RSSHub 停止异常: {e}")
            self._state.last_error = str(e)
            return False

    async def update_and_restart(self) -> tuple[bool, str]:
        """
        更新镜像并重启服务

        流程：
        1. docker compose pull
        2. docker compose up -d（自动用新镜像重建容器）
        3. 等待健康检查通过（最多 60s）

        Returns:
            tuple[bool, str]: (成功/失败, 消息)
        """
        try:
            # ① 拉取最新镜像
            success, msg = await self.pull_image()
            if not success:
                return False, f"拉取镜像失败: {msg}"

            # ② 用新镜像启动容器
            compose_file = "docker-compose.rsshub.yml"
            cmd = self._compose_command + ["-f", compose_file, "up", "-d"]

            logger.info(f"用新镜像启动 RSSHub: {' '.join(cmd)}")
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)

            if proc.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"RSSHub 启动失败: {error_msg}")
                self._state.last_error = error_msg
                self._state.status = RSSHubStatus.ERROR
                return False, f"启动失败: {error_msg}"

            # ③ 等待健康检查通过
            logger.info("等待 RSSHub 健康检查通过...")
            for attempt in range(12):
                await asyncio.sleep(5)
                if await self.check_health():
                    logger.info("RSSHub 健康检查通过")
                    self._state.status = RSSHubStatus.RUNNING
                    asyncio.create_task(self._re_enable_rsshub_sources())
                    return True, "更新并重启成功"
                logger.debug(f"健康检查尝试 {attempt + 1}/12")

            logger.error("RSSHub 健康检查超时")
            self._state.last_error = "健康检查超时"
            self._state.status = RSSHubStatus.ERROR
            return False, "服务启动后健康检查未通过"

        except asyncio.TimeoutError:
            logger.error("RSSHub 更新超时")
            self._state.last_error = "更新超时"
            self._state.status = RSSHubStatus.ERROR
            return False, "更新超时"
        except Exception as e:
            logger.error(f"RSSHub 更新异常: {e}")
            self._state.last_error = str(e)
            self._state.status = RSSHubStatus.ERROR
            return False, f"更新异常: {str(e)}"

    async def check_health(self) -> bool:
        """
        检查 RSSHub 健康状态

        向 RSSHub 根路径发送请求，检查是否响应 200

        Returns:
            bool: 健康检查通过返回 True
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._settings.rsshub_url}/")
                if resp.status_code == 200:
                    was_not_running = self._state.status != RSSHubStatus.RUNNING
                    self._state.status = RSSHubStatus.RUNNING
                    self._state.checked_at = datetime.now(timezone.utc)
                    if was_not_running:
                        asyncio.create_task(self._re_enable_rsshub_sources())
                    return True
                return False
        except Exception as e:
            logger.debug(f"RSSHub 健康检查失败: {e}")
            if self._state.status == RSSHubStatus.RUNNING:
                self._state.status = RSSHubStatus.STOPPED
                asyncio.create_task(self._disable_rsshub_sources())
            return False

    # ==================== RSS 源状态联动 ====================

    async def _disable_rsshub_sources(self) -> None:
        """
        RSSHub 停止时，批量禁用 rsshub 类型的活跃源

        将 source_type='rsshub' 且 is_active=True 的源设为 is_active=False, rsshub_unavailable=True
        """
        try:
            from app.database import db
            from app.models import RSSSource, RSSSourceType
            from sqlalchemy import update

            async with db.get_session() as session:
                stmt = (
                    update(RSSSource)
                    .where(
                        RSSSource.source_type == RSSSourceType.RSSHUB.value,
                        RSSSource.is_active == True,
                    )
                    .values(is_active=False, rsshub_unavailable=True)
                )
                result = await session.execute(stmt)
                await session.commit()
                if result.rowcount > 0:
                    logger.info(f"RSSHub 停用：已禁用 {result.rowcount} 个 rsshub 类型 RSS 源")
        except Exception as e:
            logger.error(f"批量禁用 rsshub 源失败: {e}")

    async def _re_enable_rsshub_sources(self) -> None:
        """
        RSSHub 启动时，批量清除 rsshub_unavailable 标记（恢复为可启用状态）

        将 source_type='rsshub' 且 rsshub_unavailable=True 的源的 rsshub_unavailable 设为 False
        不自动启用（is_active 保持原状），由用户手动启用
        """
        try:
            from app.database import db
            from app.models import RSSSource, RSSSourceType
            from sqlalchemy import update

            async with db.get_session() as session:
                stmt = (
                    update(RSSSource)
                    .where(
                        RSSSource.source_type == RSSSourceType.RSSHUB.value,
                        RSSSource.rsshub_unavailable == True,
                    )
                    .values(rsshub_unavailable=False)
                )
                result = await session.execute(stmt)
                await session.commit()
                if result.rowcount > 0:
                    logger.info(f"RSSHub 恢复：已清除 {result.rowcount} 个源的 rsshub_unavailable 标记")
        except Exception as e:
            logger.error(f"批量恢复 rsshub 源失败: {e}")

    async def _trigger_route_sync(self) -> None:
        """
        触发路由同步（异步，不阻塞调用方）

        等待 RSSHub 健康检查通过后执行 force_extract_and_sync()
        """
        try:
            from app.services.rsshub.route_sync import get_route_sync

            for _ in range(12):
                await asyncio.sleep(5)
                if self._state.status == RSSHubStatus.RUNNING:
                    break

            sync = get_route_sync()
            counts, msg = await sync.force_extract_and_sync()
            if counts:
                total = counts.get("inserted", 0) + counts.get("updated", 0) + counts.get("deleted", 0)
                self._state.routes_count = total
                logger.info(
                    f"启动后自动路由同步完成: 新增{counts.get('inserted',0)} "
                    f"更新{counts.get('updated',0)} 删除{counts.get('deleted',0)}"
                )
        except Exception as e:
            logger.error(f"启动后自动路由同步失败: {e}")

    # ==================== 初始化和后台任务 ====================

    async def initialize(self) -> None:
        """
        初始化 RSSHub 管理器

        流程：
        1. 检查功能是否启用
        2. 先检查 RSSHub 是否已在运行（HTTP 健康检查）
        3. 如果已运行 → 跳过 Docker 检测，直接标记 RUNNING
        4. 如果未运行 → 检测 Docker 环境 → 自动启动（如果启用）
        5. 启动健康检查后台任务

        不阻塞 FastAPI 启动
        """
        # 1. 检查功能是否启用
        if not self._settings.rsshub_enabled:
            logger.info("RSSHub 功能已禁用")
            self._state.status = RSSHubStatus.DISABLED
            return

        # 2. 先检查 RSSHub 是否已经在运行（被 compose --profile 或手动启动）
        if await self.check_health():
            logger.info("检测到 RSSHub 已在运行，跳过自动启动")
            self._state.docker_available = True  # 能访问说明网络可达
            # 健康检查后台任务会在下面启动
        else:
            # 3. RSSHub 未运行，检测 Docker 环境
            docker_available = await self._detect_docker_available()
            self._state.docker_available = docker_available

            if not docker_available:
                logger.warning("Docker 环境不可用，RSSHub 功能受限")
                self._state.status = RSSHubStatus.DOCKER_UNAVAILABLE
            elif self._settings.rsshub_auto_start:
                # 4. 自动启动
                logger.info("自动启动 RSSHub...")
                self._state.status = RSSHubStatus.STARTING
                await self.start_rsshub()

        # 5. 启动健康检查后台任务
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("RSSHub 健康检查任务已启动")

        # 6. 启动首次路由同步任务（延迟执行，不阻塞）
        asyncio.create_task(self._initial_route_sync())

    async def _health_check_loop(self) -> None:
        """
        健康检查后台循环

        每隔 rsshub_health_check_interval 秒执行一次健康检查
        """
        interval = self._settings.rsshub_health_check_interval
        logger.info(f"RSSHub 健康检查循环启动（间隔 {interval} 秒）")

        while True:
            try:
                await asyncio.sleep(interval)

                # 跳过已禁用/已停止以外的状态检查
                # DOCKER_UNAVAILABLE 也要检查（用户可能外部启动了 RSSHub）
                if self._state.status == RSSHubStatus.DISABLED:
                    continue

                # 执行健康检查
                is_healthy = await self.check_health()
                if is_healthy:
                    logger.debug("RSSHub 健康检查通过")
                else:
                    logger.warning("RSSHub 健康检查失败")

            except asyncio.CancelledError:
                logger.info("RSSHub 健康检查循环已取消")
                break
            except Exception as e:
                logger.error(f"RSSHub 健康检查循环异常: {e}")

    async def _initial_route_sync(self) -> None:
        """
        首次路由同步

        等待 RSSHub 健康检查通过后执行同步
        最多等待 rsshub_startup_timeout 秒
        """
        logger.info("等待 RSSHub 就绪以执行路由同步...")

        max_wait = self._settings.rsshub_startup_timeout
        check_interval = min(30, max_wait)
        max_attempts = max_wait // check_interval

        for attempt in range(max_attempts):
            await asyncio.sleep(check_interval)

            if self._state.status == RSSHubStatus.RUNNING:
                logger.info("RSSHub 已就绪，执行路由同步")
                try:
                    from app.services.rsshub.route_sync import get_route_sync
                    sync = get_route_sync()
                    # T-3: 提前尝试从容器提取 routes.json（如果宿主主机还没有）
                    # 这样可以避免首次同步时的 FileNotFoundError 日志噪音
                    if not os.path.exists(sync._host_path):
                        logger.info("宿主机无 routes.json，尝试从容器提取...")
                        sync._extract_from_container()
                    count = await sync.sync_if_needed()
                    if count >= 0:
                        self._state.routes_count = count
                        # 判断数据来源
                        source_path = sync._resolve_source_path()
                        self._state.routes_source = "bundled" if "static" in source_path else "live"
                        logger.info(f"路由同步完成，来源: {self._state.routes_source}，条数: {count}")
                except Exception as e:
                    logger.error(f"路由同步失败: {e}")
                return

        logger.warning(f"RSSHub 等待超时（{max_wait}秒），跳过路由同步")


# ==================== 全局单例 ====================

_rsshub_manager: Optional[RSSHubManager] = None


def get_rsshub_manager() -> RSSHubManager:
    """
    获取 RSSHub 管理器全局单例

    Returns:
        RSSHubManager: 全局单例实例
    """
    global _rsshub_manager
    if _rsshub_manager is None:
        _rsshub_manager = RSSHubManager()
    return _rsshub_manager
