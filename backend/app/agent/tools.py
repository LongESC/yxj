"""LangGraph Agent 工具定义 — 对应 agent.md §6"""

from contextvars import ContextVar

from langchain_core.tools import tool

# ── 权限上下文变量（由服务端注入，模型不可控） ──────────
current_kb_ids: ContextVar[list[int]] = ContextVar("kb_ids", default=[])
current_retrieved: ContextVar[list[dict]] = ContextVar("retrieved", default=[])
current_user_id: ContextVar[int] = ContextVar("user_id", default=0)


@tool
async def knowledge_search(query: str, top_k: int = 6) -> str:
    """在高校知识库中检索与问题相关的原文片段。

    适用：需要依据制度文件、办事指南、政策规定作答时。
    不适用：问候、闲聊、知识库范围外的问题。
    返回片段带 [n] 编号，最终答案必须使用相同编号标注引用。
    """
    from app.infrastructure.vector import hybrid_search
    from app.infrastructure.embedding import embed_query

    kb_ids = current_kb_ids.get()
    if not kb_ids:
        return "[未授权访问任何知识库]"

    try:
        dense_vec = await embed_query(query)
    except Exception:
        dense_vec = None

    hits = await hybrid_search(query, kb_ids, top_k=top_k, dense_vec=dense_vec)

    # 累计到 state
    retrieved = current_retrieved.get()
    retrieved.extend(hits)

    if not hits:
        return "[未检索到相关片段]"

    lines = []
    for i, hit in enumerate(hits, 1):
        title = hit.get("title_path", "未知文档")
        content = hit.get("content", "")[:500]
        score = hit.get("score", 0)
        lines.append(f"[{i}] 《{title}》(相关度: {score:.2f})\n{content}\n")

    return "\n".join(lines)


@tool
async def faq_search(query: str) -> str:
    """在 FAQ 问答对中搜索匹配的问题与标准答案。

    适用：常见问题（如选课时间、成绩复议流程等）的快速回答。
    不适用：需要查阅具体文件原文的复杂问题。
    命中时优先采用 FAQ 答案，但仍需标注来源。
    """
    from sqlalchemy import select, or_
    from app.core.database import async_session_factory
    from app.domain.models import FAQ

    kb_ids = current_kb_ids.get()

    async with async_session_factory() as session:
        stmt = select(FAQ).where(FAQ.status == 1)
        if kb_ids:
            stmt = stmt.where(FAQ.kb_id.in_(kb_ids))
        # 简单关键词匹配（一期），后续可接向量检索
        keywords = query.split()[:3]
        if keywords:
            conditions = [FAQ.question.ilike(f"%{kw}%") for kw in keywords]
            stmt = stmt.where(or_(*conditions))
        stmt = stmt.order_by(FAQ.priority.desc()).limit(5)

        result = await session.execute(stmt)
        faqs = result.scalars().all()

    if not faqs:
        return "[未找到匹配的 FAQ]"

    lines = []
    for i, faq in enumerate(faqs, 1):
        lines.append(f"[FAQ-{i}] 问: {faq.question}\n答: {faq.answer}\n")

    return "\n".join(lines)


@tool
async def document_expand(chunk_id: int, window: int = 1) -> str:
    """扩展指定切片的上下文内容。

    适用：命中片段的上下文不足，需要查看前后相邻段落。
    不适用：已有足够信息时不要调用。
    """
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.domain.models import Chunk

    async with async_session_factory() as session:
        # 获取当前 chunk
        result = await session.execute(select(Chunk).where(Chunk.id == chunk_id))
        chunk = result.scalar_one_or_none()
        if chunk is None:
            return f"[切片 {chunk_id} 不存在]"

        # 获取同文档的相邻切片
        stmt = (
            select(Chunk)
            .where(
                Chunk.document_id == chunk.document_id,
                Chunk.version_id == chunk.version_id,
                Chunk.chunk_index.between(chunk.chunk_index - window, chunk.chunk_index + window),
                Chunk.status == 1,
            )
            .order_by(Chunk.chunk_index)
        )
        result = await session.execute(stmt)
        neighbors = result.scalars().all()

    lines = []
    for n in neighbors:
        marker = " >>> " if n.id == chunk_id else "     "
        lines.append(f"{marker}[{n.chunk_index}] {n.title_path or ''}\n{n.content}\n")

    return "\n".join(lines)


@tool
async def doc_meta_search(keyword: str, dept: str = "") -> str:
    """搜索文档元数据（标题、部门等）。

    适用：用户询问"XX 文件在哪"、"最新版是哪个"等元数据问题。
    不适用：需要查看文件内容的检索。
    """
    from sqlalchemy import select
    from app.core.database import async_session_factory
    from app.domain.models import Document

    async with async_session_factory() as session:
        stmt = select(Document).where(Document.status == 4)  # 已上线
        if keyword:
            stmt = stmt.where(Document.title.ilike(f"%{keyword}%"))

        result = await session.execute(stmt)
        docs = result.scalars().limit(10).all()

    if not docs:
        return "[未找到相关文档]"

    lines = []
    for doc in docs:
        lines.append(f"- 《{doc.title}》(类型: {doc.source_type}, 状态: 已上线)")

    return "\n".join(lines)


@tool
async def handoff_human(reason: str) -> str:
    """请求转接人工服务。

    适用：知识库无依据、用户明确要求人工帮助、问题超出 AI 能力范围。
    不适用：能通过检索解决的问题。
    """
    return (
        f"[转人工] 原因: {reason}\n"
        "请联系以下人工服务渠道：\n"
        "- 教务咨询：教务处服务大厅 (行政楼 101)，电话: 023-XXXX-0001\n"
        "- 学工事务：学工部服务窗口 (学生活动中心 201)，电话: 023-XXXX-0002\n"
        "- 财务问题：财务处服务大厅 (行政楼 202)，电话: 023-XXXX-0003\n"
        "- 综合咨询：校园服务热线 023-XXXX-0000（工作日 8:00-17:30）"
    )


# ── 工具列表 ─────────────────────────────────────────

TOOLS = [knowledge_search, faq_search, document_expand, doc_meta_search, handoff_human]
