import logging
from fastapi import HTTPException, APIRouter
from redis.asyncio import Redis
import os

logger = logging.getLogger(__name__)

router_redis = APIRouter(prefix="/redis", tags=["Redis"])

# Асинхронный клиент Redis
redis_client = Redis(
    host=os.getenv("REDIS_HOST", "redis"),
    port=int(os.getenv("REDIS_PORT", "8379")),
    decode_responses=True
)

@router_redis.get("/set/{key}/{value}")
async def set_value(key: str, value: str):
    is_set = await redis_client.set(key, value)
    if is_set:
        logger.info(f"Ключ {key} со значением {value} сохранен")
    return {"status": "ok", "key": key, "value": value}

@router_redis.get("/get/{key}")
async def get_value(key: str):
    value = await redis_client.get(key)
    if value is None:
        logger.error("Ключ не найден")
        raise HTTPException(status_code=404, detail="Ключ не найден")
    return {"key": key, "value": value}

@router_redis.get("/get-keys")
async def get_all_keys():
    keys = await redis_client.keys()
    return {"key": keys}