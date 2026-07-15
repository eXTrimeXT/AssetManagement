import json
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import HTMLResponse

from app.database.connection import get_db
from app.database.map_assets.crud_workshop import get_all_workshop

router_map = APIRouter(tags=["workshops"])

# ==============================================================================
# === ЭНДПОИНТ ДЛЯ ГЕНЕРАЦИИ HTML-КАРТЫ ЦЕХОВ ===
# ==============================================================================
@router_map.get("/map", response_class=HTMLResponse)
async def get_all_workshops_map(
        db: AsyncSession = Depends(get_db)
):
    """Генерирует и отдает HTML-страницу с интерактивной картой цехов"""

    # Фиксированные размеры карты
    MAP_WIDTH = 2000
    MAP_HEIGHT = 2000

    # 1. Получаем все активные цеха из PostgreSQL
    workshops = await get_all_workshop(db, skip=0, limit=1000)

    # 2. Преобразуем SQLAlchemy модели в словари
    workshops_data = []
    for w in workshops:
        workshops_data.append({
            "workshop_id": w.workshop_id,
            "name": w.name,
            "code": w.code,
            "description": w.description,
            "geometry": w.geometry,
            "workshop_width": w.workshop_width,
            "workshop_height": w.workshop_height,
            "offset_x": w.offset_x,
            "offset_y": w.offset_y,
            "color": w.color or "#546E7A"
        })

    # 3. Сериализуем данные
    workshops_json = json.dumps(workshops_data, ensure_ascii=False)

    # 4. Формируем HTML с адаптивной версткой
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>Карта завода</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            min-height: 100vh;
        }}
        
        .container {{ 
            max-width: 100%; 
            margin: 0 auto; 
        }}
        
        h1 {{
            text-align: center;
            margin-bottom: 20px;
            color: #fff;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            font-size: 32px;
        }}
        
        .map-wrapper {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 20px;
            overflow: hidden;
            position: relative;
        }}
        
        .map-svg {{
            width: 100%;
            height: auto;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: #fafafa;
            cursor: grab;
            display: block;
            touch-action: none;  /* Важно для touch событий */
        }}
        
        .map-svg:active {{
            cursor: grabbing;
        }}
        
        .workshop-polygon {{
            stroke: #333;
            stroke-width: 3;
            cursor: pointer;
            transition: all 0.3s ease;
        }}
        
        .workshop-polygon:hover {{
            opacity: 0.85;
            stroke-width: 4;
            filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
        }}
        
        .workshop-text {{
            font-family: Arial, sans-serif;
            font-weight: bold;
            fill: #fff;
            text-anchor: middle;
            pointer-events: none;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
        }}
        
        .workshop-name {{ font-size: 24px; }}
        .workshop-code {{ font-size: 16px; }}
        
        /* Zoom Controls */
        .zoom-controls {{
            position: absolute;
            top: 30px;
            right: 30px;
            display: flex;
            flex-direction: column;
            gap: 8px;
            z-index: 10;
        }}
        
        .zoom-btn {{
            width: 44px;
            height: 44px;
            border: none;
            border-radius: 8px;
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            cursor: pointer;
            font-size: 22px;
            font-weight: bold;
            color: #333;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            justify-content: center;
            -webkit-tap-highlight-color: transparent;
        }}
        
        .zoom-btn:hover {{
            background: #f0f0f0;
            transform: scale(1.05);
        }}
        
        .zoom-btn:active {{
            transform: scale(0.95);
            background: #e0e0e0;
        }}
        
        .zoom-level {{
            background: white;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2);
            border-radius: 8px;
            padding: 8px 12px;
            text-align: center;
            font-size: 13px;
            font-weight: bold;
            color: #333;
            min-width: 44px;
        }}
        
        .zoom-divider {{
            height: 1px;
            background: #e0e0e0;
            margin: 4px 0;
        }}
        
        .legend {{
            margin-top: 20px;
            padding: 20px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
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
            transition: background 0.2s;
        }}
        
        .legend-item:hover {{ 
            background: #eef2f7; 
        }}
        
        .legend-color {{
            display: inline-block;
            width: 24px;
            height: 24px;
            margin-right: 12px;
            border: 2px solid #333;
            border-radius: 4px;
        }}
        
        .map-info {{
            background: #fff3cd;
            color: #856404;
            padding: 10px 15px;
            margin-bottom: 15px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
            font-family: monospace;
            font-size: 13px;
        }}
        
        .debug-info {{
            background: #e3f2fd;
            color: #0d47a1;
            padding: 15px;
            margin: 10px 0;
            border-radius: 4px;
            font-family: monospace;
            font-size: 13px;
            line-height: 1.5;
        }}
        
        .help-hint {{
            position: absolute;
            bottom: 30px;
            left: 30px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 8px 14px;
            border-radius: 6px;
            font-size: 12px;
            z-index: 10;
            pointer-events: none;
        }}
        
        /* ============================================
           АДАПТИВНАЯ ВЕРСТКА - ПК (1920x1080)
           ============================================ */
        @media screen and (min-width: 1200px) {{
            body {{
                padding: 30px 40px;
            }}
            
            h1 {{
                font-size: 36px;
                margin-bottom: 30px;
            }}
            
            .map-wrapper {{
                padding: 25px;
                max-width: 1800px;
                margin: 0 auto;
            }}
            
            .map-info {{
                font-size: 14px;
                padding: 12px 18px;
                margin-bottom: 20px;
            }}
            
            .zoom-controls {{
                top: 35px;
                right: 35px;
            }}
            
            .zoom-btn {{
                width: 50px;
                height: 50px;
                font-size: 26px;
            }}
            
            .zoom-level {{
                font-size: 14px;
                padding: 10px 14px;
            }}
            
            .help-hint {{
                font-size: 13px;
                padding: 10px 16px;
                bottom: 35px;
                left: 35px;
            }}
            
            .legend {{
                max-width: 1800px;
                margin: 30px auto 0;
                padding: 25px;
            }}
            
            .legend h3 {{
                font-size: 22px;
            }}
            
            .legend-grid {{
                grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
                gap: 12px;
            }}
            
            .legend-item {{
                padding: 10px 14px;
            }}
            
            .workshop-name {{ font-size: 26px; }}
            .workshop-code {{ font-size: 18px; }}
        }}
        
        /* ============================================
           АДАПТИВНАЯ ВЕРСТКА - ПЛАНШЕТЫ (768px - 1199px)
           ============================================ */
        @media screen and (min-width: 768px) and (max-width: 1199px) {{
            body {{
                padding: 15px;
            }}
            
            h1 {{
                font-size: 28px;
                margin-bottom: 15px;
            }}
            
            .map-wrapper {{
                padding: 15px;
            }}
            
            .map-info {{
                font-size: 12px;
                padding: 8px 12px;
                margin-bottom: 12px;
            }}
            
            .zoom-controls {{
                top: 20px;
                right: 20px;
            }}
            
            .zoom-btn {{
                width: 40px;
                height: 40px;
                font-size: 20px;
            }}
            
            .help-hint {{
                font-size: 11px;
                padding: 6px 10px;
                bottom: 20px;
                left: 20px;
            }}
            
            .legend {{
                padding: 15px;
                margin-top: 15px;
            }}
            
            .legend h3 {{
                font-size: 18px;
            }}
            
            .legend-grid {{
                grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
                gap: 8px;
            }}
        }}
        
        /* ============================================
           АДАПТИВНАЯ ВЕРСТКА - ТЕЛЕФОНЫ (< 768px)
           ============================================ */
        @media screen and (max-width: 767px) {{
            body {{
                padding: 10px;
            }}
            
            h1 {{
                font-size: 22px;
                margin-bottom: 12px;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.3);
            }}
            
            .map-wrapper {{
                padding: 12px;
                border-radius: 8px;
            }}
            
            .map-info {{
                font-size: 11px;
                padding: 8px 10px;
                margin-bottom: 10px;
                border-radius: 4px;
            }}
            
            .zoom-controls {{
                top: 15px;
                right: 15px;
                gap: 6px;
            }}
            
            .zoom-btn {{
                width: 36px;
                height: 36px;
                font-size: 18px;
                border-radius: 6px;
            }}
            
            .zoom-level {{
                font-size: 11px;
                padding: 6px 8px;
                border-radius: 6px;
            }}
            
            .help-hint {{
                display: none;  /* Скрываем на телефонах - экономим место */
            }}
            
            .legend {{
                margin-top: 12px;
                padding: 12px;
                border-radius: 8px;
            }}
            
            .legend h3 {{
                font-size: 16px;
                margin-bottom: 12px;
            }}
            
            .legend-grid {{
                grid-template-columns: 1fr;  /* Одна колонка */
                gap: 6px;
            }}
            
            .legend-item {{
                padding: 6px 10px;
                font-size: 14px;
            }}
            
            .legend-color {{
                width: 20px;
                height: 20px;
                margin-right: 10px;
            }}
            
            .workshop-name {{ font-size: 18px; }}
            .workshop-code {{ font-size: 14px; }}
            
            .debug-info {{
                font-size: 11px;
                padding: 10px;
            }}
        }}
        
        /* ============================================
           ОЧЕНЬ МАЛЕНЬКИЕ ЭКРАНЫ (< 480px)
           ============================================ */
        @media screen and (max-width: 479px) {{
            body {{
                padding: 8px;
            }}
            
            h1 {{
                font-size: 18px;
                margin-bottom: 10px;
            }}
            
            .map-wrapper {{
                padding: 10px;
            }}
            
            .map-info {{
                font-size: 10px;
                padding: 6px 8px;
                margin-bottom: 8px;
            }}
            
            .zoom-controls {{
                top: 12px;
                right: 12px;
            }}
            
            .zoom-btn {{
                width: 32px;
                height: 32px;
                font-size: 16px;
            }}
            
            .zoom-level {{
                font-size: 10px;
                padding: 4px 6px;
            }}
            
            .legend {{
                padding: 10px;
            }}
            
            .legend h3 {{
                font-size: 14px;
            }}
            
            .legend-item {{
                padding: 5px 8px;
                font-size: 13px;
            }}
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>🏭 Карта производственных цехов</h1>

    <div class="map-wrapper">
        <div class="map-info">📐 Размер карты: {MAP_WIDTH}×{MAP_HEIGHT} px | Колесо мыши/щипок — zoom, перетаскивание — pan</div>
        
        <!-- Zoom Controls -->
        <div class="zoom-controls">
            <button class="zoom-btn" id="zoomIn" title="Приблизить">+</button>
            <div class="zoom-level" id="zoomLevel">100%</div>
            <div class="zoom-divider"></div>
            <button class="zoom-btn" id="zoomOut" title="Отдалить">−</button>
            <div class="zoom-divider"></div>
            <button class="zoom-btn" id="zoomReset" title="Сбросить zoom" style="font-size: 14px;">⟲</button>
        </div>
        
        <svg id="mapSvg" class="map-svg" viewBox="0 0 {MAP_WIDTH} {MAP_HEIGHT}" preserveAspectRatio="xMidYMid meet">
            <defs>
                <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                    <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e0e0e0" stroke-width="0.5"/>
                </pattern>
            </defs>
            <rect width="{MAP_WIDTH}" height="{MAP_HEIGHT}" fill="url(#grid)" />
            <g id="mapContent">
                <g id="workshopsLayer"></g>
            </g>
        </svg>
        
        <div class="help-hint">🖱️ Колесо: zoom | Зажать ЛКМ: перемещение</div>
    </div>

    <div class="legend">
        <h3>📋 Легенда цехов</h3>
        <div class="legend-grid" id="legendContent"></div>
    </div>
    
    <div id="debug" class="debug-info" style="display: none;"></div>
</div>

<script>
    const workshops = {workshops_json};
    const MAP_WIDTH = {MAP_WIDTH};
    const MAP_HEIGHT = {MAP_HEIGHT};
    
    // === ZOOM & PAN STATE ===
    const state = {{
        scale: 1,
        panX: 0,
        panY: 0,
        minScale: 0.1,
        maxScale: 5,
        zoomStep: 0.1,
        isPanning: false,
        startPanX: 0,
        startPanY: 0,
        // Для touch событий
        lastTouchDistance: 0,
        lastTouchCenter: null
    }};
    
    const svg = document.getElementById('mapSvg');
    const mapContent = document.getElementById('mapContent');
    const zoomLevelEl = document.getElementById('zoomLevel');

    function init() {{
        renderMap();
        updateLegend();
        showDebugInfo();
        setupZoomPan();
        updateTransform();
    }}

    // === ZOOM & PAN LOGIC ===
    function setupZoomPan() {{
        // === DESKTOP: Zoom колесом мыши ===
        svg.addEventListener('wheel', (e) => {{
            e.preventDefault();
            const rect = svg.getBoundingClientRect();
            const mouseX = e.clientX - rect.left;
            const mouseY = e.clientY - rect.top;
            
            const direction = e.deltaY < 0 ? 1 : -1;
            const newScale = clampScale(state.scale + direction * state.zoomStep);
            
            const scaleChange = newScale / state.scale;
            state.panX = mouseX - (mouseX - state.panX) * scaleChange;
            state.panY = mouseY - (mouseY - state.panY) * scaleChange;
            state.scale = newScale;
            
            updateTransform();
        }}, {{ passive: false }});
        
        // === DESKTOP: Pan мышью ===
        svg.addEventListener('mousedown', (e) => {{
            if (e.button !== 0) return;
            state.isPanning = true;
            state.startPanX = e.clientX - state.panX;
            state.startPanY = e.clientY - state.panY;
            svg.style.cursor = 'grabbing';
        }});
        
        window.addEventListener('mousemove', (e) => {{
            if (!state.isPanning) return;
            e.preventDefault();
            state.panX = e.clientX - state.startPanX;
            state.panY = e.clientY - state.startPanY;
            updateTransform();
        }});
        
        window.addEventListener('mouseup', () => {{
            if (state.isPanning) {{
                state.isPanning = false;
                svg.style.cursor = 'grab';
            }}
        }});
        
        // === TOUCH: Поддержка touch событий для мобильных ===
        svg.addEventListener('touchstart', handleTouchStart, {{ passive: false }});
        svg.addEventListener('touchmove', handleTouchMove, {{ passive: false }});
        svg.addEventListener('touchend', handleTouchEnd);
        
        // Кнопки zoom
        document.getElementById('zoomIn').addEventListener('click', () => {{
            zoomAtCenter(state.zoomStep);
        }});
        
        document.getElementById('zoomOut').addEventListener('click', () => {{
            zoomAtCenter(-state.zoomStep);
        }});
        
        document.getElementById('zoomReset').addEventListener('click', () => {{
            state.scale = 1;
            state.panX = 0;
            state.panY = 0;
            updateTransform();
        }});
        
        // Двойной клик/тап — быстрый zoom
        let lastTap = 0;
        svg.addEventListener('click', (e) => {{
            const currentTime = new Date().getTime();
            const tapLength = currentTime - lastTap;
            if (tapLength < 300 && tapLength > 0) {{
                e.preventDefault();
                const rect = svg.getBoundingClientRect();
                const touchX = e.clientX - rect.left;
                const touchY = e.clientY - rect.top;
                
                const newScale = clampScale(state.scale * 1.5);
                const scaleChange = newScale / state.scale;
                state.panX = touchX - (touchX - state.panX) * scaleChange;
                state.panY = touchY - (touchY - state.panY) * scaleChange;
                state.scale = newScale;
                
                updateTransform();
            }}
            lastTap = currentTime;
        }});
    }}
    
    // === TOUCH HANDLERS ===
    function handleTouchStart(e) {{
        if (e.touches.length === 1) {{
            // Один палец - pan
            state.isPanning = true;
            state.startPanX = e.touches[0].clientX - state.panX;
            state.startPanY = e.touches[0].clientY - state.panY;
        }} else if (e.touches.length === 2) {{
            // Два пальца - pinch zoom
            state.isPanning = false;
            state.lastTouchDistance = getTouchDistance(e.touches);
            state.lastTouchCenter = getTouchCenter(e.touches);
        }}
    }}
    
    function handleTouchMove(e) {{
        e.preventDefault();
        
        if (e.touches.length === 1 && state.isPanning) {{
            // Pan одним пальцем
            state.panX = e.touches[0].clientX - state.startPanX;
            state.panY = e.touches[0].clientY - state.startPanY;
            updateTransform();
        }} else if (e.touches.length === 2) {{
            // Pinch zoom двумя пальцами
            const currentDistance = getTouchDistance(e.touches);
            const currentCenter = getTouchCenter(e.touches);
            
            if (state.lastTouchDistance > 0) {{
                const scaleChange = currentDistance / state.lastTouchDistance;
                const newScale = clampScale(state.scale * scaleChange);
                
                // Zoom к центру между пальцами
                const rect = svg.getBoundingClientRect();
                const centerX = currentCenter.x - rect.left;
                const centerY = currentCenter.y - rect.top;
                
                state.panX = centerX - (centerX - state.panX) * (newScale / state.scale);
                state.panY = centerY - (centerY - state.panY) * (newScale / state.scale);
                state.scale = newScale;
                
                updateTransform();
            }}
            
            state.lastTouchDistance = currentDistance;
            state.lastTouchCenter = currentCenter;
        }}
    }}
    
    function handleTouchEnd() {{
        state.isPanning = false;
        state.lastTouchDistance = 0;
        state.lastTouchCenter = null;
    }}
    
    function getTouchDistance(touches) {{
        const dx = touches[0].clientX - touches[1].clientX;
        const dy = touches[0].clientY - touches[1].clientY;
        return Math.sqrt(dx * dx + dy * dy);
    }}
    
    function getTouchCenter(touches) {{
        return {{
            x: (touches[0].clientX + touches[1].clientX) / 2,
            y: (touches[0].clientY + touches[1].clientY) / 2
        }};
    }}
    
    function zoomAtCenter(delta) {{
        const rect = svg.getBoundingClientRect();
        const centerX = rect.width / 2;
        const centerY = rect.height / 2;
        
        const newScale = clampScale(state.scale + delta);
        const scaleChange = newScale / state.scale;
        state.panX = centerX - (centerX - state.panX) * scaleChange;
        state.panY = centerY - (centerY - state.panY) * scaleChange;
        state.scale = newScale;
        
        updateTransform();
    }}
    
    function clampScale(value) {{
        return Math.max(state.minScale, Math.min(state.maxScale, value));
    }}
    
    function updateTransform() {{
        const width = MAP_WIDTH / state.scale;
        const height = MAP_HEIGHT / state.scale;
        const x = -state.panX / state.scale;
        const y = -state.panY / state.scale;
        
        svg.setAttribute('viewBox', `${{x}} ${{y}} ${{width}} ${{height}}`);
        zoomLevelEl.textContent = Math.round(state.scale * 100) + '%';
    }}

    function renderMap() {{
        const layer = document.getElementById('workshopsLayer');
        layer.innerHTML = '';
        workshops.forEach(workshop => renderWorkshop(workshop, layer));
    }}

    function renderWorkshop(workshop, layer) {{
        const color = workshop.color || '#546E7A';
        let coordinates = null;

        if (workshop.geometry && 
            workshop.geometry.type === 'polygon' && 
            Array.isArray(workshop.geometry.coordinates) && 
            workshop.geometry.coordinates.length >= 3) {{
            coordinates = workshop.geometry.coordinates;
        }} 
        else if (workshop.workshop_width && workshop.workshop_height) {{
            const x = workshop.offset_x || 0;
            const y = workshop.offset_y || 0;
            const w = workshop.workshop_width;
            const h = workshop.workshop_height;
            
            coordinates = [
                [x, y],
                [x + w, y],
                [x + w, y + h],
                [x, y + h]
            ];
        }} 
        else {{
            console.warn(`Цех ${{workshop.code}}: нет координат. Пропущен.`);
            return;
        }}

        const points = coordinates.map(coord => `${{coord[0]}},${{coord[1]}}`).join(' ');
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', points);
        polygon.setAttribute('fill', color);
        polygon.setAttribute('class', 'workshop-polygon');
        polygon.setAttribute('data-workshop-id', workshop.workshop_id);
        
        polygon.addEventListener('click', (e) => {{
            e.stopPropagation();
            console.log('Выбран цех:', workshop);
            alert(`Цех: ${{workshop.name}} (${{workshop.code}})\\nID: ${{workshop.workshop_id}}\\nЦвет: ${{color}}`);
        }});

        layer.appendChild(polygon);

        const centroid = calculateCentroid(coordinates);
        const textGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        textGroup.style.pointerEvents = 'none';

        const nameText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        nameText.setAttribute('x', centroid.x);
        nameText.setAttribute('y', centroid.y - 10);
        nameText.setAttribute('class', 'workshop-text workshop-name');
        nameText.textContent = workshop.name;

        const codeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        codeText.setAttribute('x', centroid.x);
        codeText.setAttribute('y', centroid.y + 20);
        codeText.setAttribute('class', 'workshop-text workshop-code');
        codeText.textContent = workshop.code;

        textGroup.appendChild(nameText);
        textGroup.appendChild(codeText);
        layer.appendChild(textGroup);
    }}

    function calculateCentroid(coordinates) {{
        let x = 0, y = 0;
        const n = coordinates.length;
        for (let i = 0; i < n; i++) {{
            x += coordinates[i][0];
            y += coordinates[i][1];
        }}
        return {{ x: x / n, y: y / n }};
    }}

    function updateLegend() {{
        const legendContent = document.getElementById('legendContent');
        legendContent.innerHTML = '';
        workshops.forEach(workshop => {{
            const color = workshop.color || '#546E7A';
            const item = document.createElement('div');
            item.className = 'legend-item';
            item.innerHTML = `
                <span class="legend-color" style="background: ${{color}}"></span>
                <div>
                    <strong>${{workshop.code}}</strong><br>
                    <span style="font-size: 0.9em; color: #555;">${{workshop.name}}</span>
                </div>
            `;
            legendContent.appendChild(item);
        }});
    }}

    function showDebugInfo() {{
        const debugInfo = workshops.map(w => {{
            let status = '';
            if (w.geometry) {{
                status = '✅ geometry из БД';
            }} else if (w.workshop_width && w.workshop_height) {{
                status = ` ${{w.workshop_width}}x${{w.workshop_height}} (offset: ${{w.offset_x}},${{w.offset_y}})`;
            }} else {{
                status = ' нет координат';
            }}
            return `<div><strong>${{w.code}}</strong>: ${{status}} | Цвет: <span style="color:${{w.color || '#546E7A'}}">■</span> ${{w.color || '#546E7A'}}</div>`;
        }}).join('');
        
        if (debugInfo) {{
            document.getElementById('debug').innerHTML = '<strong>Информация о цехах:</strong><br>' + debugInfo;
            document.getElementById('debug').style.display = 'block';
        }}
    }}

    window.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)