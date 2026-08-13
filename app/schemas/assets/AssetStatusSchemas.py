from pydantic import BaseModel

class AssetStatusCreate(BaseModel):
    status: str

class AssetStatusUpdate(BaseModel):
    status: str

class AssetStatusResponse(BaseModel):
    id: int
    status: str

    model_config = {
        "from_attributes": True
    }

