from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.connection import get_db
from app.schemas.pc_data.pc_data_schemas import PCDataCreate, PCDataResponse
from app.database.crud_pc_data import create_or_update_pc_data, get_pc_data, get_all_pc_data, update_pc_data, delete_pc_data

router_pc_data = APIRouter(prefix="/pc-data", tags=["pc_data"])

@router_pc_data.post("/", response_model=PCDataResponse, status_code=201)
async def endpoint_create_pc_data(pc_data: PCDataCreate, db: AsyncSession = Depends(get_db)):
    return await create_or_update_pc_data(db, pc_data)

@router_pc_data.get("/{username}", response_model=PCDataResponse)
async def endpoint_read_pc_data(username: str, db: AsyncSession = Depends(get_db)):
    db_pc = await get_pc_data(db, username)
    if db_pc is None:
        raise HTTPException(status_code=404, detail="PC data not found")
    return db_pc

@router_pc_data.get("/", response_model=list[PCDataResponse])
async def endpoint_read_all_pc_data(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    return await get_all_pc_data(db, skip, limit)

@router_pc_data.patch("/{username}", response_model=PCDataResponse)
async def endpoint_update_pc_data(username: str, pc_data: PCDataCreate, db: AsyncSession = Depends(get_db)):
    db_pc = await update_pc_data(db, username, pc_data)
    if db_pc is None:
        raise HTTPException(status_code=404, detail="PC data not found")
    return db_pc

@router_pc_data.delete("/{username}", status_code=204)
async def endpoint_delete_pc_data(username: str, db: AsyncSession = Depends(get_db)):
    db_pc = await delete_pc_data(db, username)
    if db_pc is None:
        raise HTTPException(status_code=404, detail="PC data not found")
    return None