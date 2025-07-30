import redis
import json
from typing import Any, Optional
from app.config import settings

class RedisClient:
    def __init__(self):
        self.client = redis.from_url(settings.redis_url, decode_responses=True)
    
    async def get(self, key: str) -> Optional[str]:
        try:
            return self.client.get(key)
        except Exception:
            return None
    
    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        try:
            return self.client.set(key, value, ex=expire)
        except Exception:
            return False
    
    async def delete(self, key: str) -> bool:
        try:
            return bool(self.client.delete(key))
        except Exception:
            return False
    
    async def exists(self, key: str) -> bool:
        try:
            return bool(self.client.exists(key))
        except Exception:
            return False
    
    async def incr(self, key: str) -> int:
        try:
            return self.client.incr(key)
        except Exception:
            return 0
    
    async def expire(self, key: str, seconds: int) -> bool:
        try:
            return bool(self.client.expire(key, seconds))
        except Exception:
            return False
    
    async def get_json(self, key: str) -> Any:
        try:
            value = await self.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception:
            return None
    
    async def set_json(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, expire)
        except Exception:
            return False

redis_client = RedisClient()