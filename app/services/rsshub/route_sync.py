"""
RSSHub 路由增量同步服务

功能：
- 增量同步 routes.json 到数据库
- mtime 检测避免无变化时的重复解析
- 软删除已移除的路由
- 数据源降级（卷挂载文件 > 静态副本）

单例模式：通过 get_route_sync() 获取全局实例
"""

import logging
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import select, update as sql_update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import db
from app.models import RSSHubRoute
from app.services.rsshub.route_parser import ParsedRoute, parse_routes_json_file

logger = logging.getLogger(__name__)

# ===== 复合唯一键类型 =====
RouteKey = tuple[str, str]


def _make_key(route: dict) -> RouteKey:
    """从路由 dict 构造复合唯一键 (namespace_id, route_path)"""
    return (route["namespace_id"], route["route_path"])


class RSSHubRouteSync:
    """
    RSSHub 路由增量同步服务（单例）

    同步策略：
    1. 数据源选择：宿主机副本 > docker cp 提取 > 静态副本
    2. mtime 检测：文件未变化则跳过
    3. 增量 UPSERT：新增 INSERT，变化 UPDATE
    4. 软删除：DB 中有但文件没有的标记为 is_active=False
    """

    def __init__(self):
        self._last_sync_mtime: float = 0.0
        self._settings = get_settings()
        project_root = _get_project_root()
        # 宿主机副本路径（docker cp 提取后存放）
        self._host_path: str = str(
            project_root / self._settings.rsshub_routes_file_path.lstrip("/")
        )
        # 静态副本路径（降级用）
        self._static_path: str = str(
            project_root / self._settings.rsshub_routes_static_path.lstrip("/")
        )

    def _extract_from_container(self) -> bool:
        """
        从 RSSHub 容器提取 routes.json 到宿主机

        使用 docker cp 命令复制容器内的 routes.json 到宿主机目录。

        Returns:
            bool: 提取成功返回 True
        """
        import subprocess

        container_name = "rsshub"
        container_path = "/app/assets/build/routes.json"

        # 确保目标目录存在
        target_dir = Path(self._host_path).parent
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            result = subprocess.run(
                ["docker", "cp", f"{container_name}:{container_path}", self._host_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0 and os.path.exists(self._host_path):
                logger.info(f"已从容器提取 routes.json → {self._host_path}")
                return True
            else:
                logger.warning(f"docker cp 失败: {result.stderr.strip()}")
                return False
        except subprocess.TimeoutExpired:
            logger.warning("docker cp 超时")
            return False
        except FileNotFoundError:
            logger.warning("docker 命令不可用")
            return False
        except Exception as e:
            logger.warning(f"docker cp 异常: {e}")
            return False

    def _resolve_source_path(self) -> str:
        """
        选择数据源路径

        优先级：
        1. 宿主机副本（storage/rsshub_build/routes.json）
        2. docker cp 从运行中的容器提取
        3. 静态副本（routes_static.json）
        4. 抛出异常

        Returns:
            str: 数据源文件路径

        Raises:
            FileNotFoundError: 所有数据源都不可用
        """
        # 优先级 1: 宿主机已有副本
        if os.path.exists(self._host_path):
            logger.debug(f"使用宿主机副本: {self._host_path}")
            return self._host_path

        # 优先级 2: docker cp 从容器提取
        if self._extract_from_container():
            return self._host_path

        # 优先级 3: 降级到静态副本
        if os.path.exists(self._static_path):
            logger.info(f"容器不可用，降级到静态副本: {self._static_path}")
            return self._static_path

        # 全部不可用
        raise FileNotFoundError(
            f"routes.json 数据源都不可用。"
            f"宿主主机副本: {self._host_path}, 静态副本: {self._static_path}"
        )

    async def sync_if_needed(self) -> int:
        """
        检查是否需要同步，需要则执行

        流程：
        ① 选择数据源（卷挂载文件 > 静态副本）
        ② mtime 检测（与上次相同则跳过）
        ③ 读取文件 → 解析
        ④ 查询 DB 现有 route_path → 构建差集
        ⑤ 新增 → INSERT，变化 → UPDATE
        ⑥ 已删除 → 标记 removed_at + is_active=False
        ⑦ 记录同步日志

        Returns:
            int: 处理的变更数（新增+更新），0=跳过，-1=失败
        """
        try:
            # ① 选择数据源
            source_path = self._resolve_source_path()
            current_mtime = os.path.getmtime(source_path)

            # ② mtime 检测
            if current_mtime == self._last_sync_mtime:
                logger.debug("routes.json mtime 未变化，跳过同步")
                return 0

            logger.info(f"检测到 routes.json 变化，开始同步: {source_path}")

            # ③ 读取并解析
            routes = parse_routes_json_file(source_path, source="routes.json")
            if not routes:
                logger.warning("解析 routes.json 返回空列表")
                return -1

            logger.info(f"解析得到 {len(routes)} 条路由")

            # ④ 执行同步
            result = await self._do_sync(routes)
            change_count = result["inserted"] + result["updated"] + result["deleted"]

            # ⑤ 同步完成后重新读取 mtime（避免中间文件被修改导致的竞态）
            self._last_sync_mtime = os.path.getmtime(source_path)

            logger.info(f"同步完成，新增 {result['inserted']} 更新 {result['updated']} 删除 {result['deleted']}")

            # ⑥ 同步成功后自动生成静态副本（用于容器移除后的降级）
            if change_count > 0 and os.path.exists(self._host_path):
                try:
                    shutil.copy2(self._host_path, self._static_path)
                    logger.info(f"已更新静态副本: {self._static_path}")
                except Exception as e:
                    logger.warning(f"更新静态副本失败: {e}")

            return change_count

        except FileNotFoundError as e:
            logger.error(f"数据源文件未找到: {e}")
            return -1
        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                logger.error(
                    f"同步失败（路由路径冲突）: {error_msg}。"
                    f"这可能是数据库已有旧数据，建议清空 rsshub_routes 表后重试"
                )
            else:
                logger.error(f"同步失败: {e}")
            return -1

    async def force_extract_and_sync(self) -> tuple[dict, str]:
        """
        强制从容器提取 routes.json 并增量同步到数据库

        跳过 mtime 检测，强制执行：
        1. docker cp 从容器提取 routes.json
        2. 解析 routes.json
        3. 增量同步到数据库

        Returns:
            tuple[dict, str]: ({"inserted": n, "updated": n, "deleted": n}, 消息)
            失败时返回 ({}, 消息)
        """
        try:
            # ① 强制从容器提取 routes.json
            if not self._extract_from_container():
                return {}, "从容器提取路由文件失败，请确认 RSSHub 容器正在运行"

            # ② 解析 routes.json
            if not os.path.exists(self._host_path):
                return {}, "从容器提取的路由文件不存在"

            routes = parse_routes_json_file(self._host_path, source="routes.json")
            if not routes:
                return {}, "路由文件解析失败或为空"

            logger.info(f"强制同步：解析得到 {len(routes)} 条路由")

            # ③ 增量同步到数据库（跳过 mtime 检测）
            result = await self._do_sync(routes)

            # ④ 更新 mtime 避免后续 sync_if_needed 重复同步
            self._last_sync_mtime = os.path.getmtime(self._host_path)

            logger.info(
                f"强制同步完成：新增 {result['inserted']} 更新 {result['updated']} 删除 {result['deleted']}"
            )

            # ⑤ 更新静态副本
            try:
                shutil.copy2(self._host_path, self._static_path)
                logger.info(f"已更新静态副本: {self._static_path}")
            except Exception as e:
                logger.warning(f"更新静态副本失败: {e}")

            return result, "同步成功"

        except Exception as e:
            error_msg = str(e)
            if "UNIQUE constraint failed" in error_msg:
                logger.error(f"强制同步失败（路由路径冲突）: {error_msg}")
                return {}, "同步失败：路由路径冲突，建议清空 rsshub_routes 表后重试"
            logger.error(f"强制同步异常: {e}")
            return {}, f"同步失败: {error_msg}"

    async def _do_sync(self, routes: list[dict]) -> dict:
        """
        核心同步逻辑（重构后）

        流程：
        1. 按 (namespace_id, route_path) 去重（防止重复路径导致 UNIQUE 冲突）
        2. 查询 DB 中路由集合
        3. 执行 UPSERT（新增 + 更新）
        4. 执行软删除
        5. 返回变更明细

        Returns:
            dict: {"inserted": n, "updated": n, "deleted": n}
        """
        now = datetime.now(timezone.utc)

        # 按 (namespace_id, route_path) 去重（保留最后出现的条目）
        routes = list({_make_key(r): r for r in routes}.values())

        async with db.get_session() as session:
            all_db_keys, active_db_keys = await self._query_route_sets(session)

            json_route_keys = {_make_key(r) for r in routes}
            insert_count, update_count = await self._upsert_routes(session, routes, all_db_keys, now)
            delete_count = await self._soft_delete_routes(
                session, active_db_keys, json_route_keys, now
            )
            return {
                "inserted": insert_count,
                "updated": update_count,
                "deleted": delete_count,
            }

    async def _query_route_sets(
        self, session: AsyncSession
    ) -> tuple[set[RouteKey], set[RouteKey]]:
        """
        查询 DB 中所有路由的 (namespace_id, route_path) 复合键集合

        Returns:
            (all_db_keys, active_db_keys): 全部路由复合键集合和活跃路由复合键集合
        """
        result = await session.execute(
            select(RSSHubRoute.namespace_id, RSSHubRoute.route_path, RSSHubRoute.is_active)
        )
        all_db_keys: set[RouteKey] = set()
        active_db_keys: set[RouteKey] = set()
        for row in result.all():
            key: RouteKey = (row[0], row[1])
            all_db_keys.add(key)
            if row[2]:
                active_db_keys.add(key)
        logger.debug(f"DB 路由数: 全部={len(all_db_keys)}, 活跃={len(active_db_keys)}")
        return all_db_keys, active_db_keys

    async def _upsert_routes(
        self,
        session: AsyncSession,
        routes: list[dict],
        all_db_keys: set[RouteKey],
        now: datetime,
    ) -> tuple[int, int]:
        """
        执行路由 UPSERT（更新已有 + 插入新增）

        Returns:
            tuple[int, int]: (insert_count, update_count)
        """
        update_count = 0
        insert_count = 0

        update_routes = [r for r in routes if _make_key(r) in all_db_keys]
        if update_routes:
            for route in update_routes:
                values = _route_to_update_values(route, now)
                stmt = (
                    sql_update(RSSHubRoute)
                    .where(
                        and_(
                            RSSHubRoute.namespace_id == route["namespace_id"],
                            RSSHubRoute.route_path == route["route_path"],
                        )
                    )
                    .values(**values)
                )
                await session.execute(stmt)
            update_count = len(update_routes)
            logger.info(f"更新 {update_count} 条路由")

        insert_routes = [r for r in routes if _make_key(r) not in all_db_keys]
        if insert_routes:
            new_objects = [
                RSSHubRoute(**_route_to_insert_values(route, now))
                for route in insert_routes
            ]
            session.add_all(new_objects)
            insert_count = len(insert_routes)
            logger.info(f"新增 {insert_count} 条路由")

        return insert_count, update_count

    async def _soft_delete_routes(
        self,
        session: AsyncSession,
        active_db_keys: set[RouteKey],
        json_route_keys: set[RouteKey],
        now: datetime,
    ) -> int:
        """
        软删除 JSON 中不存在的活跃路由

        Returns:
            int: 软删除的路由数
        """
        deleted_keys = active_db_keys - json_route_keys
        if not deleted_keys:
            return 0

        conditions = [
            and_(
                RSSHubRoute.namespace_id == ns,
                RSSHubRoute.route_path == rp,
                RSSHubRoute.is_active == True,
            )
            for ns, rp in deleted_keys
        ]
        stmt = (
            sql_update(RSSHubRoute)
            .where(or_(*conditions))
            .values(
                is_active=False,
                removed_at=now,
                last_updated_at=now,
            )
        )
        await session.execute(stmt)
        logger.info(f"软删除 {len(deleted_keys)} 条已移除的路由")
        return len(deleted_keys)


def _get_project_root() -> Path:
    """获取项目根目录"""
    # 从 app/services/rsshub/route_sync.py -> 项目根目录
    # .parent -> app/services/rsshub/
    # .parent.parent -> app/services/
    # .parent.parent.parent -> app/
    # .parent.parent.parent.parent -> 项目根目录
    return Path(__file__).resolve().parent.parent.parent.parent


# ===== 共享字段映射函数 =====


def _route_to_update_values(route: ParsedRoute, now: datetime) -> dict:
    """
    将解析后的路由 dict 转为 UPDATE 语句的 values 参数

    Args:
        route: parse_routes_json 返回的单条路由
        now: 当前时间戳

    Returns:
        dict: 可直接传给 sql_update().values(**result) 的参数
    """
    return {
        "route_name": route.get("route_name"),
        "namespace_id": route.get("namespace_id"),
        "domain": route.get("domain"),
        "example_path": route.get("example_path"),
        "category": route.get("category"),
        "categories": route.get("categories"),
        "lang": route.get("lang"),
        "has_params": route.get("has_params", False),
        "description": route.get("description"),
        "maintainers": route.get("maintainers"),
        "features": route.get("features"),
        "source_file": route.get("source_file", "routes.json"),
        "is_active": True,
        "last_updated_at": now,
        "removed_at": None,
    }


def _route_to_insert_values(route: ParsedRoute, now: datetime) -> dict:
    """
    将解析后的路由 dict 转为 INSERT 的 ORM 构造参数

    Args:
        route: parse_routes_json 返回的单条路由
        now: 当前时间戳

    Returns:
        dict: 可直接传给 RSSHubRoute(**result) 的参数
    """
    base = _route_to_update_values(route, now)
    base["namespace_id"] = route["namespace_id"]
    base["route_path"] = route["route_path"]
    base["first_seen_at"] = now
    base.pop("removed_at", None)
    return base


# ==================== 全局单例 ====================

_route_sync: Optional[RSSHubRouteSync] = None


def get_route_sync() -> RSSHubRouteSync:
    """
    获取路由同步服务全局单例

    Returns:
        RSSHubRouteSync: 全局单例实例
    """
    global _route_sync
    if _route_sync is None:
        _route_sync = RSSHubRouteSync()
    return _route_sync
