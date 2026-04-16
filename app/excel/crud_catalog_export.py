from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.AssetCatalog import AssetCatalog
from app.models.AssetClass import AssetClass
from app.models.AssetModel import AssetModel
from app.models.Asset import Asset
from app.models.User import User
from app.models.Warehouse import Warehouse
from app.models.Location import Location
from app.schemas.catalog.CatalogExportSchemas import CatalogExportRow


async def get_full_catalog_for_export(db: AsyncSession) -> List[CatalogExportRow]:
    """
    Получает полную информацию из таблицы asset_catalog со всеми связями для экспорта в Excel.
    Возвращает список объектов CatalogExportRow.
    """
    # Запрос с подгрузкой всех связанных данных
    query = (
        select(AssetCatalog)
        .options(
            # Подгружаем модель и класс через модель
            selectinload(AssetCatalog.model).selectinload(AssetModel.asset_class),
            # Подгружаем актив
            selectinload(AssetCatalog.asset),
            # Подгружаем владельца
            selectinload(AssetCatalog.owner),
            # Подгружаем создателя
            selectinload(AssetCatalog.creator),
            # Подгружаем склад и его локацию
            selectinload(AssetCatalog.warehouse).selectinload(Warehouse.location)
        )
        .order_by(AssetCatalog.catalog_id)
    )

    result = await db.execute(query)
    catalogs = result.scalars().all()

    export_rows = []

    for catalog in catalogs:
        # Извлекаем данные из связанных объектов
        model = catalog.model
        asset_class = model.asset_class if model else None
        asset = catalog.asset
        owner = catalog.owner
        creator = catalog.creator
        warehouse = catalog.warehouse
        location = warehouse.location if warehouse else None

        # Формируем строку экспорта
        row = CatalogExportRow(
            # ID каталога
            catalog_id=catalog.catalog_id,

            # Класс оборудования
            class_name=asset_class.class_name if asset_class else "",
            class_description=asset_class.description if asset_class else None,

            # Модель оборудования
            model_name=model.model_name if model else "",
            model_description=model.description if model else None,
            model_is_active=model.is_active if model else True,
            model_is_serial_required=model.is_serial_required if model else True,

            # Актив
            asset_inventory_id=asset.inventory_id if asset else "",
            asset_serial_number=asset.serial_number if asset else "",
            asset_name=asset.name if asset else "",
            asset_status=asset.asset_status if asset else "",
            asset_type_domain=asset.type_domain if asset else None,
            asset_affixed_inventory_id=asset.affixed_inventory_id if asset else None,
            asset_info_storage_location=asset.info_storage_location if asset else None,
            asset_passwork=asset.passwork if asset else None,
            asset_date_issue=asset.date_issue if asset else None,
            asset_date_purchasing=asset.date_purchasing if asset else None,
            asset_comment=asset.comment if asset else None,
            asset_source=asset.manufacturer_id if asset else None,
            asset_seller=asset.vendor_id if asset else None,
            asset_price=asset.price if asset else None,

            # Владелец
            owner_name=owner.owner if owner else None,
            owner_email=owner.email if owner else None,
            owner_department=owner.department if owner else None,

            # Склад
            warehouse_name=warehouse.name if warehouse else None,
            warehouse_location_city=location.city if location else None,
            warehouse_location_address=location.address if location else None,

            # Гарантия
            warranty_end_date=catalog.warranty_end_date,

            # Аудит
            created_at=catalog.created_at,
            created_by_name=creator.owner if creator else None,
            created_by_email=creator.email if creator else None,
        )

        export_rows.append(row)

    return export_rows