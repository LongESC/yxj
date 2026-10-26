"""LangGraph ReAct Agent 图构建"""

import asyncio
import time
import uuid
from typing import Literal

from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from app.config import get_settings
from app.agent.state import AgentState
from app.agent.tools import TOOLS, current_kb_ids, current_retrieved

settings = get_settings()

# 图版本
GRAPH_VERSION = "v1.0.0"


def build_llm() -> ChatOpenAI:
    """构建豆包 LLM 客户端"""
    return ChatOpenAI(
        model=settings.VOLCENGINE_MODEL,
        base_url=settings.VOLCENGINE_BASE_URL,
        api_key=settings.VOLCENGINE_API_KEY,
        temperature=settings.TEMPERATURE,
        max_tokens=settings.MAX_TOKENS,
        timeout=settings.TIMEOUT,
        max_retries=2,
        streaming=True,
    )


# ============================================================
# 节点函数
# ============================================================

async def guard_in(state: AgentState) -> dict:
    """输入安检 + 权限计算"""
    return {
        "trace_id": str(uuid.uuid4())[:8],
        "iteration": 0,
        "token_usage": {"prompt": 0, "completion": 0},
        "answer_type": "normal",
        "rewritten_queries": [],
        "retrieved_chunks": [],
        "citations": [],
    }


async def rewrite_query(state: AgentState) -> dict:
    """查询改写：将口语化问题改写为检索友好的 query"""
    # TODO: 使用 LLM 进行查询改写
    last_msg = state["messages"][-1]
    query = last_msg.content if hasattr(last_msg, "content") else str(last_msg)
    return {"rewritten_queries": [query]}


async def call_model(state: AgentState) -> dict:
    """ReAct 核心：模型推理 + 工具调用决策"""
    llm = build_llm().bind_tools(TOOLS)

    # 注入权限上下文
    current_kb_ids.set(state["kb_ids"])
    current_retrieved.set(state["retrieved_chunks"])

    iteration = state.get("iteration", 0) + 1

    response = await llm.ainvoke(state["messages"])

    return {
        "messages": [response],
        "iteration": iteration,
    }


def should_continue(state: AgentState) -> Literal["tools", "synthesize"]:
    """Agent 节点后的路由决策"""
    if state["iteration"] >= settings.AGENT_MAX_ITERATIONS:
        return "synthesize"
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return "synthesize"


async def synthesize(state: AgentState) -> dict:
    """综合生成最终答案"""
    # TODO: 使用检索结果构建上下文，生成带引用的答案
    # 目前返回模拟答案
    answer = (
        "根据知识库检索结果，以下是相关信息的整理：\n\n"
        "这是一个模拟回答。实际部署后将基于 Milvus 检索到的原文片段，"
        "由豆包模型生成带引用标注的准确答案。\n\n"
        "如需进一步帮助，请补充具体问题细节。"
    )
    from langchain_core.messages import AIMessage
    return {"messages": [AIMessage(content=answer)], "answer_type": "normal"}


# ============================================================
# 图构建
# ============================================================

def build_graph() -> StateGraph:
    """构建并编译 LangGraph Agent 图"""
    graph = StateGraph(AgentState)

    # 注册节点
    graph.add_node("guard_in", guard_in)
    graph.add_node("rewrite", rewrite_query)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("synthesize", synthesize)

    # 固定边
    graph.add_edge("guard_in", "rewrite")
    graph.add_edge("rewrite", "agent")
    graph.add_edge("tools", "agent")
    graph.add_edge("synthesize", END)

    # 条件边
    graph.add_conditional_edges(
        "agent", should_continue,
        {"tools": "tools", "synthesize": "synthesize"},
    )

    return graph.compile()


# 全局图实例
agent_graph = build_graph()
