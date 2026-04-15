from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
import io

from app.excel.crud_catalog_export import get_full_catalog_for_export
from app.excel.export_service import create_catalog_excel_file

router_catalog_export = APIRouter(prefix="/catalog", tags=["Catalog Export"])


@router_catalog_export.get("/export/excel")
async def export_catalog_to_excel(db: AsyncSession = Depends(get_db)):
    """
    Экспортирует полный каталог активов в Excel файл.

    Файл содержит всю информацию из таблицы asset_catalog со всеми связями:
    - Информация о классе и модели оборудования
    - Полные данные об активе
    - Информация о владельце
    - Информация о складе и его локации
    - Данные о гарантии
    - Аудиторская информация

    Returns:
        StreamingResponse: Excel файл для скачивания
    """
    try:
        # Получаем данные из БД
        catalog_data = await get_full_catalog_for_export(db)

        if not catalog_data:
            raise HTTPException(
                status_code=404,
                detail="Каталог пуст. Нет данных для экспорта."
            )

        # Создаем Excel файл
        excel_content = create_catalog_excel_file(catalog_data)

        # Формируем имя файла с текущей датой
        from datetime import datetime
        filename = f"catalog_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        # Возвращаем файл
        return StreamingResponse(
            io.BytesIO(excel_content),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при экспорте каталога: {str(e)}"
        )