from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
from app.service.map_asset.map_config_service import MapConfigService

router_map_config = APIRouter(prefix="/map-config", tags=["Map Configuration"])

class MapConfigUpdate(BaseModel):
    map_width: Optional[int] = None
    map_height: Optional[int] = None

@router_map_config.get("/")
async def get_map_config():
    """
    Получить конфигурацию карты.
    """
    return await MapConfigService.get_config()

@router_map_config.patch("/")
async def update_map_config(config: MapConfigUpdate):
    """
    Обновить конфигурацию карты.
    """
    return await MapConfigService.update_config(
        map_width=config.map_width,
        map_height=config.map_height,
    )

@router_map_config.post("/reset")
async def reset_map_config():
    """
    Сбросить конфиг к значениям по умолчанию.
    """
    await MapConfigService.init_default_config()
    return {"message": "Map config reset to default", "config": await MapConfigService.get_config()}