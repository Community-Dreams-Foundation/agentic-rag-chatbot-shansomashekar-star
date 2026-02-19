import hashlib
import json
from typing import Any, List, Optional

from app.config import settings


class EmbeddingCache:
    def __init__(self) -> None:
        self.redis = None
        if settings.redis_url:
            try:
                import redis.asyncio as redis
                self.redis = redis.from_url(settings.redis_url)
            except Exception:
                pass

    async def get(self, text: str) -> Optional[List[float]]:
        if not self.redis:
            return None
        try:
            key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
            val = await self.redis.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    async def set(self, text: str, embedding: List[float]) -> None:
        if not self.redis:
            return
        try:
            key = f"emb:{hashlib.sha256(text.encode()).hexdigest()}"
            await self.redis.setex(key, 86400, json.dumps(embedding))
        except Exception:
            pass


class QueryCache:
    def __init__(self) -> None:
        self.redis = None
        if settings.redis_url:
            try:
                import redis.asyncio as redis
                self.redis = redis.from_url(settings.redis_url)
            except Exception:
                pass

    async def get(self, user_id: str, query: str) -> Optional[dict]:
        if not self.redis:
            return None
        try:
            q = query.lower().strip()
            key = f"qry:{user_id}:{hashlib.sha256(q.encode()).hexdigest()}"
            val = await self.redis.get(key)
            if val:
                return json.loads(val)
        except Exception:
            pass
        return None

    async def set(self, user_id: str, query: str, data: dict) -> None:
        if not self.redis:
            return
        try:
            q = query.lower().strip()
            key = f"qry:{user_id}:{hashlib.sha256(q.encode()).hexdigest()}"
            await self.redis.setex(key, 3600, json.dumps(data))
        except Exception:
            pass

    async def invalidate_user(self, user_id: str) -> None:
        if not self.redis:
            return
        try:
            pattern = f"qry:{user_id}:*"
            async for key in self.redis.scan_iter(match=pattern):
                await self.redis.delete(key)
        except Exception:
            pass


embedding_cache = EmbeddingCache()
query_cache = QueryCache()
