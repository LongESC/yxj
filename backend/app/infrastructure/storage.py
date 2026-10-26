"""MinIO 对象存储客户端封装"""

import logging
import uuid
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_client = None


def get_minio_client():
    """懒加载 MinIO 客户端"""
    global _client
    if _client is None:
        try:
            from minio import Minio
            _client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_USE_SSL,
            )
            # 确保 bucket 存在
            if not _client.bucket_exists(settings.MINIO_BUCKET):
                _client.make_bucket(settings.MINIO_BUCKET)
        except Exception as exc:
            logger.warning("MinIO 初始化失败: %s", exc)
            _client = None
    return _client


async def upload_file(file_bytes: bytes, filename: str, content_type: str = "application/octet-stream") -> str:
    """上传文件，返回 object key"""
    client = get_minio_client()
    if client is None:
        raise RuntimeError("MinIO 不可用")

    ext = filename.rsplit(".", 1)[-1] if "." in filename else "bin"
    object_key = f"docs/{uuid.uuid4().hex}.{ext}"

    import io
    client.put_object(
        settings.MINIO_BUCKET,
        object_key,
        io.BytesIO(file_bytes),
        len(file_bytes),
        content_type=content_type,
    )
    return object_key


async def download_file(object_key: str) -> bytes:
    """下载文件"""
    client = get_minio_client()
    if client is None:
        raise RuntimeError("MinIO 不可用")

    response = client.get_object(settings.MINIO_BUCKET, object_key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


async def delete_file(object_key: str) -> None:
    """删除文件"""
    client = get_minio_client()
    if client is not None:
        client.remove_object(settings.MINIO_BUCKET, object_key)
