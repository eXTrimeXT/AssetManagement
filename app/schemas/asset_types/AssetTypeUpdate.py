from pydantic import BaseModel, ConfigDict

class AssetTypeUpdate(BaseModel):
    """
    Схема для частичного обновления типа актива (PATCH запрос).
    """
    # Все поля опциональны (None по умолчанию).
    # Обновятся только те поля, которые явно переданы в запросе.
    name: str | None = None
    type_id: int | None = None

    # extra='ignore' игнорирует лишние поля в JSON-запросе, которые не описаны в схеме, предотвращая ошибки валидации.
    model_config = ConfigDict(extra='ignore')