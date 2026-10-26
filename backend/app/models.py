"""SQLAlchemy 数据模型"""

from datetime import datetime
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer,
    SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


# ============================================================
# 系统模块
# ============================================================

class User(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    department: Mapped[str | None] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(32), default="user")  # user / kb_admin / sys_admin
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    conversations: Mapped[list["Conversation"]] = relationship(back_populates="user")


class AuditLog(Base):
    __tablename__ = "sys_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict | None] = mapped_column(JSONB)
    client_ip: Mapped[str | None] = mapped_column(String(64))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# 知识库模块
# ============================================================

class KnowledgeBase(Base):
    __tablename__ = "kb_knowledge_base"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    owner_dept: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(String(1000))
    retrieve_config: Mapped[dict] = mapped_column(JSONB, default={})
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    documents: Mapped[list["Document"]] = relationship(back_populates="kb")


class Document(Base):
    __tablename__ = "kb_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_knowledge_base.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf/docx/md/txt
    file_key: Mapped[str | None] = mapped_column(String(512))  # MinIO 对象键
    file_hash: Mapped[str | None] = mapped_column(String(64))
    version_no: Mapped[int] = mapped_column(Integer, default=1)
    effective_from: Mapped[datetime | None] = mapped_column(Date)
    effective_to: Mapped[datetime | None] = mapped_column(Date)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    # 1 待解析 2 解析中 3 待索引 4 已上线 5 已下线 6 解析失败
    fail_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    kb: Mapped["KnowledgeBase"] = relationship(back_populates="documents")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class Chunk(Base):
    __tablename__ = "kb_chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_document.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title_path: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_no: Mapped[int | None] = mapped_column(Integer)
    index_version: Mapped[str | None] = mapped_column(String(64))
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped["Document"] = relationship(back_populates="chunks")


class FAQ(Base):
    __tablename__ = "kb_faq"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_knowledge_base.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ============================================================
# 对话模块
# ============================================================

class Conversation(Base):
    __tablename__ = "chat_conversation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sys_user.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="web")
    kb_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="conversations")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_conversation.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    rewritten_query: Mapped[str | None] = mapped_column(String(1000))
    retrieved_chunk_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    graph_version: Mapped[str | None] = mapped_column(String(32))
    agent_steps: Mapped[dict | None] = mapped_column(JSONB)
    iteration: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    first_token_ms: Mapped[int | None] = mapped_column(Integer)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    completion_tokens: Mapped[int | None] = mapped_column(Integer)
    answer_type: Mapped[str | None] = mapped_column(String(16))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(back_populates="message", cascade="all, delete-orphan")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="message", cascade="all, delete-orphan")


class Citation(Base):
    __tablename__ = "chat_message_citation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_message.id"), nullable=False)
    chunk_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cite_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[float | None] = mapped_column()
    snippet: Mapped[str | None] = mapped_column(String(500))

    message: Mapped["Message"] = relationship(back_populates="citations")


class Feedback(Base):
    __tablename__ = "chat_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_message.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1 赞 / -1 踩
    reason_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    comment: Mapped[str | None] = mapped_column(String(2000))
    handled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    message: Mapped["Message"] = relationship(back_populates="feedbacks")
