from fastapi import APIRouter

# Корневой роутер (/)
router_root = APIRouter(tags=["root"])

# Корневая ручка
@router_root.get("/")
async def root():
    return {
        "message": "IT Assets RESTful API",
        "docs": "/docs",
        "redoc": "/redoc",
        "api": "/api",
        "assets": "/api/assets",
        "assets-types": "/api/assets-types",
    }