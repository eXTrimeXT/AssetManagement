import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from starlette.responses import Response

from app.database.connection import get_db
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogResponse, AssetCatalogUpdate, \
    AssetCatalogShortResponse
from app.database.crud_catalog import (
    add_to_catalog, get_catalog_list, get_catalog_item_by_id,
    delete_catalog_item, update_catalog_item,
)
from app.service.auth.auth_service import require_authorized_user
from app.service.permissions.permissions_rules import FilteredByAccessWithParams, has_write_permission, has_read_permission
from app.models.User import User
from app.database.crud_assets import get_asset_by_id

logger = logging.getLogger(__name__)

router_catalog_items = APIRouter(
    prefix="/catalog/items",
    tags=["Asset Catalog Items"],
    dependencies=[Depends(require_authorized_user)]
)


# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def _get_asset_type_en_name(item) -> str | None:
    """Безопасно извлекает en_name типа актива из записи каталога"""
    try:
        if (item.model
                and item.model.asset_class
                and item.model.asset_class.asset_type):
            return item.model.asset_class.asset_type.en_name
    except AttributeError:
        pass
    return None

def _get_catalog_asset_type_en_name(item) -> str | None:
    """Безопасно извлекает en_name типа актива из записи каталога.
    Путь: AssetCatalog → asset → model → asset_class → asset_type
    """
    try:
        if (item.asset
                and item.asset.model
                and item.asset.model.asset_class
                and item.asset.model.asset_class.asset_type):
            return item.asset.model.asset_class.asset_type.en_name
    except AttributeError:
        pass
    return None

# === ЭНДПОИНТЫ ===

@router_catalog_items.post("/", response_model=AssetCatalogResponse, status_code=200)
async def add_catalog_item(
        data: AssetCatalogCreate,
        current_user: User = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Добавить запись в каталог.
    Требуется право `write` на тип актива модели, к которой привязан актив.
    Если указан только serial_number (без asset_id) — проверка прав пропускается.
    """
    # 1. Проверка: должен быть указан хотя бы один идентификатор
    if not data.asset_id and not data.serial_number:
        logger.warning("Не указан ни asset_id, ни serial_number")
        raise HTTPException(400, detail="Необходимо указать asset_id или serial_number")

    # 2. Если указан asset_id — проверяем права на запись по типу актива
    try:
        if data.asset_id:

            asset = await get_asset_by_id(db, data.asset_id)
            if not asset:
                logger.warning("Актив не найден")
                raise HTTPException(404, detail="Актив не найден")

            asset_type_en_name = None
            if asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
                asset_type_en_name = asset.model.asset_class.asset_type.en_name

            if asset_type_en_name and not has_write_permission(current_user, asset_type_en_name):
                logger.warning(f"Нет доступа на запись к типу '{asset_type_en_name}'")
                raise HTTPException(403, f"Нет доступа на запись к типу '{asset_type_en_name}'")

    # 3. Создаём запись в каталоге (crud сам проверит существование asset/android)
    # try:
        data.created_by = current_user.user_tab_id
        return await add_to_catalog(db, data, current_user_tab_id=current_user.user_tab_id)
    except ValueError as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка: {str(e)}")
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=503, detail=f"Ошибка: {str(e)}")

@router_catalog_items.get("/search", response_model=List[AssetCatalogShortResponse])
async def search_catalog_items_endpoint(
        skip: int = Query(0, ge=0),
        limit: int = Query(50, ge=1, le=100),
        catalog_id: Optional[int] = Query(None),
        asset_id: Optional[int] = Query(None),
        asset_name: Optional[str] = Query(None),
        user_tab_id: Optional[str] = Query(None),
        # user_id: Optional[int] = Query(None),
        creator_tab_id: Optional[str] = Query(None),
        creator_id: Optional[int] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_authorized_user)
):
    """
    Поиск записей каталога по множеству опциональных параметров.
    Все параметры комбинируются через AND.
    Возвращает только те, на которые у пользователя есть право `read`.
    """
    items = await get_catalog_list(
        db=db,
        skip=skip,
        limit=limit,
        catalog_id=catalog_id,
        asset_id=asset_id,
        asset_name=asset_name,
        user_tab_id=user_tab_id,
        # user_id=user_id,
        creator_tab_id=creator_tab_id,
        creator_id=creator_id
    )

    # === Фильтрация по правам доступа ===
    filtered_items = []
    for item in items:
        en_name = _get_catalog_asset_type_en_name(item)
        if has_read_permission(current_user, en_name):
            filtered_items.append(item)

    return filtered_items

@router_catalog_items.patch("/{catalog_id}", response_model=AssetCatalogResponse, status_code=200)
async def patch_catalog_item(
        catalog_id: int,
        data: AssetCatalogUpdate,
        current_user: User = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Обновить запись каталога.
    Требуется право `write` на тип актива модели.
    """
    item = await get_catalog_item_by_id(db, catalog_id)
    if not item:
        logger.warning("Запись каталога не найдена")
        raise HTTPException(404, detail="Запись каталога не найдена")

    en_name = _get_asset_type_en_name(item)
    if not has_write_permission(current_user, en_name):
        logger.warning(f"Нет доступа на запись к типу '{en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{en_name}'")

    res = await update_catalog_item(db, catalog_id, data, current_user_tab_id=current_user.user_tab_id)
    if not res:
        logger.error(f"Ошибка обновления")
        raise HTTPException(404, detail="Ошибка обновления")
    return res


@router_catalog_items.delete("/{catalog_id}", status_code=200)
async def delete_catalog_item_endpoint(
        catalog_id: int,
        current_user: User = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Удалить запись каталога.
    Требуется право `write` на тип актива модели.
    """
    item = await get_catalog_item_by_id(db, catalog_id)
    if not item:
        logger.warning("Запись каталога не найдена")
        raise HTTPException(404, detail="Запись каталога не найдена")

    en_name = _get_catalog_asset_type_en_name(item)
    if not has_write_permission(current_user, en_name):
        logger.warning(f"Нет доступа на запись к типу '{en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{en_name}'")

    success = await delete_catalog_item(db, catalog_id, current_user.user_tab_id)
    if not success:
        logger.error("Ошибка удаления")
        raise HTTPException(status_code=404, detail="Ошибка удаления")

    return Response(status_code=200)


# curl 'http://10.168.143.7:8800/api/assets/11' \
#      -X 'PATCH' \
#         -H 'Accept: application/json' \
#            -H 'Accept-Language: ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7' \
#               -H 'Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOjE3ODI4ODUyNTAsImV4cCI6MTc4MjkyODQ1MCwibG9naW4iOiJndzA3MDE1MzcwIiwibGFzdF9pcCI6IjEwLjE2OC4xNTQuNDIiLCJsYXN0X3RpbWUiOiIwNTozMjozOCAwMS4wNy4yMDI2IiwiZGVwYXJ0bWVudCI6bnVsbCwicGVybWlzc2lvbnMiOlt7Im5hbWVfZ3JvdXAiOiJjb21wdXRlciIsInJlYWQiOmZhbHNlLCJ3cml0ZSI6ZmFsc2V9LHsibmFtZV9ncm91cCI6Im1lc19lcXVpcG1lbnQiLCJyZWFkIjpmYWxzZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InN1cHBsaWVzIiwicmVhZCI6dHJ1ZSwid3JpdGUiOmZhbHNlfSx7Im5hbWVfZ3JvdXAiOiJwb3dlcl9hZGFwdGVyIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6ImRhdGFfY29sbGVjdGlvbl9lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoiQWNjZXNzb3JpZXMiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoibmV0d29ya19lcXVpcG1lbnQiLCJyZWFkIjp0cnVlLCJ3cml0ZSI6dHJ1ZX0seyJuYW1lX2dyb3VwIjoicHJpbnRpbmdfZXF1aXBtZW50IiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6InNlcnZlcl9oYXJkd2FyZSIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJ1c2VycyIsInJlYWQiOnRydWUsIndyaXRlIjp0cnVlfSx7Im5hbWVfZ3JvdXAiOiJ1c2Vyc01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9LHsibmFtZV9ncm91cCI6IkFzc2V0c01VIiwicmVhZCI6dHJ1ZSwid3JpdGUiOnRydWV9XSwiYXNzZXRzX2FkbWluIjp0cnVlLCJ1c2VyX2RhdGEiOnsiZW1haWwiOiJUaW11ci5NYWx5c2hldkBobW1yLnJ1IiwiZnVsbG5hbWUiOiJUaW11ciBNYWx5c2hldiIsImRlcGFydG1lbnQiOiJTREciLCJkaXN0aW5ndWlzaGVkTmFtZSI6IkNOPVRpbXVyIE1hbHlzaGV2LE9VPVNPRlRXQVJFIERFVkVMT1BNRU5UIEdST1VQIChTREcpLE9VPUlORk9STUFUSU9OIFNZU1RFTVMgU1VQUE9SVCBTRUNUSU9OIChJU1NTKSxPVT1SdXNzaWFuIERpZ2l0YWwgQ2VudGVyIChSREMpLE9VPVVzZXJzLE9VPUhNTVIsREM9bG9jYWwsREM9aG1tcixEQz1ydSIsImdyb3VwcyI6W119fQ.9eh_hEer6OWrl4CkHB-VGCMyoVmBDoHg-SGDEKuGCOw' \
#                  -H 'Connection: keep-alive' \
#                     -H 'Content-Type: application/json' \
#                        -H 'DNT: 1' \
#                           -H 'Origin: http://gps-test.hmmr.ru' \
#                              -H 'Referer: http://gps-test.hmmr.ru/' \
#                                 -H 'User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36' \
#                                    --data-raw '{"asset_id":11,"name":"Каска желтая","inventory_id":"110000004681","serial_number":null,"asset_status":"Приемка","comment":"описание желтой каски55","model_id":null,"model_name":null,"class_id":null,"class_name":null,"asset_type_id":null,"type_asset_en_name":null,"type_asset_name":null,"warehouse_id":null,"warehouse_name":null,"parent_id":null,"parent_name":null,"software_id":null,"software_office_type":null,"manufacturer_id":null,"manufacturer_name":null,"vendor_id":1,"vendor_name":"Производитель названий","users":[{"user_id":21,"user_tab_id":null,"owner":"test comment","user_position":null,"comment":"3456365","department_id":null,"division_id":null,"group_id":null,"email":null,"selected":true},{"user_id":4,"user_tab_id":"gw07015370","owner":"Timur Malyshev","user_position":null,"comment":"test534654","department_id":3,"division_id":9,"group_id":13,"email":"Timur.Malyshev@hmmr.ru","selected":true}]}' \
#                                               --insecure