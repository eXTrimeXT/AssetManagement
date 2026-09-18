from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.services.auth.auth_service import require_authorized_user
from app.services.sap.sync_sap_assets import sync_sap_assets

router_from_sap = APIRouter(prefix="/sap", tags=["SAP API"])


@router_from_sap.post("/sync-from-sap")
async def sync_assets_from_sap(
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    result = await sync_sap_assets(db)

    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("message"))

    return result

@router_from_sap.get(
    "/departments",
    summary="Получить список подразделений из SAP API"
)
async def get_sap_departments(
        limit: int = Query(default=1000, description="Лимит записей"),
        offset: int = Query(default=0, description="Смещение (offset)"),
        department: Optional[str] = Query(None, description="Аббревиатура департамента"),
        department_name_like: str = Query(None, description="Поиск по названию департамента"),
):
    """
    Обращается к внешнему SAP API и возвращает его ответ.
    """
    sap_url = f"http://10.168.143.7:8123/sap/mvz?limit={limit}&offset={offset}"

    if department:
        sap_url += f"&department={department}"
    if department_name_like:
        sap_url += f"&department_name_like={department_name_like}"

    try:
        # Используем асинхронный клиент httpx
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(sap_url)

            # Проверяем, что ответ успешный (2xx)
            response.raise_for_status()

            # Возвращаем JSON-ответ от SAP как есть
            return response.json()

    except httpx.RequestError as exc:
        # Ошибка сети, таймаут или недоступность хоста
        raise HTTPException(
            status_code=502,
            detail=f"Ошибка соединения с SAP API: {str(exc)}"
        )
    except httpx.HTTPStatusError as exc:
        # SAP вернул ошибку (4xx или 5xx)
        raise HTTPException(
            status_code=exc.response.status_code,
            detail=f"Ошибка SAP API: {exc.response.text}"
        )
    except Exception as exc:
        # Любая другая непредвиденная ошибка
        raise HTTPException(
            status_code=500,
            detail=f"Внутренняя ошибка сервера: {str(exc)}"
        )