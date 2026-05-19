from pydantic import BaseModel
from pydantic import ConfigDict

class AssetTypeCreate(BaseModel):
    """ Схема для создания нового типа актива (POST запрос) """
    name: str
    en_name: str


class AssetTypeResponse(BaseModel):
    """ Схема для ответа клиенту (GET запросы) """
    # from_attributes=True позволяет Pydantic конвертировать объект SQLAlchemy (ORM-модель) в JSON-ответ.
    # Без этого возникнет ошибка сериализации.
    model_config = ConfigDict(from_attributes=True)
    name: str
    en_name: str

    # Внутренний первичный ключ базы данных (autoincrement).
    # Добавляется только в ответ, так как при создании он генерируется БД автоматически.
    asset_type_id: int

class AssetTypeUpdate(BaseModel):
    """ Схема для частичного обновления типа актива (PATCH запрос) """
    # Все поля опциональны (None по умолчанию).
    # Обновятся только те поля, которые явно переданы в запросе.
    name: str | None = None
    en_name: str | None = None

    # extra='ignore' игнорирует лишние поля в JSON-запросе, которые не описаны в схеме, предотвращая ошибки валидации.
    model_config = ConfigDict(extra='ignore')