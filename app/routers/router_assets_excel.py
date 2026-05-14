from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
from datetime import datetime

from app.database.connection import get_db
from app.database.crud_assets_excel import import_assets_from_rows, get_full_assets_for_export
from app.service.excel.excel_service import create_asset_export_excel, create_asset_import_template, parse_asset_import_excel
from app.service.auth.auth_service import require_authorized_user

router_assets_excel = APIRouter(prefix="/assets/excel", tags=["Assets Excel"], dependencies=[Depends(require_authorized_user)])

@router_assets_excel.get("/export")
async def export_assets_to_excel(
        skip: int = 0,
        limit: int = 1000,
        db: AsyncSession = Depends(get_db)
):
    """Экспорт всех активов в Excel"""
    try:
        data = await get_full_assets_for_export(db, skip, limit)
        if not data:
            raise HTTPException(status_code=404, detail="Нет данных для экспорта")

        content = create_asset_export_excel(data)
        filename = f"assets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            io.BytesIO(content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router_assets_excel.get("/template")
async def download_template():
    """Скачать шаблон импорта активов с цветными категориями"""
    content = create_asset_import_template()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=assets_import_template.xlsx"}
    )

@router_assets_excel.post("/import")
async def import_assets_from_excel(
        file: UploadFile = File(...),
        current_user_id: int = 1, # Заглушка, брать из auth context
        db: AsyncSession = Depends(get_db)
):
    """Импорт активов из Excel"""
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Только Excel файлы")

    try:
        content = await file.read()
        rows = await parse_asset_import_excel(content)

        if not rows:
            raise HTTPException(status_code=400, detail="Файл пуст или неверный формат")

        results = await import_assets_from_rows(db, rows, current_user_id)
        return {"message": "Импорт завершен", "results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))