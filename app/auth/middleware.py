from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from app.config import settings
from app.db import get_db, get_user_by_id

security = HTTPBearer(auto_error=False)


async def _decode_user(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    conn = await get_db()
    try:
        user = await get_user_by_id(conn, user_id)
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    finally:
        await conn.close()


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _decode_user(credentials.credentials)


async def get_user_from_token_or_header(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    token: Optional[str] = None,
) -> dict:
    if token:
        try:
            return await _decode_user(token)
        except HTTPException:
            pass
    if credentials:
        try:
            return await _decode_user(credentials.credentials)
        except HTTPException:
            pass
    raise HTTPException(status_code=401, detail="Authentication required")


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[dict]:
    if not credentials:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
