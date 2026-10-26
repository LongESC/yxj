"""Pydantic v2 请求/响应模型"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


# ============================================================
# 通用响应
# ============================================================

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Any = None
    trace_id: str | None = None


# ============================================================
# 认证
# ============================================================

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: Optional[str] = None

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ============================================================
# 对话
# ============================================================

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    kb_ids: Optional[list[int]] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None


class ConversationOut(BaseModel):
    id: int
    title: Optional[str] = None
    source: str
    kb_ids: Optional[list[int]] = None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 消息
# ============================================================

class CitationOut(BaseModel):
    cite_no: int
    chunk_id: int
    doc_title: Optional[str] = None
    snippet: Optional[str] = None
    score: Optional[float] = None

    model_config = {"from_attributes": True}


class AgentStepOut(BaseModel):
    node: str
    tool: Optional[str] = None
    hits: Optional[int] = None
    duration_ms: Optional[int] = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[list[CitationOut]] = None
    agent_steps: Optional[list[AgentStepOut]] = None
    answer_type: Optional[str] = None
    latency_ms: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 问答（SSE）
# ============================================================

class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    question: str = Field(..., min_length=1, max_length=2000)
    kb_ids: Optional[list[int]] = None
    stream: bool = True
    show_steps: bool = True


class ChatDoneData(BaseModel):
    message_id: int
    answer_type: str
    iteration: int
    latency_ms: int
    trace_id: str


# ============================================================
# 反馈
# ============================================================

class FeedbackCreate(BaseModel):
    message_id: int
    rating: int = Field(..., description="1=赞, -1=踩")
    reason_tags: Optional[list[str]] = None
    comment: Optional[str] = Field(None, max_length=2000)


class FeedbackOut(BaseModel):
    id: int
    message_id: int
    user_id: int
    rating: int
    reason_tags: Optional[list[str]] = None
    comment: Optional[str] = None
    handled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 知识库
# ============================================================

class KBCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=1, max_length=64)
    owner_dept: Optional[str] = None
    description: Optional[str] = None
    retrieve_config: Optional[dict] = None


class KBOut(BaseModel):
    id: int
    name: str
    code: str
    owner_dept: Optional[str] = None
    description: Optional[str] = None
    status: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 文档
# ============================================================

class DocumentOut(BaseModel):
    id: int
    kb_id: int
    title: str
    source_type: str
    status: int
    fail_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 管理后台
# ============================================================

class DashboardOut(BaseModel):
    total_users: int = 0
    total_conversations: int = 0
    total_messages: int = 0
    total_documents: int = 0
    avg_satisfaction: float = 0.0
    refuse_rate: float = 0.0
    hot_questions: list[dict] = []


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    object_type: Optional[str] = None
    object_id: Optional[str] = None
    client_ip: Optional[str] = None
    trace_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
