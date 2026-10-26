"""应用配置 - 从环境变量加载"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


class Settings(BaseSettings):
    """全局配置，从 .env 与环境变量加载"""

    # ── 应用 ──────────────────────────────────────────
    APP_ENV: str = "dev"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    DEBUG: bool = True

    # ── PostgreSQL ────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://myuser:cqjtu%40yxjpgsql@10.1.240.243:5432/mydb"
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 30

    # ── Redis ─────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Milvus ────────────────────────────────────────
    MILVUS_HOST: str = "10.1.240.243"
    MILVUS_PORT: int = 19530
    MILVUS_COLLECTION: str = "kb_chunks"
    EMBEDDING_DIM: int = 1024

    # ── Embedding · 阿里百炼 ──────────────────────────
    DASHSCOPE_EMBEDDING_API_KEY: str = ""
    DASHSCOPE_EMBEDDING_MODEL: str = "text-embedding-v3"
    DASHSCOPE_EMBEDDING_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    # ── LLM · 火山引擎豆包 ────────────────────────────
    VOLCENGINE_API_KEY: str = ""
    VOLCENGINE_MODEL: str = "doubao-pro-4k"
    VOLCENGINE_ENDPOINT_ID: str = ""
    VOLCENGINE_BASE_URL: str = "https://ark.cn-beijing.volces.com/api/v3"

    # ── 通用模型参数 ──────────────────────────────────
    TEMPERATURE: float = 0.7
    TOP_P: float = 0.95
    MAX_TOKENS: int = 2048
    TIMEOUT: int = 60

    # ── Agent 约束 ────────────────────────────────────
    AGENT_MAX_ITERATIONS: int = 4
    AGENT_TIMEOUT: int = 20
    AGENT_TOKEN_BUDGET: int = 12000
    MAX_RETRIEVED_CHUNKS: int = 8
    MAX_TOOL_RESULT_CHARS: int = 3000
    RETRY_ON_VERIFY_FAIL: int = 1

    # ── 检索参数 ──────────────────────────────────────
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    DENSE_TOP_K: int = 50
    SPARSE_TOP_K: int = 50
    RRF_K: int = 60
    TOOL_TOP_K: int = 6
    MIN_SCORE: float = 0.35
    HISTORY_ROUNDS: int = 5

    # ── LangSmith ─────────────────────────────────────
    LANGCHAIN_TRACING_V2: bool = True
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "uni-qa"
    LANGCHAIN_ENDPOINT: str = "https://api.smith.langchain.com"

    # ── JWT ───────────────────────────────────────────
    JWT_SECRET_KEY: str = "uni-qa-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_HOURS: int = 24

    # ── 默认管理员 ────────────────────────────────────
    ADMIN_USERNAME: str = "admin"
    ADMIN_DEFAULT_PASSWORD: str = "admin123456"

    # ── MinIO ─────────────────────────────────────────
    MINIO_ENDPOINT: str = "localhost:9000"
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_BUCKET: str = "uni-qa"
    MINIO_USE_SSL: bool = False

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
