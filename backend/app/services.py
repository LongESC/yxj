"""业务服务层"""

import time
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    User, Conversation, Message, Citation, Feedback,
    KnowledgeBase, Document, Chunk, FAQ, AuditLog,
)
from app.schemas import (
    ConversationCreate, ConversationOut, MessageOut,
    CitationOut, KBCreate, KBOut, DocumentOut,
    FeedbackCreate, FeedbackOut, UserOut,
)
from app.auth import hash_password, verify_password, create_access_token


# ============================================================
# 认证服务
# ============================================================

async def authenticate_user(db: AsyncSession, username: str, password: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.username == username, User.status == 1))
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


async def create_user(
    db: AsyncSession, username: str, password: str,
    real_name: str | None = None, role: str = "user",
    department: str | None = None,
) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        real_name=real_name,
        role=role,
        department=department,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def init_admin(db: AsyncSession, username: str, password: str) -> User:
    """初始化管理员账号"""
    result = await db.execute(select(User).where(User.username == username))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    return await create_user(db, username, password, real_name="系统管理员", role="sys_admin")


# ============================================================
# 会话服务
# ============================================================

async def list_conversations(db: AsyncSession, user_id: int) -> list[ConversationOut]:
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(desc(Conversation.updated_at))
    )
    return [ConversationOut.model_validate(c) for c in result.scalars().all()]


async def create_conversation(
    db: AsyncSession, user_id: int, data: ConversationCreate,
) -> ConversationOut:
    conv = Conversation(
        user_id=user_id,
        title=data.title or "新会话",
        kb_ids=data.kb_ids,
    )
    db.add(conv)
    await db.flush()
    await db.refresh(conv)
    return ConversationOut.model_validate(conv)


async def delete_conversation(db: AsyncSession, user_id: int, conv_id: int) -> bool:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    await db.delete(conv)
    return True


async def update_conversation_title(db: AsyncSession, user_id: int, conv_id: int, title: str) -> bool:
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        return False
    conv.title = title
    return True


# ============================================================
# 消息服务
# ============================================================

async def list_messages(db: AsyncSession, conv_id: int, user_id: int) -> list[MessageOut]:
    """获取会话消息列表（含引用）"""
    # 验证会话归属
    result = await db.execute(
        select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user_id)
    )
    if not result.scalar_one_or_none():
        return []

    result = await db.execute(
        select(Message).where(Message.conversation_id == conv_id).order_by(Message.id)
    )
    messages = result.scalars().all()

    out = []
    for msg in messages:
        cit_result = await db.execute(
            select(Citation).where(Citation.message_id == msg.id).order_by(Citation.cite_no)
        )
        citations = [CitationOut.model_validate(c) for c in cit_result.scalars().all()]
        msg_out = MessageOut.model_validate(msg)
        msg_out.citations = citations if citations else None
        out.append(msg_out)
    return out


async def save_message(
    db: AsyncSession,
    conv_id: int,
    role: str,
    content: str,
    *,
    rewritten_query: str | None = None,
    retrieved_chunk_ids: list[int] | None = None,
    model: str | None = None,
    agent_steps: list[dict] | None = None,
    iteration: int | None = None,
    latency_ms: int | None = None,
    first_token_ms: int | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    answer_type: str | None = None,
    trace_id: str | None = None,
    citations: list[dict] | None = None,
) -> Message:
    msg = Message(
        conversation_id=conv_id,
        role=role,
        content=content,
        rewritten_query=rewritten_query,
        retrieved_chunk_ids=retrieved_chunk_ids,
        model=model,
        agent_steps=agent_steps,
        iteration=iteration,
        latency_ms=latency_ms,
        first_token_ms=first_token_ms,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        answer_type=answer_type,
        trace_id=trace_id,
    )
    db.add(msg)
    await db.flush()
    await db.refresh(msg)

    # 保存引用
    if citations:
        for c in citations:
            cit = Citation(
                message_id=msg.id,
                chunk_id=c["chunk_id"],
                cite_no=c["cite_no"],
                score=c.get("score"),
                snippet=c.get("snippet"),
            )
            db.add(cit)

    return msg


# ============================================================
# 反馈服务
# ============================================================

async def create_feedback(
    db: AsyncSession, user_id: int, data: FeedbackCreate,
) -> FeedbackOut:
    fb = Feedback(
        message_id=data.message_id,
        user_id=user_id,
        rating=data.rating,
        reason_tags=data.reason_tags,
        comment=data.comment,
    )
    db.add(fb)
    await db.flush()
    await db.refresh(fb)
    return FeedbackOut.model_validate(fb)


# ============================================================
# 知识库服务
# ============================================================

async def list_kbs(db: AsyncSession) -> list[KBOut]:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.status == 1))
    return [KBOut.model_validate(k) for k in result.scalars().all()]


async def create_kb(db: AsyncSession, data: KBCreate) -> KBOut:
    kb = KnowledgeBase(**data.model_dump())
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return KBOut.model_validate(kb)


async def get_kb(db: AsyncSession, kb_id: int) -> KnowledgeBase | None:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    return result.scalar_one_or_none()


# ============================================================
# 审计日志
# ============================================================

async def log_audit(
    db: AsyncSession,
    action: str,
    user_id: int | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
    params: dict | None = None,
    client_ip: str | None = None,
    trace_id: str | None = None,
):
    db.add(AuditLog(
        user_id=user_id,
        action=action,
        object_type=object_type,
        object_id=object_id,
        params=params,
        client_ip=client_ip,
        trace_id=trace_id,
    ))
