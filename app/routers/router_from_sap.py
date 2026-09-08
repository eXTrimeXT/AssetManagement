from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import httpx

from app.database.connection import get_db
from app.models.assets import Asset
from app.services.auth.auth_service import require_authorized_user

router_from_sap = APIRouter(prefix="/assets", tags=["Assets"])


@router_from_sap.post("/sync-from-sap")
async def sync_assets_from_sap(db: AsyncSession = Depends(get_db), current_user = Depends(require_authorized_user)):
    sap_api_url = "http://10.168.143.7:8123/sap/base_materials"
    limit = 1000
    offset = 0
    total_synced = 0

    async with httpx.AsyncClient() as client:
        while True:
            response = await client.get(
                sap_api_url,
                params={
                    "limit": limit,
                    "offset": offset
                }
            )
            response.raise_for_status()
            result = response.json()

            if not result.get("success") or "response" not in result or "data" not in result["response"]:
                raise HTTPException(status_code=500, detail="Неверная структура ответа SAP API")

            data = result["response"]["data"]
            if not data:
                break

            # Используем словарь для удаления дубликатов inventory_id внутри текущей порции
            records_dict = {}
            for item in data:
                inv_id = item.get("inventory_number")
                if not inv_id:
                    continue  # Пропускаем записи без inventory_id, так как это ключ конфликта

                serial_num = item.get("serial_number")
                if not serial_num:
                    serial_num = None

                # Последняя встречающаяся запись с таким inventory_id перезапишет предыдущую в словаре
                records_dict[inv_id] = {
                    "inventory_id": inv_id,
                    "name": item.get("base_material_name"),
                    "serial_number": serial_num,
                    "quantity": item.get("quantity", 0),
                    "every_week_check": False
                }

            records = list(records_dict.values())

            if not records:
                offset += limit
                continue

            # PostgreSQL bulk upsert (вставка или обновление при конфликте по уникальному inventory_id)
            stmt = insert(Asset).values(records)
            stmt = stmt.on_conflict_do_update(
                index_elements=["inventory_id"],
                set_={
                    "name": stmt.excluded.name,
                    "serial_number": stmt.excluded.serial_number,
                    "quantity": stmt.excluded.quantity
                }
            )

            await db.execute(stmt)
            await db.commit()

            total_synced += len(records)

            # Если возвращено меньше элементов, чем limit, значит это последняя страница
            if len(data) < limit:
                break

            offset += limit

    return {
        "success": True,
        "message": "Синхронизация завершена",
        "total_synced": total_synced
    }