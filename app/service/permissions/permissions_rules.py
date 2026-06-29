import logging
from typing import Any, Literal, List, TypeVar, Awaitable, Callable, Optional
from fastapi import Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.User import User
from app.database.connection import get_db
from app.service.auth.auth_service import require_authorized_user

logger = logging.getLogger(__name__)

T = TypeVar('T')

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

def check_root(user_tab_id):
    """Проверяем является ли текущий пользователь root-пользователем, проверка и разрешение на `всё`"""
    return user_tab_id == "root"

def check_read(user_tab_id):
    """
        Проверяем является ли текущий пользователь `read`-пользователем
        Проверка и разрешение только на `чтение`.
        """
    return user_tab_id == "read"

def check_write(user_tab_id):
    """
        Проверяем является ли текущий пользователь `write`-пользователем,
        Проверка и разрешение только на `запись`, `создание`, `удаление`, `активацию`, `деактивацию`.
    """
    return user_tab_id == "write"

def check_android(user_tab_id):
    return user_tab_id == "android"

def has_android_sender_permission(user: User) -> bool:
    """Проверяет, может ли пользователь отправлять данные для этого устройства"""
    if check_root(user.user_tab_id):
        return True
    if check_android(user.user_tab_id):
        return True  # android может управлять данными для любого устройства
    return False

def has_read_permission(user: User, group_name: str | None) -> bool:
    """
        Проверяет право `read` на группу.
        Пользователь Root имеет доступ ко всему.
        Пользователь read может просматривать всё.
    """
    if check_root(user.user_tab_id):
        return True

    if check_read(user.user_tab_id):
        return True

    # Если у актива нет группы разрешаем просмотр этого актива
    if group_name is None:
        return True

    if not user.permissions:
        return False
    group_perms = user.permissions.get(group_name)
    return bool(group_perms and group_perms.get("read"))

def has_write_permission(user: User, group_name: str | None) -> bool:
    """
        Проверяет право `write` на группу.
        Пользователь Root имеет доступ ко всему.
        Пользователь write имеет доступ на запись, создание, удаление.
    """
    if check_root(user.user_tab_id):
        return True

    if check_write(user.user_tab_id):
        return True

    # Если у актива нет группы также разрешаем редактирование
    if group_name is None:
        return True

    if not user.permissions:
        # logger.warning(f"{user}:{group_name}: FALSE")
        return False
    group_perms = user.permissions.get(group_name)
    # logger.warning(f"{group_perms=}")
    return bool(group_perms and group_perms.get("write"))

def has_access(user: User, group_name: str | None, access_type: Literal["read", "write"] | None = None) -> bool:
    if check_root(user.user_tab_id):
        return True

    # Если нет группы доступ разрешен
    if group_name is None:
        return True

    if not user.permissions:
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
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}
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
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}

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
    ) -> List[T]:
        params = {**self.extra_params, "skip": skip, "limit": limit}
        items = await self.crud_func(db, **params)
        return [item for item in items if has_access(current_user, _get_nested_attr(item, self.group_field), self.access_type)]