from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.android_data.AndroidDataSchemas import AndroidDataCreate, AndroidDataResponse
from app.database.crud_android_data import (
    create_or_update_android_data,
    get_all_android_data,
    update_android_data,
    delete_android_data
)
from app.middleware.LoggingMiddleware import logger
from app.services.auth.auth_service import require_authorized_user
from app.services.auth.permission_checker import check_permission
from app.services.android.command_manager import command_manager

router_android_data = APIRouter(prefix="/android-data", tags=["Android Data"])

@router_android_data.post("/", response_model=AndroidDataResponse, status_code=200)
async def endpoint_create_android_data(
        request: Request,
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )
    return await create_or_update_android_data(db, data)


@router_android_data.get("/", response_model=list[AndroidDataResponse])
async def endpoint_read_all_android_data(
        serial_number: Optional[str] = Query(None),
        skip: int = 0, limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    return await get_all_android_data(db, serial_number, skip, limit)

@router_android_data.patch("/{serial_number}", response_model=AndroidDataResponse)
async def endpoint_update_android_data(
        request: Request,
        serial_number: str,
        data: AndroidDataCreate,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )

    db_record = await update_android_data(db, serial_number, data)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return db_record

@router_android_data.delete("/{serial_number}", status_code=200)
async def endpoint_delete_android_data(
        request: Request,
        serial_number: str,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    has_perm = await check_permission(request, "android_data", "write")
    if not has_perm:
        raise HTTPException(
            status_code=403,
            detail=f"Нет права 'write' на тип актива 'android_data'"
        )

    db_record = await delete_android_data(db, serial_number)
    if db_record is None:
        logger.warning("Данные Android не найдены")
        raise HTTPException(status_code=404, detail="Данные Android не найдены")
    return None

# Эндпоинт для ADC: "Я жду команду 30 секунд"
@router_android_data.get("/{serial_number}/check-command")
async def check_command(serial_number: str):
    """
    Long Polling: ждет команду до 30 секунд.
    """
    command = await command_manager.wait_for_command(serial_number, timeout=30.0)

    if command:
        return {"status": "success", "command": command}
    else:
        return {"status": "empty"} # Команд нет, клиент должен сразу сделать новый запрос

# Эндпоинт для GpsWarehouseApp: "Включи звук на этом устройстве"
@router_android_data.post("/{serial_number}/play-sound", status_code=200)
async def trigger_play_sound(serial_number: str):
    """
    Отправляет команду на воспроизведение звука.
    """
    command_data = {
        "action": "PLAY_ALARM_SOUND",
        "duration": 10
    }

    success = await command_manager.send_command(serial_number, command_data)

    if success:
        return {"message": f"Команда мгновенно доставлена на {serial_number}"}
    else:
        # Если устройство прямо сейчас не "висит" на сервере, оно получит команду
        # при следующем своем запросе (через 15 мин, если не изменишь интервал)
        return {"message": f"Устройство {serial_number} не на связи. Команда поставлена в очередь (требуется доработка хранения)."}