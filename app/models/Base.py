from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Базовый класс для всех моделей
    DeclarativeBase — это основа, от которой наследуются все таблицы.
    Она связывает Python-классы с таблицами в PostgreSQL.
    """
    pass