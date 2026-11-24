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

@router_android_data.post(
    "/",
    response_model=AndroidDataResponse,
    status_code=200,
    summary="Создать или обновить данные Android / Create or Update Android Data",
    description=(
            "RU: Создает новую запись данных Android или обновляет существующую (upsert). "
            "Данные передаются в теле запроса. Проверяет наличие права на запись (`write`) "
            "для ресурса `android_data`. При отсутствии прав возвращается ошибка 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Creates a new Android data record or updates an existing one (upsert). "
            "Data is passed in the request body. Checks for write permission (`write`) "
            "on the `android_data` resource. A 403 error is returned if permissions are missing. "
            "User authorization is required."
    )
)
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


@router_android_data.get(
    "/",
    response_model=list[AndroidDataResponse],
    summary="Получить список данных Android / Get Android Data List",
    description=(
            "RU: Возвращает список записей данных Android с поддержкой пагинации "
            "(`skip`, `limit`) и фильтрации по серийному номеру (`serial_number`). "
            "По умолчанию возвращается до 100 записей. Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of Android data records with pagination support "
            "(`skip`, `limit`) and filtering by serial number (`serial_number`). "
            "By default, up to 100 records are returned. User authorization is required."
    )
)
async def endpoint_read_all_android_data(
        serial_number: Optional[str] = Query(None),
        skip: int = 0, limit: int = 100,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    return await get_all_android_data(db, serial_number, skip, limit)

@router_android_data.patch(
    "/{serial_number}",
    response_model=AndroidDataResponse,
    summary="Обновить данные Android по серийному номеру / Update Android Data by Serial Number",
    description=(
            "RU: Обновляет существующую запись данных Android по её серийному номеру `serial_number`. "
            "Проверяет наличие права на запись (`write`) для ресурса `android_data`. "
            "Если запись не найдена — возвращается ошибка 404, при отсутствии прав — 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Updates an existing Android data record by its serial number `serial_number`. "
            "Checks for write permission (`write`) on the `android_data` resource. "
            "If the record is not found, a 404 error is returned; if permissions are missing, a 403 error is returned. "
            "User authorization is required."
    )
)
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

@router_android_data.delete(
    "/{serial_number}",
    status_code=200,
    summary="Удалить данные Android по серийному номеру / Delete Android Data by Serial Number",
    description=(
            "RU: Удаляет запись данных Android по её серийному номеру `serial_number`. "
            "Проверяет наличие права на запись (`write`) для ресурса `android_data`. "
            "Если запись не найдена — возвращается ошибка 404, при отсутствии прав — 403. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Deletes an Android data record by its serial number `serial_number`. "
            "Checks for write permission (`write`) on the `android_data` resource. "
            "If the record is not found, a 404 error is returned; if permissions are missing, a 403 error is returned. "
            "User authorization is required."
    )
)
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
@router_android_data.get(
    "/{serial_number}/check-command",
    summary="Получить команду для устройства (Long Polling) / Get Command for Device (Long Polling)",
    description=(
            "RU: Эндпоинт Long Polling для Android-устройств. Ожидает команду для устройства "
            "с указанным серийным номером до 30 секунд. Если команда поступает — она возвращается "
            "в поле `command`. Если за время ожидания команда не поступила — возвращается "
            "`status: empty`, и клиент должен выполнить повторный запрос. "
            "Авторизация не требуется (публичный эндпоинт для устройств).\n\n"
            "EN: Long Polling endpoint for Android devices. Waits for a command for the device "
            "with the specified serial number for up to 30 seconds. If a command arrives, it is returned "
            "in the `command` field. If no command is received during the wait time, "
            "`status: empty` is returned, and the client should make a new request. "
            "Authorization is not required (public endpoint for devices)."
    )
)
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
@router_android_data.post(
    "/{serial_number}/play-sound",
    status_code=200,
    summary="Отправить команду воспроизведения звука на устройство / Send Play Sound Command to Device",
    description=(
            "RU: Отправляет команду на воспроизведение звукового сигнала на Android-устройстве "
            "с указанным серийным номером. Параметр `duration` задаёт длительность звука в секундах "
            "(по умолчанию 10). Если устройство активно подключено к серверу — команда доставляется "
            "мгновенно. Если устройство не на связи — команда ставится в очередь и будет доставлена "
            "при следующем подключении устройства. "
            "Авторизация не требуется (публичный эндпоинт).\n\n"
            "EN: Sends a command to play an audio alarm on the Android device "
            "with the specified serial number. The `duration` parameter sets the sound duration in seconds "
            "(default is 10). If the device is actively connected to the server, the command is delivered "
            "instantly. If the device is offline, the command is queued and will be delivered "
            "upon the device's next connection. "
            "Authorization is not required (public endpoint)."
    )
)
async def trigger_play_sound(serial_number: str, duration: int = 10):
    """
    Отправляет команду на воспроизведение звука.
    """
    command_data = {
        "action": "PLAY_ALARM_SOUND",
        "duration": duration
    }

    success = await command_manager.send_command(serial_number, command_data)

    if success:
        return {"message": f"Команда мгновенно доставлена на {serial_number}"}
    else:
        # Если устройство прямо сейчас не "висит" на сервере, оно получит команду
        # при следующем своем запросе (через 15 мин, если не изменишь интервал)
        return {"message": f"Устройство {serial_number} не на связи. Команда поставлена в очередь (требуется доработка хранения)."}