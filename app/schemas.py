from pydantic import BaseModel
from typing import List, Optional


class UserRegister(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    username: str


class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None


class Citation(BaseModel):
    source: str
    chunk_index: int
    excerpt: str


class MemoryEntry(BaseModel):
    should_write: bool
    target: Optional[str] = None
    summary: str
    confidence: float
    reason: Optional[str] = None


class AnalyzeRequest(BaseModel):
    request: str


class AnalyzeResponse(BaseModel):
    result: str
    tool_calls: List[dict] = []
