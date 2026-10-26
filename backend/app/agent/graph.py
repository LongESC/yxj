"""LangGraph ReAct Agent 图构建 — 对应 agent.md §3-4

完整图结构：
START → guard_in → rewrite → agent ⇄ tools → synthesize → verify → guard_out → END
"""

import time
import uuid
from typing import Literal

from langchain_core.messages import AIMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from app.agent.callbacks import AgentCallback
from app.agent.prompts import PROMPT_VERSIONS, SYSTEM_PROMPT
from app.agent.state import AgentState
from app.agent.tools import TOOLS, current_kb_ids, current_retrieved, current_user_id
from app.core.config import get_settings
from app.infrastructure.llm import build_llm

settings = get_settings()

# 图版本 — 对应版本管理.md §10.2
GRAPH_VERSION = "v1.0.0"


# ============================================================
# 节点函数
# ============================================================

async def guard_in(state: AgentState) -> dict:
    """输入安检 + 限流 + 权限计算"""
    return {
        "trace_id": str(uuid.uuid4())[:8],
        "iteration": 0,
        "verify_retry": 0,
        "token_usage": {"prompt": 0, "completion": 0},
        "answer_type": "normal",
        "rewritten_queries": [],
        "retrieved_chunks": [],
        "citations": [],
        "start_time": time.time(),
    }


async def rewrite_query(state: AgentState) -> dict:
    """查询改写：将口语化问题改写为检索友好的 query"""
    # 一期：直接使用原始问题作为检索 query
    # TODO: 接入 LLM 做指代消解
    last_msg = state["messages"][-1]
    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    return {"rewritten_queries": [query]}


async def call_model(state: AgentState) -> dict:
    """ReAct 核心：模型推理 + 工具调用决策"""
    llm = build_llm().bind_tools(TOOLS)

    # 注入权限上下文（ContextVar）
    current_kb_ids.set(state["kb_ids"])
    current_retrieved.set(state["retrieved_chunks"])
    current_user_id.set(state["user_id"])

    iteration = state.get("iteration", 0) + 1

    # 注入系统提示词
    messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
    response = await llm.ainvoke(messages)

    # 统计 token
    token_usage = state.get("token_usage", {"prompt": 0, "completion": 0})
    if hasattr(response, "response_metadata") and "token_usage" in response.response_metadata:
        usage = response.response_metadata["token_usage"]
        token_usage["prompt"] += usage.get("prompt_tokens", 0)
        token_usage["completion"] += usage.get("completion_tokens", 0)

    return {
        "messages": [response],
        "iteration": iteration,
        "token_usage": token_usage,
    }


def should_continue(state: AgentState) -> Literal["tools", "synthesize"]:
    """Agent 节点后的路由决策"""
    # 超步数 → 强制生成
    if state["iteration"] >= settings.AGENT_MAX_ITERATIONS:
        return "synthesize"
    # 超时检查
    elapsed = time.time() - state.get("start_time", time.time())
    if elapsed >= settings.AGENT_TIMEOUT:
        return "synthesize"
    # 超 token 预算
    total_tokens = sum(state.get("token_usage", {}).values())
    if total_tokens >= settings.AGENT_TOKEN_BUDGET:
        return "synthesize"
    # 有工具调用 → 执行工具
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "synthesize"


async def synthesize(state: AgentState) -> dict:
    """综合生成最终答案"""
    from app.agent.prompts import SYNTHESIZE_PROMPT

    retrieved = state.get("retrieved_chunks", [])

    if not retrieved:
        return {
            "messages": [AIMessage(content="知识库暂无相关依据，建议通过人工服务获取帮助。")],
            "answer_type": "refused",
        }

    # 构建上下文
    context_parts = []
    for i, chunk in enumerate(retrieved[:settings.MAX_RETRIEVED_CHUNKS], 1):
        title = chunk.get("title_path", "未知文档")
        content = chunk.get("content", "")[:800]
        context_parts.append(f"[{i}] 《{title}》\n{content}")

    context = "\n\n---\n\n".join(context_parts)

    # 获取用户问题
    user_question = ""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "type") and msg.type == "human":
            user_question = msg.content
            break

    prompt = SYNTHESIZE_PROMPT.format(context=context, question=user_question)
    llm = build_llm(temperature=0.3)
    response = await llm.ainvoke([SystemMessage(content=prompt)])

    # 构建引用
    citations = []
    for i, chunk in enumerate(retrieved[:settings.MAX_RETRIEVED_CHUNKS], 1):
        citations.append({
            "cite_no": i,
            "chunk_id": chunk.get("chunk_id", 0),
            "doc_title": chunk.get("title_path", ""),
            "snippet": chunk.get("content", "")[:200],
            "score": chunk.get("score", 0),
        })

    return {
        "messages": [response],
        "citations": citations,
        "answer_type": "normal",
    }


async def verify_citations(state: AgentState) -> dict:
    """引用校验：检查答案中的 [n] 编号是否合理"""
    # 一期简化：直接通过
    # TODO: 接入 LLM 做引用校验
    return {}


def on_verify_result(state: AgentState) -> Literal["guard_out", "synthesize"]:
    """校验结果路由"""
    retry = state.get("verify_retry", 0)
    if retry >= settings.RETRY_ON_VERIFY_FAIL:
        return "guard_out"
    # 一期直接通过
    return "guard_out"


async def guard_out(state: AgentState) -> dict:
    """输出安检 + AI 标识 + 免责声明"""
    # 一期简化：直接通过
    return {}


# ============================================================
# 图构建
# ============================================================

def build_graph():
    """构建并编译 LangGraph Agent 图"""
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("guard_in", guard_in)
    graph.add_node("rewrite", rewrite_query)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("synthesize", synthesize)
    graph.add_node("verify", verify_citations)
    graph.add_node("guard_out", guard_out)

    # 入口
    graph.add_edge(START, "guard_in")

    # 固定边
    graph.add_edge("guard_in", "rewrite")
    graph.add_edge("rewrite", "agent")
    graph.add_edge("tools", "agent")
    graph.add_edge("synthesize", "verify")
    graph.add_edge("verify", "guard_out")
    graph.add_edge("guard_out", END)

    # 条件边
    graph.add_conditional_edges(
        "agent", should_continue,
        {"tools": "tools", "synthesize": "synthesize"},
    )

    return graph.compile()


# 全局图实例
agent_graph = build_graph()
