import jwt
from typing import Optional, Dict, Any
import logging

from app.models.UserJWTData import UserJWTData

logger = logging.getLogger(__name__)

class TokenValidationError(Exception):
    """Исключение при ошибке валидации токена"""
    pass

def decode_token(token: str, secret_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Декодирует JWT токен и возвращает его payload.

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи.
                   Если None и JWT_SECRET_KEY не задан — декодирование без проверки подписи
                   (НЕ ДЛЯ ПРОДАКШЕНА!).

    Returns:
        Dict с данными из payload токена

    Raises:
        TokenValidationError: Если токен невалиден, просрочен или подпись не совпадает
    """
    try:
        if secret_key:
            # Проверяем подпись и срок действия
            payload = jwt.decode(
                token,
                key=secret_key,
                algorithms=["HS256"],
                options={"verify_exp": True}
            )
            logger.debug(f"{payload=}")
        else:
            # ⚠️ ТОЛЬКО ДЛЯ ТЕСТОВ: декодируем без проверки подписи
            logger.warning(
                "JWT secret key not configured. Decoding token without signature verification! "
                "Set JWT_SECRET_KEY for production."
            )
            payload = jwt.decode(
                token,
                options={"verify_signature": False, "verify_exp": True}
            )
            logger.debug(f"{payload=}")
        return payload

    except jwt.ExpiredSignatureError:
        raise TokenValidationError("Token has expired")
    except jwt.InvalidTokenError as e:
        raise TokenValidationError(f"Invalid token: {str(e)}")


def get_user_from_token(token: str, secret_key: Optional[str] = None) -> UserJWTData:
    """
    Извлекает и возвращает данные пользователя из JWT токена.

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи (опционально)

    Returns:
        UserData объект с данными пользователя

    Raises:
        TokenValidationError: Если токен невалиден или истек
    """
    payload = decode_token(token, secret_key)
    return UserJWTData(payload)


def is_token_valid(token: str, secret_key: Optional[str] = None) -> bool:
    """
    Проверяет валидность токена (подпись + срок действия).

    Args:
        token: JWT токен
        secret_key: Секретный ключ для проверки подписи (опционально)

    Returns:
        True если токен валиден, иначе False
    """
    try:
        decode_token(token, secret_key)
        return True
    except TokenValidationError:
        return False