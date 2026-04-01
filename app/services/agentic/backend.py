from deepagents.backends import CompositeBackend, StateBackend, StoreBackend
from langgraph.store.memory import InMemoryStore
from langgraph.checkpoint.memory import MemorySaver
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)

# from app.config import


# # 项目根目录（向上三级：backend_factory.py → agentic → services → app → 项目根目录）
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
#
# # 默认 SQLite 数据库路径（在项目根目录的 storage 文件夹下）
# DEFAULT_SQLITE_DB_PATH = os.path.join(PROJECT_ROOT, "storage", "agent_memory.db")




class BackendFactory:
    """后端工厂：创建支持长期记忆的 CompositeBackend"""

    def __init__(self, store=None, checkpointer=None):
        # 存储后端：开发环境用 InMemoryStore，生产环境用 PostgresStore
        self.store = store or InMemoryStore()

        # 检查点器：用于状态持久化和人机交互
        self.checkpointer = checkpointer or MemorySaver()

        # self._connections = connections or []  # 保存连接引用以便关闭

    def create_backend(self, runtime):
        """创建 CompositeBackend 实例

        路由规则：
        - /memories/* → StoreBackend（持久化，跨会话）
        - 其他路径 → StateBackend（临时，仅当前会话）
        """
        return CompositeBackend(
            default=StateBackend(runtime),  # 临时存储
            routes={
                "/memories/": StoreBackend(runtime)  # 持久化存储
            }
        )

    @property
    def backend_factory(self):
        """返回后端工厂函数（供 create_deep_agent 使用）"""
        return self.create_backend

    # def close(self):
    #     """✅ 关闭所有数据库连接"""
    #     for conn in self._connections:
    #         try:
    #             if conn:
    #                 conn.close()
    #                 logger.debug(f"已关闭数据库连接: {conn}")
    #         except Exception as e:
    #             logger.error(f"关闭数据库连接失败: {e}")
    #
    #     self._connections.clear()
    #     logger.info("BackendFactory 资源已清理")


def create_backend_factory(
        store_type: str = "memory",
        db_url: Optional[str] = None,
        db_path: Optional[str] = None,
) -> BackendFactory:
    """创建后端工厂实例

    Args:
        store_type: 存储类型，可选 "memory"（开发）或 "postgres"（生产）
        db_url: 数据库连接 URL（仅 postgres 类型需要），格式：postgresql://user:password@host:port/database
        db_path: sqlite类型需要，格式：/path/to/database.db 或 :memory:（内存数据库）

    Returns:
        BackendFactory 实例
    """

    if not db_path:
        db_path = "storage/agent_memory.db"
    # 确保目录存在
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

    # if store_type == "postgres":
    #     try:
    #         from langgraph.store.postgres import PostgresStore
    #         if not db_url:
    #             db_url = os.environ.get("DATABASE_URL")
    #         store_ctx = PostgresStore.from_conn_string(db_url)
    #         store = store_ctx.__enter__()
    #         store.setup()
    #     except ImportError:
    #         print("警告：PostgresStore 不可用，回退到 InMemoryStore")
    #         store = InMemoryStore()

    connections = []  # 收集所有创建的连接

    if store_type == "sqlite":
        try:
            from langgraph.store.sqlite import SqliteStore
            # from app.main import agent_sqlite_conn
            # import sqlite3

            # # 为每个实例创建独立的连接
            # store_conn = sqlite3.connect(
            #     db_path,
            #     check_same_thread=False,
            #     timeout=30.0
            # )
            # # 启用 WAL 模式（允许并发读写）
            # store_conn.execute("PRAGMA journal_mode=WAL")
            #
            # # 设置 busy_timeout（锁冲突时等待而不是立即返回错误）
            # store_conn.execute("PRAGMA busy_timeout=30000")  # 30秒
            #
            # # 设置同步模式（NORMAL 平衡性能和安全）
            # store_conn.execute("PRAGMA synchronous=NORMAL")
            #
            # connections.append(store_conn)
            #
            # store = SqliteStore(store_conn)
            # store.setup()

            # if agent_sqlite_conn:
            #     store = SqliteStore(agent_sqlite_conn)
            #     store.setup()
            # else:
            #     logger.warning('Agent SQLite未连接，，回退到 InMemoryStore')
            #     store = InMemoryStore()
            from langgraph.checkpoint.sqlite import SqliteSaver
            from app.services.agentic.agent_database import get_agent_connection

            # 使用共享的 Agent 数据库连接
            conn = get_agent_connection()

            store = SqliteStore(conn)
            store.setup()

            # Store 和 Saver 共享同一个连接
            get_checkpointer = SqliteSaver(conn)

            logger.info("SqliteStore 和 SqliteSaver 已创建，使用共享连接")

        except ImportError as e:
            logger.warning(f"SqliteStore/SqliteSaver 不可用，回退到 InMemory: {e}")
            store = InMemoryStore()
            get_checkpointer = MemorySaver()

    else:
        store = InMemoryStore()
        get_checkpointer = MemorySaver()

    # # 创建 checkpointer（使用 SQLite）
    # try:
    #     from langgraph.checkpoint.sqlite import SqliteSaver
    #     # from app.main import agent_sqlite_conn
    #     # import sqlite3
    #
    #     # # 为 checkpointer 创建独立的连接
    #     # checkpointer_conn = sqlite3.connect(db_path, check_same_thread=False)
    #     # connections.append(checkpointer_conn)
    #     #
    #     # get_checkpointer = SqliteSaver(checkpointer_conn)
    #
    #     if store_type == "sqlite" and connections:
    #         get_checkpointer = SqliteSaver(connections[0])
    #     else:
    #         logger.warning('Agent SQLite未连接，，回退到 MemorySaver')
    #         get_checkpointer = MemorySaver()
    #
    # except ImportError:
    #     logger.warning("警告：SqliteSaver 不可用，回退到 MemorySaver")
    #     get_checkpointer = MemorySaver()

    return BackendFactory(
        store=store,
        checkpointer=get_checkpointer,
        # connections=connections,
    )