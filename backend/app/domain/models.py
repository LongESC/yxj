"""SQLAlchemy 数据模型 — 严格对应《数据库.md》DDL"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, ForeignKey, Integer,
    SmallInteger, String, Text, func,
)
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, REAL
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


# ============================================================
# 系统模块
# ============================================================

class Role(Base):
    __tablename__ = "sys_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str | None] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    users: Mapped[list["User"]] = relationship(back_populates="role")


class User(Base):
    __tablename__ = "sys_user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    real_name: Mapped[str | None] = mapped_column(String(64))
    email: Mapped[str | None] = mapped_column(String(128))
    phone: Mapped[str | None] = mapped_column(String(32))
    department: Mapped[str | None] = mapped_column(String(128))
    role_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sys_role.id"))
    password_hash: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    sso_id: Mapped[str | None] = mapped_column(String(128), unique=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    role: Mapped[Role | None] = relationship(back_populates="users")


class KBPermission(Base):
    __tablename__ = "sys_kb_permission"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)  # user / role / department
    subject_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    permission: Mapped[str] = mapped_column(String(16), nullable=False, default="read")  # read / write / admin
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    __tablename__ = "sys_audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str | None] = mapped_column(String(64))
    object_id: Mapped[str | None] = mapped_column(String(64))
    params: Mapped[dict | None] = mapped_column(JSONB)
    client_ip: Mapped[str | None] = mapped_column(INET)
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
    model_name: Mapped[str | None] = mapped_column(String(64))
    retrieve_config: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    agent_config: Mapped[dict | None] = mapped_column(JSONB)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1.0.0")
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    documents: Mapped[list["Document"]] = relationship(back_populates="knowledge_base")
    faqs: Mapped[list["FAQ"]] = relationship(back_populates="knowledge_base")


class Document(Base):
    __tablename__ = "kb_document"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_knowledge_base.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)  # pdf/docx/xlsx/md/txt/html
    current_version_id: Mapped[int | None] = mapped_column(BigInteger)
    effective_from: Mapped[date | None] = mapped_column(Date)
    effective_to: Mapped[date | None] = mapped_column(Date)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    # 1=待解析 2=解析中 3=待索引 4=已上线 5=已下线 6=解析失败
    fail_reason: Mapped[str | None] = mapped_column(String(1000))
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="documents")
    versions: Mapped[list["DocumentVersion"]] = relationship(back_populates="document")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class DocumentVersion(Base):
    __tablename__ = "kb_document_version"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_document.id"), nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    file_key: Mapped[str] = mapped_column(String(512), nullable=False)
    file_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    page_count: Mapped[int | None] = mapped_column(Integer)
    char_count: Mapped[int | None] = mapped_column(Integer)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="versions")


class Chunk(Base):
    __tablename__ = "kb_chunk"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    document_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_document.id"), nullable=False)
    version_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title_path: Mapped[str | None] = mapped_column(String(1000))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    page_no: Mapped[int | None] = mapped_column(Integer)
    index_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    document: Mapped[Document] = relationship(back_populates="chunks")


class FAQ(Base):
    __tablename__ = "kb_faq"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kb_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("kb_knowledge_base.id"), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    priority: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    knowledge_base: Mapped[KnowledgeBase] = relationship(back_populates="faqs")


# ============================================================
# 对话模块
# ============================================================

class Conversation(Base):
    __tablename__ = "chat_conversation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="web")
    kb_ids: Mapped[list[int] | None] = mapped_column(ARRAY(BigInteger))
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", order_by="Message.id")


class Message(Base):
    __tablename__ = "chat_message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_conversation.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user / assistant / system
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
    answer_type: Mapped[str | None] = mapped_column(String(16))  # normal / refused / degraded / unsafe
    trace_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    citations: Mapped[list["Citation"]] = relationship(back_populates="message")
    feedbacks: Mapped[list["Feedback"]] = relationship(back_populates="message")


class Citation(Base):
    __tablename__ = "chat_message_citation"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_message.id"), nullable=False)
    chunk_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    cite_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    score: Mapped[float | None] = mapped_column(REAL)
    snippet: Mapped[str | None] = mapped_column(String(500))

    message: Mapped[Message] = relationship(back_populates="citations")


class Feedback(Base):
    __tablename__ = "chat_feedback"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("chat_message.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)  # 1=赞, -1=踩
    reason_tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    comment: Mapped[str | None] = mapped_column(String(2000))
    handled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    handler_id: Mapped[int | None] = mapped_column(BigInteger)
    handle_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    message: Mapped[Message] = relationship(back_populates="feedbacks")


# ============================================================
# 配置模块
# ============================================================

class PromptTemplate(Base):
    __tablename__ = "prompt_template"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)  # rewrite / agent / synthesize
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    variables: Mapped[list | None] = mapped_column(JSONB, default=list)
    description: Mapped[str | None] = mapped_column(String(500))
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ModelConfig(Base):
    __tablename__ = "model_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    provider: Mapped[str] = mapped_column(String(32), nullable=False)  # doubao / dashscope
    base_url: Mapped[str] = mapped_column(String(256), nullable=False)
    api_key_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    model_type: Mapped[str] = mapped_column(String(16), nullable=False)  # chat / embedding
    parameters: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SysConfig(Base):
    __tablename__ = "sys_config"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    config_value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    updated_by: Mapped[int | None] = mapped_column(BigInteger)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
