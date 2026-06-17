from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.connection import get_db
from app.database import crud_workshop
from app.schemas.workshop.Workshop import (
    WorkshopCreate,
    WorkshopUpdate,
    WorkshopResponse,
    WorkshopListResponse
)
from app.models.Asset import Asset
from app.models.AssetPosition import AssetPosition

router_workshop = APIRouter(prefix="/workshops", tags=["Workshops"])



# === ЭНДПОИНТ ДЛЯ ГЕНЕРАЦИИ HTML-КАРТЫ ЦЕХА (ДОЛЖЕН БЫТЬ ПЕРВЫМ!) ===
from fastapi.responses import HTMLResponse

@router_workshop.get("/{workshop_id}/map", response_class=HTMLResponse)
async def get_workshop_map(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Генерирует HTML-страницу с картой конкретного цеха.
    Координаты активов относительны workshop.
    """
    # Получаем цех
    workshop = await crud_workshop.get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Workshop not found")

    # HARDCODED: размер общей карты всегда MAP_SIZE * MAP_SIZE
    MAP_SIZE = 4000

    # Получаем offset цеха (по умолчанию 0)
    offset_x = workshop.offset_x if hasattr(workshop, 'offset_x') else 0
    offset_y = workshop.offset_y if hasattr(workshop, 'offset_y') else 0

    # Получаем активы на карте (координаты относительные)
    positions_result = await db.execute(
        select(AssetPosition, Asset.name, Asset.inventory_id, Asset.serial_number)
        .join(Asset, AssetPosition.asset_id == Asset.asset_id)
        .where(
            AssetPosition.workshop_id == workshop_id,
            AssetPosition.is_active == True,
            Asset.deleted_at.is_(None)
        )
    )
    positions_data = positions_result.fetchall()

    # === ГЕНЕРАЦИЯ SVG ЦЕХА ===
    svg_workshop = ""

    # ПРИОРИТЕТ 1: Проверяем geometry (сложный полигон)
    if workshop.geometry and workshop.geometry.get('type') == 'polygon':
        coordinates = workshop.geometry.get('coordinates', [])
        if coordinates:
            # === СМЕЩАЕМ КООРДИНАТЫ ПОЛИГОНА НА OFFSET ===
            shifted_coords = [[x + offset_x, y + offset_y] for x, y in coordinates]
            points = " ".join([f"{x},{y}" for x, y in shifted_coords])
            centroid_x = sum(x for x, y in shifted_coords) / len(shifted_coords)
            centroid_y = sum(y for x, y in shifted_coords) / len(shifted_coords)

            svg_workshop = f'''
            <polygon points="{points}" fill="#546E7A" stroke="#333" stroke-width="3"/>
            <text x="{centroid_x}" y="{centroid_y}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
            <text x="{centroid_x}" y="{centroid_y + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
            '''

    # ПРИОРИТЕТ 2: Если geometry нет, но есть workshop_width и workshop_height — рисуем прямоугольник
    elif workshop.workshop_width and workshop.workshop_height:
        # === СМЕЩАЕМ ПРЯМОУГОЛЬНИК НА OFFSET ===
        svg_workshop = f'''
        <rect x="{offset_x}" y="{offset_y}" width="{workshop.workshop_width}" height="{workshop.workshop_height}" fill="#546E7A" stroke="#333" stroke-width="3"/>
        <text x="{offset_x + workshop.workshop_width / 2}" y="{offset_y + workshop.workshop_height / 2}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
        <text x="{offset_x + workshop.workshop_width / 2}" y="{offset_y + workshop.workshop_height / 2 + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
        '''

    # === ГЕНЕРАЦИЯ МАРКЕРОВ АКТИВОВ (координаты относительные + offset) ===
    svg_assets = ""
    for pos_data in positions_data:
        position = pos_data[0]
        asset_name = pos_data[1]
        asset_inventory = pos_data[2]

        # === СМЕЩАЕМ КООРДИНАТЫ АКТИВА НА OFFSET ===
        asset_x = position.x + offset_x
        asset_y = position.y + offset_y

        svg_assets += f'''
        <g transform="translate({asset_x}, {asset_y})">
            <rect x="-20" y="-20" width="40" height="40" fill="#607D8B" stroke="#333" stroke-width="2" rx="5"/>
            <text x="0" y="5" font-family="Arial" font-size="10" fill="#fff" text-anchor="middle" font-weight="bold">
                {asset_inventory[:8] if asset_inventory else f"A{position.asset_id}"}
            </text>
        </g>
        '''

    # === ГЕНЕРАЦИЯ HTML ===
    html_content = f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Карта цеха: {workshop.name}</title>
        <style>
            body {{ margin: 0; background: #f0f2f5; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            .map-container {{ width: 90vw; height: 90vh; background: white; border-radius: 12px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); overflow: hidden; position: relative; }}
            svg {{ width: 100%; height: 100%; display: block; }}
            .controls {{ position: absolute; top: 20px; right: 20px; background: rgba(255,255,255,0.9); padding: 10px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.2); }}
            button {{ cursor: pointer; padding: 8px 15px; margin: 2px; border: 1px solid #ccc; border-radius: 4px; background: white; }}
            button:hover {{ background: #e0e0e0; }}
        </style>
    </head>
    <body>
        <div class="map-container">
            <div class="controls">
                <button onclick="zoomIn()">➕ Приблизить</button>
                <button onclick="zoomOut()">➖ Отдалить</button>
                <button onclick="resetZoom()">🔄 Сброс</button>
            </div>

            <svg id="mapSvg" viewBox="0 0 {MAP_SIZE} {MAP_SIZE}" preserveAspectRatio="xMidYMid meet">
                <defs>
                    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
                    </filter>
                    <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                        <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e0e0e0" stroke-width="0.5"/>
                    </pattern>
                </defs>

                <rect width="{MAP_SIZE}" height="{MAP_SIZE}" fill="url(#grid)" />
                {svg_workshop}
                {svg_assets}
            </svg>
        </div>

        <script>
            const svg = document.getElementById('mapSvg');
            let viewBox = {{ x: 0, y: 0, width: {MAP_SIZE}, height: {MAP_SIZE} }};
            let isPanning = false;
            let startPoint = {{ x: 0, y: 0 }};
            let endPoint = {{ x: 0, y: 0 }};

            function updateViewBox() {{
                svg.setAttribute('viewBox', `${{viewBox.x}} ${{viewBox.y}} ${{viewBox.width}} ${{viewBox.height}}`);
            }}

            function zoomIn() {{
                const zoomFactor = 0.8;
                const newWidth = viewBox.width * zoomFactor;
                const newHeight = viewBox.height * zoomFactor;
                const dx = (viewBox.width - newWidth) / 2;
                const dy = (viewBox.height - newHeight) / 2;
                viewBox.x += dx;
                viewBox.y += dy;
                viewBox.width = newWidth;
                viewBox.height = newHeight;
                updateViewBox();
            }}

            function zoomOut() {{
                const zoomFactor = 1.2;
                const newWidth = viewBox.width * zoomFactor;
                const newHeight = viewBox.height * zoomFactor;
                const dx = (viewBox.width - newWidth) / 2;
                const dy = (viewBox.height - newHeight) / 2;
                viewBox.x += dx;
                viewBox.y += dy;
                viewBox.width = newWidth;
                viewBox.height = newHeight;
                updateViewBox();
            }}

            function resetZoom() {{
                viewBox = {{ x: 0, y: 0, width: {MAP_SIZE}, height: {MAP_SIZE} }};
                updateViewBox();
            }}

            svg.addEventListener('mousedown', (e) => {{
                isPanning = true;
                startPoint = {{ x: e.clientX, y: e.clientY }};
                svg.style.cursor = 'grabbing';
            }});

            svg.addEventListener('mousemove', (e) => {{
                if (!isPanning) return;
                endPoint = {{ x: e.clientX, y: e.clientY }};
                const dx = (startPoint.x - endPoint.x) * (viewBox.width / svg.clientWidth);
                const dy = (startPoint.y - endPoint.y) * (viewBox.height / svg.clientHeight);
                viewBox.x += dx;
                viewBox.y += dy;
                updateViewBox();
                startPoint = {{ ...endPoint }};
            }});

            svg.addEventListener('mouseup', () => {{
                isPanning = false;
                svg.style.cursor = 'grab';
            }});

            svg.addEventListener('mouseleave', () => {{
                isPanning = false;
                svg.style.cursor = 'grab';
            }});

            svg.addEventListener('wheel', (e) => {{
                e.preventDefault();
                const zoomFactor = e.deltaY > 0 ? 1.1 : 0.9;
                const rect = svg.getBoundingClientRect();
                const mouseX = e.clientX - rect.left;
                const mouseY = e.clientY - rect.top;
                const svgX = viewBox.x + (mouseX / svg.clientWidth) * viewBox.width;
                const svgY = viewBox.y + (mouseY / svg.clientHeight) * viewBox.height;
                const newWidth = viewBox.width * zoomFactor;
                const newHeight = viewBox.height * zoomFactor;
                viewBox.x = svgX - (mouseX / svg.clientWidth) * newWidth;
                viewBox.y = svgY - (mouseY / svg.clientHeight) * newHeight;
                viewBox.width = newWidth;
                viewBox.height = newHeight;
                updateViewBox();
            }});

            svg.style.cursor = 'grab';
        </script>
    </body>
    </html>
    '''

    return HTMLResponse(content=html_content, status_code=200)

@router_workshop.post("/", response_model=WorkshopResponse, status_code=201)
async def create_workshop(
        data: WorkshopCreate,
        db: AsyncSession = Depends(get_db)
):
    """
    Создание нового цеха.
    """
    try:
        workshop = await crud_workshop.create_workshop(db, data)
        return workshop
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_workshop.get("/", response_model=List[WorkshopListResponse])
async def get_workshops(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        db: AsyncSession = Depends(get_db)
):
    """
    Получение списка всех цехов с пагинацией.
    """
    workshops = await crud_workshop.get_workshops(db, skip=skip, limit=limit)
    return workshops


@router_workshop.get("/{workshop_id}", response_model=WorkshopResponse)
async def get_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Получение информации о цехе по ID.
    """
    workshop = await crud_workshop.get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return workshop


@router_workshop.patch("/{workshop_id}", response_model=WorkshopResponse)
async def update_workshop(
        workshop_id: int,
        data: WorkshopUpdate,
        db: AsyncSession = Depends(get_db)
):
    """
    Обновление данных цеха.
    """
    try:
        workshop = await crud_workshop.update_workshop(db, workshop_id, data)
        if not workshop:
            raise HTTPException(status_code=404, detail="Workshop not found")
        return workshop
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router_workshop.delete("/{workshop_id}", status_code=204)
async def delete_workshop(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Удаление цеха.
    """
    success = await crud_workshop.delete_workshop(db, workshop_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workshop not found")
    return None