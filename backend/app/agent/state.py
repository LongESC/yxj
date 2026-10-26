"""LangGraph Agent 状态定义"""

from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class AgentState(TypedDict):
    """Agent 图状态"""
    messages: Annotated[list[Any], add_messages]
    user_id: int
    kb_ids: list[int]
    rewritten_queries: list[str]
    retrieved_chunks: list[dict]
    citations: list[dict]
    iteration: int
    token_usage: dict[str, int]
    answer_type: str
    trace_id: str
