"""聊天服务 — 会话 + Agent 调用 + 落库"""

import asyncio
import json
import logging
import time
from typing import AsyncGenerator

from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent import agent_graph, GRAPH_VERSION
from app.agent.prompts import PROMPT_VERSIONS
from app.agent.state import AgentState
from app.core.config import get_settings
from app.core.errors import NotFoundError
from app.domain.models import (
    AuditLog, Citation, Conversation, Feedback, KnowledgeBase, Message, User,
)
from app.schemas import ChatDoneData, MessageOut, CitationOut

settings = get_settings()
logger = logging.getLogger(__name__)


# ── 会话管理 ──────────────────────────────────────────

async def list_conversations(db: AsyncSession, user_id: int) -> list[Conversation]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.is_pinned.desc(), Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_conversation(db: AsyncSession, user_id: int, title: str | None = None, kb_ids: list[int] | None = None) -> Conversation:
    conv = Conversation(user_id=user_id, title=title or "新对话", kb_ids=kb_ids or [])
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return conv


async def delete_conversation(db: AsyncSession, conv_id: int, user_id: int) -> None:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError("会话不存在")
    await db.delete(conv)


async def update_conversation_title(db: AsyncSession, conv_id: int, user_id: int, title: str) -> Conversation:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if conv is None:
        raise NotFoundError("会话不存在")
    conv.title = title
    await db.flush()
    return conv


# ── 消息管理 ──────────────────────────────────────────

async def list_messages(db: AsyncSession, conv_id: int, user_id: int) -> list[Message]:
    # 验证会话归属
    conv_result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    if conv_result.scalar_one_or_none() is None:
        raise NotFoundError("会话不存在")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conv_id)
        .options(selectinload(Message.citations))
        .order_by(Message.id)
    )
    return list(result.scalars().all())


async def save_message(
    db: AsyncSession,
    conv_id: int,
    role: str,
    content: str,
    **kwargs,
) -> Message:
    msg = Message(conversation_id=conv_id, role=role, content=content, **kwargs)
    db.add(msg)
    await db.flush()
    await db.refresh(msg)
    return msg


async def save_citations(db: AsyncSession, message_id: int, citations: list[dict]) -> None:
    for c in citations:
        citation = Citation(
            message_id=message_id,
            chunk_id=c.get("chunk_id", 0),
            cite_no=c.get("cite_no", 0),
            score=c.get("score"),
            snippet=c.get("snippet", "")[:500],
        )
        db.add(citation)
    await db.flush()


# ── 反馈 ──────────────────────────────────────────────

async def create_feedback(db: AsyncSession, user_id: int, message_id: int, rating: int, reason_tags: list[str] | None = None, comment: str | None = None) -> Feedback:
    fb = Feedback(message_id=message_id, user_id=user_id, rating=rating, reason_tags=reason_tags, comment=comment)
    db.add(fb)
    await db.flush()
    return fb


# ── 知识库 ────────────────────────────────────────────

async def list_kbs(db: AsyncSession, user_id: int | None = None) -> list[KnowledgeBase]:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.status == 1).order_by(KnowledgeBase.name))
    return list(result.scalars().all())


async def create_kb(db: AsyncSession, name: str, code: str, owner_dept: str | None = None, description: str | None = None) -> KnowledgeBase:
    kb = KnowledgeBase(name=name, code=code, owner_dept=owner_dept, description=description)
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return kb


# ── 认证 ──────────────────────────────────────────────

async def authenticate_user(db: AsyncSession, username: str, password: str) -> User | None:
    from app.core.auth import verify_password
    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.username == username, User.status == 1)
    )
    user = result.scalar_one_or_none()
    if user is None or not user.password_hash:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def init_admin(db: AsyncSession, username: str, password: str) -> None:
    """初始化管理员账号"""
    from app.core.auth import hash_password
    from app.domain.models import Role

    # 确保角色存在
    for code, name, desc in [
        ("user", "普通用户", "提问、查看会话、反馈"),
        ("kb_admin", "知识管理员", "文档维护、重建索引、查看统计"),
        ("sys_admin", "系统管理员", "用户管理、模型配置、系统参数、审计日志"),
    ]:
        result = await db.execute(select(Role).where(Role.code == code))
        if result.scalar_one_or_none() is None:
            db.add(Role(code=code, name=name, description=desc))
    await db.flush()

    # 确保管理员存在
    result = await db.execute(select(User).where(User.username == username))
    if result.scalar_one_or_none() is None:
        admin_role_result = await db.execute(select(Role).where(Role.code == "sys_admin"))
        admin_role = admin_role_result.scalar_one_or_none()
        admin = User(
            username=username,
            real_name="系统管理员",
            role_id=admin_role.id if admin_role else None,
            password_hash=hash_password(password),
            status=1,
        )
        db.add(admin)
        await db.flush()


# ── 审计 ──────────────────────────────────────────────

async def log_audit(db: AsyncSession, user_id: int | None, action: str, object_type: str | None = None, object_id: str | None = None, trace_id: str | None = None, client_ip: str | None = None) -> None:
    log = AuditLog(user_id=user_id, action=action, object_type=object_type, object_id=object_id, trace_id=trace_id, client_ip=client_ip)
    db.add(log)
    await db.flush()


# ── Agent 问答（SSE 流式） ────────────────────────────

async def run_agent_stream(
    db: AsyncSession,
    user: User,
    conversation_id: int,
    question: str,
    kb_ids: list[int] | None = None,
) -> AsyncGenerator[str, None]:
    """运行 Agent 并以 SSE 事件流输出"""
    start = time.time()
    trace_id = f"{int(time.time())}-{id(question) % 10000:04d}"

    # 1. 保存用户消息
    user_msg = await save_message(db, conversation_id, "user", question)

    # 2. 获取历史消息（最近 5 轮）
    history_result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id, Message.id < user_msg.id)
        .order_by(Message.id.desc())
        .limit(settings.HISTORY_ROUNDS * 2)
    )
    history_msgs = list(reversed(history_result.scalars().all()))

    # 3. 构建初始 state
    messages = []
    for m in history_msgs:
        if m.role == "user":
            messages.append(HumanMessage(content=m.content))
        elif m.role == "assistant":
            messages.append(AIMessage(content=m.content))
    messages.append(HumanMessage(content=question))

    # 计算 kb_ids
    if kb_ids is None:
        conv_result = await db.execute(select(Conversation).where(Conversation.id == conversation_id))
        conv = conv_result.scalar_one_or_none()
        kb_ids = conv.kb_ids if conv and conv.kb_ids else []

    initial_state: AgentState = {
        "messages": messages,
        "user_id": user.id,
        "conversation_id": conversation_id,
        "kb_ids": kb_ids,
        "rewritten_queries": [],
        "retrieved_chunks": [],
        "citations": [],
        "iteration": 0,
        "token_usage": {"prompt": 0, "completion": 0},
        "answer_type": "normal",
        "trace_id": trace_id,
        "verify_retry": 0,
        "start_time": time.time(),
    }

    # 4. 运行图
    final_state = None
    try:
        async for event in agent_graph.astream_events(initial_state, version="v2"):
            kind = event.get("event", "")

            if kind == "on_chain_start":
                node_name = event.get("name", "")
                label_map = {
                    "guard_in": "正在检查输入…",
                    "rewrite": "正在理解问题…",
                    "agent": "正在思考…",
                    "tools": "正在检索知识库…",
                    "synthesize": "正在生成答案…",
                    "verify": "正在校验引用…",
                    "guard_out": "正在整理输出…",
                }
                if node_name in label_map:
                    yield _sse("step", {"node": node_name, "label": label_map[node_name]})

            elif kind == "on_tool_start":
                tool_name = event.get("name", "")
                tool_input = event.get("data", {}).get("input", {})
                yield _sse("tool_call", {"tool": tool_name, "args": tool_input})

            elif kind == "on_tool_end":
                tool_name = event.get("name", "")
                output = event.get("data", {}).get("output", "")
                hits = output.count("[") if isinstance(output, str) else 0
                yield _sse("tool_result", {"tool": tool_name, "hits": hits})

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    yield _sse("delta", {"text": chunk.content})

        # 5. 获取最终状态
        final_result = await agent_graph.ainvoke(initial_state)
        final_state = final_result

    except asyncio.TimeoutError:
        yield _sse("error", {"message": "回答超时，请稍后重试", "trace_id": trace_id})
        final_state = {"answer_type": "degraded", "messages": [AIMessage(content="抱歉，处理超时。请稍后重试或联系人工服务。")], "citations": [], "iteration": 0, "token_usage": {}}
    except Exception as exc:
        logger.exception("Agent 执行异常")
        yield _sse("error", {"message": "服务异常，请稍后重试", "trace_id": trace_id})
        final_state = {"answer_type": "degraded", "messages": [AIMessage(content="抱歉，服务暂时不可用。请稍后重试。")], "citations": [], "iteration": 0, "token_usage": {}}

    # 6. 提取最终答案
    answer = ""
    if final_state and final_state.get("messages"):
        for msg in reversed(final_state["messages"]):
            if isinstance(msg, AIMessage):
                answer = msg.content
                break

    answer_type = final_state.get("answer_type", "normal") if final_state else "degraded"
    citations = final_state.get("citations", []) if final_state else []
    iteration = final_state.get("iteration", 0) if final_state else 0
    latency_ms = int((time.time() - start) * 1000)

    # 7. 保存助手消息
    assistant_msg = await save_message(
        db, conversation_id, "assistant", answer,
        answer_type=answer_type,
        iteration=iteration,
        latency_ms=latency_ms,
        trace_id=trace_id,
        graph_version=GRAPH_VERSION,
        prompt_version=PROMPT_VERSIONS.get("synthesize", "v1.0.0"),
        model=settings.VOLCENGINE_MODEL,
        agent_steps=final_state.get("token_usage", {}) if final_state else {},
    )

    # 8. 保存引用
    if citations:
        await save_citations(db, assistant_msg.id, citations)
        for c in citations:
            yield _sse("citation", c)

    # 9. 审计日志
    await log_audit(db, user.id, "query", "conversation", str(conversation_id), trace_id=trace_id)

    # 10. 完成事件
    done_data = ChatDoneData(
        message_id=assistant_msg.id,
        answer_type=answer_type,
        iteration=iteration,
        latency_ms=latency_ms,
        trace_id=trace_id,
    )
    yield _sse("done", done_data.model_dump())


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
