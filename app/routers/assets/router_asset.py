import logging
import math

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Literal
from app.database.connection import get_db
from app.database.assets.crud_asset import (
    create_asset, get_asset_by_id, get_assets_list,
    update_asset, delete_asset, get_asset_children, bulk_enrich_assets
)
from app.schemas.assets.AssetSchemas import AssetCreate, AssetUpdate, AssetResponse, AssetShortResponse, QRCodeRequest
from app.services.auth.auth_service import (
    require_authorized_user,
    get_token_from_request,
    get_user_from_token, check_assets_is_admin,
)
from app.services.auth.permission_checker import check_permission, check_asset_permission
from app.schemas.PaginationResponse import PaginatedResponse
from app.database.zup import get_position_by_guid
from app.database.zup.crud_zup_departments import get_hierarchy_departments
from app.schemas.assets.AssetAssignmentSchemas import AssetUserFullResponse
from app.services.assets.asset_list_service import get_assets_list_with_sap

# for QR-code
import qrcode

logger = logging.getLogger(__name__)
router_assets = APIRouter(prefix="/assets", tags=["Assets"])


@router_assets.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_endpoint(
        request: Request,
        data: AssetCreate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Создать актив. Проверка права write на тип актива."""
    await check_asset_permission(db, request, data.asset_type_id, "write")
    return await create_asset(db, data, current_user.employee_id)


async def enrich_users_data(db: AsyncSession, users_data: list) -> list:
    """Дополняет данные о пользователях иерархией и должностью"""
    enriched = []
    for user in users_data:
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user

        # Получаем иерархию подразделений
        if user_dict.get("department_guid"):
            hierarchy = await get_hierarchy_departments(db, user_dict["department_guid"])
            if hierarchy:
                user_dict["society"] = hierarchy.society
                user_dict["department"] = hierarchy.department
                user_dict["division"] = hierarchy.division
                user_dict["group"] = hierarchy.group

        # Получаем должность
        if user_dict.get("position_guid"):
            position = await get_position_by_guid(db, user_dict["position_guid"])
            if position:
                from app.schemas.zup.PositionSchemas import PositionResponse
                user_dict["position"] = PositionResponse.model_validate(position)

        enriched.append(AssetUserFullResponse(**user_dict))

    return enriched

@router_assets.get(
    "/",
    response_model=PaginatedResponse[AssetResponse],
    summary="Получить список активов с слиянием данных из SAP и локальной БД"
)
async def get_assets(
        page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
        page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
        name: Optional[str] = Query(None, description="Поиск по названию актива"),
        # name: Optional[str] = Query("ноутбук", description="Поиск по названию актива"),
        asset_id: Optional[int] = Query(None, description="Поиск по asset_id (one Local DB)"),
        material_id: Optional[str] = Query(None, description="Поиск по material_id (one SAP)"),
        inventory_id: Optional[str] = Query(None, description="Инвентарный номер"),
        # inventory_id: Optional[str] = Query("110000050000", description="Инвентарный номер"),
        serial_number: Optional[str] = Query(None, description="Серийный номер"),
        asset_status: Optional[str] = Query(None, description="Статус актива"),
        model_id: Optional[int] = Query(None, description="ID модели"),
        asset_type_id: Optional[int] = Query(None, description="ID типа актива"),
        parent_id: Optional[int] = Query(None, description="ID родительского актива"),
        employee_id: Optional[str] = Query(None, description="Табельный номер сотрудника"),
        only_my: Optional[bool] = Query(False, description="Показать только мои активы? (employee_id игнорируется)"),
        search_mode: Literal["ALL", "NULLS", "NOT_NULLS"] = Query("ALL", description="Режим поиска SAP: all, not_nulls, nulls"),

        # Фильтры по MVZ:
        cost_center_shortname_from: Optional[str] = Query(None, description="Ответственный департамент (short_name)"),
        cost_center_shortname_from_mode: Literal["ALL", "NULLS", "NOT_NULLS"] = Query("ALL"),
        cost_center_code_from: Optional[str] = Query(None, description="Код ответственного департамента"),

        cost_center_shortname: Optional[str] = Query(None, description="Департамент владельца (short_name)"),
        cost_center_shortname_mode: Literal["ALL", "NULLS", "NOT_NULLS"] = Query("ALL"),
        cost_center_code: Optional[str] = Query(None, description="Код департамента владельца"),

        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
    if only_my:
        employee_id = current_user.employee_id
        # print(f"employee_id = {employee_id}")

    result = await get_assets_list_with_sap(
        db=db,
        page=page,
        page_size=page_size,
        name=name,
        asset_id=asset_id,
        material_id=material_id,
        inventory_id=inventory_id,
        serial_number=serial_number,
        asset_status=asset_status,
        model_id=model_id,
        asset_type_id=asset_type_id,
        parent_id=parent_id,
        search_mode=search_mode,
        employee_id=employee_id,
        only_my=only_my,

        # Фильтры по MVZ
        cost_center_shortname_from=cost_center_shortname_from,
        cost_center_shortname_from_mode=cost_center_shortname_from_mode,
        cost_center_code_from=cost_center_code_from,
        cost_center_shortname=cost_center_shortname,
        cost_center_shortname_mode=cost_center_shortname_mode,
        cost_center_code=cost_center_code
    )

    return PaginatedResponse(**result)

@router_assets.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id
    await check_asset_permission(db, request, obj.asset_type_id, "read")

    await bulk_enrich_assets(db, [obj])
    
    return obj

@router_assets.patch("/{asset_id}", response_model=AssetResponse)
async def update_asset_endpoint(
        request: Request,
        asset_id: int,
        data: AssetUpdate,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    # Проверяем существование актива (но не блокируем, если его нет)
    obj = await get_asset_by_id(db, asset_id)

    # Проверка прав доступа (только если актив существует)
    if obj:
        final_asset_type_id = data.asset_type_id if data.asset_type_id is not None else obj.asset_type_id
        if final_asset_type_id:
            await check_asset_permission(db, request, final_asset_type_id, "write")

    # Обновляем или создаем актив
    updated = await update_asset(db, asset_id, data, current_user.employee_id)

    if not updated:
        raise HTTPException(status_code=404, detail="Не удалось создать или обновить актив")

    return updated

@router_assets.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset_endpoint(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    obj = await get_asset_by_id(db, asset_id)
    if not obj:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id
    await check_asset_permission(db, request, obj.asset_type_id, "write")

    success = await delete_asset(db, asset_id)
    if not success:
        raise HTTPException(status_code=404, detail="Актив не найден")

@router_assets.get("/{asset_id}/children", response_model=List[AssetShortResponse])
async def get_asset_children_endpoint(
        request: Request,
        asset_id: int,
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Получение всех детей актива через parent_id"""
    parent = await get_asset_by_id(db, asset_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Актив не найден")

    # Проверка прав напрямую через asset_type_id родителя
    await check_asset_permission(db, request, parent.asset_type_id, "read")

    children = await get_asset_children(db, asset_id)
    return children

# @router_assets.post("/generate-qr")
# async def generate_qr_code(request: QRCodeRequest):
#     # Данные для кодирования: серийный номер, либо инвентарный, если серийного нет
#     qr_data = request.serial_number if request.serial_number else request.inventory_id
#
#     # Генерация матрицы QR-кода и создание SVG path вручную
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=5,  # Размер одного модуля в пикселях. 21x21 модулей * 5 = 105x105 пикселей (влезает в 120x130)
#         border=0,
#     )
#     qr.add_data(qr_data)
#     qr.make(fit=True)
#     matrix = qr.get_matrix()
#
#     paths = []
#     for y, row in enumerate(matrix):
#         for x, cell in enumerate(row):
#             if cell:
#                 # Для каждого черного модуля создаем команду рисования прямоугольника в path
#                 paths.append(f'M {x * 5} {y * 5} h 5 v 5 h -5 Z')
#
#     # Собираем все в один тег <path>
#     qr_path_svg = f'<path d="{" ".join(paths)}" fill="black" />'
#
#     serial_display = request.serial_number if request.serial_number else "Не указан"
#
# #     svg_template = """<svg width="800" height="250" viewBox="0 0 800 250" xmlns="http://www.w3.org/2000/svg">
# #     <!-- Фон -->
# #     <rect width="100%" height="100%" fill="white" />
# #
# #     <!-- Внешняя рамка -->
# #     <rect x="10" y="10" width="780" height="230" fill="none" stroke="black" stroke-width="2" />
# #
# #     <!-- Вертикальные линии -->
# #     <!-- Линия после левой колонки -->
# #     <line x1="200" y1="10" x2="200" y2="240" stroke="black" stroke-width="2" />
# #     <!-- Линия перед QR-кодом -->
# #     <line x1="630" y1="10" x2="630" y2="240" stroke="black" stroke-width="2" />
# #
# #     <!-- Горизонтальные линии -->
# #     <!-- Линия между "Наименование" и "Инвентарный номер" -->
# #     <line x1="10" y1="110" x2="630" y2="110" stroke="black" stroke-width="2" />
# #     <!-- Линия между "Инвентарный номер" и "Серийный номер" -->
# #     <line x1="10" y1="170" x2="630" y2="170" stroke="black" stroke-width="2" />
# #
# #     <!-- Текст: Левая колонка -->
# #     <g font-family="Arial, sans-serif" font-size="14" fill="black">
# #         <!-- Наименование OC -->
# #         <text x="25" y="55">Наименование ОС</text>
# #         <text x="25" y="80">Fixed asset name</text>
# #
# #         <!-- Инвентарный номер -->
# #         <text x="25" y="140">Инвентарный номер</text>
# #         <text x="25" y="165">Inventory number</text>
# #
# #         <!-- Серийный номер -->
# #         <text x="25" y="205">Серийный номер</text>
# #         <text x="25" y="230">Serial number</text>
# #     </g>
# #
# #     <!-- Текст: Средняя колонка (заполнители) -->
# #     <g font-family="Arial, sans-serif" font-size="14" fill="black">
# #         <!-- Наименование OC значение -->
# #         <text x="215" y="55">{name}</text>
# #
# #         <!-- Инвентарный номер значение -->
# #         <text x="215" y="140">{inventory_id}</text>
# #
# #         <!-- Серийный номер значение -->
# #         <text x="215" y="205">{serial_number}</text>
# #     </g>
# #
# #     <g transform="translate(660, 70)">
# #         {qr_code_path}
# #     </g>
# # </svg>"""
#
#     svg_template = """<svg xmlns="http://www.w3.org/2000/svg"
#     width="70mm" height="25mm"
#     viewBox="0 0 827 295">
#     <title>Этикетка 70×25</title>
#     <g transform="scale(1.03375000 1.18000000)">
#
#         <!-- Фон -->
#         <rect width="100%" height="100%" fill="white" />
#         <!-- Внешняя рамка -->
#         <rect x="10" y="10" width="780" height="230" fill="none" stroke="black" stroke-width="2" />
#         <!-- Вертикальные линии -->
#         <!-- Линия после левой колонки -->
#         <line x1="255" y1="10" x2="255" y2="240" stroke="black" stroke-width="2" />
#         <!-- Линия перед QR-кодом -->
#         <line x1="630" y1="10" x2="630" y2="240" stroke="black" stroke-width="2" />
#         <!-- Горизонтальные линии -->
#         <!-- Линия между "Наименование" и "Инвентарный номер" -->
#         <line x1="10" y1="110" x2="630" y2="110" stroke="black" stroke-width="2" />
#         <!-- Линия между "Инвентарный номер" и "Серийный номер" -->
#         <line x1="10" y1="170" x2="630" y2="170" stroke="black" stroke-width="2" />
#         <!-- Текст: Левая колонка -->
#         <g font-family="Arial, sans-serif" font-weight="bold" font-size="22" fill="black">
#             <!-- Наименование OC -->
#             <text x="15" y="55">Наименование ОС</text>
#             <text x="15" y="80">Fixed asset name</text>
#             <!-- Инвентарный номер -->
#             <text x="15" y="140">Инвентарный номер</text>
#             <text x="15" y="165">Inventory number</text>
#             <!-- Серийный номер -->
#             <text x="15" y="205">Серийный номер</text>
#             <text x="15" y="230">Serial number</text>
#         </g>
#         <!-- Текст: Средняя колонка (заполнители) -->
#         <g font-family="Arial, sans-serif" font-size="26"  fill="black">
#             <!-- Наименование OC значение -->
#             <text font-weight="bold" x="270" y="55">{name[0]}</text>
#             <text font-weight="bold" x="270" y="80">{name[1]}</text>
#             <!-- Инвентарный номер значение -->
#             <text font-size="38" font-weight="bold" x="270" y="150">{inventory_id}</text>
#             <!-- Серийный номер значение -->
#             <text font-size="32" font-weight="bold" x="270" y="215">{serial_number}</text>
#         </g>
#         <g transform="translate(660, 70)">
#             {qr_code_path}
#         </g>
#
#     </g>
# </svg>
#     """
#
#     final_svg = svg_template.format(
#         qr_code_path=qr_path_svg,
#         name=request.name,
#         inventory_id=request.inventory_id,
#         serial_number=serial_display
#     )
#
#     # Возвращаем готовый SVG как изображение
#     return Response(content=final_svg, media_type="image/svg+xml")


from fastapi import APIRouter, Response
from pydantic import BaseModel
from typing import Optional
import qrcode

# Убедитесь, что в вашей схеме QRCodeRequest есть поле name
# class QRCodeRequest(BaseModel):
#     name: str
#     inventory_id: str
#     serial_number: Optional[str] = None

def wrap_text(text: str, max_length: int = 15, max_lines: int = 3) -> list:
    """Разбивает текст на строки по словам, не превышая max_length символов."""
    if not text:
        return [""]

    words = text.split()
    lines = []
    current_line = []
    current_length = 0

    for word in words:
        word_len = len(word)
        # Проверяем, поместится ли слово в текущую строку (+1 на пробел, если это не первое слово)
        if current_length + word_len + (1 if current_line else 0) <= max_length:
            current_line.append(word)
            current_length += word_len + (1 if current_line else 0)
        else:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = word_len

    if current_line:
        lines.append(" ".join(current_line))

    # Обрезаем до максимального количества строк, чтобы не сломать верстку этикетки
    return lines[:max_lines]

@router_assets.post("/generate-qr")
async def generate_qr_code(request: QRCodeRequest):
    qr_data = request.serial_number if request.serial_number else request.inventory_id

    # Генерация матрицы QR-кода (box_size=5 соответствует вашему примеру h 5 v 5)
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=5,
        border=0,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    paths = []
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                paths.append(f'M {x * 5} {y * 5} h 5 v 5 h -5 Z')

    qr_path_svg = f'<path d="{" ".join(paths)}" fill="black" />'

    # Обработка переноса наименования
    serial_display = request.serial_number if request.serial_number else "Не указан"
    name_lines = wrap_text(request.name, max_length=24, max_lines=3)

    # Генерируем SVG <text> теги для каждой строки названия.
    # Начальная Y = 55, шаг = +25 (55, 80, 105)
    name_svg_elements = []
    for i, line in enumerate(name_lines):
        y_pos = 35 + (i * 30)
        name_svg_elements.append(f'<text font-weight="bold" x="270" y="{y_pos}">{line}</text>')

    name_lines_svg = "\n        ".join(name_svg_elements)

    # SVG-шаблон
    svg_template = """<svg xmlns="http://www.w3.org/2000/svg" width="70mm" height="25mm" viewBox="0 0 827 295">
    <title>Этикетка 70×25</title>
    <g transform="scale(1.03375000 1.18000000)">

        <!-- Фон -->
        <rect width="100%" height="100%" fill="white" />
        <!-- Внешняя рамка -->
        <rect x="10" y="10" width="780" height="230" fill="none" stroke="black" stroke-width="2" />
        <!-- Вертикальные линии -->
        <!-- Линия после левой колонки -->
        <line x1="255" y1="10" x2="255" y2="240" stroke="black" stroke-width="2" />
        <!-- Линия перед QR-кодом -->
        <line x1="630" y1="10" x2="630" y2="240" stroke="black" stroke-width="2" />
        <!-- Горизонтальные линии -->
        <!-- Линия между "Наименование" и "Инвентарный номер" -->
        <line x1="10" y1="110" x2="630" y2="110" stroke="black" stroke-width="2" />
        <!-- Линия между "Инвентарный номер" и "Серийный номер" -->
        <line x1="10" y1="170" x2="630" y2="170" stroke="black" stroke-width="2" />
        
        <!-- Текст: Левая колонка -->
        <g font-family="Arial, sans-serif" font-weight="bold" font-size="22" fill="black">
            <!-- Наименование OC -->
            <text x="15" y="55">Наименование ОС</text>
            <text x="15" y="80">Fixed asset name</text>
            <!-- Инвентарный номер -->
            <text x="15" y="140">Инвентарный номер</text>
            <text x="15" y="165">Inventory number</text>
            <!-- Серийный номер -->
            <text x="15" y="205">Серийный номер</text>
            <text x="15" y="230">Serial number</text>
        </g>
        
        <!-- Текст: Средняя колонка (заполнители) -->
        <g font-family="Arial, sans-serif" font-size="26" fill="black">
            <!-- Наименование OC значение (динамический перенос) -->
            {name_lines}
            <!-- Инвентарный номер значение -->
            <text font-size="38" font-weight="bold" x="270" y="150">{inventory_id}</text>
            <!-- Серийный номер значение -->
            <text font-size="32" font-weight="bold" x="270" y="215">{serial_number}</text>
        </g>
        
        <g transform="translate(660, 70)">
            {qr_code_path}
        </g>

    </g>
</svg>"""

    # Сборка финального SVG
    final_svg = svg_template.format(
        qr_code_path=qr_path_svg,
        name_lines=name_lines_svg,
        inventory_id=request.inventory_id,
        serial_number=serial_display
    )

    return Response(content=final_svg, media_type="image/svg+xml")