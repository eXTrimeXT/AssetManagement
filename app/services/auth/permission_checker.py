from fastapi import HTTPException, Request
from typing import List
from app.services.auth.auth_service import (
    get_user_permissions_from_token,
    get_token_from_request,
    get_user_from_token
)
import logging

logger = logging.getLogger(__name__)

async def check_permission(
        request: Request,
        resource: str,
        action: str
) -> bool:
    """
    Проверяет наличие права на конкретный ресурс из JWT-токена.

    Args:
        request: HTTP запрос
        resource: Название ресурса (например, "computer", "supplies")
        action: Действие ("read" или "write")

    Returns:
        True если право есть, False если нет
    """
    try:
        token = await get_token_from_request(request)

        # Получаем права из токена
        permissions = get_user_permissions_from_token(token)

        if not permissions:
            logger.warning("Права не найдены в токене")
            return False

        # Проверяем наличие права на конкретный ресурс
        resource_perms = permissions.get(resource, {})
        has_permission = resource_perms.get(action, False)

        if not has_permission:
            user_data = get_user_from_token(token)
            logger.debug(f"Пользователь {user_data.login} не имеет права {action} на {resource}")

        return has_permission

    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False

async def check_any_permission(
        request: Request,
        action: str
) -> bool:
    """
    Проверяет наличие права на ЛЮБОЙ тип актива из JWT-токена.
    Исключает 'users' из проверки.
    """
    try:
        token = await get_token_from_request(request)
        permissions = get_user_permissions_from_token(token)

        if not permissions:
            return False

        # Проверяем через цикл — есть ли право хотя бы на один тип (кроме users)
        for resource, perms in permissions.items():
            if resource == "users":
                continue
            if perms.get(action, False):
                return True

        return False

    except Exception as e:
        logger.error(f"Ошибка проверки прав: {e}")
        return False

def require_permission(resource: str = None, action: str = "read"):
    """
    Зависимость для проверки права на ресурс.
    Если resource не указан — проверяет наличие права на ЛЮБОЙ тип актива.
    """
    async def dependency(request: Request):
        if resource is None:
            has_perm = await check_any_permission(request, action)
            if not has_perm:
                raise HTTPException(
                    status_code=403,
                    detail=f"Нет права '{action}' ни на один тип актива"
                )
        else:
            has_perm = await check_permission(request, resource, action)
            if not has_perm:
                raise HTTPException(
                    status_code=403,
                    detail=f"Нет права '{action}' на ресурс '{resource}'"
                )

        # Возвращаем данные пользователя
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)
        return user_data

    return dependency

def require_any_permission(action: str, resources: List[str] = None):
    """
    Проверяет наличие права на ЛЮБОЙ из указанных ресурсов.
    """
    async def dependency(request: Request):
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)
        permissions = get_user_permissions_from_token(token)

        if not permissions:
            raise HTTPException(status_code=403, detail="Права не найдены")

        if resources is None:
            check_resources = [k for k in permissions.keys() if k != "users"]
        else:
            check_resources = resources

        for resource in check_resources:
            resource_perms = permissions.get(resource, {})
            if resource_perms.get(action, False):
                return user_data

        raise HTTPException(
            status_code=403,
            detail=f"Нет права '{action}' ни на один из ресурсов"
        )

    return dependency

async def get_accessible_asset_types(request: Request) -> List[str]:
    """
    Возвращает список типов активов, на которые у пользователя есть право read.
    """
    token = await get_token_from_request(request)
    permissions = get_user_permissions_from_token(token)

    if not permissions:
        return []

    accessible_types = []
    for resource, perms in permissions.items():
        if resource == "users":
            continue
        if perms.get("read", False):
            accessible_types.append(resource)

    return accessible_types