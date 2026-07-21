# import json
# import os
#
# from fastapi import APIRouter, Depends
# from sqlalchemy.ext.asyncio import AsyncSession
# from sqlalchemy.sql.functions import current_user
# from starlette.responses import HTMLResponse, FileResponse
#
# from app.database.connection import get_db
# from app.database.map_assets.crud_workshop import get_all_workshop
#
# # 2. Получаем все активные позиции активов
# from sqlalchemy import select
# from app.models.map_assets.asset_position import AssetPosition
# from app.models.assets.asset import Asset
# from app.services.auth.auth_service import require_authorized_user
#
# router_map = APIRouter(tags=["workshops"])
#
# # ==============================================================================
# # === ЭНДПОИНТ ДЛЯ ГЕНЕРАЦИИ HTML-КАРТЫ ЦЕХОВ ===
# # ==============================================================================
# @router_map.get("/map-crud", response_class=HTMLResponse)
# async def get_all_workshops_map(
#         db: AsyncSession = Depends(get_db),
# ):
#     """Генерирует и отдает HTML-страницу с интерактивной картой цехов и активов"""
#
#     # Фиксированные размеры карты
#     MAP_WIDTH = 2000
#     MAP_HEIGHT = 2000
#
#     # 1. Получаем все активные цеха из PostgreSQL
#     workshops = await get_all_workshop(db, skip=0, limit=1000)
#
#     result = await db.execute(
#         select(AssetPosition)
#         .where(AssetPosition.is_active == True)
#         .join(Asset, AssetPosition.asset_id == Asset.asset_id)
#         .where(Asset.asset_status != "Списание")  # Только активные активы
#     )
#     positions = result.scalars().all()
#
#     # 3. Преобразуем цеха в словари
#     workshops_data = []
#     for w in workshops:
#         workshops_data.append({
#             "workshop_id": w.workshop_id,
#             "name": w.name,
#             "code": w.code,
#             "description": w.description,
#             "geometry": w.geometry,
#             "workshop_width": w.workshop_width,
#             "workshop_height": w.workshop_height,
#             "offset_x": w.offset_x,
#             "offset_y": w.offset_y,
#             "color": w.color or "#546E7A"
#         })
#
#     # 4. Преобразуем позиции активов в словари с информацией об активе
#     assets_data = []
#     for pos in positions:
#         asset = pos.asset
#         if not asset:
#             continue
#
#         # Определяем иконку в зависимости от типа актива
#         icon = "📦"  # Дефолтная иконка
#         if asset.asset_type_id:
#             # Можно добавить маппинг типов к иконкам
#             icon = "️"  # Оборудование
#
#         assets_data.append({
#             "position_id": pos.id,
#             "asset_id": asset.asset_id,
#             "name": asset.name,
#             "inventory_id": asset.inventory_id,
#             "asset_status": asset.asset_status,
#             "x": pos.x,
#             "y": pos.y,
#             "rotation": pos.rotation,
#             "scale": pos.scale,
#             "workshop_id": pos.workshop_id,
#             "icon": icon
#         })
#
#     # 5. Сериализуем данные
#     workshops_json = json.dumps(workshops_data, ensure_ascii=False)
#     assets_json = json.dumps(assets_data, ensure_ascii=False)
#
#     # 6. Формируем HTML с отображением активов
#     html_content = f"""<!DOCTYPE html>
# <html lang="ru">
# <head>
#     <meta charset="UTF-8">
#     <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
#     <title>Карта завода</title>
#     <style>
#         * {{ margin: 0; padding: 0; box-sizing: border-box; }}
#
#         body {{
#             font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#             background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#             padding: 20px;
#             min-height: 100vh;
#         }}
#
#         .container {{
#             max-width: 100%;
#             margin: 0 auto;
#         }}
#
#         h1 {{
#             text-align: center;
#             margin-bottom: 20px;
#             color: #fff;
#             text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
#             font-size: 32px;
#         }}
#
#         .map-wrapper {{
#             background: white;
#             border-radius: 12px;
#             box-shadow: 0 10px 40px rgba(0,0,0,0.2);
#             padding: 20px;
#             overflow: hidden;
#             position: relative;
#         }}
#
#         .map-svg {{
#             width: 100%;
#             height: auto;
#             border: 2px solid #e0e0e0;
#             border-radius: 8px;
#             background: #fafafa;
#             cursor: grab;
#             display: block;
#             touch-action: none;
#         }}
#
#         .map-svg:active {{
#             cursor: grabbing;
#         }}
#
#         .workshop-polygon {{
#             stroke: #333;
#             stroke-width: 3;
#             cursor: pointer;
#             transition: all 0.3s ease;
#         }}
#
#         .workshop-polygon:hover {{
#             opacity: 0.85;
#             stroke-width: 4;
#             filter: drop-shadow(0 4px 8px rgba(0,0,0,0.3));
#         }}
#
#         .workshop-text {{
#             font-family: Arial, sans-serif;
#             font-weight: bold;
#             fill: #fff;
#             text-anchor: middle;
#             pointer-events: none;
#             text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
#         }}
#
#         .workshop-name {{ font-size: 24px; }}
#         .workshop-code {{ font-size: 16px; }}
#
#         /* Стили для иконок активов */
#         .asset-icon {{
#             cursor: pointer;
#             transition: all 0.2s ease;
#             filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3));
#         }}
#
#         .asset-icon:hover {{
#             filter: drop-shadow(4px 4px 8px rgba(0,0,0,0.5));
#         }}
#
#         .asset-label {{
#             font-family: Arial, sans-serif;
#             font-size: 12px;
#             font-weight: bold;
#             fill: #333;
#             text-anchor: middle;
#             pointer-events: none;
#             text-shadow: 1px 1px 2px rgba(255,255,255,0.8);
#         }}
#
#         /* Zoom Controls */
#         .zoom-controls {{
#             position: absolute;
#             top: 30px;
#             right: 30px;
#             display: flex;
#             flex-direction: column;
#             gap: 8px;
#             z-index: 10;
#         }}
#
#         .zoom-btn {{
#             width: 44px;
#             height: 44px;
#             border: none;
#             border-radius: 8px;
#             background: white;
#             box-shadow: 0 2px 8px rgba(0,0,0,0.2);
#             cursor: pointer;
#             font-size: 22px;
#             font-weight: bold;
#             color: #333;
#             transition: all 0.2s;
#             display: flex;
#             align-items: center;
#             justify-content: center;
#             -webkit-tap-highlight-color: transparent;
#         }}
#
#         .zoom-btn:hover {{
#             background: #f0f0f0;
#             transform: scale(1.05);
#         }}
#
#         .zoom-btn:active {{
#             transform: scale(0.95);
#             background: #e0e0e0;
#         }}
#
#         .zoom-level {{
#             background: white;
#             box-shadow: 0 2px 8px rgba(0,0,0,0.2);
#             border-radius: 8px;
#             padding: 8px 12px;
#             text-align: center;
#             font-size: 13px;
#             font-weight: bold;
#             color: #333;
#             min-width: 44px;
#         }}
#
#         .zoom-divider {{
#             height: 1px;
#             background: #e0e0e0;
#             margin: 4px 0;
#         }}
#
#         .legend {{
#             margin-top: 20px;
#             padding: 20px;
#             background: white;
#             border-radius: 12px;
#             box-shadow: 0 4px 15px rgba(0,0,0,0.1);
#         }}
#
#         .legend h3 {{
#             margin-bottom: 15px;
#             color: #333;
#             font-size: 20px;
#         }}
#
#         .legend-grid {{
#             display: grid;
#             grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
#             gap: 10px;
#         }}
#
#         .legend-item {{
#             display: flex;
#             align-items: center;
#             padding: 8px 12px;
#             background: #f9f9f9;
#             border-radius: 6px;
#             transition: background 0.2s;
#         }}
#
#         .legend-item:hover {{
#             background: #eef2f7;
#         }}
#
#         .legend-color {{
#             display: inline-block;
#             width: 24px;
#             height: 24px;
#             margin-right: 12px;
#             border: 2px solid #333;
#             border-radius: 4px;
#         }}
#
#         .map-info {{
#             background: #fff3cd;
#             color: #856404;
#             padding: 10px 15px;
#             margin-bottom: 15px;
#             border-radius: 6px;
#             border-left: 4px solid #ffc107;
#             font-family: monospace;
#             font-size: 13px;
#         }}
#
#         .stats-info {{
#             background: #d1ecf1;
#             color: #0c5460;
#             padding: 10px 15px;
#             margin-bottom: 15px;
#             border-radius: 6px;
#             border-left: 4px solid #17a2b8;
#             font-family: monospace;
#             font-size: 13px;
#         }}
#
#         .debug-info {{
#             background: #e3f2fd;
#             color: #0d47a1;
#             padding: 15px;
#             margin: 10px 0;
#             border-radius: 4px;
#             font-family: monospace;
#             font-size: 13px;
#             line-height: 1.5;
#         }}
#
#         .help-hint {{
#             position: absolute;
#             bottom: 30px;
#             left: 30px;
#             background: rgba(0,0,0,0.7);
#             color: white;
#             padding: 8px 14px;
#             border-radius: 6px;
#             font-size: 12px;
#             z-index: 10;
#             pointer-events: none;
#         }}
#
#         /* Адаптивная верстка */
#         @media screen and (min-width: 1200px) {{
#             body {{ padding: 30px 40px; }}
#             h1 {{ font-size: 36px; margin-bottom: 30px; }}
#             .map-wrapper {{ padding: 25px; max-width: 1800px; margin: 0 auto; }}
#             .zoom-controls {{ top: 35px; right: 35px; }}
#             .zoom-btn {{ width: 50px; height: 50px; font-size: 26px; }}
#             .legend {{ max-width: 1800px; margin: 30px auto 0; padding: 25px; }}
#         }}
#
#         @media screen and (max-width: 767px) {{
#             body {{ padding: 10px; }}
#             h1 {{ font-size: 22px; margin-bottom: 12px; }}
#             .map-wrapper {{ padding: 12px; }}
#             .zoom-controls {{ top: 15px; right: 15px; }}
#             .zoom-btn {{ width: 36px; height: 36px; font-size: 18px; }}
#             .help-hint {{ display: none; }}
#             .legend {{ margin-top: 12px; padding: 12px; }}
#             .legend-grid {{ grid-template-columns: 1fr; }}
#         }}
#     </style>
# </head>
# <body>
# <div class="container">
#     <h1>🏭 Карта производственных цехов</h1>
#
#     <div class="map-wrapper">
#         <div class="map-info"> Размер карты: {MAP_WIDTH}×{MAP_HEIGHT} px | Колесо мыши/щипок — zoom, перетаскивание — pan</div>
#         <div class="stats-info"> Цехов: {len(workshops_data)} | Активов на карте: {len(assets_data)}</div>
#
#         <!-- Zoom Controls -->
#         <div class="zoom-controls">
#             <button class="zoom-btn" id="zoomIn" title="Приблизить">+</button>
#             <div class="zoom-level" id="zoomLevel">100%</div>
#             <div class="zoom-divider"></div>
#             <button class="zoom-btn" id="zoomOut" title="Отдалить">−</button>
#             <div class="zoom-divider"></div>
#             <button class="zoom-btn" id="zoomReset" title="Сбросить zoom" style="font-size: 14px;">⟲</button>
#         </div>
#
#         <svg id="mapSvg" class="map-svg" viewBox="0 0 {MAP_WIDTH} {MAP_HEIGHT}" preserveAspectRatio="xMidYMid meet">
#             <defs>
#                 <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
#                     <path d="M 100 0 L 0 0 0 100" fill="none" stroke="#e0e0e0" stroke-width="0.5"/>
#                 </pattern>
#             </defs>
#             <rect width="{MAP_WIDTH}" height="{MAP_HEIGHT}" fill="url(#grid)" />
#             <g id="mapContent">
#                 <g id="workshopsLayer"></g>
#                 <g id="assetsLayer"></g>
#             </g>
#         </svg>
#
#         <div class="help-hint">🖱️ Колесо: zoom | Зажать ЛКМ: перемещение | Клик по активу: информация</div>
#     </div>
#
#     <div class="legend">
#         <h3>📋 Легенда цехов</h3>
#         <div class="legend-grid" id="legendContent"></div>
#     </div>
#
#     <div id="debug" class="debug-info" style="display: none;"></div>
# </div>
#
# <script>
#     const workshops = {workshops_json};
#     const assets = {assets_json};
#     const MAP_WIDTH = {MAP_WIDTH};
#     const MAP_HEIGHT = {MAP_HEIGHT};
#
#     // === ZOOM & PAN STATE ===
#     const state = {{
#         scale: 1,
#         panX: 0,
#         panY: 0,
#         minScale: 0.1,
#         maxScale: 5,
#         zoomStep: 0.1,
#         isPanning: false,
#         startPanX: 0,
#         startPanY: 0,
#         lastTouchDistance: 0,
#         lastTouchCenter: null
#     }};
#
#     const svg = document.getElementById('mapSvg');
#     const mapContent = document.getElementById('mapContent');
#     const zoomLevelEl = document.getElementById('zoomLevel');
#
#     function init() {{
#         renderMap();
#         renderAssets();
#         updateLegend();
#         showDebugInfo();
#         setupZoomPan();
#         updateTransform();
#     }}
#
#     // === ZOOM & PAN LOGIC ===
#     function setupZoomPan() {{
#         svg.addEventListener('wheel', (e) => {{
#             e.preventDefault();
#             const rect = svg.getBoundingClientRect();
#             const mouseX = e.clientX - rect.left;
#             const mouseY = e.clientY - rect.top;
#
#             const direction = e.deltaY < 0 ? 1 : -1;
#             const newScale = clampScale(state.scale + direction * state.zoomStep);
#
#             const scaleChange = newScale / state.scale;
#             state.panX = mouseX - (mouseX - state.panX) * scaleChange;
#             state.panY = mouseY - (mouseY - state.panY) * scaleChange;
#             state.scale = newScale;
#
#             updateTransform();
#         }}, {{ passive: false }});
#
#         svg.addEventListener('mousedown', (e) => {{
#             if (e.button !== 0) return;
#             state.isPanning = true;
#             state.startPanX = e.clientX - state.panX;
#             state.startPanY = e.clientY - state.panY;
#             svg.style.cursor = 'grabbing';
#         }});
#
#         window.addEventListener('mousemove', (e) => {{
#             if (!state.isPanning) return;
#             e.preventDefault();
#             state.panX = e.clientX - state.startPanX;
#             state.panY = e.clientY - state.startPanY;
#             updateTransform();
#         }});
#
#         window.addEventListener('mouseup', () => {{
#             if (state.isPanning) {{
#                 state.isPanning = false;
#                 svg.style.cursor = 'grab';
#             }}
#         }});
#
#         svg.addEventListener('touchstart', handleTouchStart, {{ passive: false }});
#         svg.addEventListener('touchmove', handleTouchMove, {{ passive: false }});
#         svg.addEventListener('touchend', handleTouchEnd);
#
#         document.getElementById('zoomIn').addEventListener('click', () => zoomAtCenter(state.zoomStep));
#         document.getElementById('zoomOut').addEventListener('click', () => zoomAtCenter(-state.zoomStep));
#         document.getElementById('zoomReset').addEventListener('click', () => {{
#             state.scale = 1;
#             state.panX = 0;
#             state.panY = 0;
#             updateTransform();
#         }});
#
#         let lastTap = 0;
#         svg.addEventListener('click', (e) => {{
#             const currentTime = new Date().getTime();
#             const tapLength = currentTime - lastTap;
#             if (tapLength < 300 && tapLength > 0) {{
#                 e.preventDefault();
#                 const rect = svg.getBoundingClientRect();
#                 const touchX = e.clientX - rect.left;
#                 const touchY = e.clientY - rect.top;
#
#                 const newScale = clampScale(state.scale * 1.5);
#                 const scaleChange = newScale / state.scale;
#                 state.panX = touchX - (touchX - state.panX) * scaleChange;
#                 state.panY = touchY - (touchY - state.panY) * scaleChange;
#                 state.scale = newScale;
#
#                 updateTransform();
#             }}
#             lastTap = currentTime;
#         }});
#     }}
#
#     function handleTouchStart(e) {{
#         if (e.touches.length === 1) {{
#             state.isPanning = true;
#             state.startPanX = e.touches[0].clientX - state.panX;
#             state.startPanY = e.touches[0].clientY - state.panY;
#         }} else if (e.touches.length === 2) {{
#             state.isPanning = false;
#             state.lastTouchDistance = getTouchDistance(e.touches);
#             state.lastTouchCenter = getTouchCenter(e.touches);
#         }}
#     }}
#
#     function handleTouchMove(e) {{
#         e.preventDefault();
#
#         if (e.touches.length === 1 && state.isPanning) {{
#             state.panX = e.touches[0].clientX - state.startPanX;
#             state.panY = e.touches[0].clientY - state.startPanY;
#             updateTransform();
#         }} else if (e.touches.length === 2) {{
#             const currentDistance = getTouchDistance(e.touches);
#             const currentCenter = getTouchCenter(e.touches);
#
#             if (state.lastTouchDistance > 0) {{
#                 const scaleChange = currentDistance / state.lastTouchDistance;
#                 const newScale = clampScale(state.scale * scaleChange);
#
#                 const rect = svg.getBoundingClientRect();
#                 const centerX = currentCenter.x - rect.left;
#                 const centerY = currentCenter.y - rect.top;
#
#                 state.panX = centerX - (centerX - state.panX) * (newScale / state.scale);
#                 state.panY = centerY - (centerY - state.panY) * (newScale / state.scale);
#                 state.scale = newScale;
#
#                 updateTransform();
#             }}
#
#             state.lastTouchDistance = currentDistance;
#             state.lastTouchCenter = currentCenter;
#         }}
#     }}
#
#     function handleTouchEnd() {{
#         state.isPanning = false;
#         state.lastTouchDistance = 0;
#         state.lastTouchCenter = null;
#     }}
#
#     function getTouchDistance(touches) {{
#         const dx = touches[0].clientX - touches[1].clientX;
#         const dy = touches[0].clientY - touches[1].clientY;
#         return Math.sqrt(dx * dx + dy * dy);
#     }}
#
#     function getTouchCenter(touches) {{
#         return {{
#             x: (touches[0].clientX + touches[1].clientX) / 2,
#             y: (touches[0].clientY + touches[1].clientY) / 2
#         }};
#     }}
#
#     function zoomAtCenter(delta) {{
#         const rect = svg.getBoundingClientRect();
#         const centerX = rect.width / 2;
#         const centerY = rect.height / 2;
#
#         const newScale = clampScale(state.scale + delta);
#         const scaleChange = newScale / state.scale;
#         state.panX = centerX - (centerX - state.panX) * scaleChange;
#         state.panY = centerY - (centerY - state.panY) * scaleChange;
#         state.scale = newScale;
#
#         updateTransform();
#     }}
#
#     function clampScale(value) {{
#         return Math.max(state.minScale, Math.min(state.maxScale, value));
#     }}
#
#     function updateTransform() {{
#         const width = MAP_WIDTH / state.scale;
#         const height = MAP_HEIGHT / state.scale;
#         const x = -state.panX / state.scale;
#         const y = -state.panY / state.scale;
#
#         svg.setAttribute('viewBox', `${{x}} ${{y}} ${{width}} ${{height}}`);
#         zoomLevelEl.textContent = Math.round(state.scale * 100) + '%';
#     }}
#
#     function renderMap() {{
#         const layer = document.getElementById('workshopsLayer');
#         layer.innerHTML = '';
#         workshops.forEach(workshop => renderWorkshop(workshop, layer));
#     }}
#
#     function renderWorkshop(workshop, layer) {{
#         const color = workshop.color || '#546E7A';
#         let coordinates = null;
#
#         if (workshop.geometry &&
#             workshop.geometry.type === 'polygon' &&
#             Array.isArray(workshop.geometry.coordinates) &&
#             workshop.geometry.coordinates.length >= 3) {{
#             coordinates = workshop.geometry.coordinates;
#         }}
#         else if (workshop.workshop_width && workshop.workshop_height) {{
#             const x = workshop.offset_x || 0;
#             const y = workshop.offset_y || 0;
#             const w = workshop.workshop_width;
#             const h = workshop.workshop_height;
#
#             coordinates = [
#                 [x, y],
#                 [x + w, y],
#                 [x + w, y + h],
#                 [x, y + h]
#             ];
#         }}
#         else {{
#             return;
#         }}
#
#         const points = coordinates.map(coord => `${{coord[0]}},${{coord[1]}}`).join(' ');
#         const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
#         polygon.setAttribute('points', points);
#         polygon.setAttribute('fill', color);
#         polygon.setAttribute('class', 'workshop-polygon');
#         polygon.setAttribute('data-workshop-id', workshop.workshop_id);
#
#         layer.appendChild(polygon);
#
#         const centroid = calculateCentroid(coordinates);
#         const textGroup = document.createElementNS('http://www.w3.org/2000/svg', 'g');
#         textGroup.style.pointerEvents = 'none';
#
#         const nameText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
#         nameText.setAttribute('x', centroid.x);
#         nameText.setAttribute('y', centroid.y - 10);
#         nameText.setAttribute('class', 'workshop-text workshop-name');
#         nameText.textContent = workshop.name;
#
#         const codeText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
#         codeText.setAttribute('x', centroid.x);
#         codeText.setAttribute('y', centroid.y + 20);
#         codeText.setAttribute('class', 'workshop-text workshop-code');
#         codeText.textContent = workshop.code;
#
#         textGroup.appendChild(nameText);
#         textGroup.appendChild(codeText);
#         layer.appendChild(textGroup);
#     }}
#
#     // === РЕНДЕРИНГ АКТИВОВ ===
#     function renderAssets() {{
#         const layer = document.getElementById('assetsLayer');
#         layer.innerHTML = '';
#         assets.forEach(asset => renderAsset(asset, layer));
#     }}
#
#     function renderAsset(asset, layer) {{
#         const iconSize = 40 * (asset.scale / 100);  // Базовый размер 40px, масштабируется
#         const rotation = asset.rotation || 0;
#
#         // Создаем группу для актива
#         const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
#         group.setAttribute('class', 'asset-icon');
#         group.setAttribute('data-asset-id', asset.asset_id);
#         group.setAttribute('transform', `translate(${{asset.x}}, ${{asset.y}}) rotate(${{rotation}})`);
#
#         // Создаем круглый фон для иконки
#         const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
#         circle.setAttribute('r', iconSize / 2);
#         circle.setAttribute('fill', '#fff');
#         circle.setAttribute('stroke', '#333');
#         circle.setAttribute('stroke-width', '2');
#
#         // Создаем текст иконки
#         const iconText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
#         iconText.setAttribute('text-anchor', 'middle');
#         iconText.setAttribute('dominant-baseline', 'central');
#         iconText.setAttribute('font-size', iconSize * 0.6);
#         iconText.textContent = asset.icon;
#
#         // Создаем подпись с названием актива
#         const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
#         label.setAttribute('class', 'asset-label');
#         label.setAttribute('y', iconSize / 2 + 15);
#         label.setAttribute('font-size', '12');
#         label.textContent = asset.inventory_id;
#
#         group.appendChild(circle);
#         group.appendChild(iconText);
#         group.appendChild(label);
#         layer.appendChild(group);
#     }}
#
#     function calculateCentroid(coordinates) {{
#         let x = 0, y = 0;
#         const n = coordinates.length;
#         for (let i = 0; i < n; i++) {{
#             x += coordinates[i][0];
#             y += coordinates[i][1];
#         }}
#         return {{ x: x / n, y: y / n }};
#     }}
#
#     function updateLegend() {{
#         const legendContent = document.getElementById('legendContent');
#         legendContent.innerHTML = '';
#         workshops.forEach(workshop => {{
#             const color = workshop.color || '#546E7A';
#             const item = document.createElement('div');
#             item.className = 'legend-item';
#             item.innerHTML = `
#                 <span class="legend-color" style="background: ${{color}}"></span>
#                 <div>
#                     <strong>${{workshop.code}}</strong><br>
#                     <span style="font-size: 0.9em; color: #555;">${{workshop.name}}</span>
#                 </div>
#             `;
#             legendContent.appendChild(item);
#         }});
#     }}
#
#     function showDebugInfo() {{
#         const debugInfo = workshops.map(w => {{
#             let status = '';
#             if (w.geometry) {{
#                 status = '✅ geometry из БД';
#             }} else if (w.workshop_width && w.workshop_height) {{
#                 status = `📐 ${{w.workshop_width}}x${{w.workshop_height}} (offset: ${{w.offset_x}},${{w.offset_y}})`;
#             }} else {{
#                 status = '❌ нет координат';
#             }}
#             return `<div><strong>${{w.code}}</strong>: ${{status}} | Цвет: <span style="color:${{w.color || '#546E7A'}}">■</span> ${{w.color || '#546E7A'}}</div>`;
#         }}).join('');
#
#         if (debugInfo) {{
#             document.getElementById('debug').innerHTML = '<strong>Информация о цехах:</strong><br>' + debugInfo;
#             document.getElementById('debug').style.display = 'block';
#         }}
#     }}
#
#     window.addEventListener('DOMContentLoaded', init);
# </script>
# </body>
# </html>
# """
#     return HTMLResponse(content=html_content)
#
#
# @router_map.get("/map-fetch")
# async def serve_map_html():
#     """Отдает статический HTML-файл карты, который сам делает запросы к API"""
#     # Путь к файлу map.html относительно корня проекта
#     file_path = os.path.join("app", "frontend", "map.html")
#
#     if os.path.exists(file_path):
#         return FileResponse(file_path, media_type="text/html")
#
#     return {"error": "Файл map.html не найден. Создайте его в app/frontend/"}

import json
import os

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.functions import current_user
from starlette.responses import HTMLResponse, FileResponse

from app.database.connection import get_db
from app.database.map_assets.crud_workshop import get_all_workshop

# 2. Получаем все активные позиции активов
from sqlalchemy import select
from app.models.map_assets.asset_position import AssetPosition
from app.models.assets.asset import Asset
from app.services.auth.auth_service import require_authorized_user

router_map = APIRouter(tags=["workshops"])

# ==============================================================================
# === ЭНДПОИНТ ДЛЯ ГЕНЕРАЦИИ HTML-КАРТЫ ЦЕХОВ ===
# ==============================================================================
@router_map.get("/map-crud", response_class=HTMLResponse)
async def get_all_workshops_map(
        db: AsyncSession = Depends(get_db),
):
    """Генерирует и отдает HTML-страницу с интерактивной картой цехов и активов"""

    # Фиксированные размеры карты
    MAP_WIDTH = 2000
    MAP_HEIGHT = 2000

    # 1. Получаем все активные цеха из PostgreSQL
    workshops = await get_all_workshop(db, skip=0, limit=1000)

    result = await db.execute(
        select(AssetPosition)
        .where(AssetPosition.is_active == True)
        .join(Asset, AssetPosition.asset_id == Asset.asset_id)
        .where(Asset.asset_status != "Списание")  # Только активные активы
    )
    positions = result.scalars().all()

    # 3. Преобразуем цеха в словари
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

    # 4. Преобразуем позиции активов в словари с информацией об активе
    assets_data = []
    for pos in positions:
        asset = pos.asset
        if not asset:
            continue

        # Определяем иконку в зависимости от типа актива
        icon = "📦"  # Дефолтная иконка
        if asset.asset_type_id:
            # Можно добавить маппинг типов к иконкам
            icon = "⚙️"  # Оборудование

        assets_data.append({
            "position_id": pos.id,
            "asset_id": asset.asset_id,
            "name": asset.name,
            "inventory_id": asset.inventory_id,
            "asset_status": asset.asset_status,
            "x": pos.x,
            "y": pos.y,
            "rotation": pos.rotation,
            "scale": pos.scale,
            "workshop_id": pos.workshop_id,
            "icon": icon
        })

    # 5. Сериализуем данные
    workshops_json = json.dumps(workshops_data, ensure_ascii=False)
    assets_json = json.dumps(assets_data, ensure_ascii=False)

    # 6. Формируем HTML с отображением активов (ОПТИМИЗИРОВАН ДЛЯ МОБИЛЬНЫХ)
    html_content = f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <meta name="apple-mobile-web-app-capable" content="yes">
    <meta name="mobile-web-app-capable" content="yes">
    <title>Карта завода</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 10px;
            min-height: 100vh;
            overflow-x: hidden;
            touch-action: none;
        }}

        .container {{ 
            max-width: 100%; 
            margin: 0 auto; 
        }}

        h1 {{
            text-align: center;
            margin-bottom: 15px;
            color: #fff;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
            font-size: 24px;
            font-weight: 600;
        }}

        .map-wrapper {{
            background: white;
            border-radius: 12px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            padding: 15px;
            overflow: hidden;
            position: relative;
            touch-action: none;
        }}

        .map-svg {{
            width: 100%;
            height: auto;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            background: #fafafa;
            cursor: grab;
            display: block;
            touch-action: none;
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

        /* Стили для иконок активов */
        .asset-icon {{
            cursor: pointer;
            transition: all 0.2s ease;
            filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3));
        }}

        .asset-icon:hover {{
            filter: drop-shadow(4px 4px 8px rgba(0,0,0,0.5));
        }}

        .asset-label {{
            font-family: Arial, sans-serif;
            font-size: 12px;
            font-weight: bold;
            fill: #333;
            text-anchor: middle;
            pointer-events: none;
            text-shadow: 1px 1px 2px rgba(255,255,255,0.8);
        }}

        /* Zoom Controls - оптимизированы для мобильных */
        .zoom-controls {{
            position: absolute;
            top: 20px;
            right: 20px;
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
            touch-action: manipulation;
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
            margin-top: 15px;
            padding: 15px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.1);
        }}

        .legend h3 {{ 
            margin-bottom: 12px; 
            color: #333; 
            font-size: 18px; 
        }}

        .legend-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 8px;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            padding: 6px 10px;
            background: #f9f9f9;
            border-radius: 6px;
            transition: background 0.2s;
        }}

        .legend-item:hover {{ 
            background: #eef2f7; 
        }}

        .legend-color {{
            display: inline-block;
            width: 20px;
            height: 20px;
            margin-right: 10px;
            border: 2px solid #333;
            border-radius: 4px;
        }}

        .map-info {{
            background: #fff3cd;
            color: #856404;
            padding: 8px 12px;
            margin-bottom: 12px;
            border-radius: 6px;
            border-left: 4px solid #ffc107;
            font-family: monospace;
            font-size: 12px;
        }}

        .stats-info {{
            background: #d1ecf1;
            color: #0c5460;
            padding: 8px 12px;
            margin-bottom: 12px;
            border-radius: 6px;
            border-left: 4px solid #17a2b8;
            font-family: monospace;
            font-size: 12px;
        }}

        .debug-info {{
            background: #e3f2fd;
            color: #0d47a1;
            padding: 12px;
            margin: 8px 0;
            border-radius: 4px;
            font-family: monospace;
            font-size: 12px;
            line-height: 1.5;
        }}

        .help-hint {{
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 11px;
            z-index: 10;
            pointer-events: none;
        }}

        /* Адаптивная верстка для мобильных */
        @media screen and (max-width: 768px) {{
            body {{ 
                padding: 8px; 
            }}
            h1 {{ 
                font-size: 20px; 
                margin-bottom: 12px; 
            }}
            .map-wrapper {{ 
                padding: 12px; 
                border-radius: 10px;
            }}
            .zoom-controls {{ 
                top: 15px; 
                right: 15px; 
            }}
            .zoom-btn {{ 
                width: 40px; 
                height: 40px; 
                font-size: 20px; 
            }}
            .legend {{ 
                margin-top: 12px; 
                padding: 12px; 
            }}
            .legend-grid {{ 
                grid-template-columns: 1fr; 
            }}
            .help-hint {{ 
                display: none; 
            }}
        }}

        @media screen and (max-width: 480px) {{
            body {{ 
                padding: 5px; 
            }}
            h1 {{ 
                font-size: 18px; 
            }}
            .map-wrapper {{ 
                padding: 10px; 
            }}
            .workshop-name {{ font-size: 18px; }}
            .workshop-code {{ font-size: 14px; }}
        }}

        /* Поддержка темной темы */
        @media (prefers-color-scheme: dark) {{
            body {{
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            }}
            .map-wrapper, .legend {{
                background: #1e1e1e;
            }}
            .map-svg {{
                background: #2a2a2a;
                border-color: #444;
            }}
        }}
    </style>
</head>
<body>
<div class="container">
    <h1>🏭 Карта производственных цехов</h1>

    <div class="map-wrapper">
        <div class="map-info"> Размер карты: {MAP_WIDTH}×{MAP_HEIGHT} px | Колесо мыши/щипок — zoom, перетаскивание — pan</div>
        <div class="stats-info">📊 Цехов: {len(workshops_data)} | Активов на карте: {len(assets_data)}</div>

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
                <g id="assetsLayer"></g>
            </g>
        </svg>

        <div class="help-hint">🖱️ Колесо: zoom | Зажать ЛКМ: перемещение | Клик по активу: информация</div>
    </div>

    <div class="legend">
        <h3>📋 Легенда цехов</h3>
        <div class="legend-grid" id="legendContent"></div>
    </div>

    <div id="debug" class="debug-info" style="display: none;"></div>
</div>

<script>
    const workshops = {workshops_json};
    const assets = {assets_json};
    const MAP_WIDTH = {MAP_WIDTH};
    const MAP_HEIGHT = {MAP_HEIGHT};

    // === ZOOM & PAN STATE ===
    const state = {{
        scale: 1,
        panX: 0,
        panY: 0,
        minScale: 0.5,
        maxScale: 2,
        zoomStep: 0.1,
        isPanning: false,
        startPanX: 0,
        startPanY: 0,
        lastTouchDistance: 0,
        lastTouchCenter: null
    }};

    const svg = document.getElementById('mapSvg');
    const mapContent = document.getElementById('mapContent');
    const zoomLevelEl = document.getElementById('zoomLevel');

    function init() {{
        renderMap();
        renderAssets();
        updateLegend();
        showDebugInfo();
        setupZoomPan();
        updateTransform();
    }}

    // === ZOOM & PAN LOGIC ===
    function setupZoomPan() {{
        // Mouse wheel zoom
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

        // Mouse pan
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

        // Touch events для мобильных
        svg.addEventListener('touchstart', handleTouchStart, {{ passive: false }});
        svg.addEventListener('touchmove', handleTouchMove, {{ passive: false }});
        svg.addEventListener('touchend', handleTouchEnd);

        // Кнопки управления
        document.getElementById('zoomIn').addEventListener('click', () => zoomAtCenter(state.zoomStep));
        document.getElementById('zoomOut').addEventListener('click', () => zoomAtCenter(-state.zoomStep));
        document.getElementById('zoomReset').addEventListener('click', () => {{
            state.scale = 1;
            state.panX = 0;
            state.panY = 0;
            updateTransform();
        }});

        // Double tap zoom
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

    function handleTouchStart(e) {{
        if (e.touches.length === 1) {{
            state.isPanning = true;
            state.startPanX = e.touches[0].clientX - state.panX;
            state.startPanY = e.touches[0].clientY - state.panY;
        }} else if (e.touches.length === 2) {{
            state.isPanning = false;
            state.lastTouchDistance = getTouchDistance(e.touches);
            state.lastTouchCenter = getTouchCenter(e.touches);
        }}
    }}

    function handleTouchMove(e) {{
        e.preventDefault();

        if (e.touches.length === 1 && state.isPanning) {{
            state.panX = e.touches[0].clientX - state.startPanX;
            state.panY = e.touches[0].clientY - state.startPanY;
            updateTransform();
        }} else if (e.touches.length === 2) {{
            const currentDistance = getTouchDistance(e.touches);
            const currentCenter = getTouchCenter(e.touches);

            if (state.lastTouchDistance > 0) {{
                const scaleChange = currentDistance / state.lastTouchDistance;
                const newScale = clampScale(state.scale * scaleChange);

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
            return;
        }}

        const points = coordinates.map(coord => `${{coord[0]}},${{coord[1]}}`).join(' ');
        const polygon = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
        polygon.setAttribute('points', points);
        polygon.setAttribute('fill', color);
        polygon.setAttribute('class', 'workshop-polygon');
        polygon.setAttribute('data-workshop-id', workshop.workshop_id);

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

    // === РЕНДЕРИНГ АКТИВОВ ===
    function renderAssets() {{
        const layer = document.getElementById('assetsLayer');
        layer.innerHTML = '';
        assets.forEach(asset => renderAsset(asset, layer));
    }}

    function renderAsset(asset, layer) {{
        const iconSize = 40 * (asset.scale / 100);  // Базовый размер 40px, масштабируется
        const rotation = asset.rotation || 0;

        // Создаем группу для актива
        const group = document.createElementNS('http://www.w3.org/2000/svg', 'g');
        group.setAttribute('class', 'asset-icon');
        group.setAttribute('data-asset-id', asset.asset_id);
        group.setAttribute('transform', `translate(${{asset.x}}, ${{asset.y}}) rotate(${{rotation}})`);

        // Создаем круглый фон для иконки
        const circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
        circle.setAttribute('r', iconSize / 2);
        circle.setAttribute('fill', '#fff');
        circle.setAttribute('stroke', '#333');
        circle.setAttribute('stroke-width', '2');

        // Создаем текст иконки
        const iconText = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        iconText.setAttribute('text-anchor', 'middle');
        iconText.setAttribute('dominant-baseline', 'central');
        iconText.setAttribute('font-size', iconSize * 0.6);
        iconText.textContent = asset.icon;

        // Создаем подпись с названием актива
        const label = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        label.setAttribute('class', 'asset-label');
        label.setAttribute('y', iconSize / 2 + 15);
        label.setAttribute('font-size', '12');
        label.textContent = asset.inventory_id;

        group.appendChild(circle);
        group.appendChild(iconText);
        group.appendChild(label);       
        layer.appendChild(group);
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
                status = `📐 ${{w.workshop_width}}x${{w.workshop_height}} (offset: ${{w.offset_x}},${{w.offset_y}})`;
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


@router_map.get("/map-fetch")
async def serve_map_html():
    """Отдает статический HTML-файл карты, который сам делает запросы к API"""
    # Путь к файлу map.html относительно корня проекта
    file_path = os.path.join("app", "frontend", "map.html")

    if os.path.exists(file_path):
        return FileResponse(file_path, media_type="text/html")

    return {"error": "Файл map.html не найден. Создайте его в app/frontend/"}