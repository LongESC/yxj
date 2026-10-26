"""Pydantic 请求/响应模型"""

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


# ============================================================
# 认证
# ============================================================

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"


class UserOut(BaseModel):
    id: int
    username: str
    real_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: str

    model_config = {"from_attributes": True}


# ============================================================
# 对话
# ============================================================

class ConversationCreate(BaseModel):
    title: Optional[str] = None
    kb_ids: Optional[list[int]] = None


class ConversationOut(BaseModel):
    id: int
    title: Optional[str] = None
    source: str
    kb_ids: Optional[list[int]] = None
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatRequest(BaseModel):
    conversation_id: Optional[int] = None
    question: str = Field(..., min_length=1, max_length=2000)
    kb_ids: Optional[list[int]] = None
    stream: bool = True
    show_steps: bool = True


class CitationOut(BaseModel):
    cite_no: int
    chunk_id: int
    doc_title: Optional[str] = None
    version: Optional[int] = None
    page: Optional[int] = None
    snippet: Optional[str] = None
    score: Optional[float] = None


class ChatDoneData(BaseModel):
    message_id: int
    answer_type: str
    iteration: Optional[int] = None
    latency_ms: Optional[int] = None
    first_token_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    model: Optional[str] = None
    graph_version: Optional[str] = None
    trace_id: Optional[str] = None


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    citations: Optional[list[CitationOut]] = None
    agent_steps: Optional[list[dict]] = None
    answer_type: Optional[str] = None
    latency_ms: Optional[int] = None
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


class KBOut(BaseModel):
    id: int
    name: str
    code: str
    owner_dept: Optional[str] = None
    description: Optional[str] = None
    status: int
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentOut(BaseModel):
    id: int
    kb_id: int
    title: str
    source_type: str
    version_no: int
    status: int
    fail_reason: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 反馈
# ============================================================

class FeedbackCreate(BaseModel):
    message_id: int
    rating: int = Field(..., ge=-1, le=1)
    reason_tags: Optional[list[str]] = None
    comment: Optional[str] = None


class FeedbackOut(BaseModel):
    id: int
    message_id: int
    rating: int
    reason_tags: Optional[list[str]] = None
    comment: Optional[str] = None
    handled: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ============================================================
# 通用响应
# ============================================================

class ApiResponse(BaseModel):
    code: int = 0
    message: str = "ok"
    data: Optional[object] = None
    trace_id: Optional[str] = None
