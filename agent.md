# 高校智能问答助手 Agent 设计文档

| 项目 | 内容 |
|---|---|
| 系统名称 | 高校智能问答助手（`uni-qa`） |
| 文档版本 | **V1.0** |
| 编写日期 | 2026-10-24 |
| 编排框架 | LangGraph 0.2（ReAct Agent） |
| 关联文档 | 技术文档.md、需求文档.md |

---

## 1. Agent 概述

本系统采用 **ReAct（Reasoning + Acting）** 模式的 Agent 作为问答核心编排方式。与传统固定 Pipeline 不同，ReAct Agent 由大模型自主决定每一步调用什么工具、传什么参数，直到收集到足够信息后生成答案。

**为什么选择 ReAct Agent？**
- 高校问题类型多样：有的需要检索一个文档，有的需要跨多个知识库综合
- Agent 可自主判断是否需要补充检索、扩展上下文
- 工具调用过程对用户可见，提升信任感

**风险与约束：**
- 多步推理导致时延上升 → 三重约束（步数/超时/token）
- 行为不完全可控 → 工具白名单 + 权限强制注入 + 过程审计

---

## 2. 状态定义

```python
from typing import Annotated, Any
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]  # 完整对话（含工具消息）
    user_id: int
    kb_ids: list[int]                 # 权限过滤后的可见知识库（强制注入）
    rewritten_queries: list[str]      # 改写后的检索 query
    retrieved: list[RetrievedChunk]   # 累计召回切片（去重）
    citations: list[Citation]         # 最终引用
    iteration: int                    # 当前迭代轮次
    token_usage: dict[str, int]       # token 消耗统计
    answer_type: str                  # normal / refused / degraded / unsafe
    trace_id: str                     # 链路追踪 ID
```

**关键设计：**
- `kb_ids` 由服务端根据用户权限计算后注入 state，**工具不接受此参数**，模型无法绕过
- `iteration` 用于步数约束，每次进入 agent 节点递增
- `answer_type` 标记最终回答类型，便于统计与审计

---

## 3. 图结构

```
                    ┌──────────┐
         ┌─────────▶│ guard_in │  输入安检 + 限流 + 权限计算
         │          └─────┬────┘
         │                ▼
         │          ┌──────────┐
         │          │ rewrite  │  查询改写（1~3 个 query，历史指代消解）
         │          └─────┬────┘
         │                ▼
         │          ┌──────────┐
         │   ┌─────▶│  agent   │  ReAct：Thought → Action
         │   │      └─────┬────┘
         │   │            ▼ 条件边：tool_calls? / 超步数? / 超时?
         │   │      ┌──────────┐
         │   └──────│  tools   │  knowledge_search / faq_search / ...
         │          └─────┬────┘
         │                ▼ (无 tool_calls 或达到上限)
         │          ┌──────────┐
         │          │synthesize│  综合生成，强制带引用编号
         │          └─────┬────┘
         │                ▼
         │          ┌──────────┐
         │          │  verify  │  引用校验；缺失/无依据 → 最多重试 1 次
         │          └─────┬────┘
         │                ▼
         │          ┌──────────┐
         └──────────│ guard_out│  输出安检 + AI 标识 + 免责声明
                    └─────┬────┘
                          ▼  END（SSE 流输出）
```

### 3.1 节点说明

| 节点 | 职责 | 输入 | 输出 |
|---|---|---|---|
| `guard_in` | 输入安检（敏感词检测）、限流（用户频率控制）、权限计算（确定 kb_ids） | 用户原始问题 | 安检结果、限流标记、kb_ids |
| `rewrite` | 查询改写：将口语化/指代性问题改写为 1–3 个个检索友好的 query | 用户问题 + 历史 5 轮 | rewritten_queries |
| `agent` | ReAct 核心：模型决定调用哪个工具、传什么参数 | state.messages + 工具描述 | tool_calls 或最终答案意向 |
| `tools` | 执行工具调用，返回结构化结果 | agent 的 tool_calls | 工具结果写入 messages |
| `synthesize` | 综合所有召回信息生成最终答案，强制带引用编号 [n] | retrieved chunks + 问题 | 答案文本 |
| `verify` | 引用校验：检查答案中 [n] 编号是否与引用块对应 | 答案 + citations | 校验结果，不合格则触发重试 |
| `guard_out` | 输出安检、追加 AI 生成标识、免责声明 | 最终答案 | 处理后的答案 |

### 3.2 条件边

```python
def should_continue(state: AgentState) -> str:
    """Agent 节点后的路由决策"""
    # 超步数 → 强制生成
    if state["iteration"] >= settings.AGENT_MAX_ITERATIONS:  # 默认 4
        return "synthesize"
    last = state["messages"][-1]
    # 有工具调用 → 执行工具
    if getattr(last, "tool_calls", None):
        return "tools"
    # 无工具调用 → 生成答案
    return "synthesize"
```

---

## 4. 图构建代码

```python
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver  # 一期；生产换 RedisSaver

def build_agent_graph() -> StateGraph:
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("guard_in", guard_in_node)
    graph.add_node("rewrite", rewrite_query_node)
    graph.add_node("agent", call_model_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("synthesize", synthesize_node)
    graph.add_node("verify", verify_citations_node)
    graph.add_node("guard_out", guard_out_node)

    # 固定边
    graph.add_edge("guard_in", "rewrite")
    graph.add_edge("rewrite", "agent")
    graph.add_edge("tools", "agent")        # 工具执行后回到 agent 继续推理
    graph.add_edge("synthesize", "verify")
    graph.add_edge("guard_out", END)

    # 条件边
    graph.add_conditional_edges(
        "agent", should_continue,
        {"tools": "tools", "synthesize": "synthesize"}
    )
    graph.add_conditional_edges(
        "verify", on_verify_result,
        {"retry": "synthesize", "pass": "guard_out"}
    )

    return graph.compile(checkpointer=InMemorySaver())
```

---

## 5. 三重约束（必须配置）

Agent 模式下如果不加约束，模型可能无限循环调用工具，导致时延失控、成本爆炸。

| 约束 | 配置项 | 默认值 | 说明 |
|---|---|---|---|
| 步数上限 | `AGENT_MAX_ITERATIONS` | 4 | 工具调用轮次上限，超限强制进入 synthesize |
| 总超时 | `AGENT_TIMEOUT` | 20s | 整图超时（asyncio.timeout），超时走降级 |
| Token 预算 | `AGENT_TOKEN_BUDGET` | 12000 | 单次问答 token 上限，超预算停止迭代 |
| 工具结果截断 | `MAX_TOOL_RESULT_CHARS` | 3000 | 单工具返回截断长度，防止上下文爆炸 |
| 召回上限 | `MAX_RETRIEVED_CHUNKS` | 8 | 进入生成的切片上限，超出按分数截断 |
| 校验重试 | `RETRY_ON_VERIFY_FAIL` | 1 | 引用校验失败最多重生成 1 次 |

---

## 6. 工具定义

### 6.1 工具清单

| 工具 | 入参 | 返回 | 说明 |
|---|---|---|---|
| `knowledge_search` | `query: str, top_k: int = 6` | 带 chunk_id 的切片列表 | 主检索工具；kb_ids 由 state 注入 |
| `faq_search` | `query: str` | FAQ 问答对 | 高优先级知识源，命中即优先采用 |
| `document_expand` | `chunk_id: int, window: int = 1` | 相邻切片 | 命中片段上下文不足时补全 |
| `doc_meta_search` | `keyword: str, dept: str = ""` | 文档元数据列表 | 用于"XX 文件在哪/最新版是哪个" |
| `handoff_human` | `reason: str` | 人工渠道信息 | 无依据时的兜底 |

### 6.2 工具契约

- **全部 async**：用 `@tool` 或 `StructuredTool.from_function(coroutine=...)`
- **docstring 即模型可见说明**：必须写清"何时用/何时不用"，这是决定 Agent 行为的关键
- **权限强制注入**：工具内部强制注入 `kb_ids` 权限过滤，模型无法通过参数绕过
- **返回结构化文本**：编号 + 来源 + 正文，便于模型生成引用编号

### 6.3 工具示例

```python
from langchain_core.tools import tool

@tool
async def knowledge_search(query: str, top_k: int = 6) -> str:
    """在高校知识库中检索与问题相关的原文片段。

    适用：需要依据制度文件、办事指南、政策规定作答时。
    不适用：问候、闲聊、知识库范围外的问题（此时不要调用，直接说明无依据）。
    返回片段带 [n] 编号，最终答案必须使用相同编号标注引用。
    """
    kb_ids = current_kb_ids.get()          # contextvar 注入，模型不可控
    chunks = await hybrid_search(query, kb_ids, top_k)
    current_retrieved.get().extend(chunks)  # 累计，供引用校验使用
    return format_chunks(chunks)


@tool
async def faq_search(query: str) -> str:
    """在 FAQ 问答对中搜索匹配的问题与标准答案。

    适用：常见问题（如选课时间、成绩复议流程等）的快速回答。
    不适用：需要查阅具体文件原文的复杂问题。
    命中时优先采用 FAQ 答案，但仍需标注来源。
    """
    faqs = await search_faq(query, kb_ids=current_kb_ids.get())
    if not faqs:
        return "未找到匹配的 FAQ"
    return format_faqs(faqs)
```

---

## 7. 流式输出设计

Agent 模式下用户等待时间较长，**必须把中间过程可视化**。

使用 `graph.astream(..., stream_mode=["custom", "messages"])`，通过 `get_stream_writer()` 推送自定义事件：

| SSE 事件 | 时机 | 前端展示 |
|---|---|---|
| `step` | 进入节点 | "正在理解问题…" / "正在检索知识库…" / "正在核对依据…" |
| `tool_call` | 模型决定调用工具 | "检索：研究生学费缓交流程" |
| `tool_result` | 工具返回 | "找到 6 条相关依据"（可折叠查看） |
| `delta` | 最终答案 token | 打字机输出 |
| `citation` | 引用块 | 底部引用卡片，可点开原文 |
| `done` | 结束 | 耗时、步数、引用数、answer_type |
| `error` | 异常 | 错误提示 + trace_id |

**前端节流**：同类步骤合并展示（如连续 2 次检索只显示最新），避免高频刷新。

---

## 8. 提示词设计

### 8.1 ReAct System Prompt 核心要求

```
你是高校智能问答助手，专门为 {university_name} 的师生提供问答服务。

## 核心原则
1. 只依据知识库中的原文作答，绝不编造
2. 答案中每个事实性陈述必须标注引用编号 [n]
3. 知识库无依据时，明确回复"知识库暂无相关依据"并建议使用 handoff_human
4. 不得回答与高校业务无关的问题（闲聊、通用知识等）

## 回答格式
- 先给出简明答案
- 再展开必要细节
- 关键句后标注 [n] 对应引用来源
- 如涉及办理流程，给出步骤列表 + 办事链接

## 工具使用
- 优先使用 knowledge_search 检索知识库
- 若为常见问题，先尝试 faq_search
- 上下文不足时使用 document_expand 补全
- 确认无依据时调用 handoff_human 引导转人工
```

### 8.2 提示词版本管理

- 提示词存 `prompt_template` 表，按节点分别版本化
- 变更流程：新建版本 → 评测集回归 → 对比报告 → 灰度 → 全量
- 每条消息记录 `prompt_version`，便于追溯

---

## 9. 降级策略

| 故障场景 | 降级动作 | 用户感知 |
|---|---|---|
| 模型超时 / 5xx | 重试 1 次（换备用 endpoint） | 无感，耗时略增 |
| 模型配额耗尽（429） | 返回 Top3 原文片段 + 提示"AI 生成暂不可用" | 有提示，仍可得原文 |
| Agent 超时 / 超步数 | 用已有召回直接生成；无召回则拒答 | 提示"已尽力作答" |
| Embedding 不可用 | 仅走 BM25 稀疏检索 | 无感，语义召回下降 |
| Milvus 不可用 | 走 PostgreSQL 全文兜底 | 提示"检索能力降级" |

---

## 10. 可观测性

### 10.1 LangSmith 链路追踪

每次问答生成完整 trace，包含：
- 各节点耗时
- 工具调用序列与参数
- prompt/completion 内容（需脱敏）
- token 消耗
- 迭代次数

**metadata 必打字段：**
```python
{
    "user_id": state["user_id"],
    "conversation_id": conv_id,
    "kb_ids": state["kb_ids"],
    "graph_version": GRAPH_VERSION,
    "prompt_version": prompt_versions,
    "env": settings.APP_ENV,
}
```

### 10.2 关键监控指标

| 指标 | 说明 | 告警阈值 |
|---|---|---|
| `qa_agent_iterations` | Agent 步数分布 | 平均 > 3 |
| `qa_tool_call_total{tool,status}` | 工具调用统计 | — |
| `qa_total_latency_seconds` | 总时延 | P95 > 15s |
| `qa_refuse_rate` | 拒答率 | 日环比上升 > 10% |
| `qa_feedback_ratio{rating}` | 点踩率 | 日 > 10% |

---

## 11. 安全约束

| 约束 | 实现方式 |
|---|---|
| 工具不暴露权限参数 | `kb_ids` 由 contextvar 注入，工具签名中无此参数 |
| 提示词不可被覆盖 | 用户输入与 system prompt 严格分离，外部文档标记为不可信数据 |
| 注入检测 | 检测"忽略以上指令"类模式，命中则直接拒答 |
| 输出审计 | 所有答案经 guard_out 节点安检后才输出 |
| 链路脱敏 | 上报 LangSmith 前对密钥、个人信息做脱敏处理 |

---

## 12. 图版本管理

| 规则 | 说明 |
|---|---|
| 版本格式 | `graph_version` 语义化：`v1.0.0` |
| 递增条件 | 新增/删除节点或改条件边 → minor；改节点内部逻辑 → patch；改整体编排范式 → major |
| 登记位置 | 代码常量 `GRAPH_VERSION` + 消息表 `graph_version` 字段，二者必须一致 |
| 回归要求 | 图或工具变更必须跑：工具选择正确率、平均步数、超时率、最终答案准确率 |
| 回滚 | 图随代码版本回滚；工具可通过配置开关临时禁用 |
