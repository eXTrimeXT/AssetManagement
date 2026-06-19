import json
from typing import Optional
from app.service.redis.redis_client import redis_client

class MapConfigService:
    """
    Сервис для управления конфигурацией карты через Redis.
    """

    CONFIG_KEY = "map:config"

    @classmethod
    async def get_config(cls) -> dict:
        """
        Получить конфигурацию карты.
        Возвращает дефолтные значения, если конфиг не найден.
        """
        config = await redis_client.get(cls.CONFIG_KEY)

        if config:
            return json.loads(config)

        # Дефолтные значения
        return {
            "map_width": 2000,
            "map_height": 2000,
        }

    @classmethod
    async def update_config(
            cls,
            map_width: Optional[int] = None,
            map_height: Optional[int] = None,
    ) -> dict:
        """
        Обновить конфигурацию карты.
        """
        # Получаем текущий конфиг
        config = await cls.get_config()

        # Обновляем поля
        if map_width is not None:
            config["map_width"] = map_width
        if map_height is not None:
            config["map_height"] = map_height

        # Сохраняем в Redis
        await redis_client.set(
            cls.CONFIG_KEY,
            json.dumps(config)
        )

        return config

    @classmethod
    async def get_map_width(cls) -> int:
        """Получить ширину карты"""
        config = await cls.get_config()
        return config.get("map_width", 2000)

    @classmethod
    async def get_map_height(cls) -> int:
        """Получить высоту карты"""
        config = await cls.get_config()
        return config.get("map_height", 2000)


    @classmethod
    async def init_default_config(cls) -> None:
        """
        Инициализировать конфиг значениями по умолчанию.
        Вызвать при старте приложения.
        """
        config = await redis_client.get(cls.CONFIG_KEY)

        if not config:
            await redis_client.set(
                cls.CONFIG_KEY,
                json.dumps({
                    "map_width": 2000,
                    "map_height": 2000,
                })
            )