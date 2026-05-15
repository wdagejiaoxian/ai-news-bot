# -*- coding: utf-8 -*-
"""
系统配置同步服务

负责 Settings 对象 ↔ system_configs 表的双向同步，是方案四（Config Sync）的核心。

职责：
1. load_from_db()       — 启动时从 DB 恢复用户配置覆盖值
2. save_and_apply()      — Web 面板修改时写入 DB + 即时更新 settings
3. get_all()             — 获取所有可配置项的当前值（Web 面板查询用）
4. reset_to_default()    — 恢复单个配置的默认值

设计原则：
- 零侵入：不改变现有 42 个消费者文件的 get_settings().xxx 调用
- 稀疏存储：DB 仅存用户修改过的配置，未改过的从 config.py 默认值读取
- 即时生效：setattr(settings, key, value) 后下次 get_settings().xxx 即返回新值
- 类型安全：使用 pydantic TypeAdapter 做类型转换和验证
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Union

from pydantic import TypeAdapter
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import db
from app.models import SystemConfig
from app.utils.config_crypto import (
    encrypt_config_value,
    decrypt_config_value,
    is_encrypted_value,
)

logger = logging.getLogger(__name__)


# =============================================================================
# 可动态配置的白名单（硬编码 41 项）
# 来源：系统配置自定义筛选.md 中"你的决定 = ✅"的全部配置
# 不在白名单中的配置被意外写入时会抛 ValueError（安全防护）
# =============================================================================

OVERRIDABLE_KEYS: set[str] = {
    # GitHub
    "github_token", "default_github_languages",
    # 调度清理
    "cleanup_days_threshold_min", "cleanup_days_threshold_max",
    "push_log_retention_days", "task_history_retention_days",
    "operation_log_retention_days",
    # 评分推送
    "push_score_threshold",
    # RSS 采集
    "rss_concurrent_limit", "rss_error_threshold", "rss_fetch_timeout",
    # 内容处理
    "process_batch_size", "process_max_total", "process_batch_delay",
    "article_save_batch_size",
    # 内容补全
    "trafilatura_skip_domains", "trafilatura_enable_immediate_enrichment",
    "enrich_concurrency", "enrich_timeout",
    # 域名跳过
    "dynamic_skip_enabled", "dynamic_skip_threshold",
    # RSSHub
    "rsshub_enabled", "rsshub_url",
    # 向量搜索
    "semantic_search_max_results", "embedding_max_text_length",
    "ollama_embedding_base_url", "dedup_similarity_threshold",
    "cache_similarity_threshold", "embedding_timeout",
    "semantic_search_top_k", "semantic_cache_top_k",
    # 超时重试
    "llm_api_timeout", "batch_llm_timeout", "llm_max_retries",
    "embedding_max_retries", "webhook_api_timeout",
    # 企业微信
    "wecom_webhook_timeout", "wecom_api_timeout",
    "wecom_upload_timeout", "wecom_api_base_url",
    # GitHub API
    "github_api_base_url",
}

# 需要加密存储的配置（敏感信息）
ENCRYPTED_KEYS: set[str] = {
    "github_token",
}


def _serialize_value(value: Any, value_type: str) -> str:
    """将 Python 值序列化为 JSON 字符串"""
    if value_type == "bool":
        return "true" if value else "false"
    return str(value)


def _deserialize_value(value_str: str, value_type: str) -> Any:
    """将 JSON 字符串反序列化为 Python 值"""
    if value_type == "int":
        return int(value_str)
    elif value_type == "float":
        return float(value_str)
    elif value_type == "bool":
        return value_str.lower() in ("true", "1", "yes")
    else:  # str
        return value_str


class ConfigSyncValidationError(ValueError):
    """配置验证失败"""
    pass


class ConfigSyncService:
    """
    配置同步服务 — Settings 对象 ↔ system_configs 表 双向同步

    使用方式：
        # 启动时加载
        await config_sync_service.load_from_db()

        # Web 面板修改
        await config_sync_service.save_and_apply("push_score_threshold", 90, db_session)

        # Web 面板查询
        configs = await config_sync_service.get_all(db_session)

        # 恢复默认
        await config_sync_service.reset_to_default("push_score_threshold", db_session)

    线程安全：使用 asyncio.Lock 保证写入/重载的原子性
    """

    def __init__(self):
        self._settings = get_settings()
        self._lock = asyncio.Lock()
        self._field_cache: dict[str, Any] = {}

    def _get_field_info(self, key: str):
        """获取 pydantic Field metadata（带运行时缓存）"""
        if key not in self._field_cache:
            fields = self._settings.__class__.model_fields
            if key not in fields:
                raise ConfigSyncValidationError(
                    f"配置项 '{key}' 不存在于 Settings 模型中"
                )
            self._field_cache[key] = fields[key]
        return self._field_cache[key]

    def _get_default_value(self, key: str) -> Any:
        """从 config.py Field 读取默认值"""
        field_info = self._get_field_info(key)
        return field_info.default

    def _validate_value(self, key: str, raw_value: Any) -> Any:
        """
        验证并类型转换配置值

        步骤：
        1. 使用 pydantic TypeAdapter 做类型转换（"85" → 85 等）
        2. 检查 Field metadata 中的 Ge/Le 约束
        3. 返回验证通过的值

        Raises:
            ConfigSyncValidationError: 验证失败
        """
        field_info = self._get_field_info(key)

        # 步骤 1：类型转换
        try:
            adapter = TypeAdapter(field_info.annotation)
            validated = adapter.validate_python(raw_value)
        except Exception as e:
            raise ConfigSyncValidationError(
                f"配置项 '{key}' 值类型无效: {raw_value!r}，期望类型 {field_info.annotation}，错误: {e}"
            ) from e

        # 步骤 2：检查 Field 约束（Ge、Le 等）
        for meta in field_info.metadata:
            meta_name = type(meta).__name__
            if meta_name == "Ge" and validated < meta.ge:
                raise ConfigSyncValidationError(
                    f"配置项 '{key}' 值 {validated} 低于最小值 {meta.ge}"
                )
            elif meta_name == "Le" and validated > meta.le:
                raise ConfigSyncValidationError(
                    f"配置项 '{key}' 值 {validated} 超过最大值 {meta.le}"
                )
            elif meta_name == "Gt" and validated <= meta.gt:
                raise ConfigSyncValidationError(
                    f"配置项 '{key}' 值 {validated} 未大于最小值 {meta.gt}"
                )
            elif meta_name == "Lt" and validated >= meta.lt:
                raise ConfigSyncValidationError(
                    f"配置项 '{key}' 值 {validated} 未小于最大值 {meta.lt}"
                )

        return validated

    def _get_value_type(self, key: str) -> str:
        """获取配置值的 Python 类型名（用于 DB 存储标记）"""
        field_info = self._get_field_info(key)
        anno = field_info.annotation

        # 处理 Optional[X] → X
        origin = getattr(anno, "__origin__", None)
        if origin is Union:
            args = getattr(anno, "__args__", ())
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                anno = non_none[0]

        type_map = {int: "int", float: "float", bool: "bool"}
        return type_map.get(anno, "str")

    # ==================== 公共方法 ====================

    async def load_from_db(self) -> int:
        """
        启动时调用：从 system_configs 表加载用户覆盖值 → setattr 到 settings

        Returns:
            int: 成功恢复的配置项数量

        异常安全：
        - DB 为空 → 返回 0，不报错
        - 某条记录损坏 → 跳过该行，记录 warning，继续处理其余
        - 整体异常 → 捕获记录 warning，不阻塞启动
        """
        restored_count = 0

        try:
            async with db.get_session() as session:
                result = await session.execute(
                    select(SystemConfig)
                )
                rows = result.scalars().all()

            if not rows:
                logger.info("system_configs 表为空（首次启动或无用户自定义配置）")
                return 0

            for row in rows:
                key = row.config_key

                # 安全防护：跳过不在白名单中的 key
                if key not in OVERRIDABLE_KEYS:
                    logger.warning(
                        "system_configs 中存在未知配置项 '%s'，已跳过。"
                        "该记录可能由旧版本创建或数据损坏。", key
                    )
                    continue

                try:
                    # 解密（如果加密存储）
                    raw_value = row.config_value
                    if row.is_encrypted:
                        raw_value = decrypt_config_value(raw_value)

                    # 反序列化
                    value = _deserialize_value(raw_value, row.value_type)

                    # setattr 到 settings 对象
                    setattr(self._settings, key, value)
                    restored_count += 1

                    logger.debug(
                        "已加载配置: %s = %s (类型: %s, 加密: %s)",
                        key, value, row.value_type, row.is_encrypted
                    )

                except Exception as e:
                    logger.warning(
                        "加载配置项 '%s' 失败，已跳过: %s", key, e
                    )
                    continue

            logger.info(
                "配置同步完成: 成功恢复 %d/%d 项用户配置",
                restored_count, len(rows)
            )
            return restored_count

        except Exception as e:
            logger.warning("从数据库加载配置失败，使用 config.py 默认值: %s", e)
            return restored_count

    async def save_and_apply(
        self, key: str, value: Any, session: AsyncSession
    ) -> dict:
        """
        Web 面板修改时调用：验证 → 加密（如需）→ 写 DB → 更新 settings

        Args:
            key: 配置键名
            value: 配置值（Web 面板传入的原始值）
            session: 数据库会话

        Returns:
            dict: {
                "key": str,
                "previous_value": Any,
                "current_value": Any,
                "message": str,
            }

        Raises:
            ConfigSyncValidationError: 验证失败
            ValueError: key 不在白名单中
        """
        # 步骤 1：检查白名单
        if key not in OVERRIDABLE_KEYS:
            raise ValueError(
                f"配置项 '{key}' 不支持动态配置"
            )

        async with self._lock:
            # 步骤 2：验证并类型转换
            validated = self._validate_value(key, value)

            # 步骤 3：记录旧值（用于响应）
            previous_value = getattr(self._settings, key, None)

            # 步骤 4：序列化 + 加密
            value_type = self._get_value_type(key)
            serialized = _serialize_value(validated, value_type)

            is_encrypted = key in ENCRYPTED_KEYS
            if is_encrypted:
                serialized = encrypt_config_value(serialized)

            # 步骤 5：写入 DB（upsert）
            stmt = select(SystemConfig).where(SystemConfig.config_key == key)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                existing.config_value = serialized
                existing.is_encrypted = is_encrypted
                existing.updated_at = datetime.now(timezone.utc)
            else:
                new_config = SystemConfig(
                    config_key=key,
                    config_value=serialized,
                    value_type=value_type,
                    category=self._infer_category(key),
                    is_encrypted=is_encrypted,
                )
                session.add(new_config)

            await session.commit()
            logger.info(
                "配置已保存到数据库: %s = %s (加密: %s)", key, validated, is_encrypted
            )

            # 步骤 6：立即生效 — 更新内存中的 settings 对象
            setattr(self._settings, key, validated)

            logger.info(
                "配置已即时生效: %s = %s (之前: %s)", key, validated, previous_value
            )

            return {
                "key": key,
                "previous_value": previous_value,
                "current_value": validated,
                "message": "配置已更新，即时生效",
            }

    async def get_all(self, session: AsyncSession) -> list[dict]:
        """
        获取所有可配置项的当前值（Web 面板查询用）

        遍历 _overridable_keys 中所有 41 项，每项返回：
        - current_value: 当前 settings 中实际值（先 setattr 覆盖的或默认值）
        - default_value: config.py Field 默认值
        - is_customized: 该配置是否被用户修改过（有 DB 记录）

        Args:
            session: 数据库会话

        Returns:
            list[dict]: 每项包含 key, current_value, default_value, value_type,
                        category, is_encrypted, is_customized, updated_at
        """
        # 查询 DB 中所有已自定义的配置
        result = await session.execute(select(SystemConfig))
        db_rows = result.scalars().all()

        # 构建 key → DB row 映射
        customized_keys: dict[str, SystemConfig] = {
            row.config_key: row for row in db_rows
        }

        configs = []
        for key in sorted(OVERRIDABLE_KEYS):
            field_info = self._get_field_info(key)
            db_row = customized_keys.get(key)

            current_value = getattr(self._settings, key)
            default_value = self._get_default_value(key)
            value_type = self._get_value_type(key)
            category = db_row.category if db_row else self._infer_category(key)
            is_customized = db_row is not None
            is_encrypted = db_row.is_encrypted if db_row else False
            updated_at = (
                str(db_row.updated_at) if db_row and db_row.updated_at else None
            )

            # 如果已加密，current_value 脱敏
            display_value = current_value
            if is_encrypted and current_value:
                display_value = self._mask_value(current_value)

            configs.append({
                "key": key,
                "current_value": display_value,
                "default_value": default_value,
                "value_type": value_type,
                "category": category,
                "is_encrypted": is_encrypted,
                "is_customized": is_customized,
                "updated_at": updated_at,
            })

        return configs

    async def reset_to_default(self, key: str, session: AsyncSession) -> dict:
        """
        恢复单个配置为 config.py 默认值

        Args:
            key: 配置键名
            session: 数据库会话

        Returns:
            dict: {key, current_value, message}

        Raises:
            ValueError: key 不在白名单中
            ConfigSyncValidationError: 默认值验证失败
        """
        if key not in OVERRIDABLE_KEYS:
            raise ValueError(
                f"配置项 '{key}' 不支持动态配置"
            )

        async with self._lock:
            # 从 DB 删除自定义记录
            stmt = delete(SystemConfig).where(SystemConfig.config_key == key)
            await session.execute(stmt)
            await session.commit()

            # 从 config.py 读取默认值
            default_value = self._get_default_value(key)

            # setattr 到 settings
            setattr(self._settings, key, default_value)

            logger.info(
                "配置已恢复默认值: %s = %s", key, default_value
            )

            return {
                "key": key,
                "current_value": default_value,
                "message": f"配置 '{key}' 已恢复为默认值 {default_value}",
            }

    # ==================== 私有辅助方法 ====================

    def _infer_category(self, key: str) -> str:
        """根据 key 推断配置分类"""
        if key.startswith("github_") or key == "github_api_base_url":
            return "github"
        elif key.startswith("cleanup_") or key.endswith("_retention_days"):
            return "scheduler_cleanup"
        elif key == "push_score_threshold":
            return "scheduler_cleanup"
        elif key.startswith("rss_"):
            return "rss"
        elif key.startswith("process_") or key.startswith("article_"):
            return "process"
        elif key.startswith("trafilatura_") or key.startswith("enrich_"):
            return "enrich"
        elif key.startswith("dynamic_skip_"):
            return "domain_skip"
        elif key.startswith("rsshub_"):
            return "rsshub"
        elif key.startswith("semantic_") or key.startswith("embedding_") \
                or key.startswith("dedup_") or key.startswith("cache_") \
                or key.startswith("ollama_embedding_"):
            return "vector"
        elif key.startswith("llm_") or key.startswith("batch_llm_") \
                or key.startswith("embedding_max_retries") \
                or key.startswith("webhook_api_"):
            return "timeout"
        elif key.startswith("wecom_"):
            return "wecom"
        else:
            return "general"

    def _mask_value(self, value: Any) -> str:
        """脱敏显示敏感值"""
        s = str(value)
        if len(s) <= 8:
            return "****"
        return s[:4] + "****" + s[-4:]


# =============================================================================
# 模块级单例
# =============================================================================

config_sync_service = ConfigSyncService()

# 需要在 __init__.py 暴露，也需要在其他模块中按需导入
# 使用: from app.services.config_sync import config_sync_service
