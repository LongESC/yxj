"""LLM 客户端封装 — 火山引擎豆包 (ChatOpenAI 兼容)"""

import logging

from langchain_openai import ChatOpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def build_llm(
    temperature: float | None = None,
    max_tokens: int | None = None,
    streaming: bool = True,
) -> ChatOpenAI:
    """构建豆包 LLM 客户端"""
    return ChatOpenAI(
        model=settings.VOLCENGINE_MODEL,
        base_url=settings.VOLCENGINE_BASE_URL,
        api_key=settings.VOLCENGINE_API_KEY,
        temperature=temperature if temperature is not None else settings.TEMPERATURE,
        max_tokens=max_tokens if max_tokens is not None else settings.MAX_TOKENS,
        timeout=settings.TIMEOUT,
        max_retries=2,
        streaming=streaming,
    )
