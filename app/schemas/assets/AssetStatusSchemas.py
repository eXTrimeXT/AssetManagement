from pydantic import BaseModel, ConfigDict

class AssetStatusCreate(BaseModel):
    status: str

class AssetStatusUpdate(BaseModel):
    status: str

class AssetStatusResponse(BaseModel):
    id: int
    status: str

    model_config = ConfigDict(from_attributes=True)

