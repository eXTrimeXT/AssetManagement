from app.routers.assets.router_asset_status import router_asset_status
from app.routers.assets.router_asset_type import router_asset_types
from app.routers.assets.router_asset_model import router_asset_models
from app.routers.assets.router_asset import router_assets
from app.routers.assets.router_asset_assignment import router_asset_assignments
from app.routers.assets.router_inventorization import router_inventorization

__all__ = [
    "router_asset_status",
    "router_asset_types",
    "router_asset_models",
    "router_assets",
    "router_asset_assignments",
    "router_inventorization"
]