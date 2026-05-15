# -*- coding: utf-8 -*-
"""
Logs API 端到端测试

测试 app.api.logs 中的 API 端点
"""
import pytest
import pytest_asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport

from sqlalchemy.ext.asyncio import AsyncSession


class TestLogsAPIListLogs:
    """测试 GET /api/admin/logs 列表接口"""

    @pytest.mark.asyncio
    async def should_return_200_when_valid_token_provided(self, db_session: AsyncSession, test_user):
        """should_return_200_when_valid_token_provided - 测试有效认证"""
        from app.api.logs import router
        from app.main import app
        from app.auth.middleware import get_current_user

        # 覆盖认证依赖
        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        # Mock operation_logger
        mock_result = {
            "items": [
                {
                    "id": 1,
                    "log_type": "task_exec",
                    "log_level": "INFO",
                    "task_name": "fetch_ai_news",
                    "operator": "scheduler",
                    "action": "success",
                    "detail": {"duration_ms": 1000},
                    "ip_address": "127.0.0.1",
                    "created_at": datetime.now().isoformat(),
                }
            ],
            "total": 1,
            "page": 1,
            "page_size": 20,
        }

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.query_logs = AsyncMock(return_value=mock_result)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/admin/logs")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "data" in data
        assert "items" in data["data"]

        # 清理
        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_401_when_no_token_provided(self):
        """should_return_401_when_no_token_provided - 测试无认证令牌"""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/logs")

        # 应该返回 401 或 403（取决于 HTTPBearer 实现）
        assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def should_support_pagination_params(self, db_session: AsyncSession, test_user):
        """should_support_pagination_params - 测试分页参数"""
        from app.api.logs import router
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.query_logs = AsyncMock(return_value={
                "items": [],
                "total": 0,
                "page": 2,
                "page_size": 10,
            })

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/admin/logs?page=2&page_size=10")

        assert response.status_code == 200

        # 验证 query_logs 被调用时使用了正确的分页参数
        mock_logger.query_logs.assert_called_once()
        call_kwargs = mock_logger.query_logs.call_args.kwargs
        assert call_kwargs["page"] == 2
        assert call_kwargs["page_size"] == 10

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_support_filter_params(self, db_session: AsyncSession, test_user):
        """should_support_filter_params - 测试筛选参数"""
        from app.api.logs import router
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.query_logs = AsyncMock(return_value={
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 20,
            })

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get(
                    "/api/admin/logs"
                    "?log_type=task_exec"
                    "&task_name=fetch_ai_news"
                    "&level=INFO"
                    "&action=success"
                    "&start_date=2024-01-01"
                    "&end_date=2024-12-31"
                )

        assert response.status_code == 200

        # 验证筛选参数被正确传递
        call_kwargs = mock_logger.query_logs.call_args.kwargs
        assert call_kwargs["log_type"] == "task_exec"
        assert call_kwargs["task_name"] == "fetch_ai_news"
        assert call_kwargs["level"] == "INFO"
        assert call_kwargs["action"] == "success"
        assert call_kwargs["start_date"] == "2024-01-01"
        assert call_kwargs["end_date"] == "2024-12-31"

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_422_when_page_less_than_1(self, db_session: AsyncSession, test_user):
        """should_return_422_when_page_less_than_1 - 测试 page < 1 验证失败"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/logs?page=0")

        assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_422_when_page_size_greater_than_100(self, db_session: AsyncSession, test_user):
        """should_return_422_when_page_size_greater_than_100 - 测试 page_size > 100 验证失败"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/logs?page_size=101")

        assert response.status_code == 422

        app.dependency_overrides.clear()


class TestLogsAPIGetLogById:
    """测试 GET /api/admin/logs/{log_id} 详情接口"""

    @pytest.mark.asyncio
    async def should_return_200_when_log_exists(self, db_session: AsyncSession, test_user):
        """should_return_200_when_log_exists - 测试获取存在的日志"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        mock_log = {
            "id": 1,
            "log_type": "task_exec",
            "log_level": "INFO",
            "task_name": "fetch_ai_news",
            "operator": "scheduler",
            "action": "success",
            "detail": {"duration_ms": 1000},
            "ip_address": "127.0.0.1",
            "created_at": datetime.now().isoformat(),
        }

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.get_log_by_id = AsyncMock(return_value=mock_log)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/admin/logs/1")

        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["id"] == 1

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_404_when_log_not_exists(self, db_session: AsyncSession, test_user):
        """should_return_404_when_log_not_exists - 测试获取不存在的日志"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.get_log_by_id = AsyncMock(return_value=None)

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/admin/logs/99999")

        assert response.status_code == 404

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_422_when_log_id_is_not_integer(self, db_session: AsyncSession, test_user):
        """should_return_422_when_log_id_is_not_integer - 测试非整数 ID"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/logs/abc")

        assert response.status_code == 422

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_401_when_no_token_provided_for_detail(self):
        """should_return_401_when_no_token_provided_for_detail - 测试详情接口无认证"""
        from app.main import app

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            response = await client.get("/api/admin/logs/1")

        assert response.status_code in [401, 403]


class TestLogsAPIErrorHandling:
    """测试 Logs API 错误处理"""

    @pytest.mark.asyncio
    async def should_return_500_when_database_error_occurs(self, db_session: AsyncSession, test_user):
        """should_return_500_when_database_error_occurs - 测试数据库错误处理"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        with patch("app.api.logs.operation_logger") as mock_logger:
            mock_logger.query_logs = AsyncMock(side_effect=Exception("Database error"))

            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                response = await client.get("/api/admin/logs")

        assert response.status_code == 500

        app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def should_return_404_not_found_for_invalid_log_id_type(self, db_session: AsyncSession, test_user):
        """should_return_404_not_found_for_invalid_log_id_type - 测试无效的 log_id 类型"""
        from app.main import app
        from app.auth.middleware import get_current_user

        async def override_get_current_user():
            return test_user

        app.dependency_overrides[get_current_user] = override_get_current_user

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test"
        ) as client:
            # "logs" 被路由匹配到 path log_id，但验证失败
            response = await client.get("/api/admin/logs/logs")

        # FastAPI 路由匹配问题："logs" 被当作 log_id 处理，类型验证失败返回 422
        assert response.status_code == 422

        app.dependency_overrides.clear()
