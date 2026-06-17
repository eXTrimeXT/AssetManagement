from fastapi import APIRouter, Depends
from app.service.map_asset.map_config_service import MapConfigService
from pydantic import BaseModel
from typing import Optional

router_map_config = APIRouter(prefix="/map-config", tags=["Map Configuration"])

class MapConfigUpdate(BaseModel):
    map_size: Optional[int] = None
    workshop_scale: Optional[float] = None

@router_map_config.get("/")
async def get_map_config():
    """Получить конфигурацию карты"""
    return await MapConfigService.get_config()

@router_map_config.patch("/")
async def update_map_config(config: MapConfigUpdate):
    """Обновить конфигурацию карты"""
    return await MapConfigService.update_config(
        map_size=config.map_size,
        workshop_scale=config.workshop_scale
    )

@router_map_config.post("/reset")
async def reset_map_config():
    """Сбросить конфиг к значениям по умолчанию"""
    await MapConfigService.init_default_config()
    return {"message": "Config reset to default"}