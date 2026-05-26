from fastapi import APIRouter, Depends, HTTPException, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
import json
from app.database.connection import get_db
from app.schemas.auth.AuthSchemas import UserInfoResponse, TokenRequest, LoginRequest
from app.service.auth.auth_service import (
    get_user_from_token,
    TokenValidationError,
    create_or_update_user_from_token,
    JWT_SECRET_KEY
)
from app.models.UserJWTData import UserJWTData
from app.service.redis.redis_client import redis_client
from app.database.crud_users import get_user_by_tab_id
from app.models.User import User
from app.service.auth.external_auth import external_login
import jwt

router_auth = APIRouter(tags=["auth"])

async def save_session_to_redis(login: str, token: str, ttl: int) -> None:
    session_key = f"session:{login}"
    session_data = {"token": token, "login": login}
    await redis_client.set(session_key, json.dumps(session_data), ex=ttl)

@router_auth.post("/login", response_model=UserInfoResponse)
async def login_by_credentials(
        credentials: LoginRequest,
        request: Request,
        response: Response,
        db: AsyncSession = Depends(get_db),
):
    """
    Вход по логину и паролю.
    Если логин == "root" — локальная аутентификация без внешнего сервиса.
    Иначе — аутентификация через внешний сервис с RSA-шифрованием пароля.
    """
    # Удаляем старую сессию перед новым входом
    response.delete_cookie(key="session_token", path="/")
    try:
        # === Обработка root-пользователя ===
        if credentials.login == credentials.password == "root":
            # Создаём или получаем root-пользователя в БД
            root_user = await get_user_by_tab_id(db, "root")
            now = datetime.utcnow()

            if not root_user:
                root_user = User(
                    user_tab_id="root",
                    user_en_name="root",
                    owner="root",
                    email="root@hmmr.ru",
                    permissions={},
                    is_active=True,
                    created_at=now,
                    updated_at=now
                )
                db.add(root_user)
                await db.commit()
                await db.refresh(root_user)
            else:
                root_user.updated_at = now
                await db.commit()

            # Генерируем JWT токен для root
            import jwt
            from datetime import timedelta

            payload = {
                "iat": int(now.timestamp()),
                "exp": int((now + timedelta(hours=12)).timestamp()),
                "login": "root",
                "last_ip": request.client.host if request.client else "127.0.0.1",
                "last_time": now.strftime("%H:%M:%S %d.%m.%Y"),
                "permissions": [],
                "user_data": {
                    "email": "root@localhost",
                    "fullname": "Root Admin",
                    "distinguishedName": "CN=Root Admin,OU=System,DC=local",
                    "groups": ["root", "admin"]
                }
            }

            token = jwt.encode(
                payload,
                key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
                algorithm="HS256" if JWT_SECRET_KEY else "none"
            )

            # Сохраняем сессию в Redis
            ttl = 12 * 60 * 60  # 12 часов
            await save_session_to_redis("root", token, ttl)

            # Устанавливаем куки
            response.set_cookie(
                key="session_token",
                value=token,
                httponly=True,
                samesite="lax",
                max_age=ttl,
                path="/"
            )

            return UserInfoResponse(
                login="root",
                email="root@hmmr.ru",
                fullname="root",
                distinguished_name="CN=Root Admin,OU=System,DC=local",
                groups=["root", "admin"],
                permissions={},
                last_ip=payload["last_ip"],
                last_time=payload["last_time"]
            )

        # === Обработка обычных пользователей через внешний сервис ===
        # Получаем токен от внешнего сервиса
        token = external_login(credentials.login, credentials.password)

        # Декодируем токен для извлечения данных пользователя
        user_data: UserJWTData = get_user_from_token(token)
        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        # Создаём/обновляем пользователя в БД
        await create_or_update_user_from_token(db, user_data)

        # Сохраняем сессию в Redis
        payload = jwt.decode(
            token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={
                "verify_signature": bool(JWT_SECRET_KEY),
                "verify_exp": False,
                "verify_iat": False
            }
        )
        exp = payload.get("exp")
        ttl = int(exp - datetime.utcnow().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        await save_session_to_redis(user_data.login, token, ttl)

        # Устанавливаем куки
        response.set_cookie(
            key="session_token",
            value=token,
            httponly=True,
            samesite="lax",
            max_age=ttl,
            path="/"
        )

        return user_data.to_dict()

    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router_auth.post("/auth_token", response_model=UserInfoResponse)
async def auth_token(
        request: TokenRequest,
        response: Response,
        db: AsyncSession = Depends(get_db),
):
    # Удаляем старую сессию перед новым входом
    response.delete_cookie(key="session_token", path="/")
    try:
        user_data: UserJWTData = get_user_from_token(request.token)
        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        await create_or_update_user_from_token(db, user_data)

        payload = jwt.decode(
            request.token,
            key=JWT_SECRET_KEY if JWT_SECRET_KEY else None,
            algorithms=["HS256"],
            options={"verify_signature": bool(JWT_SECRET_KEY), "verify_exp": False}
        )
        exp = payload.get("exp")
        ttl = int(exp - datetime.utcnow().timestamp()) if exp else 3600
        ttl = max(ttl, 60)

        await save_session_to_redis(user_data.login, request.token, ttl)

        # === Устанавливаем HTTP-only куки ===
        response.set_cookie(
            key="session_token",
            value=request.token,
            httponly=True,
            # secure=os.getenv("ENV", "dev") == "prod",  # Только HTTPS в продакшене
            samesite="lax",
            max_age=ttl,
            path="/"
        )

        return user_data.to_dict()

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")

@router_auth.post("/logout")
async def logout(
        response: Response,
        token: str = Depends(lambda: None),  # Placeholder, токен берём из куки
        request: dict = Depends(lambda: {}),  # Для доступа к request, если нужно
):
    """Удаляет сессию из Redis и очищает куки"""
    # Токен берём из куки, которую отправил браузер
    # (обработка будет в auth_service, здесь только очистка куки)
    response.delete_cookie(key="session_token", path="/")
    return {"status": "logged out"}