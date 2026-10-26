"""文档入库服务（Celery 异步任务接口）"""

import logging

logger = logging.getLogger(__name__)


async def parse_document(document_id: int) -> bool:
    """解析文档：提取正文、标题层级、表格"""
    # TODO: 接入 PyMuPDF / python-docx / openpyxl / PaddleOCR
    logger.info("解析文档 %d (待实现)", document_id)
    return True


async def chunk_document(document_id: int) -> list[dict]:
    """切片文档"""
    # TODO: MarkdownHeaderTextSplitter + RecursiveCharacterTextSplitter
    logger.info("切片文档 %d (待实现)", document_id)
    return []


async def embed_chunks(chunks: list[dict]) -> list[list[float]]:
    """生成向量"""
    from app.infrastructure.embedding import embed_texts
    texts = [c["content"] for c in chunks]
    return await embed_texts(texts)


async def index_chunks(chunks: list[dict], vectors: list[list[float]]) -> bool:
    """写入 PostgreSQL + Milvus"""
    # TODO: 批量写入
    logger.info("索引 %d 个切片 (待实现)", len(chunks))
    return True
