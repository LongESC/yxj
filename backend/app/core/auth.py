"""JWT 认证与 RBAC 权限"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import get_settings
from app.core.database import get_db
from app.core.errors import ForbiddenError, UnauthorizedError
from app.domain.models import Role, User

settings = get_settings()
security = HTTPBearer()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── 密码工具 ──────────────────────────────────────────

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Token ─────────────────────────────────────────────

def create_access_token(user_id: int, username: str, role_code: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role_code,
        "exp": expire,
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedError(f"Token 无效: {exc}")


# ── FastAPI 依赖 ──────────────────────────────────────

async def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = creds.credentials
    payload = decode_token(token)
    user_id = int(payload["sub"])

    result = await db.execute(
        select(User).options(selectinload(User.role)).where(User.id == user_id, User.status == 1)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise UnauthorizedError("用户不存在或已禁用")
    return user


async def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    if creds is None:
        return None
    return await get_current_user(creds, db)


def require_role(*roles: str):
    """角色权限校验装饰器"""
    async def checker(user: User = Depends(get_current_user)) -> User:
        user_role = user.role.code if user.role else ""
        if user_role not in roles and user_role != "sys_admin":
            raise ForbiddenError(f"需要角色: {', '.join(roles)}")
        return user
    return checker


async def get_user_kb_ids(db: AsyncSession, user_id: int) -> list[int]:
    """计算用户可见的知识库 ID 列表"""
    from app.domain.models import KBPermission
    result = await db.execute(
        select(KBPermission.kb_id).where(
            KBPermission.subject_type == "user",
            KBPermission.subject_id == user_id,
        )
    )
    return list(result.scalars().all())
