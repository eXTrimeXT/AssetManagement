from fastapi import HTTPException, APIRouter
from redis.asyncio import Redis
import os

# Асинхронный клиент Redis
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "8379")),
    decode_responses=True
)
router_redis = APIRouter(prefix="/redis", tags=["Redis"])

@router_redis.get("/set/{key}/{value}")
async def set_value(key: str, value: str):
    await redis_client.set(key, value)
    return {"status": "ok", "key": key, "value": value}

@router_redis.get("/get/{key}")
async def get_value(key: str):
    value = await redis_client.get(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Key not found")
    return {"key": key, "value": value}