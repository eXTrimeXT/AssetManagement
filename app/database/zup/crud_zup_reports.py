from typing import Optional, Sequence, List
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.report import Report
from app.schemas.zup.report_schemas import AttendanceData


async def create_report(db: AsyncSession, attendance_data: List[AttendanceData]) -> List[Report]:
    """Создать отчёт (удаляет старые записи)"""
    # Удаляем старые записи
    await db.execute(delete(Report))

    # Создаём новые
    reports = []
    for data in attendance_data:
        report = Report(
            department_name=data.department,
            total_employees=data.total_employees,
            present_employees=data.present_employees,
            absent_employees=data.absent_employees,
            attendance_value=data.attendance_value
        )
        db.add(report)
        reports.append(report)

    await db.commit()
    for report in reports:
        await db.refresh(report)
    return reports


async def get_reports_list(db: AsyncSession) -> Sequence[Report]:
    query = select(Report)
    result = await db.execute(query)
    return result.scalars().all()