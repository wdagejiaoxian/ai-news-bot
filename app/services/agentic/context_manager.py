from typing import Dict, Optional
import hashlib
import time
from datetime import datetime, timedelta


class SessionContextManager:
    """会话上下文管理器

    职责：
    1. 管理用户会话 ID
    2. 跟踪会话状态
    3. 提供会话统计信息
    """

    def __init__(self, ttl_minutes=60):
        # 用户 ID → 会话 ID 映射
        self._user_sessions: Dict[str, str] = {}

        # 会话元数据
        self._session_metadata: Dict[str, dict] = {}

        # 过期时间
        self._ttl = timedelta(minutes=ttl_minutes)


    def get_session_id(self, user_id: str) -> (str, bool):
        """获取或创建用户的会话 ID

        Args:
            user_id: 用户唯一标识（如企业微信的 FromUserName）

        Returns:
            会话 ID
        """
        if user_id in self._user_sessions:
            sess_id = self._user_sessions[user_id]
            created_time = self._session_metadata[sess_id]["created_at"]
            if datetime.now() - created_time < self._ttl:
                self._session_metadata[sess_id]["created_at"] = datetime.now()
                return sess_id, True
            # else:
            #     del self._user_sessions[user_id]

        # 基于用户 ID 和时间戳生成会话 ID
        timestamp = datetime.now()
        session_hash = hashlib.md5(f"wecom_{user_id}".encode()).hexdigest()[:16]
        session_id = f"session_{session_hash}"

        self._user_sessions[user_id] = session_id
        self._session_metadata[session_id] = {
            "user_id": user_id,
            "created_at": timestamp,
            "interaction_count": 0,
        }

        return self._user_sessions[user_id],False

    def update_session(self, session_id: str, user_input: str, assistant_response: str):
        """更新会话元数据

        Args:
            session_id: 会话 ID
            user_input: 用户输入
            assistant_response: 助手回复
        """
        if session_id in self._session_metadata:
            metadata = self._session_metadata[session_id]
            metadata["interaction_count"] = metadata.get("interaction_count", 0) + 1
            metadata["last_interaction"] = str(int(time.time()))
            # metadata["last_user_input"] = user_input[:100]  # 保存前 100 字符

    def get_session_stats(self, session_id: str) -> Optional[dict]:
        """获取会话统计信息

        Args:
            session_id: 会话 ID

        Returns:
            会话元数据字典，如果不存在则返回 None
        """
        return self._session_metadata.get(session_id)

    def cleanup_expired_sessions(self, max_age_seconds: int = 86400):
        """清理过期会话

        Args:
            max_age_seconds: 会话最大存活时间（默认 24 小时）
        """
        current_time = int(time.time())
        expired_sessions = []

        for session_id, metadata in self._session_metadata.items():
            created_at = int(metadata.get("created_at", 0))
            if current_time - created_at > max_age_seconds:
                expired_sessions.append(session_id)

        for session_id in expired_sessions:
            # 找到对应的用户 ID 并删除
            user_id_to_remove = None
            for user_id, sid in self._user_sessions.items():
                if sid == session_id:
                    user_id_to_remove = user_id
                    break

            if user_id_to_remove:
                del self._user_sessions[user_id_to_remove]

            del self._session_metadata[session_id]


# 全局上下文管理器实例
context_manager = SessionContextManager()