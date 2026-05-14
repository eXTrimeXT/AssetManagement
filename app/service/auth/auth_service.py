import os
import jwt
import json
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import Security, Depends, HTTPException, Request, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.UserJWTData import UserJWTData
from app.models.User import User
from app.database.crud_users import get_user_by_tab_id
from app.database.connection import get_db
from app.service.redis.redis_client import redis_client

logger = logging.getLogger(__name__)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")

class TokenValidationError(Exception):
    pass

security = HTTPBearer(auto_error=False)  # auto_error=False — чтобы не выбрасывал 403, если нет заголовка

async def get_token_from_request(request: Request) -> str:
    """
    Получает токен из:
    1. Заголовка Authorization: Bearer <token>
    2. Куки session_token
    """
    # 1. Пробуем взять из заголовка
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    # 2. Пробуем взять из куки
    token = request.cookies.get("session_token")
    if token:
        return token.strip()

    raise HTTPException(status_code=401, detail="Token not provided")

async def get_session_from_redis(login: str) -> Optional[Dict[str, Any]]:
    session_key = f"session:{login}"
    data = await redis_client.get(session_key)
    return json.loads(data) if data else None

async def require_authorized_user(
        request: Request,
        db: AsyncSession = Depends(get_db)
) -> User:
    try:
        token = await get_token_from_request(request)
        user_data = get_user_from_token(token)

        if user_data.is_expired:
            raise HTTPException(status_code=401, detail="Token expired")

        session = await get_session_from_redis(user_data.login)
        if not session or session.get("token") != token:
            raise HTTPException(status_code=401, detail="Invalid or expired session")

        db_user = await get_user_by_tab_id(db, user_data.login)
        if not db_user:
            raise HTTPException(
                status_code=403,
                detail="User not found in database. Please login first via /api/validate-token"
            )

        if not db_user.is_active:
            raise HTTPException(status_code=403, detail="User account is deactivated.")

        return db_user

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))

def decode_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    key = secret_key or JWT_SECRET_KEY
    try:
        if key:
            payload = jwt.decode(
                token,
                key=key,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
            logger.warning(f"{payload=}")
        else:
            logger.warning(
                "JWT secret key not configured. Decoding token without signature verification! "
                "Set JWT_SECRET_KEY for production."
            )
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Invalid token: {str(e)}")

def get_user_from_token(token: str, secret_key: Optional[str] = None) -> UserJWTData:
    key = secret_key or JWT_SECRET_KEY
    payload = decode_token(token, key)
    return UserJWTData(payload)

def is_token_valid(token: str, secret_key: Optional[str] = None) -> bool:
    key = secret_key or JWT_SECRET_KEY
    try:
        decode_token(token, key)
        return True
    except TokenValidationError:
        return False

def parse_distinguished_name(dn: str | None) -> dict[str, Any]:
    if not dn:
        return {'CN': None, 'OU': [], 'DC': []}
    result = {'CN': None, 'OU': [], 'DC': []}
    for part in dn.split(','):
        if '=' in part:
            key, value = part.split('=', 1)
            key, value = key.strip(), value.strip()
            if key == 'CN':
                result['CN'] = value
            elif key == 'OU':
                result['OU'].append(value)
            elif key == 'DC':
                result['DC'].append(value)
    return result

def extract_role_from_dn(dn: str | None) -> str | None:
    parsed = parse_distinguished_name(dn)
    ou_list = parsed.get('OU', [])
    if 'Users' in ou_list:
        return 'user'
    return 'user'

async def create_or_update_user_from_token(
        db: AsyncSession,
        user_data: UserJWTData
) -> User:
    role = extract_role_from_dn(user_data.distinguished_name)
    existing_user = await get_user_by_tab_id(db, user_data.login)

    if existing_user:
        existing_user.user_en_name = user_data.fullname
        existing_user.owner = user_data.fullname
        existing_user.email = user_data.email
        existing_user.department = user_data.department
        if role:
            existing_user.role = role
        existing_user.updated_at = datetime.utcnow()
        await db.commit()
        await db.refresh(existing_user)
        return existing_user
    else:
        new_user = User(
            user_tab_id=user_data.login,
            user_en_name=user_data.fullname,
            owner=user_data.fullname,
            email=user_data.email,
            department=user_data.department,
            role=role,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        db.add(new_user)
        await db.commit()
        await db.refresh(new_user)
        return new_user