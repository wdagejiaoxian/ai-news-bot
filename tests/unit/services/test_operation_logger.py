# -*- coding: utf-8 -*-
"""
OperationLogger 服务单元测试

测试 operation_logger.py 中的日志写入和查询功能
"""
import json
import os
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import OperationLog, LogType, LogLevel


class TestOperationLoggerLog:
    """测试 OperationLogger.log() 方法"""

    @pytest.mark.asyncio
    async def should_write_log_successfully_when_valid_params_provided(self, db_session: AsyncSession):
        """should_write_log_successfully_when_valid_params_provided"""
        from app.services.operation_logger import OperationLogger

        # 创建 OperationLogger 实例并注入 mock db
        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = await logger.log(
            log_type=LogType.TASK_EXEC.value,
            action="start",
            operator="scheduler",
            log_level=LogLevel.INFO.value,
            task_name="fetch_ai_news",
            detail={"duration_ms": 1000},
            ip_address="127.0.0.1",
        )

        assert log_id is not None
        assert isinstance(log_id, int)

    @pytest.mark.asyncio
    async def should_return_none_when_database_write_fails(self):
        """should_return_none_when_database_write_fails - 测试数据库写入失败时的 fallback"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()

        # Mock _db 属性抛出异常
        mock_db_instance = MagicMock()
        mock_db_instance.get_session.return_value.__aenter__ = AsyncMock(side_effect=Exception("DB Error"))
        mock_db_instance.get_session.return_value.__aexit__ = AsyncMock(return_value=None)
        logger._db = mock_db_instance

        # 验证 fallback 文件存在（测试后清理）
        fallback_file = "logs/operation_fallback.log"
        if os.path.exists(fallback_file):
            os.remove(fallback_file)

        log_id = await logger.log(
            log_type=LogType.TASK_EXEC.value,
            action="start",
            operator="scheduler",
        )

        # 数据库失败时应返回 None
        assert log_id is None

        # 验证 fallback 文件被写入
        assert os.path.exists(fallback_file), "Fallback file should be created"

        # 清理
        if os.path.exists(fallback_file):
            os.remove(fallback_file)

    @pytest.mark.asyncio
    async def should_handle_null_detail_correctly(self, db_session: AsyncSession):
        """should_handle_null_detail_correctly - 测试 detail 为 None 的情况"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = await logger.log(
            log_type=LogType.SYSTEM.value,
            action="reload",
            operator="system",
            detail=None,  # None detail
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def should_handle_optional_task_name_as_none(self, db_session: AsyncSession):
        """should_handle_optional_task_name_as_none - 测试可选的 task_name 为 None"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = await logger.log(
            log_type=LogType.CONFIG_CHANGE.value,
            action="reload",
            operator="web_panel",
            task_name=None,  # 可选字段
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def should_use_default_operator_when_not_specified(self, db_session: AsyncSession):
        """should_use_default_operator_when_not_specified - 测试默认操作人"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = await logger.log(
            log_type=LogType.SYSTEM.value,
            action="start",
        )

        assert log_id is not None

    @pytest.mark.asyncio
    async def should_use_default_log_level_when_not_specified(self, db_session: AsyncSession):
        """should_use_default_log_level_when_not_specified - 测试默认日志级别"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = await logger.log(
            log_type=LogType.SYSTEM.value,
            action="start",
            operator="system",
            # 不指定 log_level，应该使用默认值 INFO
        )

        assert log_id is not None


class TestOperationLoggerQueryLogs:
    """测试 OperationLogger.query_logs() 方法"""

    @pytest.mark.asyncio
    async def should_return_paginated_results(self, db_session: AsyncSession, operation_logs):
        """should_return_paginated_results - 测试分页返回"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(page=1, page_size=2)

        assert "items" in result
        assert "total" in result
        assert "page" in result
        assert "page_size" in result
        assert result["page"] == 1
        assert result["page_size"] == 2
        assert result["total"] == 5
        assert len(result["items"]) == 2

    @pytest.mark.asyncio
    async def should_filter_by_log_type(self, db_session: AsyncSession, operation_logs):
        """should_filter_by_log_type - 测试按日志类型筛选"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(log_type="task_exec")

        assert result["total"] == 5
        for item in result["items"]:
            assert item["log_type"] == "task_exec"

    @pytest.mark.asyncio
    async def should_filter_by_action(self, db_session: AsyncSession, operation_logs):
        """should_filter_by_action - 测试按操作类型筛选"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(action="success")

        assert result["total"] == 3  # 5个日志中偶数索引(0,2,4)是success
        for item in result["items"]:
            assert item["action"] == "success"

    @pytest.mark.asyncio
    async def should_filter_by_level(self, db_session: AsyncSession, operation_logs):
        """should_filter_by_level - 测试按日志级别筛选"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(level="INFO")

        assert result["total"] == 5
        for item in result["items"]:
            assert item["log_level"] == "INFO"

    @pytest.mark.asyncio
    async def should_filter_by_date_range(self, db_session: AsyncSession, operation_logs):
        """should_filter_by_date_range - 测试按日期范围筛选"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        today = datetime.now().strftime("%Y-%m-%d")
        result = await logger.query_logs(start_date=today, end_date=today)

        assert result["total"] == 5

    @pytest.mark.asyncio
    async def should_return_empty_when_no_matching_logs(self, db_session: AsyncSession):
        """should_return_empty_when_no_matching_logs - 测试无匹配日志时返回空"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(log_type="nonexistent_type")

        assert result["total"] == 0
        assert result["items"] == []

    @pytest.mark.asyncio
    async def should_handle_invalid_date_format_gracefully(self, db_session: AsyncSession, operation_logs):
        """should_handle_invalid_date_format_gracefully - 测试无效日期格式"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        # 无效日期格式不应该抛出异常
        result = await logger.query_logs(start_date="invalid-date")

        # 应该返回所有日志（因为过滤无效）
        assert result["total"] == 5

    @pytest.mark.asyncio
    async def should_return_logs_sorted_by_created_at_desc(self, db_session: AsyncSession, operation_logs):
        """should_return_logs_sorted_by_created_at_desc - 测试日志按创建时间倒序"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs(page=1, page_size=10)

        # 验证返回的 items 按 created_at 倒序排列
        if len(result["items"]) >= 2:
            assert result["items"][0]["id"] > result["items"][1]["id"]

    @pytest.mark.asyncio
    async def should_parse_detail_json_string_to_object(self, db_session: AsyncSession, operation_logs):
        """should_parse_detail_json_string_to_object - 测试 detail JSON 字符串解析"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.query_logs()

        # 验证 detail 被正确解析为对象
        for item in result["items"]:
            if item["detail"] is not None:
                assert isinstance(item["detail"], dict) or item["detail"] == {}


class TestOperationLoggerGetLogById:
    """测试 OperationLogger.get_log_by_id() 方法"""

    @pytest.mark.asyncio
    async def should_return_log_when_exists(self, db_session: AsyncSession, operation_logs):
        """should_return_log_when_exists - 测试获取存在的日志"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = operation_logs[0].id
        result = await logger.get_log_by_id(log_id)

        assert result is not None
        assert result["id"] == log_id
        assert "log_type" in result
        assert "action" in result

    @pytest.mark.asyncio
    async def should_return_none_when_log_not_exists(self, db_session: AsyncSession):
        """should_return_none_when_log_not_exists - 测试获取不存在的日志"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        result = await logger.get_log_by_id(99999)

        assert result is None

    @pytest.mark.asyncio
    async def should_include_all_fields_in_result(self, db_session: AsyncSession, operation_logs):
        """should_include_all_fields_in_result - 测试返回结果包含所有字段"""
        from app.services.operation_logger import OperationLogger

        logger = OperationLogger()
        logger._db = MagicMock()
        logger._db.get_session.return_value.__aenter__ = AsyncMock(return_value=db_session)
        logger._db.get_session.return_value.__aexit__ = AsyncMock(return_value=None)

        log_id = operation_logs[0].id
        result = await logger.get_log_by_id(log_id)

        expected_fields = [
            "id", "log_type", "log_level", "task_name",
            "operator", "action", "detail", "ip_address", "created_at"
        ]
        for field in expected_fields:
            assert field in result, f"Field {field} should be in result"
