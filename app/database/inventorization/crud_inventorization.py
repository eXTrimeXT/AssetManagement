import io
from datetime import datetime, timezone, timedelta
from typing import Optional, Sequence, Tuple

import logging

from openpyxl import Workbook
from sqlalchemy import select, update, distinct, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from fastapi.responses import StreamingResponse

from app.scheduler.scheduler import scheduler
from apscheduler.triggers.date import DateTrigger
from app.scheduler.jobs.check_start_and_finish_inventorization import (
    start_inventory_session_job,
    complete_inventory_session_job
)

from app.models.inventorization.Inventorization import InventorizationSession, InventorizationItem
from app.models.assets.Asset import Asset
from app.models.assets.AssetType import AssetType
from app.models.assets.AssetAssignment import AssetAssignment
from app.database.crud_notifications import notify_inventory_started, notify_inventory_completed
from app.services.assets.asset_list_service import fetch_sap_materials, WITHOUT_TYPE_ASSET_ID
from app.models.inventorization.Inventorization import InventorizationStatus

logger = logging.getLogger(__name__)

def determine_inventory_status(start_date: Optional[datetime], end_date: Optional[datetime]) -> str:
    """
    Определяет актуальный статус сессии на основе дат.
    Использует локальный часовой пояс для корректного сравнения.
    """
    # Получаем текущее время
    now = datetime.now()

    # Если дата окончания уже наступила или прошла, сессия завершена
    if end_date and end_date <= now:
        return InventorizationStatus.COMPLETED

    # Если дата начала уже наступила или прошла, сессия в работе
    if start_date and start_date <= now:
        return InventorizationStatus.IN_PROGRESS

    # Иначе она в ожидании
    return InventorizationStatus.PENDING
async def get_inventory_session_by_id(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
    result = await db.execute(
        select(InventorizationSession)
        .options(selectinload(InventorizationSession.items))
        .where(InventorizationSession.session_id == session_id)
    )
    return result.scalar_one_or_none()

async def get_inventory_sessions_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[
    InventorizationSession]:
    query = select(InventorizationSession).options(
        # selectinload(InventorizationSession.items)
        # .selectinload(InventorizationSession.creator)
    ).offset(skip).limit(limit).order_by(InventorizationSession.session_id.desc())
    result = await db.execute(query)
    return result.scalars().all()

async def get_inventory_items_by_session_id(
        db: AsyncSession,
        session_id: int,
        page: int = 1,
        page_size: int = 50
) -> Tuple[Sequence[InventorizationItem], int]:
    """Получить элементы сессии инвентаризации с пагинацией. Возвращает (items, total_count)"""

    # Получаем общее количество записей для этой сессии
    count_query = select(func.count(InventorizationItem.inventorization_id)).where(
        InventorizationItem.session_id == session_id
    )
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Получаем пагинированный список элементов
    offset = (page - 1) * page_size
    items_query = (
        select(InventorizationItem)
        .where(InventorizationItem.session_id == session_id)
        .options(
            # === ДОБАВЛЕНО: Явная загрузка данных сотрудника ===
            selectinload(InventorizationItem.checked_employee)
        )
        .order_by(InventorizationItem.inventorization_id) # Добавляем порядок для стабильной пагинации
        .offset(offset)
        .limit(page_size)
    )
    items_result = await db.execute(items_query)
    items = items_result.scalars().all()

    return items, total

async def create_inventory_session(
        db: AsyncSession,
        asset_type_id: Optional[int] = None,
        department_code: Optional[str] = None,
        creator_employee_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
) -> InventorizationSession:

    # ==============================================================================
    # ЗАЩИТНАЯ ПРОВЕРКА: Нормализуем часовые пояса перед любыми сравнениями
    # Если фронтенд прислал дату без 'Z' (naive), принудительно делаем её UTC (aware)
    # ==============================================================================
    # if start_date and start_date.tzinfo is None:
    #     start_date = start_date.replace(tzinfo=timezone.utc)
    # if end_date and end_date.tzinfo is None:
    #     end_date = end_date.replace(tzinfo=timezone.utc)

    logger.warning(f"{asset_type_id=} {department_code=}")
    if asset_type_id is None and department_code is None:
        raise ValueError("Необходимо указать либо asset_type_id, либо department_codes")

    if department_code is not None:
        asset_type_name = f"По департаментам: {department_code.replace('; ', ', ').replace(';', ',')}"
        asset_type_en_name = "by_departments"

    if asset_type_id is not None:
        asset_type_result = await db.execute(
            select(AssetType).where(AssetType.asset_type_id == asset_type_id)
        )
        asset_type = asset_type_result.scalar_one_or_none()
        if not asset_type:
            raise ValueError(f"Тип актива с id {asset_type_id} не найден")
        asset_type_name = asset_type.name
        asset_type_en_name = asset_type.en_name

    # === ГЛАВНОЕ ИЗМЕНЕНИЕ: Вычисляем статус ПЕРЕД созданием объекта ===
    initial_status = determine_inventory_status(start_date, end_date)

    session = InventorizationSession(
        asset_type_id=asset_type_id,
        department_codes=department_code,
        asset_type_name=asset_type_name,
        asset_type_en_name=asset_type_en_name,
        status=initial_status,
        created_by=creator_employee_id,
        start_date=start_date,
        end_date=end_date
    )
    db.add(session)
    await db.flush()

    # ==============================================================================
    # 1. Локальные активы
    # ==============================================================================
    query = select(Asset)
    conditions = []

    if asset_type_id is not None:
        conditions.append(Asset.asset_type_id == asset_type_id)

    if department_code:
        codes_list = [code.strip().upper() for code in department_code.split(',') if code.strip()]
        if codes_list:
            conditions.append(Asset.cost_center_code_from.in_(codes_list))

    if conditions:
        query = query.where(*conditions)
    else:
        query = query.where(False)

    result = await db.execute(query)
    assets = result.scalars().all()

    items = [
        InventorizationItem(
            session_id=session.session_id,
            asset_id=asset.asset_id,
            material_id=asset.material_id,
            asset_name=asset.name,
            is_checked=False,
            serial_number=asset.serial_number,
            inventory_id=asset.inventory_id,
            quantity=asset.quantity,
            quantity_fact=None,
        )
        for asset in assets
    ]

    if items:
        db.add_all(items)
        await db.flush()

    # ==============================================================================
    # 2. ЗАПРОС SAP-АКТИВОВ (С ПАГИНАЦИЕЙ)
    # ==============================================================================
    should_fetch_sap = False
    sap_cost_center_code_from = None

    if department_code:
        should_fetch_sap = True
        sap_cost_center_code_from = department_code.replace(',', ';')

    if asset_type_id == WITHOUT_TYPE_ASSET_ID:
        should_fetch_sap = True

    if should_fetch_sap:
        try:
            all_sap_items = []
            offset = 0
            limit = 1000
            total_sap_items = float('inf')  # Инициализируем бесконечностью для входа в цикл

            logger.info(f"[SAP INVENTORY] Начинаем пагинацию запроса SAP активов. department_code={department_code}")

            while offset < total_sap_items:
                sap_response = await fetch_sap_materials(
                    offset=offset,
                    page_size=limit,
                    material_id=None,
                    search_mode="ALL",
                    base_material_name_like=None,
                    inventory_number=None,
                    serial_number=None,
                    employee_id=None,
                    cost_center_code_from=sap_cost_center_code_from,
                    cost_center_code_from_search_mode="ALL",
                    cost_center_shortname_from=None,
                    cost_center_code=None,
                    cost_center_shortname=None
                )

                if not sap_response.get("success") or "response" not in sap_response:
                    logger.warning("[SAP INVENTORY] SAP API вернул неуспешный ответ. Останавливаем пагинацию.")
                    break

                response_data = sap_response["response"]
                current_batch = response_data.get("data", [])
                total_sap_items = response_data.get("total", 0)

                all_sap_items.extend(current_batch)
                offset += limit

                logger.info(f"[SAP INVENTORY] Загружено {len(current_batch)} элементов. Всего получено: {len(all_sap_items)} / {total_sap_items}")

                # Если текущая пачка меньше лимита, значит мы дошли до конца данных
                if len(current_batch) < limit:
                    break

            # Фильтрация дубликатов и создание элементов инвентаризации
            if all_sap_items:
                local_inv_ids = {asset.inventory_id.strip().lower() for asset in assets if asset.inventory_id}
                local_mat_ids = {asset.material_id.strip().lower() for asset in assets if asset.material_id}

                sap_items_to_add = []
                for sap_item in all_sap_items:
                    inv_num = str(sap_item.get("inventory_number", "")).strip().lower()
                    mat_id = str(sap_item.get("material_id", "")).strip().lower()

                    # Пропускаем, если уже есть в локальных
                    if inv_num and inv_num in local_inv_ids:
                        continue
                    if mat_id and mat_id in local_mat_ids:
                        continue

                    sap_items_to_add.append(
                        InventorizationItem(
                            session_id=session.session_id,
                            asset_id=None,  # Виртуальный актив
                            material_id=sap_item.get("material_id"),
                            asset_name=sap_item.get("base_material_name"),
                            is_checked=False,
                            serial_number=sap_item.get("serial_number"),
                            inventory_id=sap_item.get("inventory_number"),
                            quantity=int(sap_item.get("quantity", 1)) if sap_item.get("quantity") else 1,
                            quantity_fact=None,
                        )
                    )

                if sap_items_to_add:
                    db.add_all(sap_items_to_add)
                    items.extend(sap_items_to_add)
                    await db.flush()
                    logger.info(f"[SAP INVENTORY] Добавлено {len(sap_items_to_add)} уникальных виртуальных SAP-активов в сессию (из {len(all_sap_items)} полученных).")
            else:
                logger.info("[SAP INVENTORY] SAP не вернул данных для добавления в инвентаризацию.")

        except Exception as e:
            logger.error(f"[SAP INVENTORY] Ошибка при запросе SAP-активов для инвентаризации: {e}", exc_info=True)

    # ==============================================================================
    # 3. ЛОГИКА УВЕДОМЛЕНИЙ
    # ==============================================================================
    asset_ids = [item.asset_id for item in items if item.asset_id is not None]  # Только локальные ID

    # ОТПРАВЛЯЕМ УВЕДОМЛЕНИЯ ТОЛЬКО ЕСЛИ СЕССИЯ СРАЗУ НАЧИНАЕТСЯ (IN_PROGRESS)
    # Если она создана как PENDING, уведомления отправит планировщик в момент старта
    if asset_ids and initial_status == InventorizationStatus.IN_PROGRESS:
        employees_result = await db.execute(
            select(distinct(AssetAssignment.employee_id)).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.end_date.is_(None)  # Только активные назначения
            )
        )
        responsible_employees = [row[0] for row in employees_result.all()]
        for emp_id in responsible_employees:
            await notify_inventory_started(
                db=db,
                employee_id=emp_id,
                session_id=session.session_id,
                initiator_id=creator_employee_id,
            )

    # ==============================================================================
    # 3. ПЛАНИРОВАНИЕ ЗАДАЧ В APSCHEDULER
    # ==============================================================================
    now = datetime.now()

    # Планируем задачу запуска, если start_date в будущем и сессия еще не запущена
    if start_date and start_date > now and initial_status == InventorizationStatus.PENDING:
        job_id_start = f"inventory_start_{session.session_id}"
        scheduler.add_job(
            start_inventory_session_job,
            trigger=DateTrigger(run_date=start_date),
            args=[session.session_id],
            id=job_id_start,
            replace_existing=True,
            name=f"Start inventory session {session.session_id}"
        )
        logger.info(f"[INVENTORY SCHEDULER] Запланирована задача запуска сессии {session.session_id} на {start_date}")

    # Планируем задачу завершения, если end_date в будущем
    if end_date and end_date > now:
        job_id_end = f"inventory_end_{session.session_id}"
        scheduler.add_job(
            complete_inventory_session_job,
            trigger=DateTrigger(run_date=end_date),
            args=[session.session_id],
            id=job_id_end,
            replace_existing=True,
            name=f"Complete inventory session {session.session_id}"
        )
        logger.info(f"[INVENTORY SCHEDULER] Запланирована задача завершения сессии {session.session_id} на {end_date}")

    await db.commit()
    await db.refresh(session)
    return session

async def check_inventory_item(
        db: AsyncSession,
        session_id: int,
        asset_id: Optional[int] = None,
        material_id: Optional[str] = None,
        checked_by: str = None, # Сделал без дефолта, так как он обязателен из роутера
        quantity_fact: Optional[int] = None,
) -> bool:
    # === ПРОВЕРКА: quantity_fact не может быть меньше 0 ===
    if quantity_fact is not None and quantity_fact < 0:
        raise ValueError("quantity_fact не может быть меньше 0")

    # === ПРОВЕРКА: должен быть указан хотя бы один идентификатор ===
    if asset_id is None and material_id is None:
        raise ValueError("Необходимо указать либо asset_id, либо material_id")

    # === ПРОВЕРКА: сессия не должна быть completed ===
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return False
    if session.status == InventorizationStatus.COMPLETED:
        raise ValueError("Сессия уже завершена. Изменять items нельзя.")
    # ===================================================

    # Динамически формируем условия поиска
    conditions = [InventorizationItem.session_id == session_id]

    if asset_id is not None:
        conditions.append(InventorizationItem.asset_id == asset_id)
    elif material_id is not None:
        conditions.append(InventorizationItem.material_id == material_id)

    result = await db.execute(
        select(InventorizationItem).where(*conditions)
    )
    item = result.scalar_one_or_none()

    if item:
        item.is_checked = True
        item.quantity_fact = quantity_fact
        item.checked_by = checked_by
        await db.commit()
        return True

    return False

async def complete_inventory_session(db: AsyncSession, session_id: int, updated_by: str) -> Optional[InventorizationSession]:
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        raise ValueError("Сессия не найдена.")
    if session.status == InventorizationStatus.COMPLETED:
        raise ValueError("Сессия уже завершена.")

    # Обновляем количества в активах
    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id,
            InventorizationItem.is_checked == True,
            InventorizationItem.quantity_fact.isnot(None)
        )
    )
    checked_items = result.scalars().all()

    for item in checked_items:
        await db.execute(
            update(Asset)
            .where(Asset.asset_id == item.asset_id)
            .values(quantity=item.quantity_fact, updated_by=updated_by)
        )

    # Меняем статус сессии
    session.status = InventorizationStatus.COMPLETED
    session.end_date = datetime.now()

    # Находим всех ответственных для уведомлений
    result_assets = await db.execute(
        select(InventorizationItem.asset_id).where(InventorizationItem.session_id == session_id)
    )
    asset_ids = [row[0] for row in result_assets.all()]

    responsible_employees = []
    if asset_ids:
        employees_result = await db.execute(
            select(distinct(AssetAssignment.employee_id)).where(
                AssetAssignment.asset_id.in_(asset_ids),
                AssetAssignment.end_date.is_(None)  # Только активные назначения
            )
        )
        responsible_employees = [row[0] for row in employees_result.all()]

    # Создаем уведомления (они пока только в состоянии flush)
    for emp_id in responsible_employees:
        await notify_inventory_completed(
            db=db,
            employee_id=emp_id,
            session_id=session_id,
            initiator_id=updated_by,
        )

    if not responsible_employees:
        logger.debug(f"Ответственные не найдены для сессии {session.session_id}. Уведомляем создателя.")
        await notify_inventory_started(
            db=db,
            employee_id=updated_by,
            session_id=session.session_id,
            initiator_id=updated_by,
        )

    # Сохраняем и сессию, и созданные уведомления в БД!
    await db.commit()

    # Обновляем объект сессии для возврата
    await db.refresh(session)
    return session


async def get_inventorization_report(
        db: AsyncSession,
        session_id: int,
) -> Optional[dict]:
    """Получить сводный отчёт по сессии инвентаризации."""
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id
        )
    )
    items = result.scalars().all()

    total = len(items)
    checked = sum(1 for i in items if i.is_checked)
    unchecked = total - checked

    matches = 0
    discrepancies = 0
    surplus = 0
    missing = 0

    for item in items:
        if not item.is_checked:
            continue
        if item.quantity_fact is None:
            continue

        if item.quantity == item.quantity_fact:
            matches += 1
        else:
            discrepancies += 1
            if item.quantity_fact > (item.quantity or 0):
                surplus += 1
            else:
                missing += 1

    progress = (checked / total * 100) if total > 0 else 0.0

    return {
        "session_id": session.session_id,
        "asset_type_id": session.asset_type_id,
        "asset_type_name": session.asset_type_name,
        "status": session.status,
        "created_at": session.created_at,
        "start_date": session.start_date,
        "end_date": session.end_date,
        "total_items": total,
        "checked_items": checked,
        "unchecked_items": unchecked,
        "progress_percent": round(progress, 2),
        "matches_count": matches,
        "discrepancies_count": discrepancies,
        "surplus_count": surplus,
        "missing_count": missing,
        "not_checked_count": unchecked,
    }

async def get_inventorization_discrepancies(
        db: AsyncSession,
        session_id: int,
) -> Optional[dict]:
    """Получить список расхождений по сессии."""
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        return None

    result = await db.execute(
        select(InventorizationItem).where(
            InventorizationItem.session_id == session_id
        )
    )
    items = result.scalars().all()

    discrepancies = []
    for item in items:
        # Пропускаем полностью совпадающие
        if item.is_checked and item.quantity == item.quantity_fact:
            continue

        # Определяем тип расхождения
        if not item.is_checked:
            discrepancy_type = "not_checked"
            difference = None
        elif item.quantity_fact is None:
            discrepancy_type = "not_checked"
            difference = None
        elif item.quantity_fact > (item.quantity or 0):
            discrepancy_type = "surplus"
            difference = item.quantity_fact - (item.quantity or 0)
        elif item.quantity_fact < (item.quantity or 0):
            discrepancy_type = "missing"
            difference = item.quantity_fact - (item.quantity or 0)
        else:
            continue

        # Получаем serial_number из актива
        # asset_result = await db.execute(
        #     select(Asset.serial_number).where(Asset.asset_id == item.asset_id)
        # )
        # serial_number = asset_result.scalar_one_or_none()

        discrepancies.append({
            "inventorization_id": item.inventorization_id,
            "asset_id": item.asset_id,
            "asset_name": item.asset_name,
            "serial_number": item.serial_number,
            "quantity": item.quantity,
            "quantity_fact": item.quantity_fact,
            "difference": difference,
            "discrepancy_type": discrepancy_type,
        })

    return {
        "session_id": session_id,
        "total_discrepancies": len(discrepancies),
        "items": discrepancies,
    }

async def delete_inventorization_session(db: AsyncSession, session_id: int) -> Optional[InventorizationSession]:
    obj = await get_inventory_session_by_id(db, session_id)
    if not obj:
        return None

    # Удаляем запланированные задачи из APScheduler
    job_id_start = f"inventory_start_{session_id}"
    job_id_end = f"inventory_end_{session_id}"

    if scheduler.get_job(job_id_start):
        scheduler.remove_job(job_id_start)
        logger.info(f"[INVENTORY SCHEDULER] Удалена задача запуска сессии {session_id}")

    if scheduler.get_job(job_id_end):
        scheduler.remove_job(job_id_end)
        logger.info(f"[INVENTORY SCHEDULER] Удалена задача завершения сессии {session_id}")


    # Сначала удаляем все связанные элементы (items)
    # Используем прямой DELETE-запрос для эффективности
    await db.execute(
        delete(InventorizationItem).where(InventorizationItem.session_id == session_id)
    )
    await db.delete(obj)
    await db.commit()
    return obj

async def export_inventory_session_to_excel(
        db: AsyncSession,
        session_id: int
) -> StreamingResponse:
    """Экспортировать сессию инвентаризации в Excel файл с расширенной статистикой."""
    session = await get_inventory_session_by_id(db, session_id)
    if not session:
        raise ValueError("Сессия не найдена")

    # Получаем все элементы сессии
    result = await db.execute(
        select(InventorizationItem)
        .where(InventorizationItem.session_id == session_id)
        .options(selectinload(InventorizationItem.checked_employee))
        .order_by(InventorizationItem.inventorization_id)
    )
    items = result.scalars().all()

    # === НОВАЯ ЛОГИКА: Расчет сводной статистики ===
    total_assets = len(items)
    checked_assets = sum(1 for item in items if item.is_checked)
    dept_codes_str = session.department_codes if session.department_codes else "Не указаны"
    # ================================================

    # Ru label for status
    # ru_status = "В работе" if session.status == "in_progress" else "Завершено"
    ru_status = InventorizationStatus.get_ru_label(session.status)

    # Создаем Excel файл
    wb = Workbook()
    ws = wb.active
    ws.title = "Инвентаризация"

    # Заголовок с информацией о сессии
    ws['A1'] = "Сессия инвентаризации"
    ws['A1'].font = ws['A1'].font.copy(bold=True, size=14)

    ws['A3'] = "ID сессии:"
    ws['B3'] = session.session_id
    ws['A4'] = "Тип актива:"
    ws['B4'] = session.asset_type_name or "Не указан"
    ws['A5'] = "Статус:"
    ws['B5'] = ru_status
    ws['A6'] = "Дата создания:"
    ws['B6'] = session.created_at.strftime("%Y-%m-%d %H:%M:%S") if session.created_at else ""
    ws['A7'] = "Дата начала:"
    ws['B7'] = session.start_date.strftime("%Y-%m-%d %H:%M:%S") if session.start_date else ""
    ws['A8'] = "Дата окончания:"
    ws['B8'] = session.end_date.strftime("%Y-%m-%d %H:%M:%S") if session.end_date else ""

    # === НОВАЯ ЛОГИКА: Добавляем строки со статистикой ===
    ws['A9'] = "Коды департаментов:"
    ws['B9'] = dept_codes_str
    ws['A10'] = "Всего активов в сессии:"
    ws['B10'] = total_assets
    ws['A11'] = "Проверено активов:"
    ws['B11'] = checked_assets
    # =====================================================

    # Заголовки таблицы (сдвинуты вниз на 3 строки, было 10, стало 13)
    headers = [
        "ID",
        "ID актива / Material ID",  # Немного уточнил название заголовка
        "Название актива",
        "Серийный номер",
        "Инвентарный номер",
        "Учетное кол-во",
        "Фактическое кол-во",
        "Проверено",
        "Проверил",
        "Разница"
    ]

    start_row = 13  # <-- ИЗМЕНЕНО: начало таблицы
    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col, value=header)
        cell.font = cell.font.copy(bold=True)
        cell.fill = cell.fill.copy(fgColor="D3D3D3")

    # Данные элементов
    for idx, item in enumerate(items, start=start_row + 1):
        ws.cell(row=idx, column=1, value=item.inventorization_id)
        # Красивый вывод: либо ID актива, либо пометка SAP + material_id
        ws.cell(row=idx, column=2, value=item.asset_id if item.asset_id else f"SAP ({item.material_id})")
        ws.cell(row=idx, column=3, value=item.asset_name)
        ws.cell(row=idx, column=4, value=item.serial_number or "")
        ws.cell(row=idx, column=5, value=item.inventory_id or "")
        ws.cell(row=idx, column=6, value=item.quantity)
        ws.cell(row=idx, column=7, value=item.quantity_fact if item.quantity_fact is not None else "")
        ws.cell(row=idx, column=8, value="Да" if item.is_checked else "Нет")

        # Проверяющий сотрудник
        checked_by_name = ""
        if item.checked_employee:
            checked_by_name = f"{item.checked_employee.last_name} {item.checked_employee.first_name} {item.checked_employee.middle_name or ''}".strip()
        elif item.checked_by:
            checked_by_name = item.checked_by
        ws.cell(row=idx, column=9, value=checked_by_name)

        # Разница
        if item.quantity_fact is not None and item.quantity is not None:
            difference = item.quantity_fact - item.quantity
            ws.cell(row=idx, column=10, value=difference)
        else:
            ws.cell(row=idx, column=10, value="")

    # Автоматическая ширина колонок
    for column in ws.columns:
        max_length = 0
        column_letter = column[0].column_letter
        for cell in column:
            try:
                if len(str(cell.value)) > max_length:
                    max_length = len(str(cell.value))
            except:
                pass
        adjusted_width = min(max_length + 2, 50)
        ws.column_dimensions[column_letter].width = adjusted_width

    # Сохраняем в буфер
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    # Формируем имя файла
    filename = f"inventory_session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )