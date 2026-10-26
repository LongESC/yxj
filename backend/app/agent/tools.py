"""LangGraph Agent 工具定义"""

import asyncio
from contextvars import ContextVar
from langchain_core.tools import tool

# 权限上下文变量：由服务端注入，模型不可控
current_kb_ids: ContextVar[list[int]] = ContextVar("kb_ids", default=[])
current_retrieved: ContextVar[list[dict]] = ContextVar("retrieved", default=[])


@tool
async def knowledge_search(query: str, top_k: int = 6) -> str:
    """在高校知识库中检索与问题相关的原文片段。

    适用：需要依据制度文件、办事指南、政策规定作答时。
    不适用：问候、闲聊、知识库范围外的问题。
    返回片段带 [n] 编号，最终答案必须使用相同编号标注引用。
    """
    kb_ids = current_kb_ids.get()
    # TODO: 接入 Milvus 混合检索
    # chunks = await hybrid_search(query, kb_ids, top_k)
    # current_retrieved.get().extend(chunks)
    # return format_chunks(chunks)
    return f"[模拟检索] 在知识库 {kb_ids} 中搜索: {query} (top_k={top_k})\n\n[1] 示例文档片段 - 这是模拟的检索结果，实际将接入 Milvus 混合检索。"


@tool
async def faq_search(query: str) -> str:
    """在 FAQ 问答对中搜索匹配的问题与标准答案。

    适用：常见问题（如选课时间、成绩复议流程等）的快速回答。
    不适用：需要查阅具体文件原文的复杂问题。
    """
    # TODO: 接入 FAQ 检索
    return f"[模拟FAQ] 搜索: {query}\n\n未找到匹配的 FAQ。"


@tool
async def handoff_human(reason: str) -> str:
    """当知识库无依据时，引导用户转人工服务。

    适用：确认无有效检索结果时。
    返回人工服务渠道信息。
    """
    return (
        "当前知识库暂无相关依据。建议您：\n"
        "1. 联系所在学院教务办公室\n"
        "2. 拨打学校服务热线：023-xxxx-xxxx\n"
        "3. 通过学校 OA 系统提交咨询工单"
    )


# 工具列表
TOOLS = [knowledge_search, faq_search, handoff_human]
