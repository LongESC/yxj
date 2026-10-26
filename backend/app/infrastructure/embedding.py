"""Embedding 客户端封装 — 阿里百炼 text-embedding-v3"""

import hashlib
import logging
from typing import Optional

from app.core.config import get_settings
from app.infrastructure.cache import cache_get, cache_set

logger = logging.getLogger(__name__)
settings = get_settings()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量文本向量化（10 条/批），带 Embedding 缓存"""
    results: list[Optional[list[float]]] = [None] * len(texts)
    batch_indices: list[int] = []
    batch_texts: list[str] = []

    for i, text in enumerate(texts):
        text_hash = hashlib.sha256(text.encode()).hexdigest()[:16]
        cache_key = f"emb:{text_hash}"
        cached = await cache_get(cache_key)
        if cached is not None:
            results[i] = cached
        else:
            batch_indices.append(i)
            batch_texts.append(text)

    if batch_texts:
        try:
            from langchain_openai import OpenAIEmbeddings
            embedder = OpenAIEmbeddings(
                model=settings.DASHSCOPE_EMBEDDING_MODEL,
                openai_api_key=settings.DASHSCOPE_EMBEDDING_API_KEY,
                openai_api_base=settings.DASHSCOPE_EMBEDDING_BASE_URL,
                dimensions=settings.EMBEDDING_DIM,
            )
            # 分批 10 条
            for start in range(0, len(batch_texts), 10):
                chunk = batch_texts[start:start + 10]
                vecs = await embedder.aembed_documents(chunk)
                for j, vec in enumerate(vecs):
                    idx = batch_indices[start + j]
                    results[idx] = vec
                    text_hash = hashlib.sha256(batch_texts[start + j].encode()).hexdigest()[:16]
                    await cache_set(f"emb:{text_hash}", vec, ttl=30 * 86400)
        except Exception as exc:
            logger.error("Embedding 调用失败: %s", exc)
            raise

    return [r if r is not None else [] for r in results]


async def embed_query(query: str) -> list[float]:
    """查询文本向量化"""
    vecs = await embed_texts([query])
    return vecs[0]
