"""Milvus 向量数据库客户端封装"""

import logging
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = None


def get_milvus_client():
    """懒加载 Milvus 客户端（pymilvus 非必须启动依赖）"""
    global _client
    if _client is None:
        try:
            from pymilvus import MilvusClient
            uri = f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}"
            _client = MilvusClient(uri=uri)
            logger.info("Milvus 连接成功: %s", uri)
        except Exception as exc:
            logger.warning("Milvus 连接失败（降级为仅 BM25）: %s", exc)
            _client = None
    return _client


async def hybrid_search(
    query: str,
    kb_ids: list[int],
    top_k: int = 50,
    dense_vec: list[float] | None = None,
) -> list[dict]:
    """混合检索：稠密向量 + BM25 稀疏向量，RRF 融合排序"""
    client = get_milvus_client()
    if client is None:
        logger.warning("Milvus 不可用，返回空结果")
        return []

    expr = f"kb_id in {kb_ids} and status == 1" if kb_ids else "status == 1"

    try:
        from pymilvus import AnnSearchRequest, RRFRanker

        reqs = []
        if dense_vec:
            reqs.append(
                AnnSearchRequest(
                    [dense_vec], "dense_vec",
                    {"metric_type": "COSINE", "params": {"ef": 128}},
                    limit=top_k, expr=expr,
                )
            )
        reqs.append(
            AnnSearchRequest(
                [query], "sparse_vec",
                {"metric_type": "IP"},
                limit=top_k, expr=expr,
            )
        )

        res = client.hybrid_search(
            collection_name=settings.MILVUS_COLLECTION,
            reqs=reqs,
            ranker=RRFRanker(k=settings.RRF_K),
            limit=top_k,
            output_fields=["chunk_id", "doc_id", "version_id", "title_path", "page_no", "content", "kb_id"],
        )
        return [dict(hit) for hit in res[0]] if res else []
    except Exception as exc:
        logger.error("Milvus 检索异常: %s", exc)
        return []


async def upsert_chunks(chunks: list[dict]) -> bool:
    """批量写入切片到 Milvus"""
    client = get_milvus_client()
    if client is None:
        return False
    try:
        client.upsert(collection_name=settings.MILVUS_COLLECTION, data=chunks)
        return True
    except Exception as exc:
        logger.error("Milvus upsert 失败: %s", exc)
        return False


async def delete_chunks_by_version(version_id: int) -> bool:
    """按版本删除 Milvus 中的切片"""
    client = get_milvus_client()
    if client is None:
        return False
    try:
        client.delete(
            collection_name=settings.MILVUS_COLLECTION,
            filter=f"version_id == {version_id}",
        )
        return True
    except Exception as exc:
        logger.error("Milvus delete 失败: %s", exc)
        return False
