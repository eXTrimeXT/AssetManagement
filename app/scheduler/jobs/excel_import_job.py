# import os
# import logging
# import pandas as pd
# from sqlalchemy import select, or_
#
# from app.database.connection import async_session
# from app.models.ImportTask import ImportTask
# from app.models.assets.Asset import Asset
# from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate
# from app.database.assets.crud_asset import create_asset, update_asset
# from app.database.assets.crud_asset_type import get_asset_types_list
# from app.services.excel.import_from_excel import preview_excel_row
#
# logger = logging.getLogger(__name__)
#
# async def process_excel_import_job(
#         task_id: str,
#         file_path: str,
#         allowed_cost_centers: list[str],
#         employee_id: str
# ):
#     logger.info(f"[IMPORT JOB] Запуск задачи импорта {task_id}")
#
#     try:
#         async with async_session() as db:
#             # 1. Обновляем статус на processing
#             stmt = select(ImportTask).where(ImportTask.task_id == task_id)
#             result = await db.execute(stmt)
#             task = result.scalar_one_or_none()
#             if not task:
#                 logger.error(f"[IMPORT JOB] Задача {task_id} не найдена")
#                 return
#
#             task.status = "processing"
#             await db.commit()
#
#             # 2. Читаем файл
#             df = pd.read_excel(file_path)
#
#             # Базовая подготовка столбцов (как в preview)
#             column_mapping_rules = {
#                 "инвентарный номер": "inventory_id",
#                 "Комментарий": "comment",
#                 "тип и модель пк": "name",
#                 "название": "name",
#                 "серийный номер": "serial_number",
#                 "дата выдачи": "date_issue",
#                 "дата покупки": "date_purchasing",
#                 "дата обслуживания": "next_service",
#                 "период обслуживания": "service_period",
#                 "период проверки": "check_period",
#             }
#             new_columns = {}
#             for col in df.columns:
#                 col_lower = str(col).strip().lower().replace('\n', ' ')
#                 for key, target_name in column_mapping_rules.items():
#                     if key in col_lower:
#                         new_columns[col] = target_name
#                         break
#             df = df.rename(columns=new_columns)
#
#             total_rows = len(df)
#             task.total_rows = total_rows
#             await db.commit()
#
#             # 3. Получаем типы активов один раз
#             asset_types = await get_asset_types_list(db, limit=200)
#             asset_types_map = {at.name: at.asset_type_id for at in asset_types}
#             asset_types_names = list(asset_types_map.keys())
#
#             for index, row in df.iterrows():
#                 excel_row = row.to_dict()
#                 row_index = index + 2
#
#                 try:
#                     # Вызываем логику предпросмотра (она же обогащает данные через AI)
#                     preview_data = await preview_excel_row(
#                         excel_row=excel_row,
#                         db=db,
#                         allowed_cost_centers=allowed_cost_centers,
#                         row_index=row_index,
#                         asset_types_map=asset_types_map,
#                         asset_types_names=asset_types_names
#                     )
#
#                     # Логика сохранения (аналогична bulk-save)
#                     asset_id = preview_data.get("asset_id")
#                     inv_id = preview_data.get("inventory_id")
#                     sn = preview_data.get("serial_number")
#                     material_id = preview_data.get("material_id")
#                     item_asset_type_id = preview_data.get("asset_type_id", 0)
#
#                     clean_data = {
#                         k: v for k, v in preview_data.items()
#                         if k not in ["excel_row_index", "status", "reason", "asset_type_id", "users"]
#                     }
#
#                     if not asset_id:
#                         conditions = []
#                         if inv_id: conditions.append(Asset.inventory_id == inv_id)
#                         if sn: conditions.append(Asset.serial_number == sn)
#                         if material_id: conditions.append(Asset.material_id == material_id)
#
#                         if conditions:
#                             stmt_check = select(Asset.asset_id).where(or_(*conditions))
#                             res = await db.execute(stmt_check)
#                             existing_asset_id = res.scalar_one_or_none()
#                             if existing_asset_id:
#                                 asset_id = existing_asset_id
#
#                     if asset_id:
#                         update_schema = AssetUpdate(asset_type_id=item_asset_type_id, **clean_data)
#                         await update_asset(db, asset_id, update_schema, employee_id)
#                     else:
#                         create_schema = AssetCreate(asset_type_id=item_asset_type_id, **clean_data)
#                         await create_asset(db, create_schema, employee_id)
#
#                 except Exception as e:
#                     logger.error(f"[IMPORT JOB] Ошибка в строке {row_index}: {e}")
#
#                 # Обновляем прогресс каждые 10 строк или в конце
#                 if index % 10 == 0 or index == total_rows - 1:
#                     task.processed_rows = index + 1
#                     await db.commit()
#
#             # 4. Завершение
#             task.status = "completed"
#             task.processed_rows = total_rows
#             await db.commit()
#             logger.info(f"[IMPORT JOB] Задача {task_id} завершена успешно.")
#
#     except Exception as e:
#         logger.error(f"[IMPORT JOB] Критическая ошибка задачи {task_id}: {e}", exc_info=True)
#         async with async_session() as db:
#             stmt = select(ImportTask).where(ImportTask.task_id == task_id)
#             result = await db.execute(stmt)
#             task = result.scalar_one_or_none()
#             if task:
#                 task.status = "failed"
#                 task.error_message = str(e)
#                 await db.commit()
#     finally:
#         # Удаляем временный файл
#         if os.path.exists(file_path):
#             os.remove(file_path)