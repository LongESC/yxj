"""LangGraph Agent 状态定义 — 对应 agent.md §2"""

from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class RetrievedChunk(TypedDict, total=False):
    chunk_id: int
    doc_id: int
    kb_id: int
    title_path: str
    page_no: int
    content: str
    score: float


class Citation(TypedDict, total=False):
    cite_no: int
    chunk_id: int
    doc_title: str
    snippet: str
    score: float


class AgentState(TypedDict):
    """Agent 图状态"""
    messages: Annotated[list[Any], add_messages]
    user_id: int
    conversation_id: int
    kb_ids: list[int]                     # 权限过滤后的可见知识库（强制注入）
    rewritten_queries: list[str]          # 改写后的检索 query
    retrieved_chunks: list[RetrievedChunk]  # 累计召回切片（去重）
    citations: list[Citation]             # 最终引用
    iteration: int                        # 当前迭代轮次
    token_usage: dict[str, int]           # token 消耗统计
    answer_type: str                      # normal / refused / degraded / unsafe
    trace_id: str
    verify_retry: int                     # 引用校验重试次数
    start_time: float                     # 图开始时间戳
