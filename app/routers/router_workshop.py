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
from app.models.Workshop import Workshop
from app.service.map_asset.map_config_service import MapConfigService

router_workshop = APIRouter(prefix="/workshops", tags=["Workshops"])



# === ЭНДПОИНТ ДЛЯ ГЕНЕРАЦИИ HTML-КАРТЫ ЦЕХА (ДОЛЖЕН БЫТЬ ПЕРВЫМ!) ===
@router_workshop.get("/map", response_class=HTMLResponse)
async def get_all_workshops_map(
        db: AsyncSession = Depends(get_db)
):
    """
    Генерирует HTML-страницу с картой ВСЕХ цехов.
    Размеры карты из Redis, scale и color из БД для каждого цеха.
    """
    # Получаем конфиг из Redis (только размеры карты)
    map_width = await MapConfigService.get_map_width()
    map_height = await MapConfigService.get_map_height()

    # Получаем ВСЕ активные цеха
    workshops_result = await db.execute(
        select(Workshop)
        .where(Workshop.is_active == True)
        .order_by(Workshop.workshop_id)
    )
    workshops = workshops_result.scalars().all()

    if not workshops:
        raise HTTPException(status_code=404, detail="No active workshops found")

    # Получаем ВСЕ активные позиции активов для всех цехов
    positions_result = await db.execute(
        select(AssetPosition, Asset.name, Asset.inventory_id, Asset.serial_number, AssetPosition.workshop_id)
        .join(Asset, AssetPosition.asset_id == Asset.asset_id)
        .where(
            AssetPosition.is_active == True,
            Asset.deleted_at.is_(None)
        )
    )
    positions_data = positions_result.fetchall()

    # Группируем позиции по workshop_id
    positions_by_workshop = {}
    for pos_data in positions_data:
        workshop_id = pos_data[4]  # workshop_id
        if workshop_id not in positions_by_workshop:
            positions_by_workshop[workshop_id] = []
        positions_by_workshop[workshop_id].append(pos_data)

    # === ГЕНЕРАЦИЯ SVG ДЛЯ ВСЕХ ЦЕХОВ ===
    svg_workshops = ""
    svg_assets = ""

    for workshop in workshops:
        # Получаем параметры цеха из БД
        offset_x = workshop.offset_x if hasattr(workshop, 'offset_x') else 0
        offset_y = workshop.offset_y if hasattr(workshop, 'offset_y') else 0
        workshop_scale = workshop.workshop_scale if hasattr(workshop, 'workshop_scale') else 1.0
        workshop_color = workshop.color if hasattr(workshop, 'color') and workshop.color else "#546E7A"

        # === ГЕНЕРАЦИЯ SVG ЦЕХА ===
        # ПРИОРИТЕТ 1: Проверяем geometry (сложный полигон)
        if workshop.geometry and workshop.geometry.get('type') == 'polygon':
            coordinates = workshop.geometry.get('coordinates', [])
            if coordinates:
                # СМЕЩАЕМ КООРДИНАТЫ ПОЛИГОНА НА OFFSET И ПРИМЕНЯЕМ МАСШТАБ
                shifted_coords = [[(x * workshop_scale) + offset_x, (y * workshop_scale) + offset_y] for x, y in coordinates]
                points = " ".join([f"{x},{y}" for x, y in shifted_coords])
                centroid_x = sum(x for x, y in shifted_coords) / len(shifted_coords)
                centroid_y = sum(y for x, y in shifted_coords) / len(shifted_coords)

                svg_workshops += f'''
                <polygon points="{points}" fill="{workshop_color}" stroke="#333" stroke-width="3"/>
                <text x="{centroid_x}" y="{centroid_y}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
                <text x="{centroid_x}" y="{centroid_y + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
                '''

        # ПРИОРИТЕТ 2: Если geometry нет, но есть workshop_width и workshop_height — рисуем прямоугольник
        elif workshop.workshop_width and workshop.workshop_height:
            # Применяем масштаб
            scaled_width = int(workshop.workshop_width * workshop_scale)
            scaled_height = int(workshop.workshop_height * workshop_scale)

            # СМЕЩАЕМ ПРЯМОУГОЛЬНИК НА OFFSET
            svg_workshops += f'''
            <rect x="{offset_x}" y="{offset_y}" width="{scaled_width}" height="{scaled_height}" fill="{workshop_color}" stroke="#333" stroke-width="3"/>
            <text x="{offset_x + scaled_width / 2}" y="{offset_y + scaled_height / 2}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
            <text x="{offset_x + scaled_width / 2}" y="{offset_y + scaled_height / 2 + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
            '''

        # === ГЕНЕРАЦИЯ МАРКЕРОВ АКТИВОВ ДЛЯ ЭТОГО ЦЕХА ===
        workshop_positions = positions_by_workshop.get(workshop.workshop_id, [])
        for pos_data in workshop_positions:
            position = pos_data[0]
            asset_name = pos_data[1]
            asset_inventory = pos_data[2]

            # СМЕЩАЕМ КООРДИНАТЫ АКТИВА НА OFFSET
            asset_x = position.x + offset_x
            asset_y = position.y + offset_y

            svg_assets += f'''
            <g transform="translate({asset_x}, {asset_y})">
                <rect x="-20" y="-20" width="40" height="40" fill="#607D8B" stroke="#333" stroke-width="2" rx="5"/>
                <text x="0" y="5" font-family="Arial" font-size="10" fill="#fff" text-anchor="middle" font-weight="bold">
                    {asset_name[:8] if asset_name else f"A{position.asset_id}"}
                </text>
            </g>
            '''

    # === ГЕНЕРАЦИЯ ЛЕГЕНДЫ ===
    legend_items = ""
    for workshop in workshops:
        workshop_color = workshop.color if hasattr(workshop, 'color') and workshop.color else "#546E7A"
        legend_items += f'''
        <div class="legend-item">
            <span class="legend-color" style="background: {workshop_color}"></span>
            <span class="legend-text"><strong>{workshop.code}</strong> - {workshop.name}</span>
        </div>
        '''

    # === ГЕНЕРАЦИЯ HTML ===
    html_content = f'''
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <title>Карта завода - Все цеха</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                margin: 0;
                background: #f0f2f5;
                display: flex;
                flex-direction: column;
                align-items: center;
                min-height: 100vh;
                padding: 20px;
                transition: background 0.3s ease;
            }}
            
            body.white-theme {{
                background: #ffffff;
            }}
            
            h1 {{
                color: #333;
                margin-bottom: 20px;
                font-size: 32px;
            }}
            
            body.white-theme h1 {{
                color: #000;
            }}
            
            .map-container {{
                width: 90vw;
                height: 80vh;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                overflow: hidden;
                position: relative;
                transition: background 0.3s ease, box-shadow 0.3s ease;
            }}
            
            body.white-theme .map-container {{
                background: #ffffff;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            
            svg {{
                width: 100%;
                height: 100%;
                display: block;
            }}
            
            .controls {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: rgba(255,255,255,0.9);
                padding: 10px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                display: flex;
                gap: 5px;
                transition: background 0.3s ease;
            }}
            
            body.white-theme .controls {{
                background: rgba(255,255,255,0.95);
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            
            button {{
                cursor: pointer;
                padding: 8px 15px;
                margin: 2px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
                transition: all 0.2s ease;
            }}
            
            button:hover {{
                background: #e0e0e0;
            }}
            
            body.white-theme button:hover {{
                background: #f5f5f5;
            }}
            
            .theme-toggle {{
                background: #333 !important;
                color: white !important;
            }}
            
            body.white-theme .theme-toggle {{
                background: #fff !important;
                color: #333 !important;
                border: 2px solid #333 !important;
            }}
            
            .legend {{
                width: 90vw;
                margin-top: 20px;
                padding: 20px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            
            body.white-theme .legend {{
                background: #ffffff;
                box-shadow: 0 1px 5px rgba(0,0,0,0.05);
            }}
            
            .legend h3 {{
                margin-bottom: 15px;
                color: #333;
                font-size: 20px;
            }}
            
            .legend-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
                gap: 10px;
            }}
            
            .legend-item {{
                display: flex;
                align-items: center;
                padding: 8px 12px;
                background: #f9f9f9;
                border-radius: 6px;
            }}
            
            body.white-theme .legend-item {{
                background: #f5f5f5;
            }}
            
            .legend-color {{
                display: inline-block;
                width: 24px;
                height: 24px;
                margin-right: 12px;
                border: 2px solid #333;
                border-radius: 4px;
                flex-shrink: 0;
            }}
            
            .legend-text {{
                font-size: 14px;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <h1>🏭 Карта завода - Все цеха</h1>
        
        <div class="map-container">
            <div class="controls">
                <button onclick="zoomIn()">➕</button>
                <button onclick="zoomOut()">➖</button>
                <button onclick="resetZoom()">🔄 Сброс</button>
                <button onclick="toggleTheme()" class="theme-toggle">🌓 Тема</button>
            </div>

            <svg id="mapSvg" viewBox="0 0 {map_width} {map_height}" preserveAspectRatio="xMidYMid meet">
                <defs>
                    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
                    </filter>
                    <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                        <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e0e0e0" stroke-width="0.5"/>
                    </pattern>
                </defs>

                <rect width="{map_width}" height="{map_height}" fill="url(#grid)" />
                {svg_workshops}
                {svg_assets}
            </svg>
        </div>

        <div class="legend">
            <h3>📋 Легенда ({len(workshops)} цехов)</h3>
            <div class="legend-grid">
                {legend_items}
            </div>
        </div>

        <script>
            const svg = document.getElementById('mapSvg');
            let viewBox = {{ x: 0, y: 0, width: {map_width}, height: {map_height} }};
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
                viewBox = {{ x: 0, y: 0, width: {map_width}, height: {map_height} }};
                updateViewBox();
            }}

            function toggleTheme() {{
                document.body.classList.toggle('white-theme');
                const isWhiteTheme = document.body.classList.contains('white-theme');
                localStorage.setItem('mapTheme', isWhiteTheme ? 'white' : 'dark');
            }}

            window.addEventListener('DOMContentLoaded', () => {{
                const savedTheme = localStorage.getItem('mapTheme');
                if (savedTheme === 'white') {{
                    document.body.classList.add('white-theme');
                }}
            }});

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

@router_workshop.get("/map/{workshop_id}", response_class=HTMLResponse)
async def get_workshop_map(
        workshop_id: int,
        db: AsyncSession = Depends(get_db)
):
    """
    Генерирует HTML-страницу с картой конкретного цеха.
    Размеры карты из Redis, scale и color из БД.
    """
    # Получаем конфиг из Redis (только размеры карты)
    map_width = await MapConfigService.get_map_width()
    map_height = await MapConfigService.get_map_height()

    # Получаем цех
    workshop = await crud_workshop.get_workshop(db, workshop_id)
    if not workshop:
        raise HTTPException(status_code=404, detail="Workshop not found")

    # Получаем параметры цеха из БД
    offset_x = workshop.offset_x if hasattr(workshop, 'offset_x') else 0
    offset_y = workshop.offset_y if hasattr(workshop, 'offset_y') else 0
    workshop_scale = workshop.workshop_scale if hasattr(workshop, 'workshop_scale') else 1.0
    workshop_color = workshop.color if hasattr(workshop, 'color') and workshop.color else "#546E7A"

    # Получаем активы на карте
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
            # СМЕЩАЕМ КООРДИНАТЫ ПОЛИГОНА НА OFFSET И ПРИМЕНЯЕМ МАСШТАБ
            shifted_coords = [[(x * workshop_scale) + offset_x, (y * workshop_scale) + offset_y] for x, y in coordinates]
            points = " ".join([f"{x},{y}" for x, y in shifted_coords])
            centroid_x = sum(x for x, y in shifted_coords) / len(shifted_coords)
            centroid_y = sum(y for x, y in shifted_coords) / len(shifted_coords)

            svg_workshop = f'''
            <polygon points="{points}" fill="{workshop_color}" stroke="#333" stroke-width="3"/>
            <text x="{centroid_x}" y="{centroid_y}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
            <text x="{centroid_x}" y="{centroid_y + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
            '''

    # ПРИОРИТЕТ 2: Если geometry нет, но есть workshop_width и workshop_height — рисуем прямоугольник
    elif workshop.workshop_width and workshop.workshop_height:
        # Применяем масштаб
        scaled_width = int(workshop.workshop_width * workshop_scale)
        scaled_height = int(workshop.workshop_height * workshop_scale)

        # СМЕЩАЕМ ПРЯМОУГОЛЬНИК НА OFFSET
        svg_workshop = f'''
        <rect x="{offset_x}" y="{offset_y}" width="{scaled_width}" height="{scaled_height}" fill="{workshop_color}" stroke="#333" stroke-width="3"/>
        <text x="{offset_x + scaled_width / 2}" y="{offset_y + scaled_height / 2}" font-family="Arial" font-size="24" fill="#fff" text-anchor="middle" font-weight="bold">{workshop.name}</text>
        <text x="{offset_x + scaled_width / 2}" y="{offset_y + scaled_height / 2 + 30}" font-family="Arial" font-size="18" fill="#fff" text-anchor="middle">{workshop.code}</text>
        '''

    # === ГЕНЕРАЦИЯ МАРКЕРОВ АКТИВОВ ===
    svg_assets = ""
    for pos_data in positions_data:
        position = pos_data[0]
        asset_name = pos_data[1]
        asset_inventory = pos_data[2]

        # СМЕЩАЕМ КООРДИНАТЫ АКТИВА НА OFFSET
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
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            
            body {{
                margin: 0;
                background: #f0f2f5;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                transition: background 0.3s ease;
            }}
            
            body.white-theme {{
                background: #ffffff;
            }}
            
            .map-container {{
                width: 90vw;
                height: 90vh;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
                overflow: hidden;
                position: relative;
                transition: background 0.3s ease, box-shadow 0.3s ease;
            }}
            
            body.white-theme .map-container {{
                background: #ffffff;
                box-shadow: 0 2px 10px rgba(0,0,0,0.05);
            }}
            
            svg {{
                width: 100%;
                height: 100%;
                display: block;
            }}
            
            .controls {{
                position: absolute;
                top: 20px;
                right: 20px;
                background: rgba(255,255,255,0.9);
                padding: 10px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.2);
                display: flex;
                gap: 5px;
                transition: background 0.3s ease;
            }}
            
            body.white-theme .controls {{
                background: rgba(255,255,255,0.95);
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }}
            
            button {{
                cursor: pointer;
                padding: 8px 15px;
                margin: 2px;
                border: 1px solid #ccc;
                border-radius: 4px;
                background: white;
                transition: all 0.2s ease;
            }}
            
            button:hover {{
                background: #e0e0e0;
            }}
            
            body.white-theme button:hover {{
                background: #f5f5f5;
            }}
            
            .theme-toggle {{
                background: #333 !important;
                color: white !important;
            }}
            
            body.white-theme .theme-toggle {{
                background: #fff !important;
                color: #333 !important;
                border: 2px solid #333 !important;
            }}
        </style>
    </head>
    <body>
        <div class="map-container">
            <div class="controls">
                <button onclick="zoomIn()">➕</button>
                <button onclick="zoomOut()">➖</button>
                <button onclick="resetZoom()">🔄 Сброс</button>
                <button onclick="toggleTheme()" class="theme-toggle">🌓 Тема</button>
            </div>

            <svg id="mapSvg" viewBox="0 0 {map_width} {map_height}" preserveAspectRatio="xMidYMid meet">
                <defs>
                    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="2" dy="2" stdDeviation="3" flood-opacity="0.3"/>
                    </filter>
                    <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                        <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e0e0e0" stroke-width="0.5"/>
                    </pattern>
                </defs>

                <rect width="{map_width}" height="{map_height}" fill="url(#grid)" />
                {svg_workshop}
                {svg_assets}
            </svg>
        </div>

        <script>
            const svg = document.getElementById('mapSvg');
            let viewBox = {{ x: 0, y: 0, width: {map_width}, height: {map_height} }};
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
                viewBox = {{ x: 0, y: 0, width: {map_width}, height: {map_height} }};
                updateViewBox();
            }}

            function toggleTheme() {{
                document.body.classList.toggle('white-theme');
                
                // Сохраняем тему в localStorage
                const isWhiteTheme = document.body.classList.contains('white-theme');
                localStorage.setItem('mapTheme', isWhiteTheme ? 'white' : 'dark');
            }}

            // Загружаем сохраненную тему
            window.addEventListener('DOMContentLoaded', () => {{
                const savedTheme = localStorage.getItem('mapTheme');
                if (savedTheme === 'white') {{
                    document.body.classList.add('white-theme');
                }}
            }});

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

@router_workshop.post("/", response_model=WorkshopResponse, status_code=200)
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


@router_workshop.delete("/{workshop_id}", status_code=200)
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