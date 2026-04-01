# AI News Bot

> 🔥 AI资讯与GitHub热门项目自动收录工具 - 让你不错过任何AI领域的重要动态

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.135+-009688.svg)](https://fastapi.tiangolo.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://www.docker.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## ✨ 功能特性

### 📊 数据采集
- 🤖 **自动采集**: 从RSS订阅源和GitHub Trending获取最新AI资讯
- 🔄 **智能去重**: 自动识别和过滤重复内容
- 🌐 **多源聚合**: 支持配置多个RSS源，一站式获取AI动态

### 🧠 智能处理
- 📝 **智能摘要**: 使用LLM生成文章摘要、提取关键词、生成标签
- 🏷️ **自动打标**: 智能生成文章标签，便于分类检索
- ⭐ **价值评分**: 使用LLM对资讯进行0-100分评分，从技术创新性、商业价值、行业影响力、时效性、实用价值五个维度评估
- 🚀 **实时推送**: 高分资讯(≥8分)处理完成后立即推送

### 📱 消息推送
- 📊 **日报/周报**: AI资讯与GitHub热门每日/每周汇总推送
- 🔔 **多渠道推送**: 支持企业微信（群机器人+自建应用）、Telegram
- 🤖 **智能对话**: 基于Agentic架构的智能对话处理，支持工具使用、上下文管理和多轮对话

### ⚙️ 系统特性
- ⏰ **定时任务**: 自动采集、处理、即时推送、每日精选、每周汇总
- 🔍 **搜索功能**: 支持全文检索历史资讯
- 🔄 **多平台LLM智能切换**: 支持智谱、硅基流动、OpenRouter等多平台模型智能切换和轮询，解决单一模型并发限制导致的429错误
- 🐳 **Docker部署**: 一键部署，开箱即用

## 快速开始

### 1. 环境要求

- Python 3.11+
- Docker & Docker Compose (可选)

### 2. 本地开发

```bash
# 克隆项目
git clone <repo-url>
cd ai_news_bot

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt

# 复制配置文件
cp .env.example .env

# 编辑 .env 文件，配置必要的参数
# 至少需要配置:
# - WECOM_WEBHOOK_KEY: 企业微信Webhook Key
# - OPENAI_API_KEY: OpenAI API Key (用于智谱和评分)
# - SILICONFLOW_API_KEY: 硅基流动API密钥
# - OLLAMA_BASE_URL: Ollama服务地址 (可选，用于本地摘要)

# 启动应用
python -m uvicorn app.main:app --reload
```

### 3. Docker部署

```bash
# 复制配置文件
cp .env.example .env

# 编辑 .env 文件

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

## 配置说明

### .env 配置文件

| 变量 | 说明 | 必填 | 默认值 |
|-----|------|-----|-------|
| **企业微信-群机器人** | | | |
| `WECOM_WEBHOOK_KEY` | 企业微信群机器人Webhook Key | ✅ | - |
| **企业微信-自建应用（双向交互）** | | | |
| `WECOM_CORP_ID` | 企业ID | ❌ | - |
| `WECOM_AGENT_ID` | 自建应用ID | ❌ | - |
| `WECOM_AGENT_SECRET` | 自建应用密钥 | ❌ | - |
| `WECOM_TOKEN` | API接收消息Token | ❌ | - |
| `WECOM_AES_KEY` | API接收消息EncodingAESKey | ❌ | - |
| **LLM配置** | | | |
| `OPENAI_API_KEY` | OpenAI API Key（智谱也用此字段） | ✅ | - |
| `OPENAI_API_BASE` | OpenAI API 地址 | ❌ | https://api.openai.com/v1 |
| `SILICONFLOW_API_KEY` | 硅基流动API密钥 | ❌ | - |
| `SILICONFLOW_API_BASE` | 硅基流动API地址 | ❌ | https://api.siliconflow.cn/v1 |
| `OPENROUTER_API_KEY` | OpenRouter API密钥 | ❌ | - |
| `OPENROUTER_API_BASE` | OpenRouter API地址 | ❌ | https://openrouter.ai/api/v1 |
| `OLLAMA_BASE_URL` | Ollama服务地址 | ❌ | - |
| `OLLAMA_MODEL` | 本地模型名称 | ❌ | llama3 |
| **其他配置** | | | |
| `GITHUB_TOKEN` | GitHub API Token | ❌ | - |

### 企业微信双向交互配置

项目支持两种企业微信接入方式：

#### 1. 群机器人模式（仅推送）
适合只需要单向推送资讯的场景，配置简单：
```bash
WECOM_WEBHOOK_KEY=your-webhook-key
```

#### 2. 自建应用模式（双向交互）
支持用户发送指令、智能对话等双向交互功能：
```bash
WECOM_CORP_ID=your-corp-id
WECOM_AGENT_ID=your-agent-id
WECOM_AGENT_SECRET=your-agent-secret
WECOM_TOKEN=your-token
WECOM_AES_KEY=your-encoding-aes-key
```

**自建应用模式特性**：
- 🔐 使用企业微信官方SDK进行消息加解密
- 🤖 基于Agentic架构的智能对话处理
- 🧠 支持上下文管理和多轮对话
- 🛠️ 支持工具调用，可查询资讯、执行评分等操作

### LLM模型配置

项目支持多平台LLM模型智能切换，可在 `app/main.py` 的 `init_llm_models()` 函数中配置：

| 平台 | 模型 | 思考模式 | 工具使用 | 用途 | 并发限制 |
|-----|------|---------|---------|------|----------|
| 智谱 | glm-4.7-flash | ✅ 可关闭 | ✅ 支持 | 摘要、关键词、标签、报告增强 | 1 (文档限制) |
| 智谱 | glm-4-flash-250414 | ✅ 可关闭 | ❌ 不支持 | 摘要、关键词、标签、报告增强 | 5 (文档限制) |
| OpenRouter | z-ai/glm-4.5-air:free | ✅ 可关闭 | ✅ 支持 | 摘要、关键词、标签、报告增强 | 可配置 |
| OpenRouter | nvidia/nemotron-3-nano-30b-a3b:free | ❌ 强制开启 | ✅ 支持 | 评分（需要推理） | 可配置 |
| OpenRouter | nvidia/nemotron-3-super-120b-a12b:free | ❌ 强制开启 | ✅ 支持 | 评分（需要推理） | 可配置 |
| 硅基流动 | Qwen/Qwen3-8B | ✅ 可关闭 | ✅ 支持 | 摘要、关键词、标签、报告增强 | 可配置 (默认1) |
| 硅基流动 | DeepSeek-R1-0528-Qwen3-8B | ❌ 强制开启 | ❌ 不支持 | 评分（需要推理） | 可配置 (默认1) |
| 硅基流动 | THUDM/GLM-Z1-9B-0414 | ❌ 强制开启 | ❌ 不支持 | 评分（需要推理） | 可配置 (默认1) |
| 硅基流动 | THUDM/GLM-4.1V-9B-Thinking | ❌ 强制开启 | ❌ 不支持 | 评分（需要推理） | 可配置 (默认1) |

**设计原理**：

- **思考模式**：需要思考的任务（评分）→ 使用推理模型；不需要思考的任务（摘要/标签/报告增强）→ 优先使用能关闭思考的模型，节省Token和响应时间
- **工具使用**：支持工具使用的模型可用于Agentic架构的智能对话场景
- **并发控制**：通过智能轮询和并发控制，有效规避单一模型的429限流错误
- **多平台冗余**：当一个平台的模型达到并发限制时，自动切换到其他平台的可用模型

**配置说明**：
```python
# 在 app/main.py 的 init_llm_models() 函数中配置
llm_manager.register_model(
    provider=LLMProvider.SILICONFLOW,  # 平台：ZHIPU, SILICONFLOW, OPENROUTER
    model_name="your-model-name",      # 模型名称
    api_key=settings.siliconflow_api_key,  # API密钥
    api_base=settings.siliconflow_api_base,  # API地址
    can_disable_thinking=True,  # 是否能关闭思考模式
    can_use_tool=True,          # 是否支持工具使用
    max_concurrent=3            # 最大并发数
)
```

### Agentic智能对话架构

项目采用Agentic架构实现智能对话功能，支持企业微信双向交互场景：

```
┌─────────────────────────────────────────────────────────┐
│                     主Agent (AgentManage)                 │
│  职责: 理解意图 → 任务规划 → 协调执行 → 记忆管理 → 综合回复 │
├─────────────────────────────────────────────────────────┤
│                        子Agent团队                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐  │
│  │news-researcher│  │github-analyzer│  │general-assistant│  │
│  │  AI资讯研究   │  │ GitHub分析   │  │   通用助手      │  │
│  └─────────────┘  └─────────────┘  └─────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                       工具层 (Tools)                      │
│  ┌─────────────────────────────────────────────────────┐ │
│  │ 查询资讯 │ 项目分析 │ 评分工具 │ 上下文管理 │ ... │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

**核心特性**：
- 🧠 **意图理解**：准确理解用户需求，智能路由到合适的子Agent
- 📋 **任务规划**：使用`write_todos`工具规划复杂任务
- 🤝 **多Agent协作**：主Agent协调多个专业子Agent分工执行
- 💾 **长期记忆**：持久化存储用户偏好和交互历史
- 🔄 **上下文管理**：支持多轮对话，保持对话连贯性
- 🛠️ **工具集成**：LLM可调用内部功能作为工具（查询资讯、执行评分等）

**子Agent说明**：
| Agent | 职责 | 使用场景 |
|-------|------|----------|
| `news-researcher` | AI资讯研究 | 深入分析AI资讯主题 |
| `github-analyzer` | GitHub分析 | 分析热门项目和趋势 |
| `general-assistant` | 通用助手 | 处理通用问答和任务 |

详细实现请参考：[企业微信回调实现指南](./企业微信回调.md)

### 定时任务

| 任务 | 触发方式 | 说明 |
|-----|---------|-----|
| 采集AI资讯 | 每1.5小时 | 从RSS源获取最新AI资讯 |
| 采集GitHub热门 | 每天7:00 | 获取GitHub Trending |
| 处理待处理内容 | 每1小时 | LLM生成摘要+评分+打标 |
| 即时推送 | 处理完成后 | 高分资讯(≥8分)立即推送 |
| 发送日报 | 每天9:00 | AI资讯+GitHub热门汇总 |
| 发送周报 | 每周一8:00 | 本周精选汇总 |
| 采集GitHub周热门 | 每周一6:00 | 获取GitHub Trending |

## 使用指令

| 指令 | 功能 |
|-----|------|
| `/ai_news [数量] [时间]` | 获取AI资讯 |
| `/github [语言] [时间]` | 获取GitHub热门 |
| `/today` | 今日简报 |
| `/search <关键词>` | 搜索历史 |
| `/sub <主题>` | 订阅主题 |
| `/settings` | 个人设置 |
| `/help` | 帮助文档 |

## API接口

| 接口 | 方法 | 说明 |
|-----|------|------|
| `/` | GET | 根路径 |
| `/health` | GET | 健康检查 |
| `/command` | POST | 处理指令 |
| `/fetch` | POST | 手动触发采集 |
| `/stats` | GET | 统计信息 |
| `/webhook/wecom` | POST | 企业微信回调 |
| `/webhook/telegram` | POST | Telegram回调 |

## 项目结构

```
ai_news_bot/
├── app/
│   ├── __init__.py
│   ├── config.py              # 配置管理（支持多平台LLM配置）
│   ├── database.py            # 数据库（SQLAlchemy + SQLite）
│   ├── main.py                # FastAPI入口（含LLM模型注册）
│   ├── logging.conf           # 日志配置
│   ├── models/
│   │   └── __init__.py        # 数据模型（Article, GitHubRepo, User）
│   ├── utils/
│   │   └── ...                # 工具函数（加解密等）
│   └── services/
│       ├── commands.py         # 指令解析与处理
│       ├── fetcher/
│       │   ├── __init__.py
│       │   ├── rss_parser.py   # RSS订阅源解析
│       │   └── github_trending.py  # GitHub Trending采集
│       ├── notifier/
│       │   ├── __init__.py
│       │   ├── base.py         # 消息推送基类
│       │   └── wecom_callback.py  # 企业微信回调处理
│       ├── processor/
│       │   ├── __init__.py
│       │   ├── llm_manager.py  # LLM调用管理器（多平台切换+并发控制+工具使用）
│       │   ├── llm_service.py  # LLM服务封装
│       │   ├── summarizer.py   # 摘要/关键词/标签生成
│       │   ├── scorer.py       # 文章评分
│       │   └── deduplicator.py # 内容去重
│       ├── scheduler/
│       │   ├── __init__.py
│       │   └── jobs.py         # 定时任务调度
│       └── agentic/            # Agentic智能对话架构
│           ├── __init__.py
│           ├── agent_manage.py # Agent管理（主Agent+子Agent协调）
│           ├── backend.py      # 后端存储工厂
│           ├── context_manager.py  # 上下文管理
│           ├── skills/         # Agent技能目录
│           └── tools/          # Agent工具集
├── docker/
│   └── Dockerfile
├── nginx/
│   ├── nginx.conf             # Nginx配置
│   └── conf.d/                # 站点配置
├── storage/                   # 数据存储目录
├── logs/                      # 日志目录
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .env                       # 环境配置（不提交到Git）
├── 大模型切换.md              # 大模型切换方案设计文档
├── 企业微信回调.md            # 企业微信回调实现指南（Agentic架构版）
├── 部署步骤参考.md            # 部署参考文档
└── README.md
```

## 核心模块说明

### 1. LLM调用管理器 (llm_manager.py)

项目核心模块，实现多平台LLM智能切换：

- **多平台支持**: 管理智谱、硅基流动等多个LLM提供商
- **智能模型选择**: 根据任务类型（是否需要思考）自动选择合适模型
- **并发控制**: 使用 `asyncio.Semaphore` 限制各模型并发数，防止429错误
- **轮询调度**: 平衡各模型负载，提高整体吞吐量
- **故障转移**: 主模型失败时自动切换到备用模型
- **集中重试**: 统一处理429等限流错误，支持指数退避
- **工具集成**: 支持LLM调用内部功能作为工具（如查询资讯、评分等）

### 2. 摘要生成器 (summarizer.py)

- 生成文章摘要（100-200字）
- 提取关键词（3-8个）
- 生成标签（2-5个）
- 支持批量处理
- 支持Ollama本地模型和OpenAPI方式

### 3. 评分器 (scorer.py)

- 0-10分评分体系
- 5大维度评估：技术创新性、商业价值、行业影响力、时效性、实用价值
- 高分内容(≥8分)即时推送
- 支持单篇和批量评分

### 4. 定时任务调度 (scheduler/jobs.py)

基于APScheduler的异步调度：
- 资讯采集（AI新闻和GitHub Trending）
- 内容处理（摘要+评分+打标）
- 即时推送（高分内容）
- 日报/周报汇总生成和推送

## 扩展开发

### 添加新的RSS源

在 `.env` 中配置:
```
DEFAULT_RSS_SOURCES=https://example.com/feed.xml|https://another.com/rss
```

### 添加新的LLM模型

在 `app/main.py` 的 `init_llm_models()` 函数中添加：

```python
llm_manager.register_model(
    provider=LLMProvider.SILICONFLOW,  # 或 LLMProvider.ZHIPU
    model_name="your-model-name",
    api_key=settings.siliconflow_api_key,  # 或 settings.openai_api_key
    api_base=settings.siliconflow_api_base,  # 或 settings.openai_api_base
    can_disable_thinking=True,  # 是否能关闭思考模式
    max_concurrent=3  # 最大并发数
)
```

### 添加新的推送渠道

参考 `app/services/notifier/base.py` 实现新的通知器类。

### 添加新的数据源

在 `app/services/fetcher/` 目录下添加新的采集器。

### 添加新的Agent技能

在 `app/services/agentic/skills/` 目录下添加新的技能文件，参考现有技能格式。

### 添加新的Agent工具

在 `app/services/agentic/tools/` 目录下添加新的工具函数，并在 `all_tools` 列表中注册。

## 使用示例

### 1. 通过API触发采集

```bash
# 采集AI资讯
curl -X POST "http://localhost:8001/fetch" \
  -H "Content-Type: application/json" \
  -d '{"source": "news"}'

# 采集GitHub热门
curl -X POST "http://localhost:8001/fetch" \
  -H "Content-Type: application/json" \
  -d '{"source": "github"}'

# 采集所有
curl -X POST "http://localhost:8001/fetch" \
  -H "Content-Type: application/json" \
  -d '{"source": "all"}'
```

### 2. 通过API发送指令

```bash
# 获取今日简报
curl -X POST "http://localhost:8001/command" \
  -H "Content-Type: application/json" \
  -d '{"text": "/today"}'

# 搜索AI相关资讯
curl -X POST "http://localhost:8001/command" \
  -H "Content-Type: application/json" \
  -d '{"text": "/search GPT-4"}'

# 获取GitHub热门项目
curl -X POST "http://localhost:8001/command" \
  -H "Content-Type: application/json" \
  -d '{"text": "/github Python weekly"}'
```

### 3. 查看统计信息

```bash
curl "http://localhost:8001/stats"
```

## 常见问题

### Q: 如何解决429限流错误？

A: 项目通过多平台LLM智能切换机制解决此问题：
1. 配置多个LLM平台（智谱、硅基流动、OpenRouter）
2. 为每个模型设置合理的 `max_concurrent` 值
3. 系统会自动轮询和切换可用模型

### Q: 企业微信自建应用如何配置？

A: 参考以下步骤：
1. 在企业微信管理后台创建自建应用
2. 获取 `CorpID`、`AgentID`、`AgentSecret`
3. 配置回调URL和Token
4. 将配置填入 `.env` 文件
5. 详细指南请参考：[企业微信回调实现指南](./企业微信回调.md)

### Q: 如何添加自定义RSS源？

A: 在 `.env` 文件中配置 `DEFAULT_RSS_SOURCES`，多个源用 `|` 分隔：
```bash
DEFAULT_RSS_SOURCES=https://openai.com/blog/rss.xml|https://news.ycombinator.com/rss|https://your-custom-feed.com/rss
```

### Q: Docker部署时如何查看日志？

A: 使用以下命令：
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f app

# 查看最近100行日志
docker-compose logs --tail=100 app
```

### Q: 如何更换LLM模型？

A: 修改 `app/main.py` 中的 `init_llm_models()` 函数，注册新的模型配置。确保：
1. API密钥和地址正确
2. `can_disable_thinking` 设置符合模型特性
3. `max_concurrent` 根据平台限制设置

### Q: 评分阈值如何调整？

A: 在 `.env` 文件中修改 `PUSH_SCORE_THRESHOLD`：
```bash
# 只有评分>=7的资讯才会立即推送
PUSH_SCORE_THRESHOLD=7
```

## 许可证

MIT License

## 贡献

欢迎提交Issue和PR！
