from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from app.database.connection import get_db
from app.database.analytics.crud_analytics import (
    get_assets_by_status,
    get_changes_heatmap,
    get_user_activity,
    get_asset_lifecycle,
    get_dashboard_summary,
    get_service_analytics,
    get_write_off_analytics,
    get_changes_trend,
)
from app.schemas.analytics.AnalyticsByGroup import CountByGroupResponse
from app.schemas.analytics.AssetLifecycle import AssetLifecycleEntry
from app.schemas.analytics.FieldChangeHeatmap import FieldChangeHeatmapResponse
from app.schemas.analytics.UserActivity import UserActivityResponse
from app.services.auth.auth_service import require_authorized_user

router_analytics = APIRouter(prefix="/analytics", tags=["Analytics"])


@router_analytics.get(
    "/assets/by-status",
    response_model=List[CountByGroupResponse],
    summary="Распределение активов по статусам / Assets Distribution by Status",
    description=(
            "RU: Возвращает агрегированное распределение активов по их статусам "
            "(количество активов в каждом статусе). Полезно для построения диаграмм "
            "и оценки текущего состояния парка активов. Требуется авторизация пользователя.\n\n"
            "EN: Returns an aggregated distribution of assets by their status "
            "(number of assets in each status). Useful for building charts "
            "and evaluating the current state of the asset fleet. User authorization is required."
    )
)
async def assets_by_status(db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Распределение активов по статусам"""
    return await get_assets_by_status(db)


@router_analytics.get(
    "/changes/heatmap",
    response_model=List[FieldChangeHeatmapResponse],
    summary="Тепловая карта изменений полей активов / Asset Fields Change Heatmap",
    description=(
            "RU: Возвращает статистику частоты изменения полей активов — "
            "какие поля редактируются чаще всего. Полезно для выявления наиболее "
            "динамичных атрибутов и оптимизации процессов учёта. Требуется авторизация.\n\n"
            "EN: Returns statistics on the frequency of asset field changes — "
            "which fields are edited most often. Useful for identifying the most "
            "dynamic attributes and optimizing accounting processes. Authorization is required."
    )
)
async def changes_heatmap(db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Какие поля активов меняются чаще всего"""
    return await get_changes_heatmap(db)


@router_analytics.get(
    "/users/activity",
    response_model=List[UserActivityResponse],
    summary="Топ пользователей по активности / Top Users by Activity",
    description=(
            "RU: Возвращает список наиболее активных пользователей по количеству внесённых изменений. "
            "Поддерживает параметр `limit` для ограничения размера выборки (по умолчанию 20). "
            "Полезно для анализа нагрузки на сотрудников и выявления ключевых операторов. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns a list of the most active users by the number of changes made. "
            "Supports the `limit` parameter to restrict the sample size (default is 20). "
            "Useful for analyzing employee workload and identifying key operators. "
            "User authorization is required."
    )
)
async def user_activity(limit: int = 20, db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Топ пользователей по активности (количество изменений)"""
    return await get_user_activity(db, limit=limit)


@router_analytics.get(
    "/assets/lifecycle/{asset_id}",
    response_model=List[AssetLifecycleEntry],
    summary="Жизненный цикл актива / Asset Lifecycle Timeline",
    description=(
            "RU: Возвращает полную историю жизненного цикла конкретного актива по его `asset_id` — "
            "все события от создания до текущего состояния (изменения, перемещения, назначения, "
            "обслуживания и т.д.) в формате таймлайна. Если данных нет — возвращается ошибка 404. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns the complete lifecycle history of a specific asset by its `asset_id` — "
            "all events from creation to the current state (changes, moves, assignments, "
            "maintenance, etc.) in a timeline format. If no data is available, a 404 error is returned. "
            "User authorization is required."
    )
)
async def asset_lifecycle(asset_id: int, db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Полный timeline жизни конкретного актива"""
    history = await get_asset_lifecycle(db, asset_id)
    if not history:
        raise HTTPException(status_code=404, detail="No lifecycle data for this asset")
    return history

@router_analytics.get(
    "/dashboard/summary",
    summary="Сводная статистика для дашборда / Dashboard Summary Statistics",
    description=(
            "RU: Возвращает общую сводную статистику для главного дашборда: "
            "количество активов по типам, по цехам/департаментам, топ активных пользователей "
            "и другие агрегированные показатели. Используется для отображения ключевых метрик "
            "на стартовой странице. Требуется авторизация пользователя.\n\n"
            "EN: Returns general summary statistics for the main dashboard: "
            "number of assets by type, by workshop/department, top active users, "
            "and other aggregated metrics. Used to display key metrics on the home page. "
            "User authorization is required."
    )
)
async def dashboard_summary(db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Общая статистика для дашборда: активы по типам, цехам, топ пользователей"""
    return await get_dashboard_summary(db)

@router_analytics.get(
    "/service/analytics",
    summary="Аналитика по обслуживанию / Service Analytics",
    description=(
            "RU: Возвращает аналитику по техническому обслуживанию активов: "
            "количество просроченных ТО, предстоящих ТО, средний период между обслуживаниями "
            "и другие связанные метрики. Полезно для планирования ремонтов и контроля соблюдения регламентов. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns analytics on asset technical maintenance: "
            "number of overdue maintenance, upcoming maintenance, average period between services, "
            "and other related metrics. Useful for planning repairs and monitoring compliance with regulations. "
            "User authorization is required."
    )
)
async def service_analytics(db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Аналитика по обслуживанию: просроченные ТО, предстоящие ТО, средний период"""
    return await get_service_analytics(db)

@router_analytics.get(
    "/write-offs/analytics",
    summary="Аналитика по списаниям активов / Asset Write-Off Analytics",
    description=(
            "RU: Возвращает аналитику по списаниям активов: распределение по статусам, "
            "основным причинам списания и месячный тренд количества списаний. "
            "Помогает оценить динамику выбытия активов и выявить типичные причины. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns analytics on asset write-offs: distribution by status, "
            "main write-off reasons, and monthly trend of write-off counts. "
            "Helps evaluate the dynamics of asset disposal and identify typical reasons. "
            "User authorization is required."
    )
)
async def write_off_analytics(db: AsyncSession = Depends(get_db), current_user=Depends(require_authorized_user)):
    """Аналитика по списаниям: статусы, причины, месячный тренд"""
    return await get_write_off_analytics(db)

@router_analytics.get(
    "/changes/trend",
    summary="Тренд изменений активов / Asset Changes Trend",
    description=(
            "RU: Возвращает тренд изменений активов за последние N дней "
            "(параметр `days`, по умолчанию 30, диапазон от 1 до 365). "
            "Полезно для анализа динамики активности в системе и выявления пиковых периодов. "
            "Требуется авторизация пользователя.\n\n"
            "EN: Returns the trend of asset changes over the last N days "
            "(the `days` parameter, default is 30, range from 1 to 365). "
            "Useful for analyzing the dynamics of system activity and identifying peak periods. "
            "User authorization is required."
    )
)
async def changes_trend(
        days: int = Query(30, ge=1, le=365, description="Количество дней для анализа"),
        db: AsyncSession = Depends(get_db),
        current_user=Depends(require_authorized_user)
):
    """Тренд изменений за последние N дней (по умолчанию 30)"""
    return await get_changes_trend(db, days=days)