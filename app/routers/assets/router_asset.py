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
from qrcode.image.svg import SvgPathImage
import re

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

# Старая версия без SAP API
# @router_assets.get(
#     "/",
#     response_model=PaginatedResponse[AssetResponse],
#     summary="Получить список активов (с пагинацией)"
# )
# async def get_assets(
#         request: Request,
#         page: int = Query(1, ge=1, description="Номер страницы (начинается с 1)"),
#         page_size: int = Query(50, ge=1, le=100, description="Размер страницы"),
#         name: Optional[str] = Query(None),
#         inventory_id: Optional[str] = Query(None),
#         serial_number: Optional[str] = Query(None),
#         asset_status: Optional[str] = Query(None),
#         model_id: Optional[int] = Query(None),
#         asset_type_id: Optional[int] = Query(None),
#         parent_id: Optional[int] = Query(None),
#         db: AsyncSession = Depends(get_db),
#         current_user=Depends(require_authorized_user)
# ):
#     """Получить страницу активов с фильтрацией по правам."""
#     token = await get_token_from_request(request)
#
#     if check_assets_is_admin(token):
#         allowed_type_en_names = None
#     else:
#         user_data = get_user_from_token(token)
#         permissions = user_data.permissions
#         allowed_type_en_names = [
#             en_name for en_name, perms in permissions.items()
#             if perms.get("read", False)
#         ]
#
#     assets, total = await get_assets_list(
#         db=db,
#         page=page,
#         page_size=page_size,
#         name=name,
#         inventory_id=inventory_id,
#         serial_number=serial_number,
#         asset_status=asset_status,
#         model_id=model_id,
#         asset_type_id=asset_type_id,
#         parent_id=parent_id,
#         allowed_type_en_names=allowed_type_en_names,
#     )
#
#     # === Дополняем данные о пользователях (Bulk Fetch) ===
#     await bulk_enrich_assets(db, list(assets))
#
#     total_pages = math.ceil(total / page_size) if total > 0 else 0
#
#     return PaginatedResponse(
#         items=list(assets),
#         total=total,
#         page=page,
#         page_size=page_size,
#         total_pages=total_pages,
#         has_next=page < total_pages,
#         has_previous=page > 1,
#     )


# Новая версия с SAP API
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
        search_mode: Literal["ALL", "NULLS", "NOT_NULLS"] = Query("ALL", description="Режим поиска SAP: all, not_nulls, nulls"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user),
):
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
# async def generate_qr_code(
#         request: QRCodeRequest,
#         current_user=Depends(require_authorized_user)
# ):
#     # Данные для кодирования: серийный номер, либо инвентарный, если серийного нет
#     qr_data = request.serial_number if request.serial_number else request.inventory_id
#
#     # Генерация настоящего QR-кода для встраивания в шаблон
#     qr = qrcode.QRCode(
#         version=1,
#         error_correction=qrcode.constants.ERROR_CORRECT_L,
#         box_size=4,  # Размер модуля, подобран для корректного отображения в области 120x120
#         border=0,
#         image_factory=SvgPathImage
#     )
#     qr.add_data(qr_data)
#     qr.make(fit=True)
#
#     img = qr.make_image(fill_color="black", back_color="white")
#     svg_content = img.to_string().decode('utf-8')
#
#     # Извлекаем путь из сгенерированного SVG для чистой вставки в шаблон
#     match = re.search(r'<path[^>]*d="([^"]*)"[^>]*>', svg_content)
#     qr_path = f'<path d="{match.group(1)}" fill="black" />' if match else '<rect x="0" y="0" width="120" height="120" fill="black" />'
#
#     serial_display = request.serial_number if request.serial_number else "Не указан"
#
#     # SVG-шаблон
#     svg_template = """<svg width="800" height="170" viewBox="0 0 800 170" xmlns="http://www.w3.org/2000/svg">
#       <defs>
#         <style>
#           .border {{ fill: none; stroke: black; stroke-width: 2; }}
#           .text-label {{ font-family: Arial, sans-serif; font-size: 14px; fill: black; }}
#           .text-value {{ font-family: Arial, sans-serif; font-size: 16px; fill: black; }}
#           .text-header {{ font-family: Arial, sans-serif; font-size: 14px; fill: black; font-weight: normal; }}
#         </style>
#       </defs>
#
#       <!-- Основной контейнер -->
#       <rect x="5" y="5" width="790" height="160" fill="white" stroke="black" stroke-width="2"/>
#
#       <!-- Левая колонка (QR-код) -->
#       <rect x="5" y="5" width="150" height="160" fill="white" stroke="black" stroke-width="2"/>
#
#       <!-- Сгенерированный QR-код -->
#       <g transform="translate(15, 15)">
#         {qr_code_path}
#       </g>
#
#       <!-- Правая часть: Таблица -->
#
#       <!-- Горизонтальные разделители -->
#       <!-- Строка 1 -->
#       <line x1="155" y1="58" x2="795" y2="58" stroke="black" stroke-width="2"/>
#       <!-- Строка 2 -->
#       <line x1="155" y1="108" x2="795" y2="108" stroke="black" stroke-width="2"/>
#
#       <!-- Вертикальный разделитель между названиями и значениями -->
#       <line x1="360" y1="5" x2="360" y2="165" stroke="black" stroke-width="2"/>
#
#       <!-- Текст: Строка 1 (Наименование) -->
#       <text x="165" y="30" class="text-label">Наименование ОС</text>
#       <text x="165" y="48" class="text-label">Fixed asset name</text>
#       <text x="370" y="40" class="text-value">{name}</text>
#
#       <!-- Текст: Строка 2 (Инвентарный номер) -->
#       <text x="165" y="80" class="text-label">Инвентарный номер</text>
#       <text x="165" y="98" class="text-label">Inventory number</text>
#       <text x="370" y="90" class="text-value">{inventory_id}</text>
#
#       <!-- Текст: Строка 3 (Серийный номер) -->
#       <text x="165" y="130" class="text-label">Серийный номер</text>
#       <text x="165" y="148" class="text-label">Serial number</text>
#       <text x="370" y="140" class="text-value">{serial_number}</text>
#     </svg>"""
#
#
#     final_svg = svg_template.format(
#         qr_code_path=qr_path,
#         name=request.name,
#         inventory_id=request.inventory_id,
#         serial_number=serial_display
#     )
#
#     # Возвращаем готовый SVG как изображение
#     return Response(content=final_svg, media_type="image/svg+xml")

@router_assets.post("/generate-qr")
async def generate_qr_code(request: QRCodeRequest):
    # Данные для кодирования: серийный номер, либо инвентарный, если серийного нет
    qr_data = request.serial_number if request.serial_number else request.inventory_id

    # Генерация матрицы QR-кода и создание SVG path вручную
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=5,  # Размер одного модуля в пикселях. 21x21 модулей * 5 = 105x105 пикселей (влезает в 120x130)
        border=0,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    matrix = qr.get_matrix()

    paths = []
    for y, row in enumerate(matrix):
        for x, cell in enumerate(row):
            if cell:
                # Для каждого черного модуля создаем команду рисования прямоугольника в path
                paths.append(f'M {x * 5} {y * 5} h 5 v 5 h -5 Z')

    # Собираем все в один тег <path>
    qr_path_svg = f'<path d="{" ".join(paths)}" fill="black" />'

    serial_display = request.serial_number if request.serial_number else "Не указан"

    # Ваш SVG-шаблон с заменой динамических значений.
    # Фигурные скобки в CSS экранированы двойными скобками {{ }}, чтобы str.format() их игнорировал.
    svg_template = """<svg width="800" height="170" viewBox="0 0 800 170" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <style>
      .border {{ fill: none; stroke: black; stroke-width: 2; }}
      .text-label {{ font-family: Arial, sans-serif; font-size: 14px; fill: black; }}
      .text-value {{ font-family: Arial, sans-serif; font-size: 16px; fill: black; }}
      .text-header {{ font-family: Arial, sans-serif; font-size: 14px; fill: black; font-weight: normal; }}
    </style>
  </defs>

  <!-- Основной контейнер -->
  <rect x="5" y="5" width="790" height="160" fill="white" stroke="black" stroke-width="2"/>

  <!-- Левая колонка (QR-код) -->
  <rect x="5" y="5" width="150" height="160" fill="white" stroke="black" stroke-width="2"/>
  
  <!-- Сгенерированный QR-код -->
  <g transform="translate(15, 15)">
    {qr_code_path}
  </g>

  <!-- Правая часть: Таблица -->
  
  <!-- Горизонтальные разделители -->
  <!-- Строка 1 -->
  <line x1="155" y1="58" x2="795" y2="58" stroke="black" stroke-width="2"/>
  <!-- Строка 2 -->
  <line x1="155" y1="108" x2="795" y2="108" stroke="black" stroke-width="2"/>

  <!-- Вертикальный разделитель между названиями и значениями -->
  <line x1="360" y1="5" x2="360" y2="165" stroke="black" stroke-width="2"/>

  <!-- Текст: Строка 1 (Наименование) -->
  <text x="165" y="30" class="text-label">Наименование ОС</text>
  <text x="165" y="48" class="text-label">Fixed asset name</text>
  <text x="370" y="40" class="text-value">{name}</text>

  <!-- Текст: Строка 2 (Инвентарный номер) -->
  <text x="165" y="80" class="text-label">Инвентарный номер</text>
  <text x="165" y="98" class="text-label">Inventory number</text>
  <text x="370" y="90" class="text-value">{inventory_id}</text>

  <!-- Текст: Строка 3 (Серийный номер) -->
  <text x="165" y="130" class="text-label">Серийный номер</text>
  <text x="165" y="148" class="text-label">Serial number</text>
  <text x="370" y="140" class="text-value">{serial_number}</text>
  
  <!-- Зеленая метка (галочка) в углу ячейки -->
  <path d="M 355 60 L 360 65 L 360 60 Z" fill="#4CAF50" />
</svg>"""

    final_svg = svg_template.format(
        qr_code_path=qr_path_svg,
        name=request.name,
        inventory_id=request.inventory_id,
        serial_number=serial_display
    )

    # Возвращаем готовый SVG как изображение
    return Response(content=final_svg, media_type="image/svg+xml")