import hashlib
import time
import uuid

from fastapi import APIRouter, HTTPException, status
from jose import jwt

from app.config import settings
from app.db import get_db, create_user, get_user_by_username
from app.schemas import TokenResponse, UserLogin, UserRegister

router = APIRouter(prefix="/users", tags=["auth"])


def _hash_password(password: str) -> str:
    return hashlib.sha256(f"{password}{settings.jwt_secret}".encode()).hexdigest()


def _create_token(user_id: str, username: str) -> str:
    payload = {
        "sub": user_id,
        "username": username,
        "exp": int(time.time()) + settings.jwt_expire_hours * 3600,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


@router.post("/register", response_model=TokenResponse)
async def register(data: UserRegister):
    if not data.username or not data.password:
        raise HTTPException(status_code=400, detail="Username and password required")
    conn = await get_db()
    try:
        existing = await get_user_by_username(conn, data.username)
        if existing:
            raise HTTPException(status_code=400, detail="Username already taken")
        user_id = str(uuid.uuid4())
        pw_hash = _hash_password(data.password)
        await create_user(conn, user_id, data.username, pw_hash)
        token = _create_token(user_id, data.username)
        return TokenResponse(access_token=token, user_id=user_id, username=data.username)
    finally:
        await conn.close()


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin):
    conn = await get_db()
    try:
        user = await get_user_by_username(conn, data.username)
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        pw_hash = _hash_password(data.password)
        if user["password_hash"] != pw_hash:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = _create_token(user["id"], user["username"])
        return TokenResponse(access_token=token, user_id=user["id"], username=user["username"])
    finally:
        await conn.close()
