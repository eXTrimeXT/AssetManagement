from typing import List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from datetime import date, datetime

from app.models.Asset import Asset
from app.models.AssetType import AssetType
from app.models.Location import Location
from app.models.Vendor import Vendor
from app.models.Software import Software
from app.models.User import User


async def get_full_assets_for_export(db: AsyncSession, skip: int = 0, limit: int = 1000) -> List[Dict[str, Any]]:
    """
    Получает полные данные активов для экспорта.
    Загружает все связи, чтобы превратить ID в названия (как в AssetExcelRow).
    """
    query = (
        select(Asset)
        .options(
            selectinload(Asset.asset_type),
            selectinload(Asset.location_obj),
            selectinload(Asset.preparer),
            selectinload(Asset.checker),
            selectinload(Asset.software),
            selectinload(Asset.manufacturer),
            selectinload(Asset.vendor),
            selectinload(Asset.parent) # Для получения инвентарного номера родителя
        )
        .offset(skip)
        .limit(limit)
    )

    result = await db.execute(query)
    assets = result.scalars().all()

    export_data = []
    for asset in assets:
        loc = asset.location_obj
        prep = asset.preparer
        check = asset.checker
        soft = asset.software
        manuf = asset.manufacturer
        vend = asset.vendor
        parent = asset.parent

        row = {
            # Основная информация
            "inventory_id": asset.inventory_id,
            "serial_number": asset.serial_number,
            "name": asset.name,
            "asset_type_name": asset.asset_type.name if asset.asset_type else "",
            "asset_status": asset.asset_status,

            # Локация
            "location_country": loc.country if loc else "",
            "location_city": loc.city if loc else "",
            "location_address": loc.address if loc else "",
            "location_room": loc.room if loc else "",
            "location_floor": loc.floor if loc else "",

            # Детали
            "type_domain": asset.type_domain or "",
            # "passwork": asset.passwork or "",
            "date_issue": asset.date_issue,
            "date_purchasing": asset.date_purchasing,
            "price": asset.price,
            "comment": asset.comment or "",
            "affixed_inventory_id": asset.affixed_inventory_id,

            # Вендоры
            "manufacturer_name": manuf.name if manuf else "",
            "vendor_name": vend.name if vend else "",

            # Пользователи
            "prepared_by_name": prep.owner if prep else "",
            "checked_by_name": check.owner if check else "",

            # ПО и Комплектация
            "software_os_type": soft.os_type if soft else "",
            "parent_inventory_id": parent.inventory_id if parent else "",
        }
        export_data.append(row)

    return export_data


def _parse_date(val: Any) -> date | None:
    """
    Безопасный парсер даты из Excel/Pandas.
    Преобразует строки 'YYYY-MM-DD', pandas Timestamp и datetime в объект date.
    """
    if val is None or (isinstance(val, float) and str(val) == 'nan'):
        return None

    if isinstance(val, date):
        # Если это уже date (или datetime, который наследуется от date), возвращаем как есть
        # Но если это datetime, лучше обрезать время, так как в БД тип Date
        if isinstance(val, datetime):
            return val.date()
        return val

    if isinstance(val, str):
        try:
            # Пробуем стандартный формат ISO
            return date.fromisoformat(val)
        except ValueError:
            pass
        try:
            # Пробуем формат Excel (иногда бывает DD.MM.YYYY)
            return datetime.strptime(val, "%d.%m.%Y").date()
        except ValueError:
            pass

    # Если ничего не подошло, возвращаем None
    return None


async def import_assets_from_rows(
        db: AsyncSession,
        import_rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Импортирует активы из строк Excel.
    """
    results = {"success": 0, "errors": [], "total": len(import_rows)}

    for idx, row_data in enumerate(import_rows):
        try:
            inv_id = row_data['inventory_id']

            # 1. Поиск существующего актива
            asset_obj = await db.execute(
                select(Asset).where(Asset.inventory_id == inv_id)
            )
            asset_obj = asset_obj.scalar_one_or_none()

            # 2. Поиск Типа Актива (Обязательно)
            type_name = row_data.get('asset_type_name')
            type_obj = None
            if type_name:
                t_res = await db.execute(select(AssetType).where(AssetType.name == str(type_name)))
                type_obj = t_res.scalar_one_or_none()
                if not type_obj:
                    raise ValueError(f"Тип актива '{type_name}' не найден в справочнике.")

            # 3. Поиск Локации
            loc_obj = None
            city = row_data.get('location_city')
            address = row_data.get('location_address')

            # Создаем локацию, если есть город и адрес
            if city and address:
                l_res = await db.execute(
                    select(Location).where(
                        Location.city == str(city),
                        Location.address == str(address)
                    )
                )
                loc_obj = l_res.scalar_one_or_none()

                if not loc_obj:
                    new_loc = Location(
                        country=str(row_data.get('location_country', '')),
                        city=str(city),
                        address=str(address),
                        room=str(row_data.get('location_room', '')),
                        floor=str(row_data.get('location_floor', ''))
                    )
                    db.add(new_loc)
                    await db.flush() # Получаем ID новой локации
                    loc_obj = new_loc

            # 4. Поиск Вендоров (Производитель / Поставщик)
            manuf_id = None
            manuf_name = row_data.get('manufacturer_name')
            if manuf_name:
                m_res = await db.execute(select(Vendor).where(Vendor.name == str(manuf_name)))
                m_obj = m_res.scalar_one_or_none()
                if m_obj: manuf_id = m_obj.vendor_id

            vend_id = None
            vend_name = row_data.get('vendor_name')
            if vend_name:
                v_res = await db.execute(select(Vendor).where(Vendor.name == str(vend_name)))
                v_obj = v_res.scalar_one_or_none()
                if v_obj: vend_id = v_obj.vendor_id

            # 5. Поиск ПО (по типу ОС)
            soft_id = None
            os_type = row_data.get('software_os_type')
            if os_type:
                s_res = await db.execute(select(Software).where(Software.os_type == str(os_type)))
                s_obj = s_res.scalar_one_or_none()
                if s_obj: soft_id = s_obj.software_id

            # 6. Поиск Пользователей (Подготовил / Проверил)
            prep_id = None
            prep_name = row_data.get('prepared_by_name')
            if prep_name:
                u_res = await db.execute(select(User).where(User.owner == str(prep_name)))
                u_obj = u_res.scalar_one_or_none()
                if u_obj: prep_id = u_obj.user_id

            check_id = None
            check_name = row_data.get('checked_by_name')
            if check_name:
                u_res = await db.execute(select(User).where(User.owner == str(check_name)))
                u_obj = u_res.scalar_one_or_none()
                if u_obj: check_id = u_obj.user_id

            # 7. Поиск Родителя (по инвентарному номеру)
            parent_id = None
            parent_inv = row_data.get('parent_inventory_id')
            if parent_inv:
                p_res = await db.execute(select(Asset).where(Asset.inventory_id == str(parent_inv)))
                p_obj = p_res.scalar_one_or_none()
                if p_obj: parent_id = p_obj.asset_id

            # Парсинг дат через нашу безопасную функцию
            date_issue_val = _parse_date(row_data.get('date_issue'))
            date_purchasing_val = _parse_date(row_data.get('date_purchasing'))

            # 8. Создание или Обновление
            if asset_obj:
                # --- ОБНОВЛЕНИЕ СУЩЕСТВУЮЩЕГО АКТИВА ---
                asset_obj.name = row_data.get('name', asset_obj.name)
                asset_obj.serial_number = row_data.get('serial_number', asset_obj.serial_number)
                if type_obj: asset_obj.asset_type_id = type_obj.asset_type_id
                asset_obj.asset_status = row_data.get('asset_status', asset_obj.asset_status)
                if loc_obj: asset_obj.location_id = loc_obj.location_id

                asset_obj.type_domain = row_data.get('type_domain')
                # asset_obj.passwork = row_data.get('passwork')

                # Присваиваем распарсенные даты
                asset_obj.date_issue = date_issue_val
                asset_obj.date_purchasing = date_purchasing_val

                asset_obj.price = row_data.get('price')
                asset_obj.comment = row_data.get('comment')
                asset_obj.affixed_inventory_id = row_data.get('affixed_inventory_id', False)

                asset_obj.manufacturer_id = manuf_id
                asset_obj.vendor_id = vend_id
                asset_obj.software_id = soft_id

                # ВАЖНО: Пишем ID в колонки prepared_by и checked_by
                asset_obj.prepared_by = prep_id
                asset_obj.checked_by = check_id

                asset_obj.parent_id = parent_id

            else:
                # --- СОЗДАНИЕ НОВОГО АКТИВА ---
                if not type_obj:
                    raise ValueError("Тип актива обязателен для создания нового актива.")

                new_asset = Asset(
                    inventory_id=inv_id,
                    serial_number=row_data['serial_number'],
                    name=row_data['name'],
                    asset_type_id=type_obj.asset_type_id,
                    asset_status=row_data.get('asset_status', 'Приемка'),
                    location_id=loc_obj.location_id if loc_obj else None,
                    type_domain=row_data.get('type_domain'),
                    # passwork=row_data.get('passwork'),

                    # Используем распарсенные даты
                    date_issue=date_issue_val,
                    date_purchasing=date_purchasing_val,

                    price=row_data.get('price'),
                    comment=row_data.get('comment'),
                    affixed_inventory_id=row_data.get('affixed_inventory_id', False),
                    manufacturer_id=manuf_id,
                    vendor_id=vend_id,
                    software_id=soft_id,
                    parent_id=parent_id,

                    # ВАЖНО: Заполняем КОЛОНКИ prepared_by и checked_by ID пользователей
                    prepared_by=prep_id,
                    checked_by=check_id,

                    # created_at и updated_at заполняются автоматически default=datetime.now в модели
                )
                db.add(new_asset)

            results["success"] += 1

        except Exception as e:
            results["errors"].append({
                "row": idx + 2, # +2 т.к. первая строка заголовок, индекс с 0
                "inventory_id": row_data.get('inventory_id', 'N/A'),
                "error": str(e)
            })

    await db.commit()
    return results