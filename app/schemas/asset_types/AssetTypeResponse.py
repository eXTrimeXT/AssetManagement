from pydantic import ConfigDict
from app.schemas.asset_types.AssetTypeBase import AssetTypeBase

class AssetTypeResponse(AssetTypeBase):
    """
    Схема для ответа клиенту (GET запросы).
    """
    # from_attributes=True позволяет Pydantic конвертировать объект SQLAlchemy (ORM-модель) в JSON-ответ.
    # Без этого возникнет ошибка сериализации.
    model_config = ConfigDict(from_attributes=True)

    # Внутренний первичный ключ базы данных (autoincrement).
    # Добавляется только в ответ, так как при создании он генерируется БД автоматически.
    asset_type_id: int
