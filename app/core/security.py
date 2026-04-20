import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.config import settings


def _prepare_password(password: str) -> bytes:
    """bcrypt 72 바이트 한계 대응 선해시.

    bcrypt 는 비밀번호를 최대 72 바이트만 사용한다. 한글 1글자 = 3 바이트 이므로
    25자만 넘어가도 잘리기 시작한다. SHA256 으로 선해시한 hex 문자열(64 바이트)을
    bcrypt 에 넘기면 입력 길이와 무관하게 전체 비밀번호가 반영된다.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest().encode("utf-8")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prepare_password(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prepare_password(plain), hashed.encode("utf-8"))
    except ValueError:
        # 저장된 해시가 손상됐거나 포맷이 맞지 않을 때
        return False


def create_access_token(subject: str, expires_minutes: int | None = None) -> str:
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        return None
