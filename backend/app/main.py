"""FastAPI 主应用 — 高校智能问答助手"""

import hashlib
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import GRAPH_VERSION
from app.application import chat_service
from app.application.kb_service import create_document, list_documents
from app.core.auth import create_access_token, get_current_user, require_role
from app.core.config import get_settings
from app.core.database import Base, engine, async_session_factory, get_db
from app.core.logging import setup_logging
from app.domain.models import (
    AuditLog, Conversation, Document, Feedback, KnowledgeBase, Message, User,
)
from app.schemas import (
    ApiResponse, ChatRequest, ConversationCreate, ConversationOut,
    ConversationUpdate, DashboardOut, FeedbackCreate, FeedbackOut,
    KBCreate, KBOut, DocumentOut, LoginRequest, LoginResponse,
    MessageOut, UserOut,
)
from app.infrastructure.storage import upload_file

settings = get_settings()


# ============================================================
# 生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    setup_logging()
    # 启动：创建表 + 初始化管理员
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session_factory() as db:
        await chat_service.init_admin(db, settings.ADMIN_USERNAME, settings.ADMIN_DEFAULT_PASSWORD)
        await db.commit()
    print(f"✅ 应用启动完成 | 环境: {settings.APP_ENV} | Agent图版本: {GRAPH_VERSION}")
    yield
    await engine.dispose()


app = FastAPI(
    title="高校智能问答助手",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# 健康检查
# ============================================================

@app.get("/health")
async def health():
    return {"status": "ok", "graph_version": GRAPH_VERSION}


# ============================================================
# 认证
# ============================================================

@app.post("/api/v1/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await chat_service.authenticate_user(db, body.username, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    role_code = user.role.code if user.role else "user"
    token = create_access_token(user.id, user.username, role_code)
    await chat_service.log_audit(db, user.id, "login")
    await db.commit()
    return LoginResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@app.get("/api/v1/auth/me", response_model=UserOut)
async def get_me(user: User = Depends(get_current_user)):
    return UserOut.model_validate(user)


# ============================================================
# 会话
# ============================================================

@app.get("/api/v1/conversations", response_model=list[ConversationOut])
async def list_convs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    convs = await chat_service.list_conversations(db, user.id)
    return [ConversationOut.model_validate(c) for c in convs]


@app.post("/api/v1/conversations", response_model=ConversationOut)
async def create_conv(body: ConversationCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    conv = await chat_service.create_conversation(db, user.id, body.title, body.kb_ids)
    await db.commit()
    return ConversationOut.model_validate(conv)


@app.delete("/api/v1/conversations/{conv_id}")
async def delete_conv(conv_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    await chat_service.delete_conversation(db, conv_id, user.id)
    await db.commit()
    return {"message": "已删除"}


@app.put("/api/v1/conversations/{conv_id}", response_model=ConversationOut)
async def update_conv(conv_id: int, body: ConversationUpdate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    if body.title:
        conv = await chat_service.update_conversation_title(db, conv_id, user.id, body.title)
        await db.commit()
        return ConversationOut.model_validate(conv)
    raise HTTPException(status_code=400, detail="无更新内容")


# ============================================================
# 消息
# ============================================================

@app.get("/api/v1/conversations/{conv_id}/messages", response_model=list[MessageOut])
async def list_msgs(conv_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    msgs = await chat_service.list_messages(db, conv_id, user.id)
    return [MessageOut.model_validate(m) for m in msgs]


# ============================================================
# 问答（SSE 流式）
# ============================================================

@app.post("/api/v1/chat/completions")
async def chat_completions(
    body: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # 如果没有 conversation_id，自动创建
    conv_id = body.conversation_id
    if conv_id is None:
        conv = await chat_service.create_conversation(db, user.id, body.question[:50])
        conv_id = conv.id

    async def event_stream():
        async for event in chat_service.run_agent_stream(db, user, conv_id, body.question, body.kb_ids):
            yield event
        await db.commit()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ============================================================
# 反馈
# ============================================================

@app.post("/api/v1/feedback", response_model=FeedbackOut)
async def create_fb(body: FeedbackCreate, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    fb = await chat_service.create_feedback(db, user.id, body.message_id, body.rating, body.reason_tags, body.comment)
    await db.commit()
    return FeedbackOut.model_validate(fb)


# ============================================================
# 知识库
# ============================================================

@app.get("/api/v1/knowledge-bases", response_model=list[KBOut])
async def list_kbs(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    kbs = await chat_service.list_kbs(db, user.id)
    return [KBOut.model_validate(kb) for kb in kbs]


@app.post("/api/v1/knowledge-bases", response_model=KBOut)
async def create_kb_api(
    body: KBCreate,
    user: User = Depends(require_role("kb_admin", "sys_admin")),
    db: AsyncSession = Depends(get_db),
):
    kb = await chat_service.create_kb(db, body.name, body.code, body.owner_dept, body.description)
    await db.commit()
    return KBOut.model_validate(kb)


@app.get("/api/v1/knowledge-bases/{kb_id}/documents", response_model=list[DocumentOut])
async def list_docs(kb_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    docs = await list_documents(db, kb_id)
    return [DocumentOut.model_validate(d) for d in docs]


@app.post("/api/v1/knowledge-bases/{kb_id}/documents", response_model=DocumentOut)
async def upload_doc(
    kb_id: int,
    file: UploadFile = File(...),
    user: User = Depends(require_role("kb_admin", "sys_admin")),
    db: AsyncSession = Depends(get_db),
):
    file_bytes = await file.read()
    file_hash = hashlib.sha256(file_bytes).hexdigest()
    file_key = await upload_file(file_bytes, file.filename or "unknown")

    source_type = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else "unknown"
    doc = await create_document(db, kb_id, file.filename or "unknown", source_type, file_key, file_hash, user.id)
    await db.commit()
    return DocumentOut.model_validate(doc)


# ============================================================
# 管理后台
# ============================================================

@app.get("/api/v1/admin/dashboard", response_model=DashboardOut)
async def dashboard(
    user: User = Depends(require_role("sys_admin")),
    db: AsyncSession = Depends(get_db),
):
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0
    total_convs = (await db.execute(select(func.count(Conversation.id)))).scalar() or 0
    total_msgs = (await db.execute(select(func.count(Message.id)))).scalar() or 0
    total_docs = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    return DashboardOut(
        total_users=total_users,
        total_conversations=total_convs,
        total_messages=total_msgs,
        total_documents=total_docs,
    )


@app.get("/api/v1/admin/audit-logs")
async def audit_logs(
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(require_role("sys_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
    )
    logs = result.scalars().all()
    return [{"id": l.id, "user_id": l.user_id, "action": l.action, "object_type": l.object_type, "object_id": l.object_id, "client_ip": str(l.client_ip) if l.client_ip else None, "trace_id": l.trace_id, "created_at": l.created_at.isoformat()} for l in logs]


# ============================================================
# 启动入口
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.DEBUG,
    )
