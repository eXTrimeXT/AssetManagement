from pydantic import BaseModel, ConfigDict

# Частота изменений актива по полям
class FieldChangeHeatmapResponse(BaseModel):
    field_name: str
    change_count: int
    model_config = ConfigDict(from_attributes=True)
