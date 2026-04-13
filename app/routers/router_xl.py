import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Импорт модели актива из слоя данных
from app.models.Asset import Asset
from app.database.connection import get_db
from app.schemas.assets.AssetCreate import AssetCreate
from app.services.excel.excel import create_template, parse_excel_assets, export_assets_to_excel

# Создаем роутер с префиксом /xl и тегом для группировки в Swagger UI
router_xl = APIRouter(prefix="/xl", tags=["xl"])

@router_xl.get("/template")
async def download_template():
    """Скачать Excel-шаблон для импорта активов."""
    content = create_template()
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=assets_template.xlsx"}
    )


@router_xl.post("/import")
async def import_assets(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    """
    Импорт активов из Excel.
    Возвращает: { "imported": N, "errors": [...], "details": [...] }
    """
    if not file.filename.endswith(('.xlsx', '.xls')):
        raise HTTPException(status_code=400, detail="Только файлы Excel (.xlsx)")

    content = await file.read()
    assets_data, parse_errors = parse_excel_assets(content)

    imported = []
    import_errors = []

    for data in assets_data:
        try:
            # Преобразуем в схему для валидации
            asset_in = AssetCreate(**data)
            db_asset = Asset(**asset_in.model_dump())
            db.add(db_asset)
            await db.commit()
            await db.refresh(db_asset)
            imported.append({"inv_id": asset_in.inv_id, "id": db_asset.asset_id})
        except Exception as e:
            await db.rollback()
            import_errors.append(f"{data.get('inv_id')}: {str(e)}")

    return {
        "imported_count": len(imported),
        "imported": imported,
        "parse_errors": parse_errors,
        "import_errors": import_errors,
        "total_processed": len(assets_data)
    }


@router_xl.get("/export")
async def export_assets(
        include_deleted: bool = False,
        db: AsyncSession = Depends(get_db)
):
    """
    Экспорт всех активов в Excel с точными именами полей из БД.
    """
    # Формируем запрос
    query = select(Asset)
    if not include_deleted:
        query = query.where(Asset.deleted_at.is_(None))

    result = await db.execute(query)
    assets = result.scalars().all()

    # Конвертируем в словари с ТОЧНЫМИ именами полей из БД
    assets_data = []
    for asset in assets:
        asset_dict = {
            "id": asset.asset_id,
            "caption": asset.caption,
            "description": asset.description,
            "inv_id": asset.inv_id,
            "serial_id": asset.serial_id,
            "status": asset.status.value if hasattr(asset.status, 'value') else asset.status,
            "user_info": asset.user_info,
            "seller": asset.seller,
            "price": float(asset.price) if asset.price else None,
            "staff": asset.staff,
            "department": asset.department,
            "fact_location": asset.fact_location,
            "source": asset.source,
            "prepared_by": asset.prepared_by,
            "checked_by": asset.checked_by,
            "type_id": asset.type_id,
            "parent_id": asset.parent_id,
            "delivery_date": asset.delivery_date,
            "deleted_at": asset.deleted_at,
        }
        assets_data.append(asset_dict)

    # Генерируем Excel
    excel_file = export_assets_to_excel(assets_data)

    filename = f"assets_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_file),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
