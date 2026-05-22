from typing import Any, Literal, List, TypeVar, Awaitable, Callable, Optional
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.User import User
from app.database.connection import get_db
from app.service.auth.auth_service import require_authorized_user

T = TypeVar('T')

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def has_read_permission(user: User, group_name: str | None) -> bool:
    """Проверяет право `read` на группу. Root имеет доступ ко всему."""
    # === ROOT-ПРОВЕРКА: если user_tab_id == "root" — разрешаем всё ===
    if user.user_tab_id == "root":
        return True

    if not group_name or not user.permissions:
        return False
    group_perms = user.permissions.get(group_name)
    return bool(group_perms and group_perms.get("read"))

def has_write_permission(user: User, group_name: str | None) -> bool:
    # === ROOT-ПРОВЕРКА: если user_tab_id == "root" — разрешаем всё ===
    if user.user_tab_id == "root":
        return True

    if not group_name or not user.permissions:
        return False
    group_perms = user.permissions.get(group_name)
    return bool(group_perms and group_perms.get("write"))

def has_access(user: User, group_name: str | None, access_type: Literal["read", "write"] | None = None) -> bool:
    # === ROOT-ПРОВЕРКА: если user_tab_id == "root" — разрешаем всё ===
    if user.user_tab_id == "root":
        return True
    
    if not group_name or not user.permissions:
        return False
    group_perms = user.permissions.get(group_name)
    if not group_perms:
        return False
    if access_type is None:
        return bool(group_perms.get("read") or group_perms.get("write"))
    return bool(group_perms.get(access_type))

def _get_nested_attr(obj: Any, field_path: str) -> str | None:
    """Безопасно извлекает значение вложенного атрибута по пути через точку."""
    if not obj or not field_path:
        return None
    current = obj
    for attr in field_path.split("."):
        if current is None:
            return None
        current = getattr(current, attr, None)
    return str(current)

# === ЗАВИСИМОСТИ-ФИЛЬТРЫ ===

class FilteredByRead:
    def __init__(self, crud_func: Callable[..., Awaitable[List[T]]], group_field: str, **extra_params):
        self.crud_func = crud_func
        self.group_field = group_field
        self.extra_params = extra_params

    async def __call__(
            self,
            db: AsyncSession = Depends(get_db),
            current_user: User = Depends(require_authorized_user),
            # === ЯВНЫЕ ПАРАМЕТРЫ ДЛЯ /docs И ПЕРЕДАЧИ В CRUD ===
            skip: int = Query(0, ge=0),
            limit: int = Query(50, le=100),
            class_id: Optional[int] = Query(None)
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}
        if class_id is not None:
            params["class_id"] = class_id

        items = await self.crud_func(db, **params)
        return [item for item in items if has_read_permission(current_user, _get_nested_attr(item, self.group_field))]


class FilteredByWrite:
    def __init__(self, crud_func: Callable[..., Awaitable[List[T]]], group_field: str, **extra_params):
        self.crud_func = crud_func
        self.group_field = group_field
        self.extra_params = extra_params

    async def __call__(
            self,
            db: AsyncSession = Depends(get_db),
            current_user: User = Depends(require_authorized_user),
            skip: int = Query(0, ge=0),
            limit: int = Query(50, le=100),
            class_id: Optional[int] = Query(None)
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}
        if class_id is not None:
            params["class_id"] = class_id

        items = await self.crud_func(db, **params)
        return [item for item in items if has_write_permission(current_user, _get_nested_attr(item, self.group_field))]


class FilteredByAccess:
    def __init__(self, crud_func: Callable[..., Awaitable[List[T]]], group_field: str, access_type: Literal["read", "write"] | None = "read", **extra_params):
        self.crud_func = crud_func
        self.group_field = group_field
        self.access_type = access_type
        self.extra_params = extra_params

    async def __call__(
            self,
            db: AsyncSession = Depends(get_db),
            current_user: User = Depends(require_authorized_user),
    ) -> List[T]:
        params = {**self.extra_params}
        items = await self.crud_func(db, **params)
        return [item for item in items if has_access(current_user, _get_nested_attr(item, self.group_field), self.access_type)]


class FilteredByAccessWithParams:
    def __init__(self, crud_func: Callable[..., Awaitable[List[T]]], group_field: str, access_type: Literal["read", "write"] | None = "read", **extra_params):
        self.crud_func = crud_func
        self.group_field = group_field
        self.access_type = access_type
        self.extra_params = extra_params

    async def __call__(
            self,
            db: AsyncSession = Depends(get_db),
            current_user: User = Depends(require_authorized_user),
            skip: int = Query(0, ge=0),
            limit: int = Query(50, le=100),
            class_id: Optional[int] = Query(None)
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}
        if class_id is not None:
            params["class_id"] = class_id

        items = await self.crud_func(db, **params)
        return [item for item in items if has_access(current_user, _get_nested_attr(item, self.group_field), self.access_type)]