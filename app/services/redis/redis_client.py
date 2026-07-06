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


@router_redis.delete("/delete/{key}")
async def delete_value(key: str):
    """Удалить значение по ключу"""
    deleted_count = await redis_client.delete(key)
    if deleted_count:
        logger.info(f"Ключ {key} удален из Redis")
        return {"status": "ok", "key": key, "deleted": True}
    else:
        logger.warning(f"Ключ {key} не найден для удаления")
        raise HTTPException(status_code=404, detail="Ключ не найден")


@router_redis.delete("/delete-pattern/{pattern}")
async def delete_by_pattern(pattern: str):
    """Удалить все ключи по паттерну (например, 'session:*')"""
    keys = await redis_client.keys(pattern)
    if not keys:
        logger.warning(f"Ключи по паттерну '{pattern}' не найдены")
        raise HTTPException(status_code=404, detail="Ключи не найдены")

    deleted_count = await redis_client.delete(*keys)
    logger.info(f"Удалено {deleted_count} ключей по паттерну '{pattern}'")
    return {
        "status": "ok",
        "pattern": pattern,
        "deleted_count": deleted_count,
        "keys": [k.decode('utf-8') if isinstance(k, bytes) else k for k in keys]
    }


@router_redis.delete("/flush")
async def flush_all():
    """Очистить всю базу Redis (ОСТОРОЖНО!)"""
    await redis_client.flushdb()
    logger.warning("Выполнена полная очистка Redis")
    return {"status": "ok", "message": "Redis полностью очищен"}