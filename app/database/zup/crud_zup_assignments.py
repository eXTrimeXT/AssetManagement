from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.zup.assignment import Assignment
from app.schemas.zup.assignment_schemas import AssignmentCreate


async def get_assignment_by_id(db: AsyncSession, id: str) -> Optional[Assignment]:
    result = await db.execute(select(Assignment).where(Assignment.id == id))
    return result.scalar_one_or_none()


async def create_assignment(db: AsyncSession, assignment_in: AssignmentCreate) -> Assignment:
    db_assignment = Assignment(**assignment_in.model_dump())
    db.add(db_assignment)
    await db.commit()
    await db.refresh(db_assignment)
    return db_assignment


async def get_assignments_list(db: AsyncSession, skip: int = 0, limit: int = 50) -> Sequence[Assignment]:
    query = select(Assignment).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


async def upsert_assignment(db: AsyncSession, assignment_data: dict) -> Assignment:
    assignment = await get_assignment_by_id(db, assignment_data["id"])

    if assignment:
        for key, value in assignment_data.items():
            if hasattr(assignment, key):
                setattr(assignment, key, value)
    else:
        assignment = Assignment(**assignment_data)
        db.add(assignment)

    await db.commit()
    await db.refresh(assignment)
    return assignment