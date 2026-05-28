import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from starlette.responses import Response

from app.database.connection import get_db
from app.schemas.catalog.CatalogSchemas import AssetCatalogCreate, AssetCatalogResponse, AssetCatalogUpdate
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

@router_catalog_items.post("/", response_model=AssetCatalogResponse, status_code=status.HTTP_201_CREATED)
async def add_catalog_item(
        data: AssetCatalogCreate,
        current_user: User = Depends(require_authorized_user),
        db: AsyncSession = Depends(get_db)
):
    """
    Добавить запись в каталог.
    Требуется право `write` на тип актива модели, к которой привязан актив.
    """
    # 1. Получаем актив, который добавляем в каталог
    asset = await get_asset_by_id(db, data.asset_id)
    if not asset:
        logger.warning("Актив не найден")
        raise HTTPException(404, detail="Актив не найден")

    # 2. Получаем модель актива и извлекаем en_name типа
    asset_type_en_name = None
    if asset.model and asset.model.asset_class and asset.model.asset_class.asset_type:
        asset_type_en_name = asset.model.asset_class.asset_type.en_name

    # 3. Проверка права `write` на тип актива
    if asset_type_en_name and not has_write_permission(current_user, asset_type_en_name):
        logger.warning(f"Нет доступа на запись к типу '{asset_type_en_name}'")
        raise HTTPException(403, f"Нет доступа на запись к типу '{asset_type_en_name}'")

    # 4. Создаём запись в каталоге
    try:
        return await add_to_catalog(db, data, current_user_id=current_user.user_id)
    except ValueError as e:
        logger.error(f"Ошибка: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Ошибка: {str(e)}")


@router_catalog_items.get("/", response_model=List[AssetCatalogResponse])
async def list_catalog_items(
        items = Depends(FilteredByAccessWithParams(
            get_catalog_list,
            "asset.model.asset_class.asset_type.en_name",
            "read"
        ))
):
    """
    Получить список записей каталога.
    Возвращает только те, на которые у пользователя есть право `read`.
    """
    return items


@router_catalog_items.get("/{catalog_id}", response_model=AssetCatalogResponse)
async def get_catalog_item(
        catalog_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_authorized_user)
):
    """
    Получить запись каталога по ID.
    Возвращает 404 если нет права `read`.
    """
    item = await get_catalog_item_by_id(db, catalog_id)
    if not item:
        logger.warning("Запись каталога не найдена")
        raise HTTPException(404, detail="Запись каталога не найдена")

    # === Проверка права `read` на тип актива ===
    en_name = _get_catalog_asset_type_en_name(item)
    if not has_read_permission(current_user, en_name):
        logger.warning("Нет доступа для чтения")
        raise HTTPException(404, detail="Нет доступа для чтения")

    return item


@router_catalog_items.patch("/{catalog_id}", response_model=AssetCatalogResponse)
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

    res = await update_catalog_item(db, catalog_id, data, current_user_id=current_user.user_id)
    if not res:
        logger.error(f"Ошибка обновления")
        raise HTTPException(404, detail="Ошибка обновления")
    return res


@router_catalog_items.delete("/{catalog_id}", status_code=status.HTTP_204_NO_CONTENT)
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

    success = await delete_catalog_item(db, catalog_id, current_user.user_id)
    if not success:
        logger.error("Ошибка удаления")
        raise HTTPException(status_code=404, detail="Ошибка удаления")

    return Response(status_code=status.HTTP_204_NO_CONTENT)