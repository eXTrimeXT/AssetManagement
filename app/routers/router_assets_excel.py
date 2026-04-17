# app/routers/router_assets_excel.py
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
import io
from datetime import datetime

from app.database.connection import get_db
from app.service.excel.asset_import_service import (
    create_asset_import_template,
    parse_asset_import_excel
)
from app.database.crud_assets_excel import (
    import_assets_from_rows
)

router_assets_excel = APIRouter(prefix="/assets/excel", tags=["Assets Excel"])

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