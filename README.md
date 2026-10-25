# 高校智能问答助手

> 基于 RAG + LangGraph ReAct Agent 的高校智能问答系统

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-green.svg)](https://www.python.org/)
[![Vue](https://img.shields.io/badge/vue-3.x-brightgreen.svg)](https://vuejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-teal.svg)](https://fastapi.tiangolo.com/)

## 项目简介

高校智能问答助手是一个面向高校师生的 AI 问答系统，基于检索增强生成（RAG）技术，以高校自有知识库（教务制度、办事指南、FAQ 等）为唯一依据，为师生提供**可溯源、可管控、可运营**的智能问答服务。

### 核心特性

- **知识库问答**：基于高校制度文件、办事指南等知识库内容准确回答
- **引用溯源**：每个答案标注所依据的原文片段，用户可自行核对
- **多轮对话**：支持上下文理解，如"那研究生呢？"可正确指代前文
- **明确拒答**：知识库无依据时明确告知，不编造答案
- **知识管理**：各部门可自助上传/更新/下线文档，无需研发介入
- **运营监控**：提问量、满意度、热点问题等数据可视化

## 技术栈

| 层级 | 选型 |
|---|---|
| AI 推理引擎 | LangChain 0.3 + LangGraph 0.2（ReAct Agent） |
| 后端框架 | FastAPI + uvicorn（全异步） |
| 数据库 | PostgreSQL 15+（SQLAlchemy 2.0 Async） |
| 向量数据库 | Milvus ≥ 2.5（混合检索） |
| 对象存储 | MinIO（S3 兼容） |
| 缓存/队列 | Redis + Celery |
| LLM 服务 | 火山引擎豆包（ChatOpenAI 兼容） |
| Embedding | 阿里百炼 text-embedding-v3 |
| 用户前端 | Vue 3 + Element Plus + Tailwind CSS + Pinia |
| 管理前端 | Vue 3 + Element Plus + ECharts + Pinia |
| 可观测性 | LangSmith（Agent 链路追踪） |

## 系统架构

```
┌──────────────────────────────────────────────────────────────┐
│ 接入层  用户端 Web(Vue3+Tailwind) / 管理端 Web(Vue3+ElementPlus)│
└──────────────────────────────────────────────────────────────┘
                              │ HTTPS / SSE
┌──────────────────────────────────────────────────────────────┐
│ 网关层  Nginx：反向代理、TLS、限流、静态资源                    │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│ 应用服务层（FastAPI，全异步）                                  │
│  ┌─────────┐┌─────────┐┌─────────┐┌─────────┐              │
│  │会话服务 ││Agent服务││知识库   ││管理后台 │              │
│  │         ││(LangGraph)││服务   ││服务     │              │
│  └─────────┘└─────────┘└─────────┘└─────────┘              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ LangGraph ReAct Agent 编排                           │    │
│  │  安检 → 改写 → [Thought→Action→Observation]×N       │    │
│  │        → 综合生成 → 引用校验 → 输出安检 → SSE        │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
                              │
┌──────────────────────────────────────────────────────────────┐
│ 数据层   PostgreSQL │ Milvus │ Redis │ MinIO                 │
└──────────────────────────────────────────────────────────────┘
```

## 项目结构

```
uni-qa/
├── app/                    # 后端应用
│   ├── api/v1/             # 路由层
│   ├── application/        # 应用服务层
│   ├── agent/              # LangGraph Agent（图/节点/工具/提示词）
│   ├── domain/             # 领域层
│   ├── infrastructure/     # 基础设施层（DB/Vector/LLM/Cache）
│   ├── schemas/            # Pydantic 模型
│   ├── tasks/              # Celery 异步任务
│   └── core/               # 配置/日志/中间件
├── web-user/               # 用户对话端（Vue 3）
├── web-admin/              # 管理后台（Vue 3）
├── migrations/             # Alembic 数据库迁移
├── scripts/                # 运维脚本
├── tests/                  # 测试
├── deploy/                 # 部署配置
└── docs/                   # 项目文档
    ├── 需求文档.md
    ├── 项目描述.md
    ├── agent.md
    ├── 技术文档.md
    ├── 版本管理.md
    └── 数据库.md
```

## 快速开始

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL 15+
- Milvus ≥ 2.5
- Redis 7+
- MinIO

### 后端启动

```bash
# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 填入数据库、模型 API 等配置

# 数据库迁移
alembic upgrade head

# 初始化 Milvus 集合
python scripts/init_milvus.py

# 启动服务
uvicorn app.main:app --reload --port 8000

# 启动 Celery Worker（异步任务）
celery -A app.tasks worker -l info -Q ingestion,default
```

### 前端启动

```bash
# 用户端
cd web-user
pnpm install
pnpm dev

# 管理端
cd web-admin
pnpm install
pnpm dev
```

### Docker 一键部署

```bash
# 启动基础设施（PostgreSQL/Milvus/Redis/MinIO）
docker compose -f deploy/docker-compose.infra.yml up -d

# 启动应用
docker compose up -d
```

## 核心流程

### 文档入库

```
上传 → MinIO → 文件去重 → Celery 链：
  1) parse   文档解析（PDF/Word/OCR）
  2) clean   清洗去噪
  3) chunk   文本切片（512字/片，64字重叠）
  4) embed   向量化（百炼 text-embedding-v3）
  5) index   写入 PostgreSQL + Milvus
  6) publish 上线生效
```

### Agent 问答

```
用户提问 → 输入安检 → 查询改写 → ReAct 循环（最多4轮）：
  Thought → 选择工具 → 执行检索 → Observation → ...
→ 综合生成（带引用）→ 引用校验 → 输出安检 → SSE 流式返回
```

## 配置说明

### 环境变量

| 变量 | 说明 | 示例 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://user:pwd@localhost:5432/uni_qa` |
| `MILVUS_URI` | Milvus 地址 | `http://localhost:19530` |
| `REDIS_URL` | Redis 地址 | `redis://localhost:6379/0` |
| `ARK_API_KEY` | 火山方舟 API Key | `xxx` |
| `DASHSCOPE_API_KEY` | 阿里百炼 API Key | `xxx` |
| `AGENT_MAX_ITERATIONS` | Agent 最大步数 | `4` |
| `AGENT_TIMEOUT` | Agent 超时（秒） | `20` |

## 文档索引

| 文档 | 说明 |
|---|---|
| [需求文档](docs/需求文档.md) | MVP 功能需求、用户角色、验收标准 |
| [项目描述](docs/项目描述.md) | 项目简介、技术栈、系统架构 |
| [Agent 设计](docs/agent.md) | LangGraph ReAct Agent 完整设计 |
| [技术文档](docs/技术文档.md) | 分层架构、模块划分、接口设计 |
| [版本管理](docs/版本管理.md) | GitFlow 规范、提交规范、发布流程 |
| [数据库设计](docs/数据库.md) | 表结构、索引策略、缓存设计 |

## 开发规范

- **代码风格**：Python 用 Black + Ruff，前端用 Prettier + ESLint
- **类型检查**：Python 用 mypy（strict），前端用 vue-tsc
- **提交规范**：Conventional Commits（`feat(scope): 描述`）
- **分支模型**：GitFlow（main/develop/feature/release/hotfix）
- **代码评审**：至少 1 名非作者批准

详见 [版本管理.md](docs/版本管理.md) 和 [编程规范](docs/编程规范.md)

## 性能指标

| 指标 | 目标值 |
|---|---|
| 首可见内容时延 | P95 ≤ 1.5s |
| 完整答案时延 | P95 ≤ 12s |
| 检索召回率 | Recall@5 ≥ 90% |
| 幻觉率 | ≤ 3% |
| 服务可用性 | ≥ 99.5% |

## 常见问题

### Q: 为什么选择 ReAct Agent 而不是固定 Pipeline？

高校问题类型多样，有的需要检索一个文档，有的需要跨多个知识库综合。Agent 可自主判断是否需要补充检索、扩展上下文，灵活性更高。同时通过三重约束（步数/超时/token）保证可控性。

### Q: 如何保证答案不编造？

1. **引用强制**：答案必须标注引用编号 [n]，后处理校验
2. **明确拒答**：无依据时回复"知识库暂无依据"
3. **权限隔离**：检索阶段强制过滤，不可越权

### Q: 模型 API 配额不够怎么办？

- 客户端令牌桶限流，超限排队
- 主备 endpoint 自动切换
- 高频问题答案缓存
- 降级为纯检索结果（不生成）

## 路线图

- [x] 项目文档体系
- [ ] 后端基础框架（FastAPI + PostgreSQL）
- [ ] Milvus 向量检索
- [ ] LangGraph Agent 核心链路
- [ ] 用户对话端（Vue 3）
- [ ] 管理后台（Vue 3）
- [ ] 知识库管理模块
- [ ] 运营看板
- [ ] 评测体系
- [ ] 部署上线

## 许可证

[MIT License](LICENSE)

## 联系方式

- 项目代号：`uni-qa`
- 问题反馈：[GitHub Issues](https://github.com/LongESC/yxj/issues)
