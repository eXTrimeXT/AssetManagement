from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime

from app.database.connection import get_db
from app.models.UserSession import UserSession
from app.models.UserJWTData import UserJWTData
from app.schemas.auth.AuthSchemas import UserInfoResponse, TokenRequest
from app.service.auth.auth_service import get_user_from_token, TokenValidationError, create_or_update_user_from_token

router_auth = APIRouter(tags=["auth"])

@router_auth.post("/validate-token", response_model=UserInfoResponse)
async def validate_token(
        request: TokenRequest,
        db: AsyncSession = Depends(get_db),
):
    """
    Валидирует JWT токен, создает/обновляет пользователя в Users, возвращает данные пользователя.
    """
    try:
        user_data: UserJWTData = get_user_from_token(request.token)

        if user_data.is_expired:
            stmt = select(UserSession).where(UserSession.login == user_data.login)
            result = await db.execute(stmt)
            session = result.scalars().first()
            if session:
                session.token = None
                await db.commit()
            raise HTTPException(status_code=401, detail="Token expired")

        # === КЛЮЧЕВОЕ: Создаем или обновляем пользователя в таблице Users ===
        await create_or_update_user_from_token(db, user_data)

        # Сохраняем сессию
        stmt = select(UserSession).where(UserSession.login == user_data.login)
        result = await db.execute(stmt)
        user_session = result.scalars().first()

        if user_session:
            user_session.token = request.token
            user_session.created_at = datetime.utcnow()
        else:
            user_session = UserSession(
                login=user_data.login,
                token=request.token,
                created_at=datetime.utcnow(),
                user_info=str(user_data.to_dict())
            )
            db.add(user_session)

        await db.commit()

        return user_data.to_dict()

    except TokenValidationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")