"""知识库服务"""

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NotFoundError
from app.domain.models import Document, DocumentVersion, KnowledgeBase

logger = logging.getLogger(__name__)


async def list_kbs(db: AsyncSession) -> list[KnowledgeBase]:
    result = await db.execute(
        select(KnowledgeBase).where(KnowledgeBase.status == 1).order_by(KnowledgeBase.name)
    )
    return list(result.scalars().all())


async def get_kb(db: AsyncSession, kb_id: int) -> KnowledgeBase:
    result = await db.execute(select(KnowledgeBase).where(KnowledgeBase.id == kb_id))
    kb = result.scalar_one_or_none()
    if kb is None:
        raise NotFoundError("知识库不存在")
    return kb


async def create_kb(db: AsyncSession, name: str, code: str, **kwargs) -> KnowledgeBase:
    kb = KnowledgeBase(name=name, code=code, **kwargs)
    db.add(kb)
    await db.flush()
    await db.refresh(kb)
    return kb


async def list_documents(db: AsyncSession, kb_id: int) -> list[Document]:
    result = await db.execute(
        select(Document)
        .where(Document.kb_id == kb_id)
        .order_by(Document.updated_at.desc())
    )
    return list(result.scalars().all())


async def create_document(db: AsyncSession, kb_id: int, title: str, source_type: str, file_key: str, file_hash: str, created_by: int | None = None) -> Document:
    # 检查同名文档
    result = await db.execute(
        select(Document).where(Document.kb_id == kb_id, Document.title == title)
    )
    existing = result.scalar_one_or_none()

    if existing:
        # 创建新版本
        ver_result = await db.execute(
            select(DocumentVersion)
            .where(DocumentVersion.document_id == existing.id)
            .order_by(DocumentVersion.version_no.desc())
            .limit(1)
        )
        last_ver = ver_result.scalar_one_or_none()
        new_ver_no = (last_ver.version_no + 1) if last_ver else 1

        version = DocumentVersion(
            document_id=existing.id,
            version_no=new_ver_no,
            file_key=file_key,
            file_hash=file_hash,
            is_current=True,
        )
        db.add(version)
        await db.flush()

        # 更新旧版本为非当前
        if last_ver:
            last_ver.is_current = False

        existing.current_version_id = version.id
        existing.status = 1  # 待解析
        return existing
    else:
        # 创建新文档
        doc = Document(
            kb_id=kb_id,
            title=title,
            source_type=source_type,
            status=1,
            created_by=created_by,
        )
        db.add(doc)
        await db.flush()

        version = DocumentVersion(
            document_id=doc.id,
            version_no=1,
            file_key=file_key,
            file_hash=file_hash,
            is_current=True,
        )
        db.add(version)
        await db.flush()

        doc.current_version_id = version.id
        return doc


async def update_document_status(db: AsyncSession, doc_id: int, status: int, fail_reason: str | None = None) -> Document:
    result = await db.execute(select(Document).where(Document.id == doc_id))
    doc = result.scalar_one_or_none()
    if doc is None:
        raise NotFoundError("文档不存在")
    doc.status = status
    if fail_reason:
        doc.fail_reason = fail_reason
    await db.flush()
    return doc
