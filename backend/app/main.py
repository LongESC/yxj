"""高校智能问答助手 - FastAPI 主应用"""

import json
import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db, engine, Base
from app.models import User
from app.auth import get_current_user, create_access_token
from app.services import (
    authenticate_user, init_admin,
    list_conversations, create_conversation, delete_conversation, update_conversation_title,
    list_messages, save_message, create_feedback,
    list_kbs, create_kb, get_kb,
    log_audit,
)
from app.schemas import (
    LoginRequest, LoginResponse, UserOut,
    ConversationCreate, ConversationOut,
    ChatRequest, MessageOut, CitationOut, ChatDoneData,
    KBCreate, KBOut, DocumentOut,
    FeedbackCreate, FeedbackOut,
    ApiResponse,
)
from app.agent import agent_graph, GRAPH_VERSION

settings = get_settings()


# ============================================================
# 生命周期
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """应用启动/关闭"""
    # 启动：创建表 + 初始化管理员
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with get_db().__anext__() as db:
        await init_admin(db, settings.ADMIN_USERNAME, settings.ADMIN_DEFAULT_PASSWORD)
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

@app.get("/healthz", tags=["系统"])
async def health_check():
    return {"status": "ok", "graph_version": GRAPH_VERSION}


# ============================================================
# 认证
# ============================================================

@app.post("/api/v1/auth/login", response_model=LoginResponse, tags=["认证"])
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """用户登录，返回 JWT token"""
    user = await authenticate_user(db, data.username, data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    token = create_access_token(user.id, user.username, user.role)
    await log_audit(db, "login", user_id=user.id)
    return LoginResponse(
        access_token=token,
        user=UserOut.model_validate(user),
    )


@app.get("/api/v1/auth/me", response_model=UserOut, tags=["认证"])
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return UserOut.model_validate(user)


# ============================================================
# 会话管理
# ============================================================

@app.get("/api/v1/conversations", response_model=list[ConversationOut], tags=["会话"])
async def get_conversations(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """获取当前用户的会话列表"""
    return await list_conversations(db, user.id)


@app.post("/api/v1/conversations", response_model=ConversationOut, tags=["会话"])
async def new_conversation(
    data: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建新会话"""
    conv = await create_conversation(db, user.id, data)
    await log_audit(db, "conversation_create", user_id=user.id, object_id=str(conv.id))
    return conv


@app.delete("/api/v1/conversations/{conv_id}", tags=["会话"])
async def remove_conversation(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """删除会话"""
    ok = await delete_conversation(db, user.id, conv_id)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="删除成功")


@app.patch("/api/v1/conversations/{conv_id}", tags=["会话"])
async def rename_conversation(
    conv_id: int,
    title: str = Query(..., min_length=1, max_length=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """重命名会话"""
    ok = await update_conversation_title(db, user.id, conv_id, title)
    if not ok:
        raise HTTPException(status_code=404, detail="会话不存在")
    return ApiResponse(message="更新成功")


# ============================================================
# 消息历史
# ============================================================

@app.get("/api/v1/conversations/{conv_id}/messages", response_model=list[MessageOut], tags=["消息"])
async def get_messages(
    conv_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取会话消息列表"""
    return await list_messages(db, conv_id, user.id)


# ============================================================
# 问答（SSE 流式）
# ============================================================

@app.post("/api/v1/chat/completions", tags=["问答"])
async def chat_completions(
    data: ChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    智能问答接口（SSE 流式输出）

    事件类型：step / tool_call / tool_result / delta / citation / done / error
    """
    # 确定会话
    conv_id = data.conversation_id
    if not conv_id:
        conv = await create_conversation(db, user.id, ConversationCreate(kb_ids=data.kb_ids))
        conv_id = conv.id
    else:
        # 验证会话归属
        from app.models import Conversation
        result = await db.execute(
            select(Conversation).where(Conversation.id == conv_id, Conversation.user_id == user.id)
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="会话不存在")

    # 保存用户消息
    user_msg = await save_message(db, conv_id, "user", data.question)
    await db.commit()

    # 构建 Agent 输入
    kb_ids = data.kb_ids or []
    initial_state = {
        "messages": [HumanMessage(content=data.question)],
        "user_id": user.id,
        "kb_ids": kb_ids,
        "rewritten_queries": [],
        "retrieved_chunks": [],
        "citations": [],
        "iteration": 0,
        "token_usage": {"prompt": 0, "completion": 0},
        "answer_type": "normal",
        "trace_id": "",
    }

    async def event_stream():
        start_time = time.time()
        first_token_time = None
        answer_parts = []
        trace_id = ""
        iteration = 0
        answer_type = "normal"

        try:
            async for event in agent_graph.astream(initial_state, stream_mode="updates"):
                for node_name, node_output in event.items():
                    # 发送步骤事件
                    if data.show_steps:
                        step_labels = {
                            "guard_in": "正在初始化…",
                            "rewrite": "正在理解问题…",
                            "agent": "正在思考…",
                            "tools": "正在检索知识库…",
                            "synthesize": "正在生成答案…",
                        }
                        yield f"event: step\ndata: {json.dumps({'node': node_name, 'label': step_labels.get(node_name, ''), 'ensure_ascii': False})}\n\n"

                    # 处理工具调用
                    if node_name == "agent" and "messages" in node_output:
                        for msg in node_output["messages"]:
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                for tc in msg.tool_calls:
                                    yield f"event: tool_call\ndata: {json.dumps({'tool': tc['name'], 'args': tc['args']}, ensure_ascii=False)}\n\n"

                    # 处理工具结果
                    if node_name == "tools" and "messages" in node_output:
                        for msg in node_output["messages"]:
                            yield f"event: tool_result\ndata: {json.dumps({'tool': 'result', 'content': str(msg.content)[:200]}, ensure_ascii=False)}\n\n"

                    # 处理最终答案
                    if node_name == "synthesize" and "messages" in node_output:
                        for msg in node_output["messages"]:
                            content = msg.content if hasattr(msg, "content") else str(msg)
                            if first_token_time is None:
                                first_token_time = time.time()

                            # 逐字发送
                            for char in content:
                                answer_parts.append(char)
                                yield f"event: delta\ndata: {json.dumps({'text': char}, ensure_ascii=False)}\n\n"

                    # 记录 trace_id 和迭代次数
                    if "trace_id" in node_output and node_output["trace_id"]:
                        trace_id = node_output["trace_id"]
                    if "iteration" in node_output:
                        iteration = node_output["iteration"]
                    if "answer_type" in node_output:
                        answer_type = node_output["answer_type"]

            # 发送完成事件
            total_latency = int((time.time() - start_time) * 1000)
            first_token_ms = int((first_token_time - start_time) * 1000) if first_token_time else None

            # 保存助手消息
            answer_text = "".join(answer_parts)
            await save_message(
                db, conv_id, "assistant", answer_text,
                model=settings.VOLCENGINE_MODEL,
                iteration=iteration,
                latency_ms=total_latency,
                first_token_ms=first_token_ms,
                answer_type=answer_type,
                trace_id=trace_id,
            )
            await db.commit()

            done_data = {
                "message_id": user_msg.id + 1,  # 近似值
                "answer_type": answer_type,
                "iteration": iteration,
                "latency_ms": total_latency,
                "first_token_ms": first_token_ms,
                "model": settings.VOLCENGINE_MODEL,
                "graph_version": GRAPH_VERSION,
                "trace_id": trace_id,
            }
            yield f"event: done\ndata: {json.dumps(done_data, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

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

@app.post("/api/v1/feedback", response_model=FeedbackOut, tags=["反馈"])
async def submit_feedback(
    data: FeedbackCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交问答反馈（点赞/点踩）"""
    return await create_feedback(db, user.id, data)


# ============================================================
# 知识库
# ============================================================

@app.get("/api/v1/knowledge-bases", response_model=list[KBOut], tags=["知识库"])
async def get_knowledge_bases(db: AsyncSession = Depends(get_db)):
    """获取知识库列表"""
    return await list_kbs(db)


@app.post("/api/v1/knowledge-bases", response_model=KBOut, tags=["知识库"])
async def create_knowledge_base(
    data: KBCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """创建知识库"""
    if user.role not in ("kb_admin", "sys_admin"):
        raise HTTPException(status_code=403, detail="权限不足")
    kb = await create_kb(db, data)
    await log_audit(db, "kb_create", user_id=user.id, object_id=str(kb.id))
    return kb


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
