import asyncio
import logging

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert

# Импорт ваших функций синхронизации
from app.services.zup.zup_integration import sync_all_data_for_zup
from app.services.sap.sync_sap_assets import sync_sap_departments, sync_sap_material_classes

# Импорт моделей (УБЕДИТЕСЬ, что пути к моделям соответствуют вашему проекту)
from app.models.assets.AssetStatus import AssetStatus
from app.models.assets.AssetType import AssetType
from app.models.map_assets.Workshop import Workshop  # Проверьте имя файла/модели цехов
from app.database.connection import get_db

logger = logging.getLogger(__name__)

async def _seed_table(db: AsyncSession, model, data: list, index_elements: list, update_cols: list):
    """Вспомогательная функция для безопасного UPSERT справочных данных."""
    if not data:
        return 0

    stmt = pg_insert(model).values(data)
    update_dict = {col: stmt.excluded[col] for col in update_cols}

    # Добавляем обновление updated_at, если такое поле есть в модели
    if hasattr(model, 'updated_at'):
        update_dict['updated_at'] = func.now()

    stmt = stmt.on_conflict_do_update(
        index_elements=index_elements,
        set_=update_dict
    )

    result = await db.execute(stmt)
    return result.rowcount

async def sync_all_data(db: AsyncSession) -> dict:
    """
    Полная синхронизация всех справочников и внешних данных.
    1. Инициализация/обновление базовых таблиц (статусы, типы, цеха).
    2. Синхронизация 1С (ZUP).
    3. Синхронизация справочников SAP.
    """
    logger.info("[FULL SYNC] Запуск полной синхронизации данных...")

    results = {
        "statuses_synced": 0,
        "types_synced": 0,
        "workshops_synced": 0,
        "zup_result": None,
        "sap_departments_result": None,
        "sap_classes_result": None,
        "success": True,
        "message": "Синхронизация завершена"
    }

    try:
        # ======================================================================
        # ШАГ 1: Инициализация справочных данных (UPSERT)
        # ======================================================================
        logger.info("[FULL SYNC] Шаг 1: Инициализация справочных данных...")

        # 1.1 Статусы активов
        statuses_data = [
            {"id": 1, "status": "Приемка"},
            {"id": 2, "status": "В ремонте"},
            {"id": 3, "status": "Ожидает ЗЧ"},
            {"id": 4, "status": "Отремонтирован"},
            {"id": 5, "status": "Удален"},
            {"id": 6, "status": "На обслуживании"},
            {"id": 7, "status": "Списан"},
            {"id": 8, "status": "Требует проверки"},
            {"id": 9, "status": "На складе"},
            {"id": 10, "status": "В работе"},
            {"id": 11, "status": "Требует обслуживания"},
        ]
        results["statuses_synced"] = await _seed_table(
            db, AssetStatus, statuses_data,
            index_elements=["id"],
            update_cols=["status"]
        )

        # 1.2 Типы активов
        types_data = [
            {"asset_type_id": 0, "name": "Без типа", "en_name": "without_type"},
            {"asset_type_id": 1, "name": "Компьютер", "en_name": "computer"},
            {"asset_type_id": 2, "name": "MES оборудование", "en_name": "mes_equipment"},
            {"asset_type_id": 3, "name": "Расходные материалы", "en_name": "supplies"},
            {"asset_type_id": 4, "name": "Адаптер питания", "en_name": "power_adapter"},
            {"asset_type_id": 5, "name": "Терминалы сбора данных", "en_name": "data_collection_equipment"}, # Завершена оборванная строка
            {"asset_type_id": 6, "name": "Комплектующие", "en_name": "Accessories"},
            {"asset_type_id": 7, "name": "Сетевое оборудование", "en_name": "network_equipment"},
            {"asset_type_id": 8, "name": "Печатное оборудование", "en_name": "printing_equipment"},
            {"asset_type_id": 9, "name": "Серверное оборудование", "en_name": "server_hardware"},
            {"asset_type_id": 10, "name": "Оборудование M&U", "en_name": "AssetsMU"},
        ]
        results["types_synced"] = await _seed_table(
            db, AssetType, types_data,
            index_elements=["asset_type_id"],
            update_cols=["name", "en_name"]
        )

        # 1.3 Цеха (Workshops)
        workshops_data = [
            {"workshop_id": 1, "name": "Цех штамповки", "code": "1-01", "description": "Обновленное описание цеха", "geometry": "", "workshop_width": 600, "workshop_height": 225, "offset_x": 75, "offset_y": 1125, "workshop_scale": 1, "color": "#1E3A6E", "is_active": True},
            {"workshop_id": 2, "name": "Цех сварки", "code": "1-02", "description": "", "geometry": "", "workshop_width": 450, "workshop_height": 525, "offset_x": 225, "offset_y": 600, "workshop_scale": 1, "color": "#B8422A", "is_active": True},
            {"workshop_id": 3, "name": "Цех окраски", "code": "1-03", "description": "", "geometry": "", "workshop_width": 450, "workshop_height": 900, "offset_x": 825, "offset_y": 600, "workshop_scale": 1, "color": "#4DB8A8", "is_active": True},
            {"workshop_id": 4, "name": "Цех сборки", "code": "1-04", "description": "", "geometry": '{"type": "polygon", "coordinates": [[450, 225], [975, 225], [975, 0], [1350, 0], [1350, 600], [450, 600]]}', "workshop_width": 0, "workshop_height": 0, "offset_x": 450, "offset_y": 0, "workshop_scale": 1, "color": "#5F7A72", "is_active": True},
            {"workshop_id": 5, "name": "Цех двигателей", "code": "1-05", "description": "", "geometry": "", "workshop_width": 450, "workshop_height": 225, "offset_x": 525, "offset_y": 0, "workshop_scale": 1, "color": "#D4C82A", "is_active": True},
            {"workshop_id": 6, "name": "Логистика", "code": "1-06", "description": "", "geometry": "", "workshop_width": 375, "workshop_height": 375, "offset_x": 75, "offset_y": 225, "workshop_scale": 1, "color": "#E8943A", "is_active": True},
            {"workshop_id": 7, "name": "Главный офис", "code": "1-07", "description": "", "geometry": "", "workshop_width": 450, "workshop_height": 225, "offset_x": 825, "offset_y": 1500, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 8, "name": "Офис в цехе сборки", "code": "1-09", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 9, "name": "Департамент производства систем трасмиссии", "code": "TM", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 10, "name": "Цех сборки производства систем трасмиссии", "code": "TM AS", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 11, "name": "Кондиционеры", "code": "AC", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 12, "name": "Логистика сварка", "code": "1-06+", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 13, "name": "Производственные технологии производства систем трасмиссии", "code": "TM MTC", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
            {"workshop_id": 14, "name": "СГП", "code": "1-20", "description": "", "geometry": "", "workshop_width": 0, "workshop_height": 0, "offset_x": 0, "offset_y": 0, "workshop_scale": 1, "color": "#2E7D32", "is_active": True},
        ]
        results["workshops_synced"] = await _seed_table(
            db, Workshop, workshops_data,
            index_elements=["workshop_id"],
            update_cols=["name", "code", "description", "geometry", "workshop_width", "workshop_height", "offset_x", "offset_y", "workshop_scale", "color", "is_active"]
        )

        # Коммитим справочники перед запуском тяжелых внешних синхронизаций
        await db.commit()
        logger.info("[FULL SYNC] Справочные данные успешно инициализированы/обновлены.")

        # ======================================================================
        # ШАГ 2: Внешние синхронизации
        # ======================================================================
        logger.info("[FULL SYNC] Шаг 2: Запуск синхронизации 1С (ZUP)...")
        results["zup_result"] = await sync_all_data_for_zup(db=db)

        logger.info("[FULL SYNC] Шаг 3: Запуск синхронизации подразделений SAP...")
        results["sap_departments_result"] = await sync_sap_departments(db=db)

        logger.info("[FULL SYNC] Шаг 4: Запуск синхронизации классов материалов SAP...")
        results["sap_classes_result"] = await sync_sap_material_classes(db=db)

        # Финальный коммит всех изменений
        await db.commit()
        logger.info("[FULL SYNC] Полная синхронизация успешно завершена.")

        return results

    except Exception as e:
        await db.rollback()
        logger.error(f"[FULL SYNC] Критическая ошибка при полной синхронизации: {e}", exc_info=True)
        results["success"] = False
        results["message"] = f"Ошибка синхронизации: {str(e)}"
        return results