import logging
import os
import uuid
from typing import Optional

from deepagents import create_deep_agent
from langchain_openai import ChatOpenAI

from app.services.agentic.backend import create_backend_factory
from app.services.agentic.tools import all_tools,base_tools,ai_news_tools,github_proj_tools
from app.services.agentic.middleware.tool_cache_middleware import create_tool_cache_middleware_v2

logger = logging.getLogger(__name__)

SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")



class AgentManage:
    """用于管理agent"""
    def __init__(
            self,
            _selected_model=None,
            _llm_mode=None,
            store_type: str = "memory",
            db_url: Optional[str] = None,
            db_path: Optional[str] = None,
            skills_paths=None,
    ):
        """初始化主 Agent（通用的意图理解与任务协调器）
        核心职责：
            1. 理解用户意图
            2. 任务规划与分解
            3. 协调子 Agent 执行
            4. 管理长期记忆
            5. 维护对话上下文
        :param _selected_model:选择的模型对象
        :param _llm_mode:
        :param skills_paths:
        :param db_url:
        :param db_path:
        """

        # 包装模型
        self.selected_model = _selected_model
        self.model = self.llm_warpper(self.selected_model)

        self.skills_paths = skills_paths or [SKILLS_DIR]        # skills的路径

        # 后端
        self.backend = create_backend_factory(
            store_type=store_type,
            db_url=db_url,
            db_path=db_path,
        )

        # 工具调用中间件实例
        self.tool_cache_middleware = create_tool_cache_middleware_v2(
            cache_store=self.backend.store,
            ttl_seconds=600,
        )

        # 创建缓存中间件
        self.cache_middleware = self.tool_cache_middleware.create_middleware()

        # 子agent列表
        self.subagents = [
            self.get_news_researcher_subagent(self.cache_middleware),
            self.get_github_analyzer_subagent(self.cache_middleware),
            self.get_general_assistant_subagent(self.cache_middleware),
        ]

        # # 系统提示词：定义秘书 Agent 的角色和能力
        # self.system_prompt = """你是一个专业的 AI 秘书助手。
        #
        # ## 你的职责
        #
        # 1. **理解用户意图**：准确理解用户的需求和问题
        # 2. **任务规划**：使用 write_todos 工具规划复杂任务
        # 3. **协调执行**：主agent能完成的任务可以直接完成，专业的任务则委托给合适的子 Agent
        # 4. **记忆管理**：保存和检索用户偏好、历史交互
        # 5. **综合回复**：将子 Agent 的结果整合为连贯的回复
        #
        # ## 可用子 Agent
        #
        # - **news-researcher**：深入研究 AI 资讯主题
        # - **github-analyzer**：分析 GitHub 热门项目和趋势
        # - **general-assistant**：处理通用问答和任务
        #
        # ## 长期记忆
        #
        # 你有持久化的记忆存储在 /memories/ 目录：
        # - `/memories/user_preferences.txt`：用户偏好设置
        # - `/memories/interaction_history.md`：重要交互记录
        # - `/memories/knowledge_base/`：知识库
        #
        # 在对话开始时，检查 /memories/ 了解用户偏好。
        # 当用户表达偏好或重要信息时，保存到 /memories/。
        #
        # ## 回复原则
        #
        # - 简洁、专业、易于理解
        # - 适当使用 emoji 增强可读性
        # - 优先使用子 Agent 处理专业任务
        # - 保持对话连贯性，引用之前的上下文
        # """

        # 不使用子agent的提示词：定义秘书 Agent 的角色和能力
        self.system_prompt = """你是一个专业的 AI 秘书助手。

                ## 你的职责

                1. **理解用户意图**：准确理解用户的需求和问题
                2. **任务规划**：使用 write_todos 工具规划复杂任务
                3. **协调执行**：看看是否需要调用skills，如需要，则参考对应的skills执行
                4. **记忆管理**：保存和检索用户偏好、历史交互
                5. **综合回复**：将各种工具调用结果或者模型回复结果整合为连贯的回复

                ## 长期记忆

                你有持久化的记忆存储在 /memories/ 目录：
                - `/memories/user_preferences.txt`：用户偏好设置
                - `/memories/interaction_history.md`：重要交互记录
                - `/memories/knowledge_base/`：知识库

                在对话开始时，检查 /memories/ 了解用户偏好。
                当用户表达偏好或重要信息时，保存到 /memories/。

                ## 工具使用原则

                - 调用工具获取信息后，如果已能回答用户问题，不要重复调用
                - 不要为了"验证"而重复调用相同的工具
                - 如果需要多次调用不同工具，明确说明目的

                ## 回复原则

                - 简洁、专业、易于理解
                - 适当使用 emoji 增强可读性
                - 优先使用子 Agent 处理专业任务
                - 保持对话连贯性，引用之前的上下文
                """

        self.main_agent = create_deep_agent(
            model=self.model,
            tools=all_tools,  # 所有工具
            system_prompt=self.system_prompt,
            # subagents=self.subagents,       # 子agent列表
            backend=self.backend.backend_factory,   # 后端工厂
            store=self.backend.store,  # 存储后端
            checkpointer=self.backend.checkpointer,  # 检查点器
            skills=self.skills_paths,   # Skills 目录
            memory=["/memories/"],  # 记忆文件路径
            middleware=[self.cache_middleware]  # 添加中间件
        )



    def llm_warpper(
            self,
            selected_model
    ):
        """
        将注册的大模型包装成agent可用的模型对象
        :param selected_model: 传入的模型
        :return: 返回一个适配agent模型对象
        """
        return ChatOpenAI(
            base_url=selected_model.api_base,
            model=selected_model.model_name,
            api_key=selected_model.api_key,
        )

    # def close(self):
    #     """✅ 关闭Agent实例及其资源"""
    #     try:
    #         # 关闭后端连接
    #         if hasattr(self, 'backend') and self.backend:
    #             self.backend.close()
    #
    #         # 清理其他资源
    #         if hasattr(self, 'main_agent'):
    #             # 如果agent有cleanup方法，调用它
    #             if hasattr(self.main_agent, 'cleanup'):
    #                 self.main_agent.cleanup()
    #
    #         logger.info(f"AgentManage 资源已清理")
    #
    #     except Exception as e:
    #         logger.error(f"AgentManage 关闭失败: {e}")

    async def process(
            self,
            user_input: str,
            session_id: Optional[str] = None
    ) -> str:
        """处理用户输入

        Args:
            user_input: 用户输入文本
            session_id: 会话 ID（用于上下文持久化）

        Returns:
            Agent 的回复文本
        """
        # 生成或使用提供的会话 ID
        thread_id = session_id or str(uuid.uuid4())

        # 创建配置
        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # 调用 Agent
        result = self.main_agent.invoke(
            {"messages": [{"role": "user", "content": user_input}]},
            config=config
        )

        # 返回最终响应
        return result["messages"][-1].content

    async def process_stream(self, user_input: str, session_id: Optional[str] = None):
        """流式处理用户输入（用于实时显示进度）

        Args:
            user_input: 用户输入文本
            session_id: 会话 ID

        Yields:
            流式事件 chunks
        """
        thread_id = session_id or str(uuid.uuid4())

        config = {
            "configurable": {
                "thread_id": thread_id
            }
        }

        # 流式调用
        for chunk in self.main_agent.stream(
                {"messages": [{"role": "user", "content": user_input}]},
                config=config,
                stream_mode=["updates", "messages"],
                subgraphs=True,
                version="v2",
        ):
            yield chunk


    def get_news_researcher_subagent(self, cache_middleware):
        """资讯研究员子 Agent

        职责：深入研究特定 AI 主题，收集并分析相关文章
        加载 Skills：ai-news（获取领域知识和工作流程）
        """
        return {
            "name": "news-researcher",
            "description": "深入研究特定AI主题，搜索相关文章并进行分析，提供专业的研究报告",
            "system_prompt": """你是一个专业的 AI 资讯研究员。

    ## 你的职责
    深入研究特定 AI 主题，搜索相关文章并进行评分分析，提供专业的研究报告。

    ## 工作流程
    1. 参考ai-news的skill的流程执行
    2. 综合分析生成研究报告

    ## 输出格式
    - 研究主题
    - 发现的文章数量
    - 高质量文章列表（标题 + 评分 + 摘要）
    - 综合分析与趋势洞察
    - 推荐阅读（得分最高的 3 篇文章）
    
    ## 工具使用原则
    
    - 调用工具获取信息后，如果已能回答用户问题，不要重复调用
    - 不要为了"验证"而重复调用相同的工具
    - 如果需要多次调用不同工具，明确说明目的

    保持响应简洁、专业，便于用户快速获取关键信息。""",
            "tools": ai_news_tools,  # 引用 AI 资讯工具
            "skills": [os.path.join(SKILLS_DIR, "ai-news")],  # 加载 AI 资讯 Skill 获取专业知识
            "middleware": [cache_middleware]
        }

    def get_github_analyzer_subagent(self, cache_middleware):
        """GitHub 分析师子 Agent

        职责：分析 GitHub 热门项目，提取技术趋势和价值洞察
        加载 Skills：github-trending（获取领域知识和工作流程）
        """
        return {
            "name": "github-analyzer",
            "description": "分析GitHub热门项目，提供技术趋势分析和项目推荐",
            "system_prompt": """你是一个专业的 GitHub 技术分析师。

    ## 你的职责
    分析 GitHub 热门项目，提取技术趋势和价值洞察。

    ## 工作流程
    1. 参考github-trending的skill的流程执行
    2. 综合分析生成项目推荐或技术趋势分析

    ## 输出格式
    - 趋势概述（热门语言、技术方向）
    - 重点推荐项目（项目名 + 星标数 + 语言 + 简短描述）
    - 技术洞察（基于项目描述的分析）

    保持响应简洁、专业，突出最有价值的信息。""",
            "tools": github_proj_tools,  # 引用 GitHub 工具
            "skills": [os.path.join(SKILLS_DIR, "github-trending")],  # 加载 GitHub Skill 获取专业知识
            "middleware": [cache_middleware]
        }

    def get_general_assistant_subagent(self, cache_middleware):
        """通用助手子 Agent

        职责：处理通用任务，如问答、解释、建议等
        加载 Skills：general（获取通用任务知识）
        """
        return {
            "name": "general-assistant",
            "description": "处理通用问答、解释概念、提供建议等任务",
            "system_prompt": """你是一个专业的 AI 助手。

    ## 你的职责
    1. 回答用户的通用问题
    2. 解释技术概念
    3. 提供建议和指导
    4. 协助处理日常任务

    ## 回复要求
    - 准确、专业、易于理解
    - 结构清晰，重点突出
    - 适当使用 emoji 增强可读性""",
            "tools": base_tools,  # 引用基础工具
            "skills": [os.path.join(SKILLS_DIR, "basic")],  # 加载通用 Skill
            "middleware": [cache_middleware]
        }



def get_agent_manage(
    _selected_model=None,
    _llm_mode=None,
    skills_paths=None,
    store_type: str = "memory",
    db_url: Optional[str] = None,
    db_path: Optional[str] = None,
):

    return AgentManage(
        _selected_model=_selected_model,
        _llm_mode=_llm_mode,
        skills_paths=skills_paths,
        store_type= store_type,
        db_url = db_url,
        db_path = db_path,
    )
