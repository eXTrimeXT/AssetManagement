import os
import io
import uuid
import shutil
import logging
from typing import Literal

import pandas as pd
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Response, Request, Form
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from app.scheduler.scheduler import scheduler

from app.database.connection import get_db
from app.database.assets.crud_asset import update_asset, create_asset
from app.models.assets.Asset import Asset
from app.models.ImportTask import ImportTask
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate, BulkSaveRequest, UpdateRequestForImport
from app.services.auth.auth_service import get_token_from_request, require_authorized_user
from app.services.gps_rs.getinfouser import get_user_allowed_cost_centers
from app.services.excel.import_from_excel import process_excel_import_job

logger = logging.getLogger(__name__)

router_excel_import = APIRouter(prefix="/excel/assets", tags=["Assets"])

# ENDPOINTS
@router_excel_import.post("/import")
async def start_excel_import(
        request: Request,
        file: UploadFile = File(..., description="Excel файл для импорта"),
        priority: Literal["local", "sap", "excel"] = Form(..., description="Приоритет источника данных: local, sap или excel"),
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    if not file.filename.endswith((".xlsx", ".xls")):
        raise HTTPException(status_code=400, detail="Поддерживаются только файлы .xlsx или .xls")

    token = await get_token_from_request(request)
    allowed_cost_centers = await get_user_allowed_cost_centers(token)

    task_id = str(uuid.uuid4())
    new_task = ImportTask(task_id=task_id, status="pending", employee_id=current_user.employee_id)
    db.add(new_task)
    await db.commit()

    temp_dir = "temp_imports"
    os.makedirs(temp_dir, exist_ok=True)
    file_path = os.path.join(temp_dir, f"{task_id}_{file.filename}")

    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    scheduler.add_job(
        func=process_excel_import_job,
        args=[task_id, file_path, allowed_cost_centers, current_user.employee_id, priority],
        id=f"import_{task_id}",
        replace_existing=True
    )

    return {
        "task_id": new_task.task_id,
        "employee_id": new_task.employee_id,
        "status": new_task.status,
        "total_rows": new_task.total_rows,
        "processed_rows": new_task.processed_rows,
        "progress_percent": 0,
        "error_message": new_task.error_message,
        "allowed_cost_centers_used": new_task.allowed_cost_centers or [],
        "items": new_task.items_data or [],
        "priority": priority  # Возвращаем priority в ответе для подтверждения
    }

@router_excel_import.delete("/import/cancel", status_code=200)
async def cancel_excel_import(
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """Отменяет выполняющуюся или ожидающую задачу импорта."""
    # Находим задачу и проверяем, что она принадлежит текущему пользователю и еще не завершена
    stmt = (select(ImportTask).where(
        ImportTask.employee_id == current_user.employee_id,
        ImportTask.status.in_(["pending", "processing"])
    ).order_by(ImportTask.created_at.desc()))

    result = await db.execute(stmt)
    task = result.scalar_one_or_none()

    if not task:
        raise HTTPException(
            status_code=404,
            detail="Задача не найдена, уже завершена, отменена, либо у вас нет прав на её отмену"
        )

    # Меняем статус на cancelled (это сигнал для фоновой задачи остановиться)
    task.status = "cancelled"
    task.error_message = "Отменено пользователем"
    await db.commit()

    # Удаляем задачу из планировщика APScheduler, если она там еще есть
    job_id = f"import_{task.task_id}"
    if scheduler.get_job(job_id):
        scheduler.remove_job(job_id)
        logger.info(f"[IMPORT JOB] Задача {task.task_id} принудительно удалена из планировщика")

    return {
        "message": "Задача импорта успешно отменена",
        "task_id": task.task_id
    }

@router_excel_import.get("/import/status")
async def get_import_status(
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    stmt = (select(ImportTask).where(ImportTask.employee_id == current_user.employee_id).order_by(ImportTask.created_at.desc()))
    result = await db.execute(stmt)
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    progress = 0
    if task.total_rows > 0:
        progress = int((task.processed_rows / task.total_rows) * 100)

    return {
        "task_id": task.task_id,
        "employee_id": task.employee_id,
        "status": task.status,
        "total_rows": task.total_rows,
        "processed_rows": task.processed_rows,
        "progress_percent": progress,
        "error_message": task.error_message,
        "allowed_cost_centers_used": task.allowed_cost_centers or [],
        "items": task.items_data or []
    }

@router_excel_import.post("/import/update")
async def update_excel_items(
        request: UpdateRequestForImport,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    """
    Обновляет список элементов для последней задачи импорта !
    """
    # Находим задачу и проверяем, что она принадлежит текущему пользователю
    stmt = (select(ImportTask).where(ImportTask.employee_id == current_user.employee_id).order_by(ImportTask.created_at.desc()))
    result = await db.execute(stmt)
    task = result.scalars().first()

    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")

    # Проверяем, что задача НЕ в статусе failed
    if task.status == "failed":
        raise HTTPException(
            status_code=400,
            detail="Нельзя обновить данные задачи, которая завершилась с ошибкой (failed)"
        )

    # Обновляем только items_data в таблице import_tasks
    task.items_data = request.items
    await db.commit()

    return {
        "task_id": task.task_id,
        "message": "items_data успешно обновлены в задаче импорта",
        "updated_items_count": len(request.items) if request.items else 0
    }

@router_excel_import.post("/bulk-save")
async def bulk_save_assets(
        request_data: BulkSaveRequest,
        db: AsyncSession = Depends(get_db),
        current_user = Depends(require_authorized_user)
):
    results = []
    items = request_data.items

    for item_data in items:
        asset_id = item_data.get("asset_id")
        inv_id = item_data.get("inventory_id")
        sn = item_data.get("serial_number")
        material_id = item_data.get("material_id")
        item_asset_type_id = request_data.asset_type_id if request_data.asset_type_id else item_data.get("asset_type_id")

        try:
            clean_data = {k: v for k, v in item_data.items() if k not in ["excel_row_index", "status", "reason", "asset_type_id"]}

            if not asset_id:
                conditions = []
                if inv_id: conditions.append(Asset.inventory_id == inv_id)
                if sn: conditions.append(Asset.serial_number == sn)
                if material_id: conditions.append(Asset.material_id == material_id)

                if conditions:
                    stmt = select(Asset.asset_id).where(or_(*conditions))
                    result = await db.execute(stmt)
                    existing_asset_id = result.scalar_one_or_none()
                    if existing_asset_id:
                        asset_id = existing_asset_id

            if asset_id:
                update_schema = AssetUpdate(asset_type_id=item_asset_type_id, **clean_data)
                await update_asset(db, asset_id, update_schema, current_user.employee_id)
                results.append({"asset_id": asset_id, "status": "updated", "success": True})
            else:
                create_schema = AssetCreate(asset_type_id=item_asset_type_id, **clean_data)
                created_asset = await create_asset(db, create_schema, current_user.employee_id)
                results.append({"asset_id": created_asset.asset_id if created_asset else None, "status": "created", "success": True})
        except Exception as e:
            await db.rollback()
            logger.error(f"Ошибка при сохранении актива {item_data.get('inventory_id')}: {e}", exc_info=True)
            results.append({"asset_id": asset_id, "status": "error", "success": False, "reason": str(e)})

    success_count = sum(1 for r in results if r["success"])
    return {
        "total_processed": len(items), "success_count": success_count,
        "error_count": len(items) - success_count, "details": results
    }

@router_excel_import.get("/import-template")
async def get_import_template():
    columns = [
        "Инвентарный номер / Inventory number", "Тип и модель ПК / PC type and model",
        "Серийный номер / Serial Number", "Комментарий", "Дата выдачи / Issue Date",
        "Дата покупки / Purchasing Date", "Дата обслуживания / Service date",
        "Период обслуживания / Service period", "Период проверки / Check period"
    ]
    example_data = [{
        "Инвентарный номер / Inventory number": "0088", "Тип и модель ПК / PC type and model": "Ноутбук Dell Latitude 5520",
        "Серийный номер / Serial Number": "SN987654321", "Комментарий": "Выдан сотруднику отдела разработки",
        "Дата выдачи / Issue Date": "2023-10-01", "Дата покупки / Purchasing Date": "2023-09-15",
        "Дата обслуживания / Service date": "2024-10-01", "Период обслуживания / Service period": 365,
        "Период проверки / Check period": 30
    }]
    df = pd.DataFrame(example_data, columns=columns)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Шаблон импорта")

    return Response(
        content=output.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=asset_import_template_new.xlsx"}
    )